"""
سرویس CoinMarketCap — شاخص‌های کلان بازار + شاخص فصل آلت‌کوین.

پلن Basic محدودیت دارد (هارد‌کپ ماهانه ۲۰٬۰۰۰ کردیت، ۵۰ درخواست/دقیقه، بدون
دادهٔ تاریخی). برای رعایت دقیق این سقف:
  • هر درخواست پیش از ارسال با cmc_budget بررسی می‌شود؛ اگر سقف پر باشد اصلاً
    درخواست زده نمی‌شود و از کش کهنه/نمونه استفاده می‌گردد.
  • نتایج طولانی‌مدت کش می‌شوند (global-metrics هر ۵ دقیقه، فصل آلت‌کوین هر ۱۵
    دقیقه) تا مصرف ماهانه بسیار زیر سقف بماند (~۱۱٬۵۰۰ کردیت در ماه).

اندپوینت‌ها (هر دو روی پلن Basic فعال‌اند):
  GET /v1/global-metrics/quotes/latest   → ارزش بازار، حجم، دامیننس BTC/ETH (۱ کردیت)
  GET /v1/cryptocurrency/listings/latest → برای محاسبهٔ فصل آلت‌کوین (۱ کردیت تا ۲۰۰ ارز)
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.services import mock_data

# نمادهای استیبل‌کوین/پوشش‌داده‌شده که از شمارش فصل آلت‌کوین کنار گذاشته می‌شوند.
_EXCLUDE_TAGS = {"stablecoin", "wrapped-tokens", "asset-backed-token"}


def _headers() -> dict[str, str]:
    return {"X-CMC_PRO_API_KEY": settings.cmc_api_key, "Accept": "application/json"}


async def get_macro() -> dict[str, Any]:
    """شاخص‌های کلان از global-metrics (۱ کردیت)."""
    from app.cache import cmc_budget
    if not settings.cmc_api_key:
        raise RuntimeError("CMC: API key not set")
    if not cmc_budget.can_spend(1):
        raise RuntimeError("CMC: credit budget exhausted")

    timeout = httpx.Timeout(settings.http_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(
            f"{settings.cmc_base_url}/v1/global-metrics/quotes/latest",
            params={"convert": "USD"}, headers=_headers(),
        )
        resp.raise_for_status()
        payload = resp.json()
    cmc_budget.spend(int(payload.get("status", {}).get("credit_count", 1)) or 1)

    d = payload.get("data", {})
    quote = (d.get("quote") or {}).get("USD", {})
    total_mc = _f(quote, "total_market_cap")
    total_vol = _f(quote, "total_volume_24h")
    btc_dom = _f(d, "btc_dominance")
    eth_dom = _f(d, "eth_dominance")
    others_dom = max(round(100 - btc_dom - eth_dom, 2), 0.0)
    mc_change = _f(quote, "total_market_cap_yesterday_percentage_change")
    vol_change = _f(quote, "total_volume_24h_yesterday_percentage_change")

    if total_mc <= 0:
        raise RuntimeError("CMC: empty global data")

    return {
        "source": "live",
        "market_cap": {"value": total_mc, "change_24h": round(mc_change, 2)},
        "volume_24h": {"value": total_vol, "change_24h": round(vol_change, 2)},
        "dominance": {
            "btc": round(btc_dom, 2),
            "eth": round(eth_dom, 2),
            "others": others_dom,
            "btc_change_24h": round(_f(d, "btc_dominance_24h_percentage_change"), 2),
        },
    }


async def macro() -> dict[str, Any]:
    from app.cache import cached
    return await cached("cmc:macro", settings.cmc_macro_ttl, get_macro, mock_data.cmc_macro)


# ---- شاخص ترس و طمع از CoinMarketCap (v3/fear-and-greed، روی پلن Basic، ۱ کردیت) ----
_FNG_FA = {
    "Extreme Fear": "ترس شدید", "Fear": "ترس", "Neutral": "خنثی",
    "Greed": "طمع", "Extreme Greed": "طمع شدید",
}


async def get_fng() -> dict[str, Any]:
    """ترس و طمع از CMC؛ در صورت نبود کلید/پر شدن بودجه/خطا، از alternative.me."""
    from app.cache import cmc_budget
    if settings.cmc_api_key and cmc_budget.can_spend(1):
        try:
            timeout = httpx.Timeout(settings.http_timeout)
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(
                    f"{settings.cmc_base_url}/v3/fear-and-greed/latest",
                    headers=_headers(),
                )
                resp.raise_for_status()
                payload = resp.json()
            cmc_budget.spend(int(payload.get("status", {}).get("credit_count", 1)) or 1)
            d = payload.get("data", {}) or {}
            value = int(_f(d, "value"))
            label_en = d.get("value_classification") or "Neutral"
            if value > 0:
                return {"value": value, "label_en": label_en,
                        "label_fa": _FNG_FA.get(label_en, label_en)}
        except Exception:  # noqa: BLE001 — به پشتیبان می‌افتیم
            pass
    # پشتیبان: alternative.me (رایگان، بدون کلید)
    from app.services import fng as altfng
    return await altfng.get_fng()


async def fng() -> dict[str, Any]:
    from app.cache import cached
    return await cached("fng", settings.cmc_fng_ttl, get_fng, mock_data.fear_greed)


def _altseason_label(value: int) -> tuple[str, str]:
    if value >= 75:
        return "Altcoin Season", "فصل آلت‌کوین"
    if value <= 25:
        return "Bitcoin Season", "فصل بیت‌کوین"
    return "Mixed", "بازار متعادل"


async def get_altseason() -> dict[str, Any]:
    """شاخص فصل آلت‌کوین = درصد از ۵۰ ارز برتر (بدون استیبل/پوشش‌داده) که در ۹۰ روز
    گذشته از بیت‌کوین بهتر عمل کرده‌اند. (۱ کردیت)"""
    from app.cache import cmc_budget
    if not settings.cmc_api_key:
        raise RuntimeError("CMC: API key not set")
    if not cmc_budget.can_spend(1):
        raise RuntimeError("CMC: credit budget exhausted")

    timeout = httpx.Timeout(settings.http_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(
            f"{settings.cmc_base_url}/v1/cryptocurrency/listings/latest",
            params={"start": "1", "limit": "150", "convert": "USD", "sort": "market_cap"},
            headers=_headers(),
        )
        resp.raise_for_status()
        payload = resp.json()
    cmc_budget.spend(int(payload.get("status", {}).get("credit_count", 1)) or 1)

    coins = payload.get("data", []) or []
    btc_90d = None
    usdt_mc = 0.0
    for c in coins:
        sym = (c.get("symbol") or "").upper()
        q = (c.get("quote") or {}).get("USD", {})
        if sym == "BTC":
            btc_90d = _f(q, "percent_change_90d")
        elif sym == "USDT":
            usdt_mc = _f(q, "market_cap")
    if btc_90d is None:
        raise RuntimeError("CMC: BTC 90d change missing")

    # ۵۰ ارز برتر به‌جز بیت‌کوین، استیبل‌کوین‌ها و توکن‌های پوشش‌داده‌شده.
    # مطابق روش رسمی CoinMarketCap، ارزهایی که کل ۹۰ روز را در بازار نبوده‌اند
    # (percent_change_90d ندارند) کنار گذاشته می‌شوند تا شاخص به‌اشتباه پایین نیاید.
    eligible = []
    for c in coins:
        sym = (c.get("symbol") or "").upper()
        if sym == "BTC":
            continue
        tags = {str(t).lower() for t in (c.get("tags") or [])}
        if tags & _EXCLUDE_TAGS:
            continue
        q = (c.get("quote") or {}).get("USD", {})
        if q.get("percent_change_90d") is None:   # سابقهٔ کامل ۹۰روزه ندارد
            continue
        eligible.append(c)
        if len(eligible) >= 50:
            break

    if not eligible:
        raise RuntimeError("CMC: no eligible coins for altseason")

    beat = sum(
        1 for c in eligible
        if _f((c.get("quote") or {}).get("USD", {}), "percent_change_90d") > btc_90d
    )
    value = round(beat / len(eligible) * 100)
    label_en, label_fa = _altseason_label(value)
    return {"source": "live",
            "altcoin_season": {"value": value, "label_en": label_en, "label_fa": label_fa},
            # ارزش بازار تتر — برای محاسبهٔ دامیننس تتر در روتر (بدون درخواست اضافه)
            "usdt_market_cap": usdt_mc}


async def altseason() -> dict[str, Any]:
    from app.cache import cached
    return await cached("cmc:altseason", settings.cmc_altseason_ttl, get_altseason,
                        mock_data.cmc_altseason)


# ---- نقشهٔ حرارتی از listings/latest (قیمت/مارکت‌کپ/حجم + تغییر چنددوره‌ای) ----
_STABLE = {"USDT", "USDC", "DAI", "FDUSD", "USDE", "USDS", "TUSD", "USD1", "BUSD",
           "PYUSD", "USDP", "GUSD", "USDD", "FRAX", "LUSD", "USDG", "USD0"}
# نگاشت برچسب CMC → دستهٔ نمایشی (به ترتیب اولویت)
_CAT_TAGS = [
    ("stablecoin", "Stablecoin"),
    ("memes", "Meme"),
    ("decentralized-exchange", "DeFi"), ("defi", "DeFi"), ("yield", "DeFi"),
    ("lending", "DeFi"), ("liquid-staking", "DeFi"), ("derivatives", "DeFi"), ("dao", "DeFi"),
    ("centralized-exchange", "CeFi"), ("exchange-token", "CeFi"), ("exchange-based-tokens", "CeFi"),
    ("artificial-intelligence", "AI"), ("ai-big-data", "AI"), ("ai-agents", "AI"),
    ("gaming", "GameFi"), ("metaverse", "GameFi"),
    ("oracles", "Infrastructure"), ("interoperability", "Infrastructure"),
    ("infrastructure", "Infrastructure"), ("data-availability", "Infrastructure"),
    ("real-world-assets", "RWA"), ("tokenized", "RWA"),
    ("smart-contracts", "Blockchain"), ("layer-1", "Blockchain"), ("layer-2", "Blockchain"),
    ("store-of-value", "Currency"), ("payments", "Currency"),
]
# بازنویسی دستی برای ارزهای بزرگ (وقتی برچسب‌ها مبهم‌اند)
_SYMBOL_CAT = {
    "BTC": "Currency", "XRP": "Currency", "LTC": "Currency", "BCH": "Currency",
    "XMR": "Currency", "ZEC": "Currency", "DASH": "Currency",
    "ETH": "Blockchain", "BNB": "Blockchain", "SOL": "Blockchain", "ADA": "Blockchain",
    "TRX": "Blockchain", "AVAX": "Blockchain", "NEAR": "Blockchain", "DOT": "Blockchain",
    "SUI": "Blockchain", "TON": "Blockchain", "APT": "Blockchain", "HBAR": "Blockchain",
    "ICP": "Blockchain", "ETC": "Blockchain", "XLM": "Blockchain", "ALGO": "Blockchain",
    "ATOM": "Blockchain", "SEI": "Blockchain", "KAS": "Blockchain", "TAO": "AI",
    "LINK": "Infrastructure", "HYPE": "DeFi", "UNI": "DeFi", "AAVE": "DeFi", "ENA": "DeFi",
    "DOGE": "Meme", "SHIB": "Meme", "PEPE": "Meme", "WIF": "Meme", "BONK": "Meme", "FLOKI": "Meme",
    "WBT": "CeFi", "LEO": "CeFi", "OKB": "CeFi", "CRO": "CeFi", "BGB": "CeFi", "KCS": "CeFi", "GT": "CeFi",
    "RENDER": "AI", "FET": "AI", "ONDO": "RWA",
}


def _category_from(symbol: str, tags: list) -> str:
    s = (symbol or "").upper()
    if s in _STABLE:
        return "Stablecoin"
    if s in _SYMBOL_CAT:
        return _SYMBOL_CAT[s]
    tl = [str(t).lower() for t in (tags or [])]
    for sub, cat in _CAT_TAGS:
        if any(sub in t for t in tl):
            return cat
    return "Other"


async def get_heatmap() -> dict[str, Any]:
    """نقشهٔ حرارتی از listings/latest: مارکت‌کپ/حجم/قیمت + تغییر ۲۴ساعته/۷روزه/
    ۳۰روزه/۹۰روزه + دسته از برچسب‌ها."""
    if not settings.cmc_api_key:
        return mock_data.cr_heatmap()
    from app.cache import cmc_budget
    if not cmc_budget.can_spend(1):
        raise RuntimeError("CMC: credit budget exhausted (heatmap)")

    timeout = httpx.Timeout(settings.http_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(
            f"{settings.cmc_base_url}/v1/cryptocurrency/listings/latest",
            params={"start": "1", "limit": str(settings.cmc_heatmap_limit),
                    "convert": "USD", "sort": "market_cap"},
            headers=_headers(),
        )
        resp.raise_for_status()
        payload = resp.json()
    cmc_budget.spend(int(payload.get("status", {}).get("credit_count", 1)) or 1)

    items = []
    for c in payload.get("data", []) or []:
        sym = (c.get("symbol") or "").upper()
        if not sym:
            continue
        q = (c.get("quote") or {}).get("USD", {})
        mc = _f(q, "market_cap")
        if mc <= 0:
            continue
        items.append({
            "symbol": sym,
            "name": c.get("name") or sym,
            "category": _category_from(sym, c.get("tags")),
            "type": "coin" if c.get("platform") is None else "token",
            "price": _f(q, "price"),
            "market_cap": mc,
            "volume": _f(q, "volume_24h"),
            "changes": {
                "h24": round(_f(q, "percent_change_24h"), 2),
                "d7": round(_f(q, "percent_change_7d"), 2),
                "d30": round(_f(q, "percent_change_30d"), 2),
                "m3": round(_f(q, "percent_change_90d"), 2),
            },
        })
    if not items:
        raise RuntimeError("CMC heatmap: empty listings")
    return {"source": "live", "items": items}


async def heatmap() -> dict[str, Any]:
    from app.cache import cached
    return await cached("cmc:heatmap", settings.cmc_heatmap_ttl, get_heatmap, mock_data.cr_heatmap)


def _f(d: dict, *keys: str) -> float:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                continue
    return 0.0
