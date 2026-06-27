"""
رندر نمودار کندل‌استیک به‌صورت SVG (بدون هیچ وابستگی) برای «تصویرسازی» تحلیل.

کندل‌های Toobit + نواحی خرید/فروش را به یک نمودار شمعی تمیز با خطوط حمایت
(سبز) و مقاومت (قرمز) و میانگین متحرک تبدیل می‌کند. این تصویر هم در خود سایت
نمایش داده می‌شود و هم می‌تواند به‌عنوان ورودیِ بینایی به مدل داده شود تا
تحلیل دیداریِ روند را تکمیل کند.
"""
from __future__ import annotations

from typing import Any

_W, _H = 760, 360
_PAD_L, _PAD_R, _PAD_T, _PAD_B = 8, 64, 28, 22
_BG = "#0a1525"
_GRID = "#1d2c44"
_UP = "#16C784"
_DOWN = "#EA3943"
_TEXT = "#aebbcb"
_MA = "#f0a531"


def _fmt(v: float) -> str:
    if v >= 1000:
        return f"{v:,.0f}"
    if v >= 1:
        return f"{v:,.2f}"
    return f"{v:.6f}"


def _sma(vals: list[float], p: int) -> list[float | None]:
    out: list[float | None] = []
    for i in range(len(vals)):
        out.append(sum(vals[i - p + 1:i + 1]) / p if i >= p - 1 else None)
    return out


def render(symbol: str, kl: list[dict[str, float]], analysis: dict[str, Any] | None = None,
           interval: str = "") -> str:
    """SVG رشته‌ای نمودار شمعی. analysis = خروجی تایم‌فریمِ ta (نواحی + MA)."""
    if not kl:
        return _empty(symbol)
    kl = kl[-120:]                                  # حداکثر ۱۲۰ کندل برای خوانایی
    hi = max(k["h"] for k in kl)
    lo = min(k["l"] for k in kl)
    # گنجاندن نواحی در محدودهٔ عمودی
    zones_all: list[dict] = []
    if analysis:
        zones_all = (analysis.get("buy_zones") or []) + (analysis.get("sell_zones") or [])
        for z in zones_all:
            hi = max(hi, z.get("high", hi)); lo = min(lo, z.get("low", lo))
    rng = (hi - lo) or 1
    hi += rng * 0.04; lo -= rng * 0.04; rng = hi - lo

    plot_w = _W - _PAD_L - _PAD_R
    plot_h = _H - _PAD_T - _PAD_B
    n = len(kl)
    cw = plot_w / n
    body = max(1.0, cw * 0.62)

    def x(i: int) -> float:
        return _PAD_L + i * cw + cw / 2

    def y(p: float) -> float:
        return _PAD_T + (hi - p) / rng * plot_h

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_W} {_H}" '
        f'width="{_W}" height="{_H}" font-family="Vazirmatn,Arial,sans-serif">')
    parts.append(f'<rect width="{_W}" height="{_H}" rx="14" fill="{_BG}"/>')

    # شبکهٔ افقی + برچسب قیمت
    for g in range(5):
        gy = _PAD_T + plot_h * g / 4
        gp = hi - rng * g / 4
        parts.append(f'<line x1="{_PAD_L}" y1="{gy:.1f}" x2="{_PAD_L + plot_w}" y2="{gy:.1f}" '
                     f'stroke="{_GRID}" stroke-width="1"/>')
        parts.append(f'<text x="{_PAD_L + plot_w + 6}" y="{gy + 3:.1f}" fill="{_TEXT}" '
                     f'font-size="10">{_fmt(gp)}</text>')

    # نواحی خرید/فروش (نوار افقی نیمه‌شفاف + خط)
    if analysis:
        for z in (analysis.get("buy_zones") or []):
            _band(parts, y, z, _UP, _PAD_L, plot_w)
        for z in (analysis.get("sell_zones") or []):
            _band(parts, y, z, _DOWN, _PAD_L, plot_w)

    # میانگین متحرک MA20
    closes = [k["c"] for k in kl]
    ma = _sma(closes, 20)
    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(ma) if v is not None)
    if pts:
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{_MA}" '
                     f'stroke-width="1.4" opacity=".9"/>')

    # شمع‌ها
    for i, k in enumerate(kl):
        up = k["c"] >= k["o"]
        col = _UP if up else _DOWN
        cx = x(i)
        parts.append(f'<line x1="{cx:.1f}" y1="{y(k["h"]):.1f}" x2="{cx:.1f}" '
                     f'y2="{y(k["l"]):.1f}" stroke="{col}" stroke-width="1"/>')
        oy, cy = y(k["o"]), y(k["c"])
        top = min(oy, cy); h = max(1.0, abs(cy - oy))
        parts.append(f'<rect x="{cx - body / 2:.1f}" y="{top:.1f}" width="{body:.1f}" '
                     f'height="{h:.1f}" fill="{col}"/>')

    # قیمت فعلی
    last = closes[-1]
    ly = y(last)
    parts.append(f'<line x1="{_PAD_L}" y1="{ly:.1f}" x2="{_PAD_L + plot_w}" y2="{ly:.1f}" '
                 f'stroke="#fff" stroke-width="1" stroke-dasharray="3 3" opacity=".6"/>')
    parts.append(f'<rect x="{_PAD_L + plot_w}" y="{ly - 8:.1f}" width="{_PAD_R}" height="16" fill="#fff"/>')
    parts.append(f'<text x="{_PAD_L + plot_w + 4}" y="{ly + 3:.1f}" fill="#0a1525" '
                 f'font-size="10" font-weight="700">{_fmt(last)}</text>')

    # عنوان
    title = symbol + (f" · {interval}" if interval else "")
    parts.append(f'<text x="{_PAD_L + 4}" y="18" fill="#fff" font-size="13" font-weight="800">{title}</text>')
    parts.append('</svg>')
    return "".join(parts)


def _band(parts: list[str], y, z: dict, color: str, px: float, pw: float) -> None:
    y1, y2 = y(z["high"]), y(z["low"])
    top = min(y1, y2); h = max(1.5, abs(y2 - y1))
    parts.append(f'<rect x="{px}" y="{top:.1f}" width="{pw:.1f}" height="{h:.1f}" '
                 f'fill="{color}" opacity=".10"/>')
    parts.append(f'<line x1="{px}" y1="{y(z["mid"]):.1f}" x2="{px + pw:.1f}" y2="{y(z["mid"]):.1f}" '
                 f'stroke="{color}" stroke-width="1" stroke-dasharray="5 3" opacity=".7"/>')


def _empty(symbol: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_W} {_H}" width="{_W}" '
            f'height="{_H}"><rect width="{_W}" height="{_H}" rx="14" fill="{_BG}"/>'
            f'<text x="{_W/2}" y="{_H/2}" fill="{_TEXT}" font-size="13" text-anchor="middle">'
            f'دادهٔ کندل برای {symbol} موجود نیست</text></svg>')
