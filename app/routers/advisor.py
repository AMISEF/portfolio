"""
مشاور سبد — «ابزارِ» تحلیل بازار برای ورک‌فلو Dify.

این روتر دو نقش دارد:
  1) GET  /api/advisor/chart/{symbol}.svg   ← نمودار شمعی + نواحی خرید/فروش (SVG)
  2) POST /api/advisor/context              ← بستهٔ کامل زمینه برای مدل زبانی

اندپوینت context همهٔ آنچه را مدل Gemini برای ساختن سبد لازم دارد یکجا فراهم
می‌کند: دارایی‌های فعلی کاربر (با ارزش‌گذاری)، پروفایل ریسک، رژیم کلی بازار،
و تحلیل تکنیکال چند‌تایم‌فریمیِ (هفتگی/ماهانه/سالانه) هر نماد به‌همراه نواحی
خرید/فروش. ورک‌فلو Dify فقط این را می‌گیرد، به Gemini می‌دهد و سبد می‌سازد.

امنیت: اگر ADVISOR_API_KEY در .env تنظیم شده باشد، context هدر
«X-Advisor-Key» را الزامی می‌کند تا دادهٔ مالی کاربران بی‌اجازه خوانده نشود.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
from fastapi import APIRouter, Body, Header, Request
from fastapi.responses import JSONResponse, Response

from app import db
from app.config import settings
from app.services import portfolio_valuation, risk, sourcearena, ta, tabdeal, toobit
from app.services import chart_svg

router = APIRouter(prefix="/api/advisor", tags=["advisor"])

# جهان نمادهای کاندید بر اساس سطح ریسک (نماد ⇒ جفت USDT روی Toobit).
_CORE = ["BTC", "ETH"]
_LARGE = ["SOL", "BNB", "XRP"]
_MID = ["ADA", "AVAX", "LINK", "DOT", "TON"]
_SMALL = ["DOGE", "PEPE", "WIF", "SUI"]
_GOLD_PROXY = "PAXG"               # طلای توکنایزشده روی Toobit برای نواحی طلا


def _pair(sym: str) -> str:
    return sym.upper() + "USDT"


def _universe(risk_pct: float, user_syms: list[str]) -> list[str]:
    """نمادهای کریپتویی که تحلیل می‌شوند: هسته + هلدینگ کاربر + آلت‌ها بر پایهٔ ریسک."""
    syms = list(_CORE) + list(_LARGE)
    if risk_pct >= 40:
        syms += _MID
    if risk_pct >= 60:
        syms += _SMALL
    for s in user_syms:                       # هرچه کاربر دارد حتماً تحلیل شود
        if s and s not in syms:
            syms.append(s)
    # یکتا با حفظ ترتیب، سقف ۱۴ نماد برای کنترل تأخیر
    seen: set[str] = set()
    out: list[str] = []
    for s in syms:
        u = s.upper()
        if u not in seen:
            seen.add(u); out.append(u)
    return out[:14]


async def _ticker_map(client: httpx.AsyncClient) -> dict[str, dict]:
    """نگاشت نماد ⇒ تیکر ۲۴ساعته (قیمت/تغییر/حجم) برای ضمیمه به تحلیل."""
    try:
        r = await client.get(f"{settings.toobit_base_url}/quote/v1/ticker/24hr")
        r.raise_for_status()
        data = r.json()
    except Exception:  # noqa: BLE001
        return {}
    out = {}
    for t in (data if isinstance(data, list) else []):
        s = (t.get("s") or t.get("symbol") or "").upper()
        if s.endswith("USDT"):
            out[s[:-4]] = t
    return out


# ───────────────────────── نمودار SVG ─────────────────────────
@router.get("/chart/{symbol}.svg")
async def chart(symbol: str, interval: str = "1d", limit: int = 160):
    """نمودار شمعی یک نماد با نواحی خرید/فروش. مثال: /api/advisor/chart/BTC.svg?interval=1d"""
    pair = _pair(symbol)
    async with httpx.AsyncClient(timeout=httpx.Timeout(settings.http_timeout)) as client:
        try:
            kl = await ta.fetch_klines(client, pair, interval, limit)
        except Exception:  # noqa: BLE001
            kl = []
        analysis = None
        if len(kl) >= 30:
            closes = [k["c"] for k in kl]
            analysis = ta.zones(kl, closes[-1], ta.atr(kl))
    svg = chart_svg.render(symbol.upper(), kl, analysis, interval)
    return Response(content=svg, media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=120"})


# ───────────────────────── بستهٔ زمینه برای Dify ─────────────────────────
@router.post("/context")
async def context(request: Request, payload: dict[str, Any] = Body(default={}),
                  x_advisor_key: str | None = Header(default=None)):
    """زمینهٔ کامل برای مدل: دارایی‌ها + ریسک + رژیم بازار + تحلیل تکنیکال نمادها.

    بدنه (همه اختیاری):
      uid           شناسهٔ کاربر برای واکشی دارایی/ریسک ذخیره‌شده
      assets        فهرست دارایی مستقیم (جایگزین uid)
      risk_percent  درصد ریسک‌پذیری (۰–۱۰۰)
      risk_label, risk_desc   برچسب و توضیح ریسک
      extra_symbols فهرست نمادهای کریپتوی اضافه برای تحلیل
    """
    # ۱) احراز کلید مشاور (در صورت تنظیم)
    if settings.advisor_api_key and x_advisor_key != settings.advisor_api_key:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    uid = (payload.get("uid") or request.cookies.get("cs_uid") or "").strip()

    # ۲) دارایی‌ها
    raw_assets = payload.get("assets")
    if not isinstance(raw_assets, list):
        raw_assets = db.list_assets(uid) if uid else []
    valued = await portfolio_valuation.value_portfolio(raw_assets)

    # ۳) پروفایل ریسک
    risk_profile = _resolve_risk(payload, uid)

    # ۴) نمادهای کریپتوی کاربر + جهان کاندید
    user_syms = [(_norm_sym(a)) for a in raw_assets if (a.get("kind") == "crypto")]
    user_syms = [s for s in user_syms if s]
    extra = [str(s).upper() for s in (payload.get("extra_symbols") or []) if s]
    universe = _universe(risk_profile["percent"], user_syms + extra)

    # ۵) واکشی موازی: تیکرها + رژیم بازار + فلزات/تتر + تحلیل هر نماد
    timeout = httpx.Timeout(45.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        tickers, regime, metals, usdt = await asyncio.gather(
            _ticker_map(client),
            _market_regime(client),
            _safe(sourcearena.metals()),
            _safe(tabdeal.usdt()),
        )
        sem = asyncio.Semaphore(6)

        async def _one(sym: str):
            async with sem:
                a = await _safe_analyze(client, sym)
            tk = tickers.get(sym) or {}
            if tk:
                a["change_24h"] = toobit._pct(tk) if hasattr(toobit, "_pct") else None
                a["volume_24h"] = _num(tk.get("qv") or tk.get("quoteVolume"))
            a["chart_url"] = f"/api/advisor/chart/{sym}.svg?interval=1d"
            return a

        crypto = await asyncio.gather(*[_one(s) for s in universe])

    crypto = [c for c in crypto if c.get("ok")]

    # ۶) دارایی‌های غیرکریپتو (تتر/طلا/نقره) — قیمت و تغییر فعلی (بدون نواحی کندلی)
    macro_assets = _macro_assets(metals, usdt)

    return JSONResponse({
        "generated_for": uid or "anonymous",
        "risk": risk_profile,
        "portfolio": {
            "total_usd": valued.get("total_usd"),
            "total_toman": valued.get("total_toman"),
            "items": valued.get("items", []),
        },
        "market_regime": regime,
        "macro_assets": macro_assets,
        "crypto_analysis": crypto,
        "horizons": list(ta.TIMEFRAMES.keys()),
        "notes": (
            "buy_zones = حمایت‌های پیشنهادی برای ورود؛ sell_zones = مقاومت‌های "
            "پیشنهادی برای برداشت سود. dist_pct = فاصلهٔ ٪ ناحیه تا قیمت فعلی. "
            "تحلیل سه افق: weekly(4h) / monthly(1d) / yearly(1w)."
        ),
    })


# ───────────────────────── سیگنال‌های کانال تلگرام ─────────────────────────
_HASHTAG_RE = re.compile(r"#(\w+)", re.UNICODE)


@router.get("/signals")
async def channel_signals(x_advisor_key: str | None = Header(default=None),
                          limit: int = 50, tag: str | None = None):
    """آخرین تحلیل‌های کانال کریپتو اسمارت که ربات «الگو آنالایزر» دیده است.

    با توکن ربات (ALGO_ANALYZER_BOT_TOKEN) از getUpdates پیام‌های کانال خوانده،
    هشتگ‌ها (#طلا #تتر #btc #eth …) و کپشن تصاویر استخراج می‌شوند تا ورک‌فلو Dify
    بتواند نقاط خرید روز را در سبد لحاظ کند.

    نکته: ربات باید ادمین کانال باشد و وب‌هوک فعال نباشد تا getUpdates کار کند.
    فیلتر اختیاری: ?tag=btc تنها پست‌های دارای آن هشتگ را برمی‌گرداند.
    """
    if settings.advisor_api_key and x_advisor_key != settings.advisor_api_key:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    token = settings.algo_analyzer_bot_token
    if not token:
        return JSONResponse({"posts": [], "error": "no_bot_token"})

    try:
        chan_id = int(settings.algo_channel_id)
    except (TypeError, ValueError):
        chan_id = None

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
            r = await client.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"allowed_updates": '["channel_post","edited_channel_post"]',
                        "limit": 100, "timeout": 0},
            )
            r.raise_for_status()
            data = r.json()
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"posts": [], "error": f"{type(exc).__name__}: {exc}"})

    posts: list[dict[str, Any]] = []
    for upd in (data.get("result") or []):
        post = upd.get("channel_post") or upd.get("edited_channel_post")
        if not post:
            continue
        chat = post.get("chat") or {}
        if chan_id is not None and chat.get("id") != chan_id:
            continue
        text = post.get("text") or post.get("caption") or ""
        if not text:
            continue
        tags = [t.lower() for t in _HASHTAG_RE.findall(text)]
        photos = post.get("photo") or []
        file_id = photos[-1].get("file_id") if photos else None
        posts.append({
            "message_id": post.get("message_id"),
            "date": post.get("date"),
            "text": text,
            "hashtags": tags,
            "has_image": bool(file_id),
            "image_file_id": file_id,
        })

    if tag:
        t = tag.lstrip("#").lower()
        posts = [p for p in posts if t in p["hashtags"]]
    posts.sort(key=lambda p: p.get("date") or 0, reverse=True)
    return JSONResponse({
        "channel": settings.algo_channel_url,
        "count": len(posts[:limit]),
        "posts": posts[:limit],
        "note": "هشتگ‌ها: #طلا #تتر #btc #eth و سایر آلت‌کوین‌ها (مثل #stg).",
    })


# ───────────────────────── کمکی‌ها ─────────────────────────
def _resolve_risk(payload: dict, uid: str) -> dict[str, Any]:
    if payload.get("risk_percent") is not None:
        pct = _num(payload.get("risk_percent"))
        cat = risk._category(pct)
        return {"percent": pct, "label": payload.get("risk_label") or cat["label"],
                "desc": payload.get("risk_desc") or cat["desc"], "key": cat["key"],
                "source": "input"}
    prof = db.get_risk(uid) if uid else None
    if isinstance(prof, dict) and prof.get("percent") is not None:
        pct = _num(prof.get("percent")) or 0.0
        cat = risk._category(pct)
        return {"percent": pct, "label": prof.get("label") or cat["label"],
                "desc": cat["desc"], "key": prof.get("category") or cat["key"],
                "source": "stored"}
    # پیش‌فرض: متعادل
    cat = risk._category(50.0)
    return {"percent": 50.0, "label": cat["label"], "desc": cat["desc"],
            "key": cat["key"], "source": "default"}


def _norm_sym(a: dict) -> str:
    s = (a.get("symbol") or "").strip().upper()
    if s.endswith("USDT"):
        s = s[:-4]
    return s


async def _safe_analyze(client: httpx.AsyncClient, sym: str) -> dict[str, Any]:
    try:
        return await ta.analyze_pair(client, sym, _pair(sym))
    except Exception:  # noqa: BLE001
        return {"symbol": sym, "ok": False}


async def _market_regime(client: httpx.AsyncClient) -> dict[str, Any]:
    """رژیم کلی بازار: روند بیت‌کوین + RSI و ترس‌وطمع از کش."""
    out: dict[str, Any] = {}
    try:
        kl = await ta.fetch_klines(client, "BTCUSDT", "1d", 220)
        if len(kl) >= 50:
            closes = [k["c"] for k in kl]
            out["btc_trend"] = ta._trend(closes)
            out["btc_rsi"] = ta.rsi(closes)
            out["btc_price"] = ta._r(closes[-1])
    except Exception:  # noqa: BLE001
        pass
    from app.cache import cache
    fng = cache.get("fng")
    if isinstance(fng, dict):
        out["fear_greed"] = {"value": fng.get("value"), "label": fng.get("label")}
    rsi_cache = cache.get("toobit:avg_rsi")
    if isinstance(rsi_cache, dict):
        out["market_avg_rsi"] = rsi_cache.get("value")
    return out


def _macro_assets(metals: Any, usdt: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(usdt, dict):
        irt = usdt.get("usdt_irt") or {}
        out["tether"] = {"name": "تتر (USDT)", "price_toman": irt.get("price"),
                         "change_24h": irt.get("change_24h"), "role": "anchor",
                         "note": "نقدینگی پایدار؛ سپر در برابر نوسان."}
    if isinstance(metals, dict):
        g = metals.get("gold_18k") or {}
        comm = metals.get("commodities") or {}
        out["gold_18k"] = {"name": "طلای ۱۸ عیار", "price_toman": g.get("price"),
                           "change_24h": g.get("change_24h"), "role": "store_of_value"}
        if comm.get("XAU"):
            out["gold_ounce"] = {"name": "انس طلا", "price_usd": comm["XAU"].get("price"),
                                 "change_24h": comm["XAU"].get("change_24h"), "role": "store_of_value"}
        if comm.get("XAG"):
            out["silver_ounce"] = {"name": "انس نقره", "price_usd": comm["XAG"].get("price"),
                                   "change_24h": comm["XAG"].get("change_24h"), "role": "store_of_value"}
    return out


async def _safe(coro):
    try:
        return await coro
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}


def _num(x) -> float | None:
    if x is None:
        return None
    try:
        return float(str(x).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None
