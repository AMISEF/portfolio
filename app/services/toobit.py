"""
سرویس Toobit — قیمت لحظه‌ای ارزهای برتر بازار (مارکت‌کپ بالا).

طبق درخواست، باکس ارزها ارزهای اصلی بازار (BTC، ETH، XRP، SOL، BNB) را با
قیمت لحظه‌ای، تغییر ۲۴ساعته و حجم دلاری نمایش می‌دهد. آیکون هر ارز در فرانت‌اند
از روی نماد ساخته می‌شود.

نگاشت فیلدهای تیکر ۲۴ساعتهٔ توبیت (تأییدشده از پاسخ زنده):
  s = نماد، c = آخرین قیمت، pcp = درصد تغییر (کسری، در ۱۰۰ ضرب می‌شود)،
  pc = تغییر مطلق، qv = حجم دلاری ۲۴ساعته.
اندپوینت عمومی است؛ کلیدها برای فاز بعد (همگام‌سازی پورتفولیو، فقط‌خواندنی) می‌مانند.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.services import mock_data

# ارزهای اصلی بازار به ترتیب نمایش (نماد بدون USDT)
TOP_SYMBOLS = ["BTC", "ETH", "XRP", "SOL", "BNB"]


async def get_top_coins() -> dict[str, Any]:
    timeout = httpx.Timeout(settings.http_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(f"{settings.toobit_base_url}/quote/v1/ticker/24hr")
        resp.raise_for_status()
        data = resp.json()

    tickers = data if isinstance(data, list) else []
    by_sym: dict[str, dict] = {}
    for t in tickers:
        s = (t.get("s") or t.get("symbol") or "").upper()
        if s:
            by_sym[s] = t

    rows = []
    for sym in TOP_SYMBOLS:
        t = by_sym.get(sym + "USDT")
        if not t:
            continue
        rows.append({
            "symbol": sym,
            "pair": sym + "USDT",
            "price": _f(t, "c", "lastPrice", "close"),
            "change_24h": round(_pct(t), 2),
            "volume_24h": _f(t, "qv", "quoteVolume", "q", "volume"),
        })

    if not rows:
        raise RuntimeError("Toobit returned no usable tickers for top coins")
    return {"source": "live", "coins": rows}


async def top_coins() -> dict[str, Any]:
    from app.cache import cached
    return await cached("toobit:top_coins", settings.toobit_ttl, get_top_coins, mock_data.toobit_top_coins)


def _pct(t: dict) -> float:
    """درصد تغییر ۲۴ساعته. pcp کسری است (مثلاً -0.0183 ⇒ -1.83٪)."""
    v = _f(t, "pcp", "priceChangePercent", "P", "changeRate")
    # اگر مقدار کسری باشد (|v|<1) آن را به درصد تبدیل کن
    return v * 100 if abs(v) < 1 else v


def _f(d: dict, *keys: str) -> float:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                continue
    return 0.0
