"""
روتر JSON بازار — فرانت‌اند فقط با این اندپوینت‌ها صحبت می‌کند و هرگز
مستقیماً به APIهای بیرونی وصل نمی‌شود. هر گروه TTL مخصوص خودش را دارد:

* /api/market/macro     ← CryptoRank (کش ۱۰ دقیقه) + ترس و طمع
* /api/market/gainers   ← Toobit (کش ~۱۲ ثانیه)
* /api/market/internal  ← تتر (تبدیل) + طلای ۱۸ع (سورس‌آرنا، ۳۰ دقیقه) + فیوچرز توبیت
* /api/market/credits   ← وضعیت مصرف کردیت CryptoRank (شفافیت)
"""
from __future__ import annotations

import asyncio

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
    """درخواست خام برای عیب‌یابی — وضعیت + بدنهٔ کوتاه‌شده را برمی‌گرداند.
    مهلت کوتاه تا کل اندپوینت عیب‌یابی زیر تایم‌اوت Nginx بماند."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(6.0)) as client:
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

    async def _safe(coro):
        try:
            return await coro
        except Exception as e:  # noqa: BLE001
            return {"error": f"{type(e).__name__}: {e}"}

    # --- پارس‌شدهٔ نهایی (همان چیزی که UI می‌بیند) + پاسخ خام — همگی هم‌زمان ---
    raw_calls = [
        ("tabdeal_usdtirt", _raw_get(f"{settings.tabdeal_base_url}/r/api/v1/depth/", {"symbol": "USDTIRT"})),
        ("toobit_ticker24", _raw_get(f"{settings.toobit_base_url}/quote/v1/ticker/24hr")),
        ("fng", _raw_get(f"{settings.fng_base_url}/", {"limit": "1"})),
    ]
    if settings.sourcearena_token:
        raw_calls.append(("sourcearena", _raw_get(
            f"{settings.sourcearena_base_url}/",
            {"token": settings.sourcearena_token, "currency": "", "v2": ""})))

    results = await asyncio.gather(
        _safe(tabdeal.usdt()),
        _safe(sourcearena.gold18()),
        _safe(toobit.futures()),
        _safe(toobit.gainers()),
        _safe(cryptorank.macro()),
        *[c for _, c in raw_calls],
    )

    out["parsed"]["tabdeal_usdt"] = results[0]
    out["parsed"]["sourcearena_gold"] = results[1]
    out["parsed"]["toobit_futures"] = results[2]
    g = results[3]
    out["parsed"]["toobit_gainers"] = (
        g if "error" in g else {"source": g.get("source"), "top": g.get("gainers", [])[:3]})
    m = results[4]
    if "error" in m:
        out["parsed"]["cryptorank"] = m
    else:
        hm = m.get("heatmap", [])
        out["parsed"]["cryptorank"] = {
            "source": m.get("source"),
            "btc_eth": [c for c in hm if c.get("symbol") in ("BTC", "ETH")],
        }

    for (name, _), res in zip(raw_calls, results[5:]):
        out["raw"][name] = res

    # محدودکردن حجم تیکر توبیت (لیست بزرگ است)
    tb = out["raw"]["toobit_ticker24"].get("json")
    if isinstance(tb, list):
        sample = [t for t in tb if isinstance(t, dict) and t.get("s", t.get("symbol", "")).upper() in
                  ("BTCUSDT", "ETHUSDT", "XAUUSDT", "XAGUSDT", "OILBRENTUSDT")]
        out["raw"]["toobit_ticker24"]["json"] = {"count": len(tb), "sample": sample[:8]}

    return out
