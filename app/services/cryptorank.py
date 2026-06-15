"""
سرویس CryptoRank — داده‌های کلان بازار و هیت‌مپ دسته‌بندی‌شده.

* مصرف کردیت با CreditBudget کنترل می‌شود (سقف ماهانهٔ ۱۰٬۰۰۰).
* داده با TTL ۱۰ دقیقه میان همهٔ کاربران به‌اشتراک گذاشته می‌شود.
* پارس فیلدها مقاوم است: هر فیلد چند نام محتمل دارد و در نبود، صفر می‌شود.
* probe() برای عیب‌یابی روی سرور: خام + پارس‌شده + خطا را برمی‌گرداند.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.cache import cache, credit_budget
from app.config import settings
from app.services import icons, mock_data

_KEY = "cryptorank:macro"

# نگاشت نماد ⇒ دستهٔ هیت‌مپ (مطابق نمای CryptoRank)
_CATEGORY = {
    "BTC": "Currency", "XRP": "Currency", "LTC": "Currency", "BCH": "Currency",
    "XLM": "Currency", "ZEC": "Currency", "XMR": "Currency",
    "ETH": "Blockchain", "BNB": "Blockchain", "SOL": "Blockchain", "ADA": "Blockchain",
    "TRX": "Blockchain", "AVAX": "Blockchain", "DOT": "Blockchain", "NEAR": "Blockchain",
    "TON": "Blockchain", "APT": "Blockchain", "SUI": "Blockchain", "ICP": "Blockchain",
    "USDT": "Stablecoin", "USDC": "Stablecoin", "DAI": "Stablecoin", "FDUSD": "Stablecoin",
    "USDE": "Stablecoin", "TUSD": "Stablecoin",
    "DOGE": "Meme", "SHIB": "Meme", "PEPE": "Meme", "WIF": "Meme", "BONK": "Meme", "FLOKI": "Meme",
    "UNI": "DeFi", "LINK": "DeFi", "AAVE": "DeFi", "HYPE": "DeFi", "MKR": "DeFi", "LDO": "DeFi",
    "BNB_CEX": "CeFi", "OKB": "CeFi", "CRO": "CeFi", "LEO": "CeFi", "WBT": "CeFi", "BGB": "CeFi", "KCS": "CeFi",
}


def _headers() -> dict[str, str]:
    return {"X-Api-Key": settings.cryptorank_api_key, "Accept": "application/json"}


def _num(d: Any, *keys: str) -> float:
    """استخراج عدد از dict با چند نام محتمل (سطحی یا تو در تو data/values.USD)."""
    if isinstance(d, dict):
        for k in keys:
            if k in d and d[k] is not None:
                try:
                    return float(d[k])
                except (TypeError, ValueError):
                    pass
    return 0.0


def _vals(c: dict) -> dict:
    v = c.get("values") or {}
    if isinstance(v, dict):
        return v.get("USD") or v.get("usd") or {}
    return {}


def _price(c: dict) -> float:
    return _num(c, "price") or _num(_vals(c), "price")


def _mc(c: dict) -> float:
    return _num(c, "marketCap", "market_cap") or _num(_vals(c), "marketCap", "market_cap")


def _vol(c: dict) -> float:
    return _num(c, "volume24h", "volume_24h") or _num(_vals(c), "volume24h", "volume24hUsd")


def _chg(c: dict) -> float:
    pc = c.get("percentChange") or c.get("percent_change") or {}
    if isinstance(pc, dict):
        v = _num(pc, "h24", "24h", "day")
        if v:
            return v
    return _num(c, "percentChange24h", "percentChangeH24", "change24h", "percent_change_24h")


def _category(c: dict) -> str:
    sym = (c.get("symbol") or "").upper()
    if sym in _CATEGORY:
        return _CATEGORY[sym]
    cat = c.get("category") or c.get("type") or ""
    if isinstance(cat, str) and cat:
        low = cat.lower()
        if "stable" in low:
            return "Stablecoin"
        if "meme" in low:
            return "Meme"
        if "defi" in low:
            return "DeFi"
    return "Currency"


async def _get_global(client: httpx.AsyncClient) -> dict:
    cost = settings.cryptorank_cost_global
    if not credit_budget.can_spend(cost):
        raise RuntimeError("CryptoRank credit budget exhausted (global)")
    r = await client.get(f"{settings.cryptorank_base_url}/global", headers=_headers())
    r.raise_for_status()
    credit_budget.spend(cost)
    j = r.json()
    return j.get("data", j) if isinstance(j, dict) else {}


async def _get_currencies(client: httpx.AsyncClient, limit: int = 40) -> list[dict]:
    cost = settings.cryptorank_cost_currencies
    if not credit_budget.can_spend(cost):
        raise RuntimeError("CryptoRank credit budget exhausted (currencies)")
    r = await client.get(
        f"{settings.cryptorank_base_url}/currencies",
        headers=_headers(),
        params={"limit": limit},
    )
    r.raise_for_status()
    credit_budget.spend(cost)
    j = r.json()
    data = j.get("data", j) if isinstance(j, dict) else j
    return data if isinstance(data, list) else []


async def get_macro() -> dict[str, Any]:
    if not settings.cryptorank_api_key:
        return mock_data.macro()

    async with httpx.AsyncClient(timeout=httpx.Timeout(settings.http_timeout)) as client:
        g = await _get_global(client)
        coins = await _get_currencies(client, limit=40)

    total_mc = _num(g, "totalMarketCap", "total_market_cap", "marketCap")
    total_vol = _num(g, "totalVolume24h", "total_volume_24h", "volume24h")
    btc_dom = _num(g, "btcDominance", "btc_dominance")
    eth_dom = _num(g, "ethDominance", "eth_dominance")

    by_sym = {(c.get("symbol") or "").upper(): c for c in coins}
    btc_mc = _mc(by_sym.get("BTC", {}))
    eth_mc = _mc(by_sym.get("ETH", {}))
    usdt_mc = _mc(by_sym.get("USDT", {}))

    stats = {
        "total_market_cap": {"value": total_mc, "change_24h": _num(g, "totalMarketCapChange24h", "marketCapChange24h")},
        "total_volume_24h": {"value": total_vol, "change_24h": _num(g, "totalVolumeChange24h", "volumeChange24h")},
        "btc_dominance": {"value": btc_dom, "change_24h": _num(g, "btcDominanceChange24h")},
        "eth_dominance": {"value": eth_dom, "change_24h": _num(g, "ethDominanceChange24h")},
        "eth_market_cap": {"value": eth_mc, "change_24h": _chg(by_sym.get("ETH", {}))},
        "alt_market_cap": {"value": max(total_mc - btc_mc, 0), "change_24h": 0.0},
        "usdt_dominance": {"value": (usdt_mc / total_mc * 100) if total_mc else 0.0, "change_24h": 0.0},
    }

    heatmap = []
    for c in coins:
        sym = (c.get("symbol") or "").upper()
        if not sym:
            continue
        heatmap.append({
            "symbol": sym,
            "name": c.get("name") or sym,
            "category": _category(c),
            "price": _price(c),
            "change_24h": round(_chg(c), 2),
            "market_cap": _mc(c),
            "icon": icons.coin_icon(sym),
        })

    fng = cache.get_stale("fng") or mock_data.macro()["fear_greed"]
    return {"source": "live", "stats": stats, "fear_greed": fng, "heatmap": heatmap}


async def macro() -> dict[str, Any]:
    hit = cache.get(_KEY)
    if hit is not None:
        return hit
    try:
        value = await get_macro()
        cache.set(_KEY, value, settings.cryptorank_ttl)
        return value
    except Exception:
        return cache.get_stale(_KEY) or mock_data.macro()


async def probe() -> dict[str, Any]:
    """عیب‌یابی: خروجی خام و پارس‌شده + خطا."""
    out: dict[str, Any] = {"key_set": bool(settings.cryptorank_api_key), "credits": credit_budget.usage()}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.http_timeout)) as client:
            rg = await client.get(f"{settings.cryptorank_base_url}/global", headers=_headers())
            out["global"] = {"url": str(rg.url), "status": rg.status_code, "raw": _trim(rg.text)}
            rc = await client.get(f"{settings.cryptorank_base_url}/currencies", headers=_headers(), params={"limit": 3})
            out["currencies"] = {"url": str(rc.url), "status": rc.status_code, "raw": _trim(rc.text)}
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def _trim(s: str, n: int = 1500) -> str:
    return s if len(s) <= n else s[:n] + " …[truncated]"
