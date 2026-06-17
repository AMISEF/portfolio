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


async def get_heatmap(limit: int = 48) -> dict[str, Any]:
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
