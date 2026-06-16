"""
روتر JSON بازار — فرانت‌اند فقط با این اندپوینت‌ها صحبت می‌کند و هرگز
مستقیماً به APIهای بیرونی وصل نمی‌شود. هر گروه TTL مخصوص خودش را دارد:

* /api/market/macro     ← CryptoRank (کش ۱۰ دقیقه) + ترس و طمع
* /api/market/gainers   ← Toobit (کش ~۱۲ ثانیه)
* /api/market/internal  ← تتر (تبدیل) + طلای ۱۸ع (سورس‌آرنا، ۳۰ دقیقه) + فیوچرز توبیت
* /api/market/credits   ← وضعیت مصرف کردیت CryptoRank (شفافیت)
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter

from app.cache import credit_budget
from app.config import settings
from app.services import cryptorank, fng, sourcearena, tabdeal, toobit

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/macro")
async def macro():
    data = await cryptorank.macro()
    try:
        data["fear_greed"] = await fng.fng()
    except Exception:
        pass
    return data


@router.get("/gainers")
async def gainers():
    return await toobit.gainers()


@router.get("/internal")
async def internal():
    usdt = await tabdeal.usdt()
    gold = await sourcearena.gold18()
    fut = await toobit.futures()
    return {
        "usdt_irt": usdt["usdt_irt"],
        "gold_18k": gold["gold_18k"],
        "futures": fut["futures"],
        "sources": {"usdt": usdt["source"], "gold": gold["source"], "futures": fut["source"]},
    }


@router.get("/credits")
async def credits():
    return credit_budget.usage()


def _trim(s: str, n: int = 2500) -> str:
    return s if len(s) <= n else s[:n] + " …[truncated]"


async def _raw_get(url: str, params: dict | None = None) -> dict:
    """درخواست خام برای عیب‌یابی — وضعیت + بدنهٔ کوتاه‌شده را برمی‌گرداند."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.http_timeout)) as client:
            r = await client.get(url, params=params or {})
            body = r.text
            try:
                parsed = r.json()
            except Exception:
                parsed = None
            return {
                "url": str(r.url),
                "status": r.status_code,
                "json": parsed if parsed is not None else _trim(body),
            }
    except Exception as e:  # noqa: BLE001
        return {"url": url, "error": f"{type(e).__name__}: {e}"}


@router.get("/debug")
async def debug():
    """
    عیب‌یابی زندهٔ منابع داده. این اندپوینت پاسخ خام هر API + مقدار پارس‌شدهٔ
    نهایی + وضعیت کلیدها را برمی‌گرداند تا نگاشت فیلدها قطعی شود.
    خروجی این آدرس را برای رفع باگ قیمت‌ها بفرستید:
        https://portfolio.cryptosmart.site/api/market/debug
    """
    keys = {
        "cryptorank_api_key_set": bool(settings.cryptorank_api_key),
        "sourcearena_token_set": bool(settings.sourcearena_token),
        "tabdeal_base_url": settings.tabdeal_base_url,
        "toobit_base_url": settings.toobit_base_url,
        "sourcearena_base_url": settings.sourcearena_base_url,
    }

    out: dict = {"keys": keys, "parsed": {}, "raw": {}}

    # --- پارس‌شدهٔ نهایی (همان چیزی که UI می‌بیند) + برچسب منبع ---
    try:
        out["parsed"]["tabdeal_usdt"] = await tabdeal.usdt()
    except Exception as e:  # noqa: BLE001
        out["parsed"]["tabdeal_usdt"] = {"error": f"{type(e).__name__}: {e}"}
    try:
        out["parsed"]["sourcearena_gold"] = await sourcearena.gold18()
    except Exception as e:  # noqa: BLE001
        out["parsed"]["sourcearena_gold"] = {"error": f"{type(e).__name__}: {e}"}
    try:
        out["parsed"]["toobit_futures"] = await toobit.futures()
    except Exception as e:  # noqa: BLE001
        out["parsed"]["toobit_futures"] = {"error": f"{type(e).__name__}: {e}"}
    try:
        g = await toobit.gainers()
        out["parsed"]["toobit_gainers"] = {"source": g.get("source"), "top": g.get("gainers", [])[:3]}
    except Exception as e:  # noqa: BLE001
        out["parsed"]["toobit_gainers"] = {"error": f"{type(e).__name__}: {e}"}
    try:
        m = await cryptorank.macro()
        hm = m.get("heatmap", [])
        out["parsed"]["cryptorank"] = {
            "source": m.get("source"),
            "btc_eth": [c for c in hm if c.get("symbol") in ("BTC", "ETH")],
        }
    except Exception as e:  # noqa: BLE001
        out["parsed"]["cryptorank"] = {"error": f"{type(e).__name__}: {e}"}

    # --- پاسخ خام مستقیم از هر API (برای نگاشت دقیق فیلدها) ---
    out["raw"]["tabdeal_usdtirt"] = await _raw_get(
        f"{settings.tabdeal_base_url}/r/api/v1/depth/", {"symbol": "USDTIRT"})
    out["raw"]["toobit_ticker24"] = await _raw_get(
        f"{settings.toobit_base_url}/quote/v1/ticker/24hr")
    if settings.sourcearena_token:
        out["raw"]["sourcearena"] = await _raw_get(
            f"{settings.sourcearena_base_url}/", {"token": settings.sourcearena_token, "currency": "", "v2": ""})
    out["raw"]["fng"] = await _raw_get(f"{settings.fng_base_url}/", {"limit": "1"})

    # محدودکردن حجم تیکر توبیت (لیست بزرگ است)
    tb = out["raw"]["toobit_ticker24"].get("json")
    if isinstance(tb, list):
        sample = [t for t in tb if isinstance(t, dict) and t.get("s", t.get("symbol", "")).upper() in
                  ("BTCUSDT", "ETHUSDT", "XAUUSDT", "XAGUSDT", "OILBRENTUSDT")]
        out["raw"]["toobit_ticker24"]["json"] = {"count": len(tb), "sample": sample[:8]}

    return out
