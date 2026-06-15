"""
کمک‌تابع آدرس آیکون ارزها.

از مجموعهٔ آیکون متن‌باز spothq روی CDN استفاده می‌شود (پوشش صدها ارز).
برای ارزهای ناشناس، فرانت‌اند با onerror به نشان حرفی (badge) برمی‌گردد.
"""
from __future__ import annotations

_CDN = "https://cdn.jsdelivr.net/gh/spothq/cryptocurrency-icons@latest/128/color"

# نگاشت چند نماد خاص که در مجموعهٔ آیکون نام متفاوتی دارند
_ALIASES = {
    "MIOTA": "iota",
    "XBT": "btc",
}


def coin_icon(symbol: str) -> str:
    if not symbol:
        return ""
    s = symbol.lower()
    s = _ALIASES.get(symbol.upper(), s)
    return f"{_CDN}/{s}.png"
