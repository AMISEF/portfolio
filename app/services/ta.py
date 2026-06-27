"""
موتور تحلیل تکنیکال — کندل‌های Toobit ⇒ نواحی خرید/فروش، روند و اندیکاتورها.

این ماژول «مغز عددیِ» مشاور سبد است: داده‌های واقعی کندل (OHLCV) را از صرافی
Toobit می‌گیرد و به‌جای آنکه مدل زبانی پیکسلِ نمودار را حدس بزند، اندیکاتورهای
دقیق را محاسبه می‌کند:

  • روند (صعودی/نزولی/خنثی) از همترازی میانگین‌های متحرک + شیب
  • RSI-14، MA20/50/200، EMA، ATR (نوسان)
  • نواحی حمایت/مقاومت از سوینگ‌های واقعی قیمت (فرکتال) + خوشه‌بندی
        ⇒ «نواحی خرید» = حمایت‌های زیر/نزدیک قیمت
        ⇒ «نواحی فروش» = مقاومت‌های بالای قیمت
  • فاصلهٔ قیمت تا هر ناحیه و فاصله تا سقف/کف بازهٔ اخیر
  • تغییرات چنددوره‌ای برای افق‌های هفتگی/ماهانه/سالانه

خروجی کاملاً ساخت‌یافته (JSON) است تا ورک‌فلو Dify آن را به مدل Gemini بدهد و
سبد پیشنهادی با نقاط ورود/خروج بسازد. همهٔ محاسبات با کتابخانهٔ استاندارد است
(بدون numpy/pandas) تا وابستگی اضافه نشود.
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.config import settings

# افق ⇒ (تایم‌فریم کندل، تعداد کندل). هفتگی=۴ساعته، ماهانه=روزانه، سالانه=هفتگی.
TIMEFRAMES: dict[str, tuple[str, int]] = {
    "weekly": ("4h", 180),     # ~۳۰ روز کندل ۴ساعته برای دید کوتاه‌مدت
    "monthly": ("1d", 180),    # ~۶ ماه کندل روزانه برای دید میان‌مدت
    "yearly": ("1w", 160),     # ~۳ سال کندل هفتگی برای دید بلندمدت
}


# ───────────────────────── واکشی کندل ─────────────────────────
async def fetch_klines(client: httpx.AsyncClient, pair: str, interval: str,
                       limit: int) -> list[dict[str, float]]:
    """کندل‌های OHLCV یک جفت‌ارز از Toobit. خروجی: فهرست {t,o,h,l,c,v}."""
    r = await client.get(
        f"{settings.toobit_base_url}/quote/v1/klines",
        params={"symbol": pair, "interval": interval, "limit": str(limit)},
    )
    r.raise_for_status()
    data = r.json()
    rows = data if isinstance(data, list) else (data.get("data") if isinstance(data, dict) else []) or []
    out: list[dict[str, float]] = []
    for k in rows:
        try:
            if isinstance(k, list) and len(k) >= 6:
                out.append({"t": float(k[0]), "o": float(k[1]), "h": float(k[2]),
                            "l": float(k[3]), "c": float(k[4]), "v": float(k[5])})
            elif isinstance(k, dict):
                out.append({"t": float(k.get("t") or 0), "o": float(k.get("o") or k.get("open") or 0),
                            "h": float(k.get("h") or k.get("high") or 0),
                            "l": float(k.get("l") or k.get("low") or 0),
                            "c": float(k.get("c") or k.get("close") or 0),
                            "v": float(k.get("v") or k.get("volume") or 0)})
        except (TypeError, ValueError):
            continue
    return [k for k in out if k["c"] > 0]


# ───────────────────────── اندیکاتورها ─────────────────────────
def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    k = 2 / (period + 1)
    e = sum(values[:period]) / period
    for v in values[period:]:
        e = v * k + e * (1 - k)
    return e


def rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains = losses = 0.0
    for i in range(1, period + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    avg_g, avg_l = gains / period, losses / period
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        avg_g = (avg_g * (period - 1) + max(d, 0.0)) / period
        avg_l = (avg_l * (period - 1) + max(-d, 0.0)) / period
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return round(100 - 100 / (1 + rs), 1)


def atr(kl: list[dict[str, float]], period: int = 14) -> float | None:
    if len(kl) < period + 1:
        return None
    trs: list[float] = []
    for i in range(1, len(kl)):
        h, l, pc = kl[i]["h"], kl[i]["l"], kl[i - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / period


def _pct_change(closes: list[float], bars: int) -> float | None:
    if len(closes) <= bars:
        return None
    past = closes[-1 - bars]
    if past <= 0:
        return None
    return round((closes[-1] - past) / past * 100, 2)


# ───────────────────────── سوینگ‌ها و نواحی ─────────────────────────
def _swings(kl: list[dict[str, float]], k: int = 3) -> tuple[list[float], list[float]]:
    """سوینگ‌های فرکتالِ بالا/پایین: نقطه‌ای که k کندل هر طرفش پایین‌تر/بالاتر است."""
    highs, lows = [], []
    n = len(kl)
    for i in range(k, n - k):
        hi = kl[i]["h"]; lo = kl[i]["l"]
        if all(kl[i]["h"] >= kl[i + j]["h"] and kl[i]["h"] >= kl[i - j]["h"] for j in range(1, k + 1)):
            highs.append(hi)
        if all(kl[i]["l"] <= kl[i + j]["l"] and kl[i]["l"] <= kl[i - j]["l"] for j in range(1, k + 1)):
            lows.append(lo)
    return highs, lows


def _cluster(levels: list[float], tol: float) -> list[dict[str, Any]]:
    """سطوح نزدیک به هم را به یک ناحیه ادغام می‌کند. tol = پهنای نسبی خوشه."""
    if not levels:
        return []
    levels = sorted(levels)
    clusters: list[list[float]] = [[levels[0]]]
    for lv in levels[1:]:
        if abs(lv - clusters[-1][-1]) <= clusters[-1][-1] * tol:
            clusters[-1].append(lv)
        else:
            clusters.append([lv])
    out = []
    for c in clusters:
        out.append({"low": round(min(c), 8), "high": round(max(c), 8),
                    "mid": round(sum(c) / len(c), 8), "touches": len(c)})
    return out


def zones(kl: list[dict[str, float]], price: float, atr_val: float | None) -> dict[str, Any]:
    """نواحی خرید (حمایت زیر قیمت) و فروش (مقاومت بالای قیمت) از سوینگ‌های واقعی."""
    highs, lows = _swings(kl)
    # پهنای خوشه ~ ۰٫۷٪ یا نصف ATR نسبت به قیمت، هرکدام بزرگ‌تر
    tol = max(0.007, (atr_val / price * 0.5) if (atr_val and price) else 0.0)
    sup = _cluster(lows, tol)
    res = _cluster(highs, tol)

    buy = [z for z in sup if z["mid"] <= price * 1.01]      # حمایت‌های زیر/نزدیک قیمت
    sell = [z for z in res if z["mid"] >= price * 0.99]     # مقاومت‌های بالای قیمت
    # نزدیک‌ترین‌ها به قیمت، حداکثر ۳ ناحیه
    buy.sort(key=lambda z: price - z["mid"])
    sell.sort(key=lambda z: z["mid"] - price)
    for z in buy + sell:
        z["dist_pct"] = round((z["mid"] - price) / price * 100, 2) if price else 0.0
    return {"buy_zones": buy[:3], "sell_zones": sell[:3]}


def _trend(closes: list[float]) -> dict[str, Any]:
    """روند از همترازی MA و شیب اخیر."""
    ma20, ma50, ma200 = sma(closes, 20), sma(closes, 50), sma(closes, 200)
    price = closes[-1]
    score = 0
    if ma50 and price > ma50:
        score += 1
    if ma50 and ma200 and ma50 > ma200:
        score += 1
    if ma20 and ma50 and ma20 > ma50:
        score += 1
    # شیب MA20 روی ۵ کندل اخیر
    slopes = [sma(closes[:i], 20) for i in range(len(closes) - 5, len(closes) + 1) if i >= 20]
    slopes = [s for s in slopes if s is not None]
    if len(slopes) >= 2 and slopes[-1] > slopes[0]:
        score += 1
    if score >= 3:
        label = "صعودی"
    elif score <= 1:
        label = "نزولی"
    else:
        label = "خنثی"
    return {"label": label, "score": score,
            "ma20": _r(ma20), "ma50": _r(ma50), "ma200": _r(ma200)}


# ───────────────────────── تحلیل یک نماد ─────────────────────────
async def analyze_pair(client: httpx.AsyncClient, symbol: str, pair: str) -> dict[str, Any]:
    """تحلیل چند‌تایم‌فریمی یک جفت‌ارز برای افق‌های هفتگی/ماهانه/سالانه."""
    out: dict[str, Any] = {"symbol": symbol, "pair": pair, "ok": False, "timeframes": {}}
    price = 0.0
    for horizon, (interval, limit) in TIMEFRAMES.items():
        try:
            kl = await fetch_klines(client, pair, interval, limit)
        except Exception:  # noqa: BLE001
            kl = []
        if len(kl) < 30:
            continue
        closes = [k["c"] for k in kl]
        price = closes[-1]
        a = atr(kl)
        out["timeframes"][horizon] = {
            "interval": interval,
            "candles": len(kl),
            "rsi": rsi(closes),
            "atr": _r(a),
            "atr_pct": round(a / price * 100, 2) if (a and price) else None,
            "trend": _trend(closes),
            "range_high": _r(max(k["h"] for k in kl)),
            "range_low": _r(min(k["l"] for k in kl)),
            **zones(kl, price, a),
        }
    if out["timeframes"]:
        out["ok"] = True
        out["price"] = _r(price)
        # تغییرات چنددوره‌ای از کندل روزانه (اگر موجود)
        out["changes"] = _changes_from(out["timeframes"].get("monthly"))
    return out


def _changes_from(daily: dict | None) -> dict[str, Any]:
    return {}  # جای‌نگه‌دار؛ تغییرات از تیکر ۲۴ساعته در روتر اضافه می‌شود


# ───────────────────────── ابزار ─────────────────────────
def _r(x: float | None) -> float | None:
    if x is None:
        return None
    if x >= 1000:
        return round(x, 2)
    if x >= 1:
        return round(x, 4)
    return round(x, 8)
