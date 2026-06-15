"""
سرویس Toobit — تاپ گینرهای اسپات + قیمت فیوچرز فلزات/نفت.

نکات پارس مقاوم:
* درصد تغییر ۲۴ساعته اگر فیلد مستقیم نبود، از روی قیمت باز (o) و بسته (c)
  محاسبه می‌شود: (c-o)/o*100 — قابل‌اعتمادتر از حدس نام فیلد.
* برای فیوچرز چند اندپوینت محتمل امتحان می‌شود تا قرارداد پیدا شود.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.services import icons, mock_data

_FUTURES_NAMES = {
    "XAUUSDT": "طلای جهانی (اونس)",
    "XAGUSDT": "نقره (اونس)",
    "OILBRENTUSDT": "نفت برنت",
}


def _f(d: dict, *keys: str) -> float:
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                pass
    return 0.0


def _sym(t: dict) -> str:
    return (t.get("s") or t.get("symbol") or "").upper()


def _last(t: dict) -> float:
    return _f(t, "c", "lastPrice", "close", "last", "p")


def _open(t: dict) -> float:
    return _f(t, "o", "openPrice", "open")


def _change_pct(t: dict) -> float:
    """درصد تغییر؛ از فیلد مستقیم یا محاسبه از open/close."""
    direct = _f(t, "priceChangePercent", "P", "pcp", "changeRate", "rose")
    if direct:
        # برخی APIها نرخ کسری می‌دهند (0.76 یعنی ۷۶٪)
        return direct * 100 if abs(direct) < 1 else direct
    o, c = _open(t), _last(t)
    if o > 0 and c > 0:
        return (c - o) / o * 100
    return 0.0


def _quote_vol(t: dict) -> float:
    return _f(t, "qv", "quoteVolume", "q", "v", "volume", "amount")


async def _fetch_tickers(client: httpx.AsyncClient, base: str) -> list[dict]:
    r = await client.get(f"{base}/quote/v1/ticker/24hr")
    r.raise_for_status()
    j = r.json()
    if isinstance(j, dict):
        j = j.get("data") or j.get("result") or []
    return j if isinstance(j, list) else []


async def get_gainers() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=httpx.Timeout(settings.http_timeout)) as client:
        tickers = await _fetch_tickers(client, settings.toobit_base_url)

    rows = []
    for t in tickers:
        sym = _sym(t)
        if not sym.endswith("USDT"):
            continue
        price = _last(t)
        if price <= 0:
            continue
        base = sym[:-4]  # حذف USDT
        rows.append({
            "symbol": base,
            "pair": sym,
            "price": price,
            "change_24h": round(_change_pct(t), 2),
            "volume_24h": _quote_vol(t),
            "icon": icons.coin_icon(base),
        })

    rows.sort(key=lambda r: r["change_24h"], reverse=True)
    top = rows[: settings.toobit_gainers_count]
    if not top:
        raise RuntimeError("Toobit returned no usable USDT tickers")
    return {"source": "live", "gainers": top}


async def get_futures() -> dict[str, Any]:
    symbols = [s.strip().upper() for s in settings.toobit_futures_symbols.split(",") if s.strip()]
    out: dict[str, Any] = {}

    # چند مسیر محتمل برای دادهٔ فیوچرز
    candidates = [
        f"{settings.toobit_futures_base_url}/api/v1/futures/ticker/24hr",
        f"{settings.toobit_futures_base_url}/quote/v1/contract/ticker/24hr",
        f"{settings.toobit_futures_base_url}/quote/v1/ticker/24hr",
    ]
    async with httpx.AsyncClient(timeout=httpx.Timeout(settings.http_timeout)) as client:
        tickers: list[dict] = []
        for url in candidates:
            try:
                r = await client.get(url)
                if r.status_code != 200:
                    continue
                j = r.json()
                if isinstance(j, dict):
                    j = j.get("data") or j.get("result") or []
                if isinstance(j, list) and j:
                    tickers = j
                    break
            except Exception:  # noqa: BLE001
                continue

        index = {_sym(t): t for t in tickers}
        for sym in symbols:
            t = index.get(sym)
            if not t:
                # تلاش تک‌نمادی
                try:
                    r = await client.get(f"{settings.toobit_futures_base_url}/quote/v1/ticker/24hr", params={"symbol": sym})
                    jj = r.json()
                    if isinstance(jj, list) and jj:
                        t = jj[0]
                    elif isinstance(jj, dict) and jj.get("s"):
                        t = jj
                except Exception:  # noqa: BLE001
                    t = None
            if t:
                out[sym] = {
                    "name": _FUTURES_NAMES.get(sym, sym),
                    "price": _last(t),
                    "change_24h": round(_change_pct(t), 2),
                }

    if not out:
        raise RuntimeError("Toobit futures symbols not found")
    return {"source": "live", "futures": out}


async def gainers() -> dict[str, Any]:
    from app.cache import cached
    return await cached("toobit:gainers", settings.toobit_ttl, get_gainers, mock_data.toobit_gainers)


async def futures() -> dict[str, Any]:
    from app.cache import cached
    return await cached("toobit:futures", settings.toobit_ttl, get_futures, mock_data.toobit_futures)


async def probe() -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.http_timeout)) as client:
            r = await client.get(f"{settings.toobit_base_url}/quote/v1/ticker/24hr")
            txt = r.text
            out["spot"] = {"url": str(r.url), "status": r.status_code, "raw": _trim(txt)}
    except Exception as e:  # noqa: BLE001
        out["spot_error"] = f"{type(e).__name__}: {e}"
    try:
        fut = await get_futures()
        out["futures_parsed"] = fut
    except Exception as e:  # noqa: BLE001
        out["futures_error"] = f"{type(e).__name__}: {e}"
    return out


def _trim(s: str, n: int = 1500) -> str:
    return s if len(s) <= n else s[:n] + " …[truncated]"
