"""
سرویس Tabdeal — قیمت لحظه‌ای و درصد تغییر ۲۴ساعتهٔ تتر تومانی (USDT/IRT).

⚠️ مهم: قیمت بازگشتی همان «تومان» است و هیچ تبدیلی (تقسیم بر ۱۰ یا مشابه) روی آن
انجام نمی‌شود. عدد دقیقاً همان‌طور که از صرافی می‌آید نمایش داده می‌شود.

درصد تغییر ۲۴ساعته (مطابق مستند رسمی API تبدیل، بخش «بازار»):
اندپوینت عمقِ بازار (`/r/api/v1/depth`) خودش درصد تغییر ندارد، پس درصد تغییر به
ترتیبِ اولویت از منابعِ خودِ تبدیل گرفته می‌شود و اولین منبعِ موفق برنده است:

  ۱. تیکر ۲۴ساعتهٔ بایننس‌مانند (`ticker/24hr`) — فیلد `priceChangePercent`
     عیناً «درصد» است و هیچ ضریبی نمی‌خورد.
  ۲. کندل ساعتی (`klines`) — قیمت پایانیِ الان نسبت به کندلِ ۲۴ساعت پیش.
  ۳. دیتافیدِ نمودارِ تبدیل (`plots/.../history`) — سری زمانیِ ساعتی.
  ۴. تاریخچهٔ قیمتِ پایدارِ خودمان (`price_history`) — آخرین سنگر تا عدد هرگز
     روی صفر گیر نکند.

❌ هرگز درصد تغییر دلار آزاد (SourceArena) به‌عنوان درصد تغییر تتر جا زده نمی‌شود؛
آن عدد به بازار تبدیل ربطی ندارد و ریشهٔ نمایشِ اشتباهِ قبلی بود.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import settings
from app.services import mock_data, price_history

# نماد بازار تتر/تومان: بدون «_» برای APIهای بایننس‌مانند، با «_» برای دیتافید نمودار.
SYMBOL = "USDTIRT"
TABDEAL_SYMBOL = "USDT_IRT"

_WINDOW = 24 * 3600  # پنجرهٔ ۲۴ساعته

# مسیرهای محتمل (اولین پاسخِ معتبر برنده است؛ ۴۰۴ نادیده گرفته می‌شود).
_TICKER_PATHS = ("/r/api/v1/ticker/24hr", "/r/api/v1/ticker/24hr/", "/api/v1/ticker/24hr")
_KLINE_PATHS = ("/r/api/v1/klines", "/r/api/v1/klines/", "/api/v1/klines")
_PLOT_PATHS = ("/r/plots/api/v1/history", "/plots/api/v1/history")


def _num(x: Any) -> float:
    if x is None:
        return 0.0
    try:
        return float(str(x).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _first_num(d: dict, *keys: str) -> float:
    for k in keys:
        if k in d:
            v = _num(d[k])
            if v:
                return v
    return 0.0


def _secs(ts: float) -> float:
    """زمان را به ثانیه برمی‌گرداند (ورودی میلی‌ثانیه هم پذیرفته می‌شود)."""
    return ts / 1000.0 if ts > 1e11 else ts


def _series_change(points: list[tuple[float, float]], window: int = _WINDOW) -> float:
    """درصد تغییر آخرین قیمت نسبت به نزدیک‌ترین نمونهٔ حدوداً `window` ثانیه پیش."""
    pts = sorted([(t, p) for t, p in points if t > 0 and p > 0], key=lambda x: x[0])
    if len(pts) < 2:
        return 0.0
    now, last = pts[-1]
    older = [p for t, p in pts if t <= now - window]
    ref = older[-1] if older else pts[0][1]
    if ref <= 0:
        return 0.0
    return round((last - ref) / ref * 100, 2)


async def _depth(client: httpx.AsyncClient) -> tuple[float, float, float]:
    """میانگینِ بهترین خرید/فروش از عمقِ بازار (تومان) → (mid, bid, ask)."""
    resp = await client.get(f"{settings.tabdeal_base_url}/r/api/v1/depth/",
                            params={"symbol": SYMBOL, "limit": "5"})
    resp.raise_for_status()
    data = resp.json()

    bids = data.get("bids") or []
    asks = data.get("asks") or []
    best_bid = _num(bids[0][0]) if bids else 0.0
    best_ask = _num(asks[0][0]) if asks else 0.0
    mid = (best_bid + best_ask) / 2 if (best_bid and best_ask) else (best_bid or best_ask)
    if not mid:
        raise RuntimeError("Tabdeal depth empty")
    return mid, best_bid, best_ask


async def _ticker_change(client: httpx.AsyncClient) -> float:
    """درصد تغییر ۲۴ساعته از تیکرِ بایننس‌مانندِ تبدیل (اگر در دسترس باشد)."""
    for path in _TICKER_PATHS:
        try:
            resp = await client.get(f"{settings.tabdeal_base_url}{path}",
                                    params={"symbol": SYMBOL})
            if resp.status_code != 200:
                continue
            data = resp.json()
        except Exception:  # noqa: BLE001
            continue

        rows = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
        for row in rows:
            if not isinstance(row, dict):
                continue
            sym = str(row.get("symbol") or row.get("s") or SYMBOL).upper().replace("_", "")
            if sym and sym != SYMBOL:
                continue
            # این فیلد در APIهای بایننس‌مانند «درصد» است؛ هیچ ضریبی نمی‌خورد.
            pct = _first_num(row, "priceChangePercent", "priceChangePercentage", "P")
            if pct:
                return round(pct, 2)
            last = _first_num(row, "lastPrice", "close", "c")
            opened = _first_num(row, "openPrice", "open", "o")
            if last > 0 and opened > 0:
                return round((last - opened) / opened * 100, 2)
            chg = _first_num(row, "priceChange", "p")
            if last > 0 and chg and (last - chg) > 0:
                return round(chg / (last - chg) * 100, 2)
    return 0.0


async def _kline_change(client: httpx.AsyncClient) -> float:
    """درصد تغییر ۲۴ساعته از کندل‌های ساعتیِ تبدیل."""
    params = {"symbol": SYMBOL, "interval": "1h", "limit": "48"}
    for path in _KLINE_PATHS:
        try:
            resp = await client.get(f"{settings.tabdeal_base_url}{path}", params=params)
            if resp.status_code != 200:
                continue
            data = resp.json()
        except Exception:  # noqa: BLE001
            continue

        rows = data if isinstance(data, list) else (
            data.get("data") if isinstance(data, dict) else None)
        pts: list[tuple[float, float]] = []
        for k in rows or []:
            if isinstance(k, list) and len(k) >= 5:
                pts.append((_secs(_num(k[0])), _num(k[4])))    # [t, o, h, l, c, ...]
            elif isinstance(k, dict):
                pts.append((_secs(_first_num(k, "t", "openTime", "time")),
                            _first_num(k, "c", "close")))
        ch = _series_change(pts)
        if ch:
            return ch
    return 0.0


async def _plot_change(client: httpx.AsyncClient) -> float:
    """درصد تغییر ۲۴ساعته از دیتافیدِ نمودارِ تبدیل (سری زمانیِ ساعتی)."""
    now = int(time.time())
    params = {"symbol": TABDEAL_SYMBOL, "resolution": "60",
              "from": str(now - 30 * 3600), "to": str(now)}
    for path in _PLOT_PATHS:
        try:
            resp = await client.get(f"{settings.tabdeal_base_url}{path}", params=params)
            if resp.status_code != 200:
                continue
            data = resp.json()
        except Exception:  # noqa: BLE001
            continue

        if not isinstance(data, dict):
            continue
        times = data.get("t") or []
        closes = data.get("c") or []
        pts = [(_secs(_num(t)), _num(c)) for t, c in zip(times, closes)]
        ch = _series_change(pts)
        if ch:
            return ch
    return 0.0


async def _change_24h(client: httpx.AsyncClient) -> tuple[float, str]:
    """درصد تغییر ۲۴ساعته از خودِ تبدیل؛ به ترتیبِ اولویتِ منابع."""
    for name, fn in (("ticker24", _ticker_change),
                     ("klines", _kline_change),
                     ("plots", _plot_change)):
        try:
            ch = await fn(client)
        except Exception:  # noqa: BLE001
            ch = 0.0
        if ch:
            return ch, name
    return 0.0, ""


async def get_usdt() -> dict[str, Any]:
    timeout = httpx.Timeout(settings.http_timeout)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        mid, best_bid, best_ask = await _depth(client)
        change, source = await _change_24h(client)

    # قیمت همیشه ثبت می‌شود تا پشتیبانِ محاسبهٔ داخلی همیشه آماده باشد.
    own = price_history.record_and_change("usdt_irt", mid)
    if not change:
        change, source = own, "history"

    # بدون هیچ تبدیلی — همان تومان.
    return {
        "source": "live",
        "usdt_irt": {
            "name": "تتر / تومان",
            "price": round(mid),
            "change_24h": round(change, 2),
            "bid": round(best_bid),
            "ask": round(best_ask),
            "change_source": source or "none",
        },
    }


async def usdt() -> dict[str, Any]:
    from app.cache import cached
    return await cached("tabdeal:usdt", settings.tabdeal_ttl, get_usdt, mock_data.tabdeal_usdt)
