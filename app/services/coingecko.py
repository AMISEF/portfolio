"""
سرویس CoinGecko — شاخص‌های کلان بازار (بدون نیاز به کلید).

دامیننس و ارزش بازار CoinGecko با منابع رایجی که کاربران می‌بینند هم‌خوان است
(مثلاً دامیننس بیت‌کوین ~۵۸٪)، برخلاف محاسبهٔ متفاوت برخی منابع دیگر.
خروجی هر ۶۰ ثانیه کش می‌شود.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.services import mock_data


async def get_macro() -> dict[str, Any]:
    timeout = httpx.Timeout(settings.http_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(f"{settings.coingecko_base_url}/global")
        resp.raise_for_status()
        d = resp.json().get("data", {})

    total_mc = _num(d.get("total_market_cap", {}), "usd")
    total_vol = _num(d.get("total_volume", {}), "usd")
    mcp = d.get("market_cap_percentage", {})
    btc_dom = _f(mcp, "btc")
    eth_dom = _f(mcp, "eth")
    usdt_dom = _f(mcp, "usdt")
    mc_change = _f(d, "market_cap_change_percentage_24h_usd")

    btc_mc = total_mc * btc_dom / 100 if total_mc else 0.0
    eth_mc = total_mc * eth_dom / 100 if total_mc else 0.0

    stats = {
        "total_market_cap": {"value": total_mc, "change_24h": mc_change},
        "total_volume_24h": {"value": total_vol, "change_24h": 0.0},
        "btc_dominance": {"value": round(btc_dom, 2), "change_24h": 0.0},
        "eth_dominance": {"value": round(eth_dom, 2), "change_24h": 0.0},
        "eth_market_cap": {"value": eth_mc, "change_24h": 0.0},
        "alt_market_cap": {"value": max(total_mc - btc_mc, 0.0), "change_24h": 0.0},
        "usdt_dominance": {"value": round(usdt_dom, 2), "change_24h": 0.0},
    }
    if total_mc <= 0:
        raise RuntimeError("CoinGecko: empty global data")
    return {"source": "live", "stats": stats}


async def macro() -> dict[str, Any]:
    from app.cache import cached
    return await cached("coingecko:macro", settings.coingecko_ttl, get_macro,
                        lambda: {"source": "sample", "stats": mock_data.macro()["stats"]})


def _num(d: dict, *keys: str) -> float:
    return _f(d, *keys)


def _f(d: dict, *keys: str) -> float:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                continue
    return 0.0
