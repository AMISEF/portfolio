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
import json
import os
import re
from typing import Any

import httpx
from fastapi import APIRouter, Header, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from app import db
from app.config import settings
from app.services import portfolio_valuation, risk, sourcearena, ta, tabdeal, toobit
from app.services import chart_svg, telegram_signals

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
async def context(request: Request,
                  x_advisor_key: str | None = Header(default=None)):
    """زمینهٔ کامل برای مدل: دارایی‌ها + ریسک + رژیم بازار + تحلیل تکنیکال نمادها.

    بدنه (همه اختیاری):
      uid           شناسهٔ کاربر برای واکشی دارایی/ریسک ذخیره‌شده
      assets        فهرست دارایی مستقیم (جایگزین uid)
      risk_percent  درصد ریسک‌پذیری (۰–۱۰۰)
      risk_label, risk_desc   برچسب و توضیح ریسک
      extra_symbols فهرست نمادهای کریپتوی اضافه برای تحلیل
    """
    # ۰) بدنه را مستقل از Content-Type پارس می‌کنیم؛ برخی کلاینت‌ها (مثل نود HTTP
    #    دیفای) هدر application/json را درست نمی‌فرستند و Body() آنگاه 422 می‌دهد.
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        try:
            payload = json.loads((await request.body()) or b"{}")
        except Exception:  # noqa: BLE001
            payload = {}
    if not isinstance(payload, dict):
        payload = {}

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


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request,
                           x_telegram_bot_api_secret_token: str | None = Header(default=None)):
    """وب‌هوک تلگرام برای ربات سیگنال‌ها: هر پست کانال را ذخیره می‌کند.

    تلگرام هدر «X-Telegram-Bot-Api-Secret-Token» را با همان مقداری که هنگام
    setWebhook دادیم می‌فرستد؛ اگر نخواند، درخواست را رد می‌کنیم. همیشه ۲۰۰
    برمی‌گردانیم تا تلگرام پیام را دوباره صف نکند (خطاها داخلی نادیده گرفته می‌شوند).
    """
    if x_telegram_bot_api_secret_token != settings.signals_webhook_secret_effective:
        return JSONResponse({"ok": False}, status_code=403)
    try:
        update = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse({"ok": True})
    try:
        await telegram_signals.process_update(update)
    except Exception:  # noqa: BLE001
        pass
    return JSONResponse({"ok": True})


@router.get("/signal-image/{message_id}")
async def signal_image(message_id: int, i: int = 1):
    """تصویرِ n اُمِ آلبومِ یک تحلیل کانال (۱-محور: ?i=1، ?i=2، …)."""
    imgs = db.signal_images(message_id)
    idx = i - 1
    path = imgs[idx] if 0 <= idx < len(imgs) else None
    if not path or not os.path.exists(path):
        return JSONResponse({"error": "not_found"}, status_code=404)
    return FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})


@router.get("/signals")
async def channel_signals(x_advisor_key: str | None = Header(default=None),
                          limit: int = 50, tag: str | None = None):
    """تحلیل‌های معتبر کانال پورتفولیو (ذخیره‌شده از وب‌هوک، اعتبار ۷ روز).

    ربات «portfolio_Cryptosmart_bot» پست‌های کانال را با نقاط خرید/فروش و تصویر
    چارت می‌فرستد؛ این‌جا تحلیل‌های منقضی‌نشده برگردانده می‌شوند تا ورک‌فلوِ
    سبدچینی Dify آن‌ها را در پیشنهاد لحاظ کند. فیلتر اختیاری: ?tag=btc.
    """
    if settings.advisor_api_key and x_advisor_key != settings.advisor_api_key:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    telegram_signals.purge_expired()
    base = settings.public_base_url.rstrip("/")
    rows = db.list_active_signals(limit=limit, tag=tag)
    posts: list[dict[str, Any]] = []
    by_asset: dict[str, Any] = {}
    for r in rows:
        try:
            tags = json.loads(r.get("hashtags") or "[]")
        except Exception:  # noqa: BLE001
            tags = []
        mid = r.get("message_id")
        n_imgs = len(r.get("image_list") or [])
        images = [f"{base}/api/advisor/signal-image/{mid}?i={k}" for k in range(1, n_imgs + 1)]
        text = r.get("text") or ""
        post = {
            "message_id": mid,
            "date": r.get("ts"),
            "text": text,
            "hashtags": tags,
            "has_image": bool(images),
            "image_url": images[0] if images else None,
            "images": images,
            "levels": _extract_levels(text),
            "expires_at": r.get("expires_at"),
        }
        posts.append(post)
        # نگاشتِ «هر دارایی ← جدیدترین تحلیلِ کانالِ آن» (rows از پیش newest-first است)
        for a in {_canon_asset(t) for t in tags}:
            if a and a not in by_asset:
                by_asset[a] = {
                    "asset": a,
                    "hashtags": tags,
                    "text": text,
                    "levels": post["levels"],
                    "date": r.get("ts"),
                    "expires_at": r.get("expires_at"),
                    "message_id": mid,
                    "image_url": post["image_url"],
                    "images": images,
                    "allow_mid": bool(r.get("allow_mid")),
                    "allow_long": bool(r.get("allow_long")),
                }
    return JSONResponse({
        "channel": settings.signals_channel_url,
        "count": len(posts),
        "posts": posts,
        "by_asset": by_asset,
        "note": ("تحلیل‌های کانال پورتفولیو با نقاط خرید/فروش و وین‌ریت بالا؛ اعتبار "
                 "هر تحلیل ۷ روز (پس از آن حذف می‌شود تا تحلیل تازه جایگزین شود). "
                 "by_asset = جدیدترین تحلیلِ کانال برای هر دارایی (تتر، طلا، دلار، "
                 "BTC، ETH و همهٔ آلت‌کوین‌ها) با levels = قیمت‌های اعلامیِ متن. "
                 "برای هر دارایی، اگر در by_asset تحلیلِ کانال وجود دارد، نقاط "
                 "خرید/فروش/حد ضررِ همان را مبنای پیشنهاد قرار بده."),
    })


# ───────────────────────── کمکی‌ها ─────────────────────────
# نگاشتِ هشتگ‌های کانال به «کلیدِ داراییِ» یکتا (برای by_asset در سبدچینیِ AI).
_ASSET_ALIASES: dict[str, set[str]] = {
    "tether": {"تتر", "usdt", "tether"},
    "dollar": {"دلار", "usd", "dollar"},
    "gold": {"طلا", "طلای", "سکه", "gold", "gold18", "xau", "xauusd", "انس"},
    "silver": {"نقره", "silver", "xag", "xagusd"},
    "oil": {"نفت", "oil", "wti", "brent"},
    "BTC": {"btc", "bitcoin", "بیتکوین", "btcusdt"},
    "ETH": {"eth", "ethereum", "اتریوم", "ethusdt"},
}
_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٫٬", "0123456789.,")
_LEVEL_RE = re.compile(r"[0-9][0-9,\.]{2,}")


def _canon_asset(tag: str) -> str:
    """کلیدِ داراییِ یکتا از یک هشتگ (مثلاً «تتر»/«usdt» → tether؛ «stg» → STG)."""
    t = str(tag).lstrip("#").strip().lower()
    if not t:
        return ""
    for key, aliases in _ASSET_ALIASES.items():
        if t in aliases:
            return key
    return t.upper() if t.isascii() else t


def _extract_levels(text: str) -> list[str]:
    """قیمت‌های اعلامیِ متنِ تحلیل را استخراج می‌کند (ارقام فارسی/انگلیسی، بدونِ
    جداکنندهٔ هزارگان). برای استفادهٔ مدل به‌عنوان نقاطِ خرید/فروشِ همان دارایی."""
    norm = (text or "").translate(_FA_DIGITS)
    out: list[str] = []
    seen: set[str] = set()
    for m in _LEVEL_RE.findall(norm):
        v = m.replace(",", "").rstrip(".")
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out[:12]


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
