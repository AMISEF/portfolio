"""
روتر پورتفولیو / مدیریت سرمایه.

صفحات:
  GET /portfolio            ← آزمون ریسک‌پذیری (اگر انجام نشده) یا نتیجه + شروع
  GET /portfolio/assistant  ← چت‌بات مدیریت سرمایه + ورود دارایی‌ها + نمودار

API (فرانت‌اند فقط با این‌ها صحبت می‌کند):
  GET    /api/portfolio/risk/questions  ← پرسش‌نامه
  POST   /api/portfolio/risk            ← ثبت پاسخ‌ها + محاسبهٔ درصد و طبقه
  GET    /api/portfolio/risk            ← پروفایل ریسک ذخیره‌شده
  GET    /api/portfolio/assets          ← فهرست دارایی‌ها + ارزش‌گذاری زنده
  POST   /api/portfolio/assets          ← افزودن دارایی
  DELETE /api/portfolio/assets/{id}     ← حذف دارایی

هویت کاربر: تا فعال‌شدن احراز هویت واقعی، هر کاربر با شناسهٔ ناشناسِ کوکی‌محور
(cs_uid) شناخته می‌شود.
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Body, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from app import db
from app.config import settings
from app.services import instruments, portfolio_valuation, risk

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
# نسخهٔ استاتیک مشترک تا کش CSS/JS با هر استقرار باطل شود
from app.routers.pages import STATIC_V  # noqa: E402
templates.env.globals["static_v"] = STATIC_V

_COOKIE = "cs_uid"
_COOKIE_MAX_AGE = 60 * 60 * 24 * 365 * 2   # دو سال


def _uid(request: Request) -> tuple[str, bool]:
    """(شناسهٔ کاربر، آیا تازه ساخته شد). شناسه از کوکی cs_uid خوانده می‌شود."""
    uid = request.cookies.get(_COOKIE)
    if uid:
        return uid, False
    return uuid.uuid4().hex, True


def _attach_uid(resp: Response, uid: str, is_new: bool) -> Response:
    if is_new:
        resp.set_cookie(_COOKIE, uid, max_age=_COOKIE_MAX_AGE,
                        httponly=True, samesite="lax")
    return resp


def _json(data: Any, uid: str, is_new: bool, status: int = 200) -> JSONResponse:
    return _attach_uid(JSONResponse(data, status_code=status), uid, is_new)


def _ctx(request: Request, active: str) -> dict:
    from app.routers.auth import account_display_name
    return {
        "request": request,
        "brand_fa": settings.app_brand_fa,
        "title_fa": settings.app_title_fa,
        "subtitle_fa": settings.app_subtitle_fa,
        "active": active,
        "account_name": account_display_name(request),
    }


# ───────────────────────── صفحات ─────────────────────────
@router.get("/portfolio", response_class=HTMLResponse)
async def portfolio_page(request: Request):
    uid, is_new = _uid(request)
    resp = templates.TemplateResponse("portfolio.html", _ctx(request, "portfolio"))
    return _attach_uid(resp, uid, is_new)


@router.get("/portfolio/assistant", response_class=HTMLResponse)
async def assistant_page(request: Request):
    uid, is_new = _uid(request)
    resp = templates.TemplateResponse("portfolio_assistant.html", _ctx(request, "portfolio"))
    return _attach_uid(resp, uid, is_new)


# ───────────────────────── API: ریسک ─────────────────────────
@router.get("/api/portfolio/risk/questions")
async def risk_questions():
    return {"questions": risk.questions_payload(), "count": len(risk.QUESTIONS)}


@router.post("/api/portfolio/risk")
async def submit_risk(request: Request, payload: dict[str, Any] = Body(...)):
    uid, is_new = _uid(request)
    answers = payload.get("answers")
    if not isinstance(answers, list):
        return _json({"error": "پاسخ‌ها نامعتبر است"}, uid, is_new, 400)
    try:
        result = risk.score_answers([int(x) for x in answers])
    except (ValueError, TypeError) as e:
        return _json({"error": str(e)}, uid, is_new, 400)
    db.save_risk(uid, result, json.dumps(answers, ensure_ascii=False))
    return _json(result, uid, is_new)


@router.get("/api/portfolio/risk")
async def get_risk(request: Request):
    uid, is_new = _uid(request)
    return _json({"profile": db.get_risk(uid)}, uid, is_new)


# ───────────────────────── API: چت Dify ─────────────────────────

# نگاشت نوع دارایی Dify → نوع داخلی + عیار طلا
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
        kind_dify = (a.get("kind") or "other").lower()
        kind = _DIFY_KIND.get(kind_dify, "toman")
        symbol = (a.get("symbol") or "").strip().upper() or _DIFY_SYMBOL.get(kind, kind.upper())
        name = (a.get("name") or symbol).strip()
        try:
            amount = float(a.get("amount") or 0)
        except (TypeError, ValueError):
            continue
        if amount <= 0:
            continue

        buy_value = a.get("buy_value")
        buy_currency = (a.get("buy_currency") or "toman").lower()
        buy_basis = (a.get("buy_basis") or "per_unit").lower()

        buy_price: float | None = None
        if buy_value is not None:
            try:
                buy_price = float(buy_value)
            except (TypeError, ValueError):
                pass
        if buy_price and buy_basis == "total" and amount > 0:
            buy_price = buy_price / amount
        # قیمت دلاری → تومان با نرخ کَش‌شده (تقریبی زمان ثبت)
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
        })

    db.merge_assets(uid, merged)
    return True


@router.post("/api/portfolio/chat")
async def portfolio_chat(request: Request, payload: dict[str, Any] = Body(...)):
    """پروکسی چت Dify: پیام → Dify → پارس assets → ذخیره (اگر آماده)."""
    uid, is_new = _uid(request)
    message = (payload.get("message") or "").strip()
    conversation_id = (payload.get("conversation_id") or "").strip() or None

    if not message:
        return _json({"error": "پیام خالی است"}, uid, is_new, 400)
    if not settings.dify_api_key:
        return _json({"error": "کلید Dify تنظیم نشده است"}, uid, is_new, 503)

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
        return _json({"error": f"خطای Dify: {exc.response.status_code}"}, uid, is_new, 502)
    except Exception as exc:
        return _json({"error": str(exc)}, uid, is_new, 502)

    data = r.json()
    answer: str = data.get("answer") or ""
    conv_id: str = data.get("conversation_id") or ""

    # استخراج و ذخیرهٔ دارایی‌ها از کامنت مخفی <!-- ASSETS:{json} -->
    assets_saved = False
    m = _ASSETS_RE.search(answer)
    if m:
        answer = _ASSETS_RE.sub("", answer).strip()
        assets_saved = _parse_dify_assets(uid, m.group(1).strip())

    return _json({
        "answer": answer,
        "conversation_id": conv_id,
        "assets_saved": assets_saved,
    }, uid, is_new)


# ───────────────────────── API: کاتالوگ ابزارها ─────────────────────────
@router.get("/api/portfolio/instruments")
async def list_instruments(request: Request):
    """کاتالوگ کامل برای انتخابگرِ افزودن دارایی (همهٔ ارزها + طلا/سکه/نقره/نفت)."""
    uid, is_new = _uid(request)
    return _json(await instruments.catalog(), uid, is_new)


@router.get("/api/portfolio/history")
async def portfolio_history(request: Request, days: int = 365):
    """سری زمانی ارزش کل سبد (برای نمودار پورتفولیو)."""
    uid, is_new = _uid(request)
    return _json({"history": db.get_portfolio_history(uid, days)}, uid, is_new)


# ───────────────────────── API: دارایی‌ها ─────────────────────────
_KINDS = {"crypto", "gold", "coin", "silver", "oil", "usdt", "toman", "usd_cash"}


@router.post("/api/portfolio/assets")
async def add_asset(request: Request, payload: dict[str, Any] = Body(...)):
    uid, is_new = _uid(request)
    kind = (payload.get("kind") or "").strip()
    if kind not in _KINDS:
        return _json({"error": "نوع دارایی نامعتبر است"}, uid, is_new, 400)
    try:
        amount = float(payload.get("amount") or 0)
    except (TypeError, ValueError):
        return _json({"error": "مقدار نامعتبر است"}, uid, is_new, 400)
    if amount <= 0:
        return _json({"error": "مقدار باید بزرگ‌تر از صفر باشد"}, uid, is_new, 400)

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
    return _json({"id": asset_id, "ok": True}, uid, is_new)


@router.get("/api/portfolio/assets")
async def get_assets(request: Request):
    uid, is_new = _uid(request)
    valued = await portfolio_valuation.value_portfolio(db.list_assets(uid))
    # ثبت لحظه‌ای ارزش کل برای نمودار تاریخچه (با گلوگاه داخلی: حداکثر هر ساعت)
    if valued.get("total_toman"):
        try:
            db.record_portfolio_value(uid, valued["total_toman"], valued.get("total_usd") or 0)
        except Exception:  # noqa: BLE001
            pass
    return _json(valued, uid, is_new)


@router.patch("/api/portfolio/assets/{asset_id}")
async def update_asset(request: Request, asset_id: int, payload: dict[str, Any] = Body(...)):
    """به‌روزرسانی مقدار و/یا میانگین قیمت خرید دارایی؛ مقدار ≤ ۰ ⇒ حذف کامل."""
    uid, is_new = _uid(request)
    has_amount = "amount" in payload
    has_buy = "buy_price" in payload
    if not has_amount and not has_buy:
        return _json({"error": "موردی برای تغییر داده نشد"}, uid, is_new, 400)

    amount: float | None = None
    if has_amount:
        try:
            amount = float(payload.get("amount"))
        except (TypeError, ValueError):
            return _json({"error": "مقدار نامعتبر است"}, uid, is_new, 400)
        if amount <= 0:
            return _json({"ok": db.delete_asset(uid, asset_id), "deleted": True}, uid, is_new)

    buy_price: Any = "__keep__"
    if has_buy:
        bp = payload.get("buy_price")
        if bp in (None, ""):
            buy_price = None
        else:
            try:
                buy_price = float(bp)
            except (TypeError, ValueError):
                return _json({"error": "قیمت خرید نامعتبر است"}, uid, is_new, 400)

    return _json({"ok": db.update_asset(uid, asset_id, amount=amount, buy_price=buy_price)},
                 uid, is_new)


@router.delete("/api/portfolio/assets/{asset_id}")
async def remove_asset(request: Request, asset_id: int):
    uid, is_new = _uid(request)
    return _json({"ok": db.delete_asset(uid, asset_id)}, uid, is_new)
