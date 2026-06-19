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

from app.cache import cache, cmc_budget, credit_budget
from app.config import settings
from app.services import coinmarketcap, etf_flows, mock_data, sourcearena, tabdeal, toobit
from app.services import commodities as commodities_svc

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/macro")
async def macro():
    """شاخص‌های کلان از CoinMarketCap (ارزش بازار، حجم، دامیننس) + فصل آلت‌کوین
    + شاخص ترس و طمع. هر بخش به‌طور مستقل امن می‌شود تا خطای یک منبع کل پاسخ را
    خراب نکند."""
    data, alt, fg = await asyncio.gather(
        _safe(coinmarketcap.macro()),
        _safe(coinmarketcap.altseason()),
        _safe(coinmarketcap.fng()),
    )
    if not isinstance(data, dict) or "error" in data:
        data = mock_data.cmc_macro()
    if isinstance(alt, dict) and "error" not in alt:
        data["altcoin_season"] = alt.get("altcoin_season")
        # دامیننس تتر = ارزش بازار تتر ÷ کل بازار (بدون درخواست اضافه)
        usdt_mc = alt.get("usdt_market_cap") or 0
        total_mc = (data.get("market_cap") or {}).get("value") or 0
        if usdt_mc and total_mc and isinstance(data.get("dominance"), dict):
            data["dominance"]["usdt"] = round(usdt_mc / total_mc * 100, 2)
    else:
        data["altcoin_season"] = mock_data.cmc_altseason()["altcoin_season"]
    if isinstance(fg, dict) and "error" not in fg:
        data["fear_greed"] = fg
    return data


@router.get("/etf")
async def etf():
    """جریان خالص ETFهای کریپتو (بیت‌کوین + اتریوم) از Farside Investors."""
    return await etf_flows.flows()


@router.get("/heatmap")
async def heatmap():
    """نقشهٔ حرارتی زنده از توبیت (قیمت و تغییر ۲۴ساعتهٔ لحظه‌ای)."""
    return await toobit.heatmap()


@router.get("/coins")
async def coins():
    """ارزهای برتر بازار (مارکت‌کپ بالا) از توبیت."""
    return await toobit.top_coins()


@router.get("/prices")
async def prices():
    """قیمت‌های کلیدی: تتر تومانی (Tabdeal) + طلای ۱۸ع و دلار آزاد (SourceArena)
    + انس طلا/نقره و نفت خام (Yahoo Finance، با تغییر ۲۴ساعتهٔ واقعی).
    ترس‌وطمع از کش تا گیج هر ۸ ثانیه به‌روز شود."""
    usdt, metals, comm = await asyncio.gather(
        _safe(tabdeal.usdt()), _safe(sourcearena.metals()),
        _safe(commodities_svc.commodities()),
    )

    # کالاهای جهانی از Yahoo (قیمت + تغییر واقعی)؛ در نبود، از SourceArena پر می‌شود.
    commodities = {}
    if isinstance(comm, dict) and "error" not in comm:
        commodities = dict(comm.get("commodities", {}))
    sa_comm = metals.get("commodities", {}) if isinstance(metals, dict) else {}
    for k, v in sa_comm.items():
        commodities.setdefault(k, v)

    # تغییر ۲۴ساعتهٔ تتر/تومان از تغییر دلار آزاد (SourceArena) گرفته می‌شود؛
    # اندپوینت عمق Tabdeal خودش درصد تغییر ندارد.
    usdt_irt = usdt.get("usdt_irt") if isinstance(usdt, dict) else None
    if isinstance(usdt_irt, dict) and isinstance(metals, dict):
        usd_chg = metals.get("usd_change_24h")
        if usd_chg and not usdt_irt.get("change_24h"):
            usdt_irt["change_24h"] = usd_chg

    # طلای ۱۸ عیار: قیمت از SourceArena. درصد تغییر هم از SourceArena؛ اما وقتی
    # بازار طلای ایران بسته است SourceArena صفر می‌دهد — در آن صورت تغییر را از
    # «تغییر انس جهانی + تغییر دلار آزاد» تخمین می‌زنیم تا ثابت نماند.
    gold_18k = metals.get("gold_18k") if isinstance(metals, dict) else None
    if isinstance(gold_18k, dict) and not gold_18k.get("change_24h"):
        xau_chg = (commodities.get("XAU") or {}).get("change_24h") or 0
        usd_chg = metals.get("usd_change_24h") if isinstance(metals, dict) else 0
        est = round((xau_chg or 0) + (usd_chg or 0), 2)
        if est:
            gold_18k["change_24h"] = est

    fg = cache.get("fng") or mock_data.fear_greed()

    return {
        "usdt_irt": usdt_irt,
        "gold_18k": gold_18k,
        "commodities": commodities,
        "fear_greed": fg,
        "sources": {
            "usdt": usdt.get("source") if isinstance(usdt, dict) else "error",
            "metals": metals.get("source") if isinstance(metals, dict) else "error",
            "commodities": comm.get("source") if isinstance(comm, dict) else "error",
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
        "cmc_api_key_set": bool(settings.cmc_api_key),
        "cryptorank_api_key_set": bool(settings.cryptorank_api_key),
        "sourcearena_token_set": bool(settings.sourcearena_token),
        "toobit_keys_set": bool(settings.toobit_access_key),
        "tabdeal_keys_set": bool(settings.tabdeal_api_key),
        "tabdeal_base_url": settings.tabdeal_base_url,
        "toobit_base_url": settings.toobit_base_url,
        "sourcearena_base_url": settings.sourcearena_base_url,
        "cmc_base_url": settings.cmc_base_url,
    }
    out: dict = {"keys": keys, "credits": credit_budget.usage(),
                 "cmc_credits": cmc_budget.usage(), "parsed": {}, "raw": {}}

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
        _safe(toobit.heatmap()),
        _safe(coinmarketcap.macro()),
        _safe(coinmarketcap.altseason()),
        _safe(coinmarketcap.fng()),
        _safe(etf_flows.flows()),
        _safe(commodities_svc.commodities()),
        *[c for _, c in raw_calls],
    )

    out["parsed"]["tabdeal_usdt"] = results[0]
    out["parsed"]["sourcearena_metals"] = results[1]
    g = results[2]
    out["parsed"]["toobit_coins"] = g if "error" in g else {"source": g.get("source"), "coins": g.get("coins", [])}
    out["parsed"]["toobit_oil"] = results[3]
    hm = results[4]
    out["parsed"]["toobit_heatmap"] = hm if "error" in hm else {"source": hm.get("source"), "top5": hm.get("heatmap", [])[:5]}
    out["parsed"]["cmc_macro"] = results[5]
    out["parsed"]["cmc_altseason"] = results[6]
    out["parsed"]["fear_greed"] = results[7]
    etf = results[8]
    out["parsed"]["etf_flows"] = etf if "error" in etf else {
        "source": etf.get("source"), "updated": etf.get("updated"),
        "count": len(etf.get("points", [])), "last": (etf.get("points") or [{}])[-1]}
    out["parsed"]["commodities"] = results[9]

    for (name, _), res in zip(raw_calls, results[10:]):
        out["raw"][name] = res

    # کوتاه‌کردن تیکر بزرگ توبیت
    tb = out["raw"].get("toobit_ticker24", {}).get("json")
    if isinstance(tb, list):
        sample = [t for t in tb if isinstance(t, dict) and
                  (t.get("s", t.get("symbol", "")) or "").upper() in ("BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT")]
        out["raw"]["toobit_ticker24"]["json"] = {"count": len(tb), "sample": sample[:6]}

    return out
