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
import datetime as _dt

import httpx
from fastapi import APIRouter

from app.cache import cache, cmc_budget, credit_budget
from app.config import settings
from app.services import coinmarketcap, mock_data, sourcearena, tabdeal, toobit
from app.services import commodities as commodities_svc

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/macro")
async def macro():
    """شاخص‌های کلان از CoinMarketCap (ارزش بازار، حجم، دامیننس) + فصل آلت‌کوین
    + شاخص ترس و طمع. هر بخش به‌طور مستقل امن می‌شود تا خطای یک منبع کل پاسخ را
    خراب نکند."""
    data, alt, fg, rsi = await asyncio.gather(
        _safe(coinmarketcap.macro()),
        _safe(coinmarketcap.altseason()),
        _safe(coinmarketcap.fng()),
        _safe(toobit.avg_rsi()),
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
    if isinstance(rsi, dict) and "error" not in rsi:
        data["rsi"] = rsi
    return data


@router.get("/heatmap")
async def heatmap():
    """نقشهٔ حرارتی به‌سبک CryptoRank: ساختار (دسته/مارکت‌کپ/حجم/تغییر ۲۴س/۷ر/۳۰ر/۹۰ر)
    از CoinMarketCap (listings) + قیمت و تغییر ۲۴ساعتهٔ زندهٔ توبیت روی آن (هر ۵ ثانیه).
    در نبود CMC، به دادهٔ زندهٔ توبیت (فقط ۲۴ساعته) برمی‌گردد.
    (توجه: API رایگان CryptoRank در لیست، تغییر چنددوره‌ای ندارد؛ برای همین داده
    از CMC گرفته می‌شود اما ظاهر کاملاً مثل CryptoRank است.)"""
    cr, tb = await asyncio.gather(_safe(coinmarketcap.heatmap()), _safe(toobit.heatmap()))

    # نگاشت قیمت/تغییر زندهٔ ۲۴ساعته از توبیت
    live = {}
    if isinstance(tb, dict) and tb.get("heatmap"):
        live = {x["symbol"]: x for x in tb["heatmap"]}

    if isinstance(cr, dict) and "error" not in cr and cr.get("items"):
        for it in cr["items"]:
            lv = live.get(it["symbol"])
            if lv:
                it["price"] = lv["price"]
                ch = dict(it.get("changes") or {})
                ch["h24"] = lv["change_24h"]
                it["changes"] = ch
        return {"source": cr.get("source", "live"), "items": cr["items"]}

    # پشتیبان: فقط توبیت (تغییر ۲۴ساعته)
    if live:
        items = [{
            "symbol": x["symbol"], "name": x.get("name", x["symbol"]),
            "category": x.get("category", "Other"), "type": "coin",
            "price": x["price"], "market_cap": x["market_cap"], "volume": x["market_cap"],
            "changes": {"h24": x["change_24h"], "d7": 0, "d30": 0, "m3": 0, "y1": 0, "ytd": 0},
        } for x in tb["heatmap"]]
        return {"source": tb.get("source", "live"), "items": items}

    return mock_data.cr_heatmap()


@router.get("/coins")
async def coins():
    """۵ ارز برتر از توبیت (قیمت زندهٔ ۵ثانیه) + شِماتیک قیمت (اسپارک‌لاین، ۶۰ثانیه)."""
    c, sp = await asyncio.gather(_safe(toobit.top_coins()), _safe(toobit.sparklines()))
    data = c if isinstance(c, dict) and "error" not in c else mock_data.toobit_top_coins()
    spmap = sp.get("sparklines", {}) if isinstance(sp, dict) and "error" not in sp else {}
    for coin in data.get("coins", []):
        coin["spark"] = spmap.get(coin["symbol"], [])
    return data


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

    # طلای ۱۸ عیار: وقتی دادهٔ SourceArena «تازه» است، قیمت واقعی بازار ایران را
    # نشان می‌دهیم و ضریب پرمیوم (قیمت واقعی ÷ ارزش ذوب) را ذخیره می‌کنیم. اگر
    # SourceArena در دسترس نباشد یا کهنه شود (مثلاً چند روز قطع)، قیمت را از انس
    # جهانیِ زندهٔ Yahoo × دلار زندهٔ Tabdeal × همان ضریب محاسبه می‌کنیم تا هرگز
    # منجمد نماند و با حرکت بازار به‌روز بماند.
    gold_18k = metals.get("gold_18k") if isinstance(metals, dict) else None
    sa_fresh = bool(metals.get("fresh")) if isinstance(metals, dict) else False
    xau = commodities.get("XAU") or {}
    xau_usd = xau.get("price") or 0
    xau_chg = xau.get("change_24h") or 0
    usd_toman = (usdt_irt.get("price") or 0) if isinstance(usdt_irt, dict) else 0
    melt = sourcearena.estimate_gold_18k_toman(xau_usd, usd_toman)

    if sa_fresh and isinstance(gold_18k, dict) and gold_18k.get("price"):
        # کالیبراسیون ضریب بازار ایران از دادهٔ تازه (یک هفته ماندگار)
        if melt > 0:
            cache.set("gold18k:factor", gold_18k["price"] / melt, 7 * 24 * 3600)
        # پراکسی sa.resicard.ir فیلد change سورس‌آرنا را صفر می‌دهد. پس درصد تغییر
        # ۲۴ساعته را خودمان محاسبه می‌کنیم: قیمتِ امروز نسبت به آخرین قیمتِ روز قبل.
        # قیمت هر روز ذخیره می‌شود (۳ روز ماندگار)؛ کلیدِ روز قبل = بستهٔ آن روز.
        if not gold_18k.get("change_24h"):
            today = _dt.date.today()
            price = gold_18k["price"]
            cache.set(f"gold18k:day:{today.isoformat()}", price, 3 * 24 * 3600)
            prev = cache.get_stale(f"gold18k:day:{(today - _dt.timedelta(days=1)).isoformat()}")
            if prev:
                gold_18k["change_24h"] = round((price - prev) / prev * 100, 2)
    else:
        # SourceArena کهنه/خطا ⇒ تخمین زنده فقط اگر قبلاً با دادهٔ واقعی کالیبره
        # شده باشیم (وگرنه واحد/ضریب نامعلوم است و عددِ پرت می‌دهد). در نبود ضریب،
        # آخرین قیمت واقعیِ کش‌شده حفظ می‌شود.
        factor = cache.get_stale("gold18k:factor")
        if melt > 0 and factor:
            gold_18k = {"name": "طلای ۱۸ عیار", "sub": "هر گرم",
                        "price": round(melt * factor), "change_24h": round(xau_chg or 0, 2),
                        "estimated": True}

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
    out["parsed"]["commodities"] = results[8]

    for (name, _), res in zip(raw_calls, results[9:]):
        out["raw"][name] = res

    # نقشهٔ حرارتی CMC (دسته/مارکت‌کپ/تغییر چنددوره‌ای) — خلاصهٔ پارس‌شده
    crh = await _safe(coinmarketcap.heatmap())
    out["parsed"]["heatmap_cmc"] = crh if "error" in crh else {
        "source": crh.get("source"), "count": len(crh.get("items", [])),
        "cats": sorted({i.get("category") for i in (crh.get("items") or [])}),
        "sample": (crh.get("items") or [])[:3]}

    # کوتاه‌کردن تیکر بزرگ توبیت
    tb = out["raw"].get("toobit_ticker24", {}).get("json")
    if isinstance(tb, list):
        sample = [t for t in tb if isinstance(t, dict) and
                  (t.get("s", t.get("symbol", "")) or "").upper() in ("BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT")]
        out["raw"]["toobit_ticker24"]["json"] = {"count": len(tb), "sample": sample[:6]}

    return out
