"""
سرویس Toobit — تاپ گینرهای اسپات (۵ ارز با بیشترین رشد ۲۴ساعته).

از تیکر ۲۴ساعتهٔ عمومی، جفت‌های USDT را بر اساس درصد رشد مرتب کرده و موارد
برتر را با قیمت، رشد و حجم دلاری برمی‌گرداند. آیکون ارز در فرانت‌اند از روی
نماد ساخته می‌شود. اندپوینت عمومی احراز هویت نمی‌خواهد؛ کلیدها برای فاز بعد
(همگام‌سازی پورتفولیو، فقط‌خواندنی) نگه داشته می‌شوند.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.services import mock_data


async def get_gainers() -> dict[str, Any]:
    timeout = httpx.Timeout(settings.http_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(f"{settings.toobit_base_url}/quote/v1/ticker/24hr")
        resp.raise_for_status()
        data = resp.json()

    tickers = data if isinstance(data, list) else []
    rows = []
    for t in tickers:
        sym = (t.get("s") or t.get("symbol") or "")
        if not sym.endswith("USDT"):
            continue
        change = _f(t, "priceChangePercent", "P", "changeRate")
        if abs(change) < 1:  # برخی APIها نرخ را کسری می‌دهند
            change *= 100
        price = _f(t, "lastPrice", "c", "close")
        if price <= 0:
            continue
        rows.append({
            "symbol": sym[:-4],
            "pair": sym,
            "price": price,
            "change_24h": round(change, 2),
            "volume_24h": _f(t, "quoteVolume", "qv", "q", "volume"),
        })

    rows.sort(key=lambda r: r["change_24h"], reverse=True)
    top = rows[: settings.toobit_gainers_count]
    if not top:
        raise RuntimeError("Toobit returned no usable tickers")
    return {"source": "live", "gainers": top}


async def gainers() -> dict[str, Any]:
    from app.cache import cached
    return await cached("toobit:gainers", settings.toobit_ttl, get_gainers, mock_data.toobit_gainers)


def _f(d: dict, *keys: str) -> float:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                continue
    return 0.0
