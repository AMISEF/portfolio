"""
روتر پورتفولیو / مدیریت سرمایه.

صفحات:
  GET /portfolio            ← آزمون ریسک‌پذیری (نیاز به ورود)
  GET /portfolio/assistant  ← مدیریت سرمایه + ورود دارایی + نمودار (نیاز به ورود)

API (نیاز به ورود — به‌جز instruments و risk/questions):
  GET    /api/portfolio/risk/questions  ← پرسش‌نامه (عمومی)
  POST   /api/portfolio/risk            ← ثبت پاسخ‌ها
  GET    /api/portfolio/risk            ← پروفایل ریسک ذخیره‌شده
  GET    /api/portfolio/instruments     ← کاتالوگ ابزارها (عمومی)
  GET    /api/portfolio/history         ← سری زمانی ارزش سبد
  GET    /api/portfolio/assets          ← فهرست دارایی‌ها + ارزش‌گذاری زنده
  POST   /api/portfolio/assets          ← افزودن دارایی
  PATCH  /api/portfolio/assets/{id}     ← ویرایش مقدار یا قیمت خرید
  DELETE /api/portfolio/assets/{id}     ← حذف دارایی
  POST   /api/portfolio/chat            ← چت‌بات Dify (asset_registration)
  POST   /api/portfolio/advisor         ← ورک‌فلو مشاور سبد (portfolio_advisor)
"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx
from fastapi import APIRouter, Body, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app import db
from app.config import settings
from app.routers.auth import account_display_name, current_user
from app.services import algo_allocation, instruments, portfolio_valuation, risk

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
from app.routers.pages import STATIC_V  # noqa: E402
templates.env.globals["static_v"] = STATIC_V


def _auth_uid(request: Request) -> str | None:
    """شناسهٔ پایدار کاربرِ احراز هویت‌شده، یا None اگر وارد نشده باشد.

    از همان منطق auth.py/_login_response استفاده می‌شود تا با داده‌های مهاجرت‌شده
    سازگار باشد: uid ذخیره‌شده در جدول users اولویت دارد؛ در غیر این صورت u{id}.
    """
    user = current_user(request)
    if not user:
        return None
    return user.get("uid") or f"u{user['id']}"


def _401() -> JSONResponse:
    return JSONResponse(
        {"error": "برای ادامه باید وارد حساب کاربری خود شوید.", "auth_required": True},
        status_code=401,
    )


def _ctx(request: Request, active: str, is_authed: bool = False) -> dict:
    return {
        "request": request,
        "brand_fa": settings.app_brand_fa,
        "title_fa": settings.app_title_fa,
        "subtitle_fa": settings.app_subtitle_fa,
        "active": active,
        "account_name": account_display_name(request),
        "is_authed": is_authed,
    }


# ───────────────────────── صفحات ─────────────────────────
@router.get("/portfolio", response_class=HTMLResponse)
async def portfolio_page(request: Request):
    user = current_user(request)
    # اگر کاربر واردشده و قبلاً آزمون را داده، همین‌جا (سمتِ سرور) به مدیریت
    # سرمایه هدایت می‌شود تا صفحهٔ آزمون اصلاً رندر و «فلش» نشود — مگر اینکه
    # صریحاً آزمونِ مجدد خواسته باشد (?retake=1).
    if user and "retake" not in request.query_params:
        uid = _auth_uid(request)
        if uid and db.get_risk(uid):
            return RedirectResponse("/portfolio/assistant", status_code=303)
    return templates.TemplateResponse("portfolio.html", _ctx(request, "portfolio", bool(user)))


@router.get("/portfolio/assistant", response_class=HTMLResponse)
async def assistant_page(request: Request):
    user = current_user(request)
    ctx = _ctx(request, "portfolio", bool(user))
    # اطلاعات پلن برای گیتِ سبدچینی هوش مصنوعی (سهمیه‌محور به‌جای بولیِ has_sub)
    from app.services import plans
    ai_used = db.ai_used_count(int(user["id"]), plans.tehran_month_key()) if user else 0
    info = plans.tier_info(user, ai_used)
    ctx["has_sub"] = info["is_paid"]
    ctx["tier_info"] = info
    return templates.TemplateResponse("portfolio_assistant.html", ctx)


# ───────────────────────── API: ریسک ─────────────────────────
@router.get("/api/portfolio/risk/questions")
async def risk_questions():
    """پرسش‌نامه — عمومی، احراز هویت لازم نیست."""
    return {"questions": risk.questions_payload(), "count": len(risk.QUESTIONS)}


@router.post("/api/portfolio/risk")
async def submit_risk(request: Request, payload: dict[str, Any] = Body(...)):
    uid = _auth_uid(request)
    if uid is None:
        return _401()
    answers = payload.get("answers")
    if not isinstance(answers, list):
        return JSONResponse({"error": "پاسخ‌ها نامعتبر است"}, status_code=400)
    try:
        result = risk.score_answers([int(x) for x in answers])
    except (ValueError, TypeError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    db.save_risk(uid, result, json.dumps(answers, ensure_ascii=False))
    return JSONResponse(result)


@router.get("/api/portfolio/risk")
async def get_risk(request: Request):
    uid = _auth_uid(request)
    if uid is None:
        return _401()
    return JSONResponse({"profile": db.get_risk(uid)})


# ───────────────────────── API: چت Dify ─────────────────────────

_DIFY_KIND: dict[str, str] = {
    "tether": "usdt",
    "paper_dollar": "toman",
    "gold18": "gold",
    "gold24": "gold",
    "gold_coin": "gold",
    "crypto": "crypto",
    "other": "toman",
}
_DIFY_PURITY: dict[str, str] = {
    "gold18": "18",
    "gold24": "24",
    "gold_coin": "coin",
}
_DIFY_SYMBOL: dict[str, str] = {
    "usdt": "USDT",
    "toman": "TOMAN",
    "gold": "GOLD",
}

_ASSETS_RE = re.compile(r"<!--\s*ASSETS:(.*?)\s*-->", re.DOTALL)


def _parse_dify_assets(uid: str, raw_json: str) -> bool:
    """پارس JSON دارایی‌های Dify، ذخیره در DB و بازگشت True در صورت موفقیت."""
    try:
        assets = json.loads(raw_json)
    except Exception:
        return False
    if not isinstance(assets, list) or not assets:
        return False

    merged = []
    for a in assets:
        action = (a.get("action") or "set").lower()
        if action not in ("add", "remove", "set"):
            action = "set"

        kind_dify = (a.get("kind") or "other").lower()
        kind = _DIFY_KIND.get(kind_dify, "toman")
        symbol = (a.get("symbol") or "").strip().upper() or _DIFY_SYMBOL.get(kind, kind.upper())
        name = (a.get("name") or symbol).strip()
        try:
            amount = float(a.get("amount") or 0)
        except (TypeError, ValueError):
            amount = 0.0

        if amount <= 0 and action != "remove":
            continue

        buy_price: float | None = None
        if action != "remove":
            buy_value = a.get("buy_value")
            buy_currency = (a.get("buy_currency") or "toman").lower()
            buy_basis = (a.get("buy_basis") or "per_unit").lower()

            if buy_value is not None:
                try:
                    buy_price = float(buy_value)
                except (TypeError, ValueError):
                    pass
            if buy_price and buy_basis == "total" and amount > 0:
                buy_price = buy_price / amount
            if buy_price and buy_currency == "usd":
                from app.cache import cache as _cache
                usdt_data = _cache.get_stale("tabdeal:usdt")
                rate = ((usdt_data or {}).get("usdt_irt") or {}).get("price") or 0
                if rate > 0:
                    buy_price = buy_price * rate

        merged.append({
            "kind": kind,
            "symbol": symbol if kind == "crypto" else _DIFY_SYMBOL.get(kind, kind.upper()),
            "name": name,
            "amount": amount,
            "buy_price": buy_price,
            "purity": _DIFY_PURITY.get(kind_dify),
            "horizon": None,
            "action": action,
        })

    if not merged:
        return False
    db.merge_assets(uid, merged)
    return True


@router.post("/api/portfolio/chat")
async def portfolio_chat(request: Request, payload: dict[str, Any] = Body(...)):
    """پروکسی چت Dify: پیام → Dify → پارس assets → ذخیره (اگر آماده)."""
    uid = _auth_uid(request)
    if uid is None:
        return _401()
    message = (payload.get("message") or "").strip()
    conversation_id = (payload.get("conversation_id") or "").strip() or None

    if not message:
        return JSONResponse({"error": "پیام خالی است"}, status_code=400)
    if not settings.dify_api_key:
        return JSONResponse({"error": "کلید Dify تنظیم نشده است"}, status_code=503)

    body: dict[str, Any] = {
        "inputs": {},
        "query": message,
        "response_mode": "blocking",
        "user": uid,
    }
    if conversation_id:
        body["conversation_id"] = conversation_id

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                f"{settings.dify_api_base}/chat-messages",
                headers={
                    "Authorization": f"Bearer {settings.dify_api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return JSONResponse({"error": f"خطای Dify: {exc.response.status_code}"}, status_code=502)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)

    data = r.json()
    answer: str = data.get("answer") or ""
    conv_id: str = data.get("conversation_id") or ""

    assets_saved = False
    m = _ASSETS_RE.search(answer)
    if m:
        answer = _ASSETS_RE.sub("", answer).strip()
        assets_saved = _parse_dify_assets(uid, m.group(1).strip())

    return JSONResponse({
        "answer": answer,
        "conversation_id": conv_id,
        "assets_saved": assets_saved,
    })


@router.post("/api/portfolio/advisor")
async def portfolio_advisor(request: Request):
    """ورک‌فلوِ مشاور سبد (portfolio_advisor.yml): سه سبد هفتگی/ماهانه/سالانه."""
    uid = _auth_uid(request)
    if uid is None:
        return _401()
    if not settings.dify_advisor_key:
        return JSONResponse({"error": "کلید DIFY_ADVISOR_KEY تنظیم نشده است"}, status_code=503)

    profile = db.get_risk(uid)
    valued = await portfolio_valuation.value_portfolio(db.list_assets(uid))
    risk_pct = float((profile or {}).get("percent") or 50)

    assets_json = json.dumps(
        [
            {
                "kind": it.get("kind"), "symbol": it.get("symbol"),
                "name": it.get("name"), "amount": it.get("amount"),
                "buy_price": it.get("buy_price"),
            }
            for it in valued.get("items", [])
        ],
        ensure_ascii=False,
    )

    inputs = {
        "uid": uid,
        "risk_percent": round(risk_pct),
        "risk_label": (profile or {}).get("label") or "",
        "risk_desc": (profile or {}).get("description") or "",
        "assets_json": assets_json,
        "extra_symbols": "",
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            r = await client.post(
                f"{settings.dify_api_base}/workflows/run",
                headers={
                    "Authorization": f"Bearer {settings.dify_advisor_key}",
                    "Content-Type": "application/json",
                },
                json={"inputs": inputs, "response_mode": "blocking", "user": uid},
            )
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as exc:
        return JSONResponse({"error": f"خطای Dify: {exc.response.status_code}"}, status_code=502)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)

    outputs = ((data.get("data") or {}).get("outputs")) or {}
    advice = outputs.get("advice") or next((v for v in outputs.values() if isinstance(v, str) and v.strip()), "")
    return JSONResponse({"ok": bool(advice), "advice": advice, "context": outputs.get("context", "")})


# ───────────────────────── API: کاتالوگ ابزارها ─────────────────────────
@router.get("/api/portfolio/instruments")
async def list_instruments():
    """کاتالوگ کامل ابزارها — عمومی، احراز هویت لازم نیست."""
    return JSONResponse(await instruments.catalog())


# ───────────────────────── API: تاریخچه ─────────────────────────
@router.get("/api/portfolio/history")
async def portfolio_history(request: Request, days: int = 365):
    """سری زمانی ارزش کل سبد (برای نمودار روند)."""
    uid = _auth_uid(request)
    if uid is None:
        return _401()
    return JSONResponse({"history": db.get_portfolio_history(uid, days)})


# ───────────────────────── API: دارایی‌ها ─────────────────────────
_KINDS = {"crypto", "gold", "coin", "silver", "oil", "usdt", "toman", "usd_cash"}


@router.post("/api/portfolio/assets")
async def add_asset(request: Request, payload: dict[str, Any] = Body(...)):
    uid = _auth_uid(request)
    if uid is None:
        return _401()
    kind = (payload.get("kind") or "").strip()
    if kind not in _KINDS:
        return JSONResponse({"error": "نوع دارایی نامعتبر است"}, status_code=400)
    try:
        amount = float(payload.get("amount") or 0)
    except (TypeError, ValueError):
        return JSONResponse({"error": "مقدار نامعتبر است"}, status_code=400)
    if amount <= 0:
        return JSONResponse({"error": "مقدار باید بزرگ‌تر از صفر باشد"}, status_code=400)

    buy_price = payload.get("buy_price")
    try:
        buy_price = float(buy_price) if buy_price not in (None, "") else None
    except (TypeError, ValueError):
        buy_price = None

    asset = {
        "kind": kind,
        "symbol": (payload.get("symbol") or kind).strip().upper(),
        "name": (payload.get("name") or payload.get("symbol") or kind).strip(),
        "amount": amount,
        "buy_price": buy_price,
        "purity": payload.get("purity"),
        "horizon": payload.get("horizon"),
    }
    asset_id = db.add_asset(uid, asset)
    return JSONResponse({"id": asset_id, "ok": True})


@router.get("/api/portfolio/assets")
async def get_assets(request: Request):
    uid = _auth_uid(request)
    if uid is None:
        return _401()
    valued = await portfolio_valuation.value_portfolio(db.list_assets(uid))
    if valued.get("total_toman"):
        try:
            db.record_portfolio_value(uid, valued["total_toman"], valued.get("total_usd") or 0)
        except Exception:  # noqa: BLE001
            pass
    return JSONResponse(valued)


@router.patch("/api/portfolio/assets/{asset_id}")
async def update_asset(request: Request, asset_id: int, payload: dict[str, Any] = Body(...)):
    """به‌روزرسانی مقدار و/یا میانگین قیمت خرید دارایی؛ مقدار ≤ ۰ ⇒ حذف کامل."""
    uid = _auth_uid(request)
    if uid is None:
        return _401()
    has_amount = "amount" in payload
    has_buy = "buy_price" in payload
    if not has_amount and not has_buy:
        return JSONResponse({"error": "موردی برای تغییر داده نشد"}, status_code=400)

    amount: float | None = None
    if has_amount:
        try:
            amount = float(payload.get("amount"))
        except (TypeError, ValueError):
            return JSONResponse({"error": "مقدار نامعتبر است"}, status_code=400)
        if amount <= 0:
            return JSONResponse({"ok": db.delete_asset(uid, asset_id), "deleted": True})

    buy_price: Any = "__keep__"
    if has_buy:
        bp = payload.get("buy_price")
        if bp in (None, ""):
            buy_price = None
        else:
            try:
                buy_price = float(bp)
            except (TypeError, ValueError):
                return JSONResponse({"error": "قیمت خرید نامعتبر است"}, status_code=400)

    return JSONResponse(
        {"ok": db.update_asset(uid, asset_id, amount=amount, buy_price=buy_price)}
    )


@router.delete("/api/portfolio/assets/{asset_id}")
async def remove_asset(request: Request, asset_id: int):
    uid = _auth_uid(request)
    if uid is None:
        return _401()
    return JSONResponse({"ok": db.delete_asset(uid, asset_id)})


# ───────────────────────── API: سبدچینی با هوش مصنوعی ─────────────────────────
@router.get("/api/portfolio/ai-allocation/access")
async def ai_allocation_access(request: Request):
    """وضعیت دسترسیِ سبدچینی هوش مصنوعی: پلن + سهمیهٔ باقی‌مانده."""
    user = current_user(request)
    if not user:
        return _401()
    from app.services import plans
    ai_used = db.ai_used_count(int(user["id"]), plans.tehran_month_key())
    info = plans.tier_info(user, ai_used)
    quota = info["ai_quota"]
    remaining = info["ai_remaining"]
    allowed = (remaining is None) or (remaining > 0)
    return JSONResponse({
        "allowed": allowed,
        "tier": info["tier"],
        "tier_name_fa": info["tier_name_fa"],
        "is_paid": info["is_paid"],
        "ai_quota": quota,
        "ai_used": ai_used,
        "ai_remaining": remaining,
    })


@router.post("/api/portfolio/ai-allocation")
async def ai_allocation(request: Request):
    """ساخت سبد پیشنهادی با هوش مصنوعی الگو اسمارت.

    نیازمند ورود است. سهمیهٔ تحلیل بر اساس پلن کاربر:
      برنزی ۱/ماه، نقره‌ای ۲/ماه، طلایی/الماسی نامحدود. کارکنان = نامحدود.
    موجودی تتر و ریسک‌پذیری کاربر را به ورک‌فلوِ Dify می‌دهد و متن سبد پیشنهادی +
    چنل پیشنهادی را برمی‌گرداند.
    """
    user = current_user(request)
    if not user:
        return _401()

    from app.services import plans
    month = plans.usage_key(user)
    ai_used = db.ai_used_count(int(user["id"]), month)
    info = plans.tier_info(user, ai_used)
    quota = info["ai_quota"]
    remaining = info["ai_remaining"]
    per_fa = "امسال" if info.get("ai_period") == "year" else "این ماه"
    if remaining is not None and remaining <= 0:
        return JSONResponse(
            {"error": f"سهمیهٔ سبدچینی هوش مصنوعی {per_fa} شما تمام شده است.",
             "quota_exhausted": True, "ai_quota": quota, "ai_used": ai_used,
             "tier": info["tier"], "tier_name_fa": info["tier_name_fa"]},
            status_code=403,
        )

    uid = user.get("uid") or f"u{user['id']}"
    valued = await portfolio_valuation.value_portfolio(db.list_assets(uid))
    profile = db.get_risk(uid)
    risk_pct = float((profile or {}).get("percent") or 50.0)
    cat = risk._category(risk_pct)
    risk_label = (profile or {}).get("label") or cat["label"]

    tether = algo_allocation.tether_usd(valued)
    channel = algo_allocation.recommend_channel(tether)
    universe = algo_allocation.allowed_universe(risk_pct)

    # زمینهٔ ارسالی به ورک‌فلو Dify (ورودی‌های متنی برای سازگاری حداکثری).
    holdings = "، ".join(
        f"{it.get('name') or it.get('symbol')}: {it.get('amount')}"
        for it in valued.get("items", [])
    ) or "بدون دارایی"

    # قواعد افق زمانی برای هر دارایی (کوتاه/میان/بلندمدت).
    user_coins = [
        (it.get("symbol") or "").upper()
        for it in valued.get("items", [])
        if (it.get("kind") or "") == "crypto"
    ]
    user_coins = [c for c in user_coins if c]
    hz = db.active_horizon_tags()
    mid_ok = "، ".join(hz.get("mid") or []) or "—"
    long_ok = "، ".join(hz.get("long") or []) or "—"
    horizon_rules = (
        "قواعد افق زمانی (بسیار مهم): "
        f"۱) ارزهای موجود در سبد کاربر ({'، '.join(user_coins) or '—'}) فقط در سبد "
        "کوتاه‌مدت پیشنهاد شوند، نه میان‌مدت و نه بلندمدت. "
        "۲) تتر و طلا در هر سه افق (کوتاه‌مدت، میان‌مدت، بلندمدت) مجاز و توصیه‌شده‌اند. "
        f"۳) این ارزها با تأیید ادمین برای میان‌مدت هم مجازند: {mid_ok}. و برای "
        f"بلندمدت: {long_ok}. "
        "۴) برای سایر ارزهایی که قید نشده‌اند، خودِ هوش مصنوعی تصمیم بگیرد در کدام "
        "افق‌ها (کوتاه/میان/بلند) بیایند."
    )

    inputs = {
        "uid": uid,
        "risk_percent": str(round(risk_pct)),
        "risk_label": risk_label,
        "risk_level": universe["level"],
        "allowed_assets": "، ".join(universe["assets"]),
        "tether_usd": str(tether),
        "total_usd": str(valued.get("total_usd") or 0),
        "total_toman": str(valued.get("total_toman") or 0),
        "holdings": holdings,
        "channel": channel["name"],
        "horizon_rules": horizon_rules,
    }

    result = await algo_allocation.run_workflow(inputs, uid)
    # شمارش یک تحلیلِ موفق در سهمیهٔ ماه جاری (نامحدودها بی‌تأثیر است).
    if result.get("ok") and quota is not None:
        db.ai_increment(int(user["id"]), month)
    return JSONResponse({
        "ok": result["ok"],
        "text": result["text"],
        "error": result["error"],
        "risk": {"percent": round(risk_pct), "label": risk_label, "level": universe["level"]},
        "universe": universe,
        "channel": channel,
        "ai_remaining": (None if quota is None else max(quota - ai_used - 1, 0)),
    })
