"""
سرویس CryptoRank — داده‌های کلان بازار و هیت‌مپ.

نکات مهم:
* مصرف کردیت با CreditBudget کنترل می‌شود تا از سقف ماهانهٔ ۱۰٬۰۰۰ عبور نکند.
* داده با TTL ۱۰ دقیقه میان همهٔ کاربران به‌اشتراک گذاشته می‌شود (کش سمت سرور)
  تا فرانت‌اند هرگز مستقیم به API وصل نشود و کردیت اضافه مصرف نکند.
* در هر خطا یا اتمام بودجه، دادهٔ کش کهنه یا نمونه برگردانده می‌شود.

ساختار دقیق پاسخ‌های v2 ممکن است نیاز به تنظیم جزئی نگاشت فیلدها داشته باشد؛
کد طوری نوشته شده که در صورت تغییر شکل، به‌جای خطا به نمونه برگردد.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.cache import cache, credit_budget
from app.config import settings
from app.services import mock_data

_KEY = "cryptorank:macro"


def _headers() -> dict[str, str]:
    return {"X-Api-Key": settings.cryptorank_api_key, "Accept": "application/json"}


async def _fetch_global(client: httpx.AsyncClient) -> dict[str, Any]:
    cost = settings.cryptorank_cost_global
    if not credit_budget.can_spend(cost):
        raise RuntimeError("CryptoRank credit budget exhausted (global)")
    resp = await client.get(f"{settings.cryptorank_base_url}/global", headers=_headers())
    resp.raise_for_status()
    credit_budget.spend(cost)
    return resp.json().get("data", resp.json())


async def _fetch_currencies(client: httpx.AsyncClient, limit: int = 30) -> list[dict[str, Any]]:
    cost = settings.cryptorank_cost_currencies
    if not credit_budget.can_spend(cost):
        raise RuntimeError("CryptoRank credit budget exhausted (currencies)")
    resp = await client.get(
        f"{settings.cryptorank_base_url}/currencies",
        headers=_headers(),
        params={"limit": limit},
    )
    resp.raise_for_status()
    credit_budget.spend(cost)
    payload = resp.json()
    return payload.get("data", payload) if isinstance(payload, dict) else payload


def _category_of(coin: dict[str, Any]) -> str:
    """نگاشت تقریبی هر ارز به دستهٔ هیت‌مپ."""
    cats = coin.get("category") or coin.get("type") or ""
    name = (coin.get("symbol") or "").upper()
    if name in {"USDT", "USDC", "DAI", "FDUSD", "TUSD"}:
        return "Stablecoin"
    if name in {"DOGE", "SHIB", "PEPE", "WIF", "BONK"}:
        return "Meme"
    if isinstance(cats, str) and cats:
        return cats
    return "Currency"


async def get_macro() -> dict[str, Any]:
    """دادهٔ کلان نرمال‌شده برای فرانت‌اند."""
    if not settings.cryptorank_api_key:
        return mock_data.macro()

    timeout = httpx.Timeout(settings.http_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        g = await _fetch_global(client)
        coins = await _fetch_currencies(client, limit=30)

    total_mc = _num(g, "totalMarketCap", "total_market_cap")
    eth_mc = next((_coin_mc(c) for c in coins if (c.get("symbol") or "").upper() == "ETH"), 0)

    stats = {
        "total_market_cap": {"value": total_mc, "change_24h": _num(g, "totalMarketCapChange24h", "marketCapChange24h")},
        "total_volume_24h": {"value": _num(g, "totalVolume24h", "total_volume_24h"), "change_24h": _num(g, "volumeChange24h")},
        "btc_dominance": {"value": _num(g, "btcDominance", "btc_dominance"), "change_24h": _num(g, "btcDominanceChange24h")},
        "eth_dominance": {"value": _num(g, "ethDominance", "eth_dominance"), "change_24h": _num(g, "ethDominanceChange24h")},
        "eth_market_cap": {"value": eth_mc, "change_24h": 0.0},
        "alt_market_cap": {"value": max(total_mc - _btc_mc(coins), 0), "change_24h": 0.0},
        "usdt_dominance": {"value": _num(g, "usdtDominance", "usdt_dominance"), "change_24h": 0.0},
    }

    heatmap = [
        {
            "symbol": (c.get("symbol") or "").upper(),
            "name": c.get("name") or c.get("symbol"),
            "category": _category_of(c),
            "price": _coin_price(c),
            "change_24h": _coin_change(c),
            "market_cap": _coin_mc(c),
        }
        for c in coins
    ]

    return {"source": "live", "stats": stats, "fear_greed": cache.get_stale("fng") or mock_data.macro()["fear_greed"], "heatmap": heatmap}


async def macro() -> dict[str, Any]:
    """نقطهٔ ورود با کش. در صورت خطا، کش کهنه یا نمونه."""
    hit = cache.get(_KEY)
    if hit is not None:
        return hit
    try:
        value = await get_macro()
        cache.set(_KEY, value, settings.cryptorank_ttl)
        return value
    except Exception:
        return cache.get_stale(_KEY) or mock_data.macro()


# ---- کمک‌تابع‌های استخراج امن فیلدها ----
def _num(d: dict, *keys: str) -> float:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                continue
        # شکل تو در تو: data.values.USD
    return 0.0


def _coin_values(c: dict) -> dict:
    v = c.get("values") or {}
    return v.get("USD") or v.get("usd") or c


def _coin_price(c: dict) -> float:
    return _num(_coin_values(c), "price", "lastPrice") or _num(c, "price")


def _coin_change(c: dict) -> float:
    v = _coin_values(c)
    return _num(v, "percentChange24h", "change24h") or _num(c, "percentChange24h", "change24h")


def _coin_mc(c: dict) -> float:
    return _num(_coin_values(c), "marketCap", "market_cap") or _num(c, "marketCap", "market_cap")


def _btc_mc(coins: list[dict]) -> float:
    return next((_coin_mc(c) for c in coins if (c.get("symbol") or "").upper() == "BTC"), 0.0)
