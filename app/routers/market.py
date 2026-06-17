"""
روتر JSON بازار — فرانت‌اند فقط با این اندپوینت‌ها صحبت می‌کند و هرگز مستقیم
به APIهای بیرونی وصل نمی‌شود. هر گروه TTL مخصوص خودش را دارد.

  GET /api/market/macro    ← CryptoRank (کلان + هیت‌مپ + کالاها) + ترس‌وطمع
  GET /api/market/gainers  ← Toobit (۵ ارز برتر رشد)
  GET /api/market/prices   ← تتر (تبدیل) + طلای ۱۸ع (سورس‌آرنا) + کالاها (CryptoRank)
  GET /api/market/credits  ← وضعیت مصرف کردیت CryptoRank
  GET /api/market/debug    ← عیب‌یابی زنده (پاسخ خام + پارس‌شده + وضعیت کلیدها)
"""
from __future__ import annotations

import asyncio

import httpx
from fastapi import APIRouter

from app.cache import cache, credit_budget
from app.config import settings
from app.services import cryptorank, fng, mock_data, sourcearena, tabdeal, toobit

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/macro")
async def macro():
    # CryptoRank و ترس‌وطمع هم‌زمان (سرعت بیشتر)
    data, fg = await asyncio.gather(_safe(cryptorank.macro()), _safe(fng.fng()))
    if not isinstance(data, dict) or "error" in data:
        data = mock_data.macro()
    if isinstance(fg, dict) and "error" not in fg:
        data["fear_greed"] = fg
    return data


@router.get("/coins")
async def coins():
    """ارزهای برتر بازار (مارکت‌کپ بالا) از توبیت."""
    return await toobit.top_coins()


@router.get("/prices")
async def prices():
    """قیمت‌های کلیدی: تتر تومانی (تبدیل) + طلای ۱۸ع و انس طلا/نقره (سورس‌آرنا)
    + نفت (توبیت). ترس‌وطمع از کش تا گیج هر ۲۰ ثانیه به‌روز شود."""
    usdt, metals, oil = await asyncio.gather(
        _safe(tabdeal.usdt()), _safe(sourcearena.metals()), _safe(toobit.oil())
    )

    commodities = dict(metals.get("commodities", {})) if isinstance(metals, dict) else {}
    if isinstance(oil, dict) and oil.get("oil"):
        commodities["OIL"] = oil["oil"]

    fg = cache.get("fng") or mock_data.fear_greed()

    return {
        "usdt_irt": usdt.get("usdt_irt") if isinstance(usdt, dict) else None,
        "gold_18k": metals.get("gold_18k") if isinstance(metals, dict) else None,
        "commodities": commodities,
        "fear_greed": fg,
        "sources": {
            "usdt": usdt.get("source") if isinstance(usdt, dict) else "error",
            "metals": metals.get("source") if isinstance(metals, dict) else "error",
            "oil": oil.get("source") if isinstance(oil, dict) else "error",
        },
    }


@router.get("/credits")
async def credits():
    return credit_budget.usage()


async def _safe(coro):
    try:
        return await coro
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}


def _trim(s: str, n: int = 2500) -> str:
    return s if len(s) <= n else s[:n] + " …[truncated]"


async def _raw_get(url: str, params: dict | None = None) -> dict:
    """درخواست خام برای عیب‌یابی — مهلت کوتاه تا کل /debug زیر تایم‌اوت Nginx بماند."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(6.0)) as client:
            r = await client.get(url, params=params or {})
            try:
                parsed = r.json()
            except Exception:
                parsed = None
            return {"url": str(r.url), "status": r.status_code,
                    "json": parsed if parsed is not None else _trim(r.text)}
    except Exception as e:  # noqa: BLE001
        return {"url": url, "error": f"{type(e).__name__}: {e}"}


@router.get("/debug")
async def debug():
    """پاسخ خام + پارس‌شدهٔ هر منبع + وضعیت کلیدها، برای تثبیت نگاشت فیلدها."""
    keys = {
        "cryptorank_api_key_set": bool(settings.cryptorank_api_key),
        "sourcearena_token_set": bool(settings.sourcearena_token),
        "toobit_keys_set": bool(settings.toobit_access_key),
        "tabdeal_keys_set": bool(settings.tabdeal_api_key),
        "tabdeal_base_url": settings.tabdeal_base_url,
        "toobit_base_url": settings.toobit_base_url,
        "sourcearena_base_url": settings.sourcearena_base_url,
        "cryptorank_base_url": settings.cryptorank_base_url,
    }
    out: dict = {"keys": keys, "credits": credit_budget.usage(), "parsed": {}, "raw": {}}

    raw_calls = [
        ("tabdeal_usdtirt", _raw_get(f"{settings.tabdeal_base_url}/r/api/v1/depth/", {"symbol": "USDTIRT"})),
        ("toobit_ticker24", _raw_get(f"{settings.toobit_base_url}/quote/v1/ticker/24hr")),
        ("fng", _raw_get(settings.fng_base_url, {"limit": "1"})),
    ]
    if settings.sourcearena_token:
        raw_calls.append(("sourcearena", _raw_get(
            f"{settings.sourcearena_base_url}/",
            {"token": settings.sourcearena_token, "currency": "", "v2": ""})))

    results = await asyncio.gather(
        _safe(tabdeal.usdt()),
        _safe(sourcearena.metals()),
        _safe(toobit.top_coins()),
        _safe(toobit.oil()),
        _safe(cryptorank.macro()),
        _safe(fng.fng()),
        _safe(cryptorank.raw_debug()),
        *[c for _, c in raw_calls],
    )

    out["parsed"]["tabdeal_usdt"] = results[0]
    out["parsed"]["sourcearena_metals"] = results[1]
    g = results[2]
    out["parsed"]["toobit_coins"] = g if "error" in g else {"source": g.get("source"), "coins": g.get("coins", [])}
    out["parsed"]["toobit_oil"] = results[3]
    m = results[4]
    if "error" in m:
        out["parsed"]["cryptorank"] = m
    else:
        hm = m.get("heatmap", [])
        out["parsed"]["cryptorank"] = {
            "source": m.get("source"),
            "stats": m.get("stats"),
            "btc_eth": [c for c in hm if c.get("symbol") in ("BTC", "ETH")],
        }
    out["parsed"]["fear_greed"] = results[5]
    out["raw"]["cryptorank"] = results[6]

    for (name, _), res in zip(raw_calls, results[7:]):
        out["raw"][name] = res

    # کوتاه‌کردن تیکر بزرگ توبیت
    tb = out["raw"].get("toobit_ticker24", {}).get("json")
    if isinstance(tb, list):
        sample = [t for t in tb if isinstance(t, dict) and
                  (t.get("s", t.get("symbol", "")) or "").upper() in ("BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT")]
        out["raw"]["toobit_ticker24"]["json"] = {"count": len(tb), "sample": sample[:6]}

    return out
