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
            params={"start": "1", "limit": "100", "convert": "USD", "sort": "market_cap"},
            headers=_headers(),
        )
        resp.raise_for_status()
        payload = resp.json()
    cmc_budget.spend(int(payload.get("status", {}).get("credit_count", 1)) or 1)

    coins = payload.get("data", []) or []
    btc_90d = None
    for c in coins:
        if (c.get("symbol") or "").upper() == "BTC":
            btc_90d = _f((c.get("quote") or {}).get("USD", {}), "percent_change_90d")
            break
    if btc_90d is None:
        raise RuntimeError("CMC: BTC 90d change missing")

    # ۵۰ ارز برتر به‌جز بیت‌کوین، استیبل‌کوین‌ها و توکن‌های پوشش‌داده‌شده
    eligible = []
    for c in coins:
        sym = (c.get("symbol") or "").upper()
        if sym == "BTC":
            continue
        tags = {str(t).lower() for t in (c.get("tags") or [])}
        if tags & _EXCLUDE_TAGS:
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
    return {"source": "live", "altcoin_season": {
        "value": value, "label_en": label_en, "label_fa": label_fa}}


async def altseason() -> dict[str, Any]:
    from app.cache import cached
    return await cached("cmc:altseason", settings.cmc_altseason_ttl, get_altseason,
                        mock_data.cmc_altseason)


def _f(d: dict, *keys: str) -> float:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                continue
    return 0.0
