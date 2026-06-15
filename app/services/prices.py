"""
کمک‌سرویس قیمت — نگاشت نماد ⇒ قیمت دلاری از دادهٔ کش‌شدهٔ CryptoRank،
به‌علاوهٔ نرخ تتر/تومان برای نمایش معادل تومانی.
"""
from __future__ import annotations

from typing import Any

from app.services import cryptorank, icons, tabdeal


async def price_map() -> dict[str, dict[str, Any]]:
    """{ "BTC": {"price":..., "change_24h":..., "name":..., "icon":...}, ... }"""
    macro = await cryptorank.macro()
    out: dict[str, dict[str, Any]] = {}
    for c in macro.get("heatmap", []):
        sym = (c.get("symbol") or "").upper()
        if sym:
            out[sym] = {
                "price": c.get("price", 0.0),
                "change_24h": c.get("change_24h", 0.0),
                "name": c.get("name", sym),
                "icon": c.get("icon") or icons.coin_icon(sym),
            }
    # تتر همیشه ~۱ دلار
    out.setdefault("USDT", {"price": 1.0, "change_24h": 0.0, "name": "Tether", "icon": icons.coin_icon("USDT")})
    return out


async def usdt_toman() -> float:
    """نرخ هر دلار تتر به تومان (برای معادل تومانی پورتفولیو)."""
    try:
        d = await tabdeal.usdt()
        return float(d["usdt_irt"]["price"]) or 0.0
    except Exception:  # noqa: BLE001
        return 0.0
