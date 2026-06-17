"""
سرویس Toobit — تاپ گینرهای اسپات + قیمت فیوچرز فلزات/نفت.

* تاپ گینرها: از تیکر ۲۴ ساعتهٔ اسپات، جفت‌های USDT را بر اساس درصد رشد
  مرتب کرده و ۵ مورد برتر را برمی‌گرداند (قیمت، رشد ۲۴ ساعته، حجم دلاری).
* فیوچرز: قیمت XAUUSDT، XAGUSDT، OILBRENTUSDT.

اندپوینت‌های عمومی توبیت احراز هویت نمی‌خواهند؛ کلیدها برای فاز بعد (همگام‌سازی
پورتفولیو Read-Only) نگه داشته می‌شوند.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.services import mock_data

_FUTURES_NAMES = {
    "XAUUSDT": "طلای جهانی (اونس)",
    "XAGUSDT": "نقره (اونس)",
    "OILBRENTUSDT": "نفت برنت",
}


async def get_gainers() -> dict[str, Any]:
    timeout = httpx.Timeout(settings.http_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(f"{settings.toobit_base_url}/quote/v1/ticker/24hr")
        resp.raise_for_status()
        tickers = resp.json()

    rows = []
    for t in tickers if isinstance(tickers, list) else []:
        sym = t.get("s") or t.get("symbol") or ""
        if not sym.endswith("USDT"):
            continue
        change = _f(t, "priceChangePercent", "P", "changeRate")
        # برخی APIها نرخ را به‌صورت کسری (0.76) می‌دهند؛ به درصد تبدیل کن
        if abs(change) < 1:
            change *= 100
        rows.append(
            {
                "symbol": sym.replace("USDT", ""),
                "pair": sym,
                "price": _f(t, "lastPrice", "c", "close"),
                "change_24h": round(change, 2),
                "volume_24h": _f(t, "quoteVolume", "qv", "q", "volume"),
            }
        )

    rows.sort(key=lambda r: r["change_24h"], reverse=True)
    top = rows[: settings.toobit_gainers_count]
    if not top:
        raise RuntimeError("Toobit returned no usable tickers")
    return {"source": "live", "gainers": top}


async def get_futures() -> dict[str, Any]:
    timeout = httpx.Timeout(settings.http_timeout)
    out: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(f"{settings.toobit_base_url}/quote/v1/ticker/24hr")
        resp.raise_for_status()
        data = resp.json()
        tickers = {_sym(t): t for t in (data if isinstance(data, list) else [])}

    for sym, fa in _FUTURES_NAMES.items():
        t = tickers.get(sym)
        if not t:
            continue
        change = _f(t, "priceChangePercent", "P", "changeRate")
        if abs(change) < 1:
            change *= 100
        out[sym] = {"name": fa, "price": _f(t, "lastPrice", "c"), "change_24h": round(change, 2)}

    if not out:
        raise RuntimeError("Toobit futures symbols not found")
    return {"source": "live", "futures": out}


async def gainers() -> dict[str, Any]:
    from app.cache import cached
    return await cached("toobit:gainers", settings.toobit_ttl, get_gainers, mock_data.toobit_gainers)


async def futures() -> dict[str, Any]:
    from app.cache import cached
    return await cached("toobit:futures", settings.toobit_ttl, get_futures, mock_data.toobit_futures)


def _sym(t: dict) -> str:
    return (t.get("s") or t.get("symbol") or "").upper()


def _f(d: dict, *keys: str) -> float:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                continue
    return 0.0
