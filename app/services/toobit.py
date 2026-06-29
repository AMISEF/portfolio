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

# ارزهای اصلی بازار به ترتیب نمایش (نماد بدون USDT) — مطابق CoinMarketCap
TOP_SYMBOLS = ["BTC", "ETH", "BNB", "SOL", "XRP"]


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
    return await cached("toobit:top_coins", settings.toobit_coins_ttl, get_top_coins, mock_data.toobit_top_coins)


async def get_price_map() -> dict[str, Any]:
    """نگاشت نماد ارز (بدون USDT) → قیمت دلاری زنده، برای ارزش‌گذاری پورتفولیو."""
    timeout = httpx.Timeout(settings.http_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(f"{settings.toobit_base_url}/quote/v1/ticker/24hr")
        resp.raise_for_status()
        data = resp.json()
    prices: dict[str, float] = {}
    for t in (data if isinstance(data, list) else []):
        sym = (t.get("s") or t.get("symbol") or "").upper()
        if sym.endswith("USDT"):
            p = _f(t, "c", "lastPrice", "close")
            if p > 0:
                prices[sym[:-4]] = p
    if not prices:
        raise RuntimeError("Toobit: empty price map")
    return {"source": "live", "prices": prices}


async def price_map() -> dict[str, Any]:
    from app.cache import cached
    return await cached("toobit:price_map", settings.toobit_coins_ttl, get_price_map,
                        lambda: {"source": "mock", "prices": {}})


# نمادهای محتمل نفت در توبیت (به ترتیب اولویت) + جست‌وجوی زیررشته‌ای
_OIL_SYMBOLS = ["OILUSDT", "OILBRENTUSDT", "USOILUSDT", "WTIUSDT", "BRENTUSDT", "UKOILUSDT", "USOUSDT", "CRUDEOILUSDT"]


def _find_oil(by_sym: dict) -> dict | None:
    for s in _OIL_SYMBOLS:
        if s in by_sym:
            return by_sym[s]
    # جست‌وجوی زیررشته‌ای: هر نماد دلاری که «OIL» یا «BRENT» یا «WTI» دارد
    for sym, t in by_sym.items():
        if sym.endswith("USDT") and ("OIL" in sym or "BRENT" in sym or "WTI" in sym):
            return t
    return None


async def get_oil() -> dict[str, Any]:
    timeout = httpx.Timeout(settings.http_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(f"{settings.toobit_base_url}/quote/v1/ticker/24hr")
        resp.raise_for_status()
        data = resp.json()

    by_sym = {(t.get("s") or t.get("symbol") or "").upper(): t for t in (data if isinstance(data, list) else [])}
    t = _find_oil(by_sym)
    if not t:
        raise RuntimeError("Toobit: no oil symbol found")
    return {
        "source": "live",
        "oil": {"name": "نفت خام", "sub": "بشکه", "price": _f(t, "c", "lastPrice"), "change_24h": round(_pct(t), 2)},
    }


async def oil() -> dict[str, Any]:
    from app.cache import cached
    return await cached("toobit:oil", settings.toobit_oil_ttl, get_oil, mock_data.toobit_oil)


# ---- کالاهای زندهٔ فیوچرز توبیت (USDT-M): انس طلا / نقره / نفت برنت ----
# نمادهای قرارداد دائمی (perpetual swap) — مطابق مستند رسمی فیوچرز توبیت.
# اندپوینت ویژهٔ فیوچرز: /quote/v1/contract/ticker/24hr (با /contract/) و نه تیکر اسپات.
_SWAP_MAP = [
    ("XAU-SWAP-USDT", "XAU", "انس طلا",    "اونس"),
    ("XAG-SWAP-USDT", "XAG", "نقره جهانی", "اونس"),
    ("XBR-SWAP-USDT", "OIL", "نفت برنت",   "بشکه"),
]


async def get_swap_commodities() -> dict[str, Any]:
    """قیمت و تغییر ۲۴ساعتهٔ انس طلا/نقره/نفت برنت از تیکر ۲۴ساعتهٔ *فیوچرز* توبیت.

    نمادها: XAU-SWAP-USDT، XAG-SWAP-USDT، XBR-SWAP-USDT (قرارداد دائمی USDT-M).
    اندپوینت قرارداد، فهرستی از تیکرها با همان فیلدهای اسپات برمی‌گرداند
    (s=نماد، c=قیمت، pcp=درصد تغییر کسری، pc=تغییر مطلق).
    """
    timeout = httpx.Timeout(settings.http_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(f"{settings.toobit_base_url}/quote/v1/contract/ticker/24hr")
        resp.raise_for_status()
        data = resp.json()

    # پاسخ ممکن است فهرست باشد یا (هنگام نماد منفرد) یک شیء؛ هر دو را پوشش بده.
    rows = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
    by_sym: dict[str, dict] = {}
    for t in rows:
        s = (t.get("s") or t.get("symbol") or "").upper()
        if s:
            by_sym[s] = t

    commodities: dict[str, Any] = {}
    for sym, key, name, sub in _SWAP_MAP:
        t = by_sym.get(sym)
        if not t:
            continue
        price = _f(t, "c", "lastPrice", "close")
        ch = round(_pct(t), 2)
        if price > 0:
            commodities[key] = {"name": name, "sub": sub, "price": price, "change_24h": ch}

    if not commodities:
        raise RuntimeError("Toobit futures: no commodity tickers (XAU/XAG/XBR-SWAP-USDT)")
    return {"source": "live", "commodities": commodities}


async def swap_commodities() -> dict[str, Any]:
    from app.cache import cached
    return await cached("toobit:swap_commodities", settings.toobit_swap_ttl,
                        get_swap_commodities, mock_data.toobit_swap_commodities)


# ---- نقشهٔ حرارتی زنده از توبیت ----
# دستهٔ هر نماد (انگلیسی). نمادهای ناشناخته در «Other».
_CATEGORY = {
    "BTC": "Currency", "XRP": "Currency", "XLM": "Currency", "XMR": "Currency", "BCH": "Currency", "LTC": "Currency",
    "ETH": "Smart Contract", "SOL": "Smart Contract", "BNB": "Smart Contract", "ADA": "Smart Contract",
    "TRX": "Smart Contract", "AVAX": "Smart Contract", "NEAR": "Smart Contract", "DOT": "Smart Contract",
    "SUI": "Smart Contract", "TON": "Smart Contract", "APT": "Smart Contract", "HBAR": "Smart Contract",
    "ALGO": "Smart Contract", "ICP": "Smart Contract", "ETC": "Smart Contract", "VET": "Smart Contract",
    "UNI": "DeFi", "AAVE": "DeFi", "LINK": "DeFi", "MKR": "DeFi", "LDO": "DeFi", "CRV": "DeFi",
    "HYPE": "DeFi", "ENA": "DeFi", "ATOM": "DeFi", "PENDLE": "DeFi", "JUP": "DeFi",
    "DOGE": "Meme", "SHIB": "Meme", "PEPE": "Meme", "WIF": "Meme", "BONK": "Meme", "FLOKI": "Meme",
    "TRUMP": "Meme", "MEW": "Meme", "POPCAT": "Meme", "BRETT": "Meme", "SPX": "Meme",
    "FARTCOIN": "Meme", "PNUT": "Meme", "MOG": "Meme", "TURBO": "Meme", "MEME": "Meme",
}

# استیبل‌کوین‌ها و توکن‌های دلاری که از نقشهٔ حرارتی کنار گذاشته می‌شوند.
_STABLES = {
    "USDT", "USDC", "DAI", "FDUSD", "USDE", "USDS", "TUSD", "USD1", "BUSD",
    "USDP", "GUSD", "PYUSD", "EURT", "EURS", "USDD", "FRAX", "LUSD", "USDF",
    "USDX", "USTC", "USD0", "USDG",
}


async def get_heatmap(limit: int = 40) -> dict[str, Any]:
    """نقشهٔ حرارتی زنده: پرحجم‌ترین جفت‌های USDT (بدون استیبل‌کوین) با قیمت و
    تغییر ۲۴ساعتهٔ لحظه‌ای."""
    timeout = httpx.Timeout(settings.http_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(f"{settings.toobit_base_url}/quote/v1/ticker/24hr")
        resp.raise_for_status()
        data = resp.json()

    rows = []
    for t in (data if isinstance(data, list) else []):
        sym = (t.get("s") or t.get("symbol") or "").upper()
        if not sym.endswith("USDT"):
            continue
        base = sym[:-4]
        # استیبل‌کوین‌ها نمایش داده نمی‌شوند (نوسان صفر، جای ارزهای دیگر را می‌گیرند)
        if base in _STABLES:
            continue
        price = _f(t, "c", "lastPrice")
        vol = _f(t, "qv", "quoteVolume", "q")
        if price <= 0 or vol <= 0:
            continue
        rows.append({
            "symbol": base,
            "name": base,
            "category": _CATEGORY.get(base, "Other"),
            "price": price,
            "change_24h": round(_pct(t), 2),
            "market_cap": vol,  # اندازهٔ کاشی بر اساس حجم ۲۴ساعته (توبیت ارزش بازار ندارد)
        })

    rows.sort(key=lambda r: r["market_cap"], reverse=True)
    top = rows[:limit]
    if not top:
        raise RuntimeError("Toobit heatmap: no usable tickers")
    return {"source": "live", "heatmap": top}


async def heatmap() -> dict[str, Any]:
    from app.cache import cached
    return await cached("toobit:heatmap", settings.toobit_heatmap_ttl, get_heatmap, mock_data.toobit_heatmap)


# ---- اسپارک‌لاین (شِماتیک قیمت) ۵ ارز برتر از کندل‌های توبیت ----
async def _closes(client: httpx.AsyncClient, sym: str, interval: str, limit: int) -> list[float]:
    r = await client.get(f"{settings.toobit_base_url}/quote/v1/klines",
                         params={"symbol": sym + "USDT", "interval": interval, "limit": str(limit)})
    r.raise_for_status()
    data = r.json()
    rows = data if isinstance(data, list) else (data.get("data") if isinstance(data, dict) else []) or []
    closes = []
    for k in rows:
        if isinstance(k, list) and len(k) >= 5:
            closes.append(float(k[4]))                      # [t,o,h,l,c,...]
        elif isinstance(k, dict):
            closes.append(float(k.get("c") or k.get("close") or 0))
    return [c for c in closes if c > 0]


async def get_sparklines() -> dict[str, Any]:
    timeout = httpx.Timeout(settings.http_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        import asyncio
        res = await asyncio.gather(*[_closes(client, s, "15m", 24) for s in TOP_SYMBOLS],
                                   return_exceptions=True)
    out = {}
    for s, r in zip(TOP_SYMBOLS, res):
        if isinstance(r, list) and len(r) >= 3:
            out[s] = [round(x, 6) for x in r]
    if not out:
        raise RuntimeError("Toobit: no kline data for sparklines")
    return {"source": "live", "sparklines": out}


async def sparklines() -> dict[str, Any]:
    from app.cache import cached
    return await cached("toobit:sparklines", settings.toobit_sparkline_ttl, get_sparklines,
                        mock_data.toobit_sparklines)


# ---- میانگین RSI بازار (RSI-14 روی کندل روزانهٔ ارزهای برتر) ----
_RSI_SYMS = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "TRX", "AVAX", "LINK", "DOT", "LTC"]


def _rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        if d >= 0:
            gains += d
        else:
            losses -= d
    avg_g, avg_l = gains / period, losses / period
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        avg_g = (avg_g * (period - 1) + (d if d > 0 else 0)) / period
        avg_l = (avg_l * (period - 1) + (-d if d < 0 else 0)) / period
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100 - 100 / (1 + rs)


async def get_avg_rsi() -> dict[str, Any]:
    timeout = httpx.Timeout(settings.http_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        import asyncio
        res = await asyncio.gather(*[_closes(client, s, "1d", 20) for s in _RSI_SYMS],
                                   return_exceptions=True)
    vals = []
    for r in res:
        if isinstance(r, list):
            v = _rsi(r)
            if v is not None:
                vals.append(v)
    if not vals:
        raise RuntimeError("Toobit: no kline data for RSI")
    return {"source": "live", "value": round(sum(vals) / len(vals), 2)}


async def avg_rsi() -> dict[str, Any]:
    from app.cache import cached
    return await cached("toobit:avg_rsi", settings.toobit_rsi_ttl, get_avg_rsi, mock_data.avg_rsi)


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
