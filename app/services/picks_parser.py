"""استخراجِ ارزهای پیشنهادی از متنِ سبدچینیِ هوش مصنوعی.

خروجیِ ورک‌فلو یک متنِ Markdownِ آزاد است (جدول یا فهرست). این ماژول از همان متن
نمادِ ارز، افقِ زمانی (کوتاه/میان/بلندمدت) و قیمتِ خرید و فروش را بیرون می‌کشد تا
در دیتابیس ذخیره شود و پایینِ صفحهٔ مدیریت سرمایه نمایش داده شود.

قالبِ خروجی ثابت نیست، پس هر دو شکلِ رایج پشتیبانی می‌شود و هرچه پیدا نشد
None می‌ماند تا کاربر خودش در پنل عدد را وارد کند.
"""
from __future__ import annotations

import re
from typing import Any

# نمادهایی که ارز نیستند و نباید ردیف بسازند.
NOT_COIN = {
    "USD", "IRR", "IRT", "RIAL", "TOMAN", "GOLD", "XAU", "XAG", "OIL",
    "TP", "SL", "RR", "AI", "USDT",
}

_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٬،", "0123456789,,")

_NUM_RE = re.compile(r"\$?\s*(\d[\d,]*(?:\.\d+)?)")
_SYM_RE = re.compile(r"\b([A-Za-z]{2,8})\b")
_LI_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(.*)$")
_TABLE_RE = re.compile(r"^\s*\|.*\|\s*$")
_SEP_RE = re.compile(r"^[\s:|-]+$")

# کلمات کلیدیِ قیمت و اعداد، در یک اسکنِ واحد. هر عدد به «نزدیک‌ترین کلیدواژهٔ
# قبل از خودش» نسبت داده می‌شود؛ وگرنه در عبارتی مثل «هدف ورود ۰٫۶۲، تارگت ۱٫۴۰»
# کلمهٔ «هدف» عددِ ورود را هم به فروش نسبت می‌داد.
_BUY_WORDS = r"خرید|ورود|entry|buy"
_SELL_WORDS = r"فروش|تارگت|هدف|target|sell|tp"
_TOKEN_RE = re.compile(
    rf"(?P<buy>{_BUY_WORDS})|(?P<sell>{_SELL_WORDS})|(?P<num>\$?\s*\d[\d,]*(?:\.\d+)?)",
    re.IGNORECASE,
)


def _prices_by_keyword(text: str) -> tuple[float | None, float | None]:
    """(قیمت خرید، قیمت فروش) بر پایهٔ نزدیک‌ترین کلیدواژهٔ پیش از هر عدد."""
    buy = sell = None
    last: str | None = None
    for m in _TOKEN_RE.finditer(_norm(text)):
        if m.group("buy"):
            last = "buy"
        elif m.group("sell"):
            last = "sell"
        else:
            v = _first_price(m.group("num"))
            if v is None:
                continue
            if last == "buy" and buy is None:
                buy = v
            elif last == "sell" and sell is None:
                sell = v
    return buy, sell


def _norm(s: Any) -> str:
    return str(s or "").translate(_FA_DIGITS)


def _first_price(text: str) -> float | None:
    m = _NUM_RE.search(_norm(text))
    if not m:
        return None
    try:
        v = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    return v if v > 0 else None


def horizon_of(line: str) -> str | None:
    """افقِ زمانیِ یک عنوان را تشخیص می‌دهد."""
    s = str(line or "")
    if re.search(r"کوتاه|short", s, re.IGNORECASE):
        return "short"
    if re.search(r"میان|mid|medium", s, re.IGNORECASE):
        return "mid"
    if re.search(r"بلند|long", s, re.IGNORECASE):
        return "long"
    return None


def _valid_symbol(sym: str) -> bool:
    return bool(sym) and 2 <= len(sym) <= 8 and sym not in NOT_COIN and not sym.isdigit()


def _header_kind(cell: str) -> str | None:
    """ستونِ جدول را به «خرید» یا «فروش» نگاشت می‌کند."""
    c = str(cell or "")
    if re.search(r"خرید|ورود|buy|entry", c, re.IGNORECASE):
        return "buy"
    if re.search(r"فروش|هدف|تارگت|sell|target|tp", c, re.IGNORECASE):
        return "sell"
    return None


def parse(text: str) -> list[dict[str, Any]]:
    """[{symbol, horizon, buy_price, sell_price}] از متنِ سبد."""
    lines = str(text or "").replace("\r", "").split("\n")
    found: dict[tuple[str, str], dict[str, Any]] = {}
    hz: str | None = None
    # نگاشتِ ستون‌های جدولِ جاری (اندیس ⇒ buy/sell)، با هر جدولِ تازه بازنشانی می‌شود.
    cols: dict[int, str] = {}
    in_table = False

    def add(sym: str, horizon: str, buy: float | None, sell: float | None) -> None:
        sym = re.sub(r"[^A-Z0-9]", "", str(sym or "").upper())
        if not _valid_symbol(sym):
            return
        key = (sym, horizon)
        cur = found.get(key)
        if cur is None:
            found[key] = {"symbol": sym, "horizon": horizon,
                          "buy_price": buy, "sell_price": sell}
            return
        if cur.get("buy_price") is None and buy is not None:
            cur["buy_price"] = buy
        if cur.get("sell_price") is None and sell is not None:
            cur["sell_price"] = sell

    for ln in lines:
        head = horizon_of(ln)
        # عنوان/تیترِ افق (یا خطِ کوتاهی که فقط نامِ افق دارد)
        if head and (re.match(r"^\s*#{1,4}\s", ln) or ln.strip().startswith("**")
                     or len(ln.strip()) < 40):
            hz = head
            in_table = False
            cols = {}
            continue

        cur_hz = head or hz
        if not cur_hz:
            continue

        if _TABLE_RE.match(ln):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if _SEP_RE.match("".join(cells)):
                continue                      # خطِ جداکنندهٔ ---|---
            if not in_table:
                # نخستین خطِ جدول = سرستون‌ها؛ ستون‌های قیمت را شناسایی کن.
                mapped = {i: k for i, c in enumerate(cells) if (k := _header_kind(c))}
                if mapped:
                    cols = mapped
                    in_table = True
                    continue
                in_table = True               # جدولِ بدونِ سرستونِ قابل‌تشخیص
            _row(cells, cols, cur_hz, add)
            continue

        in_table = False
        cols = {}
        if (li := _LI_RE.match(ln)):
            body = li.group(1)
            m = _SYM_RE.search(body)
            if not m:
                continue
            buy, sell = _prices_by_keyword(body)
            if buy is None and sell is None and "$" in body:
                buy = _first_price(body[body.index("$"):])
            add(m.group(1), cur_hz, buy, sell)

    return list(found.values())


def _row(cells: list[str], cols: dict[int, str], hz: str, add) -> None:
    """یک ردیفِ جدول: نماد از نخستین سلولِ حرفی، قیمت‌ها از ستون‌های شناسایی‌شده."""
    sym = ""
    for c in cells:
        m = _SYM_RE.search(c)
        if m and m.group(1).upper() not in NOT_COIN:
            sym = m.group(1)
            break
    if not sym:
        return
    buy = sell = None
    for i, kind in cols.items():
        if i < len(cells):
            v = _first_price(cells[i])
            if v is None:
                continue
            if kind == "buy":
                buy = v
            else:
                sell = v
    if buy is None and sell is None:
        # جدولِ بدونِ سرستونِ قیمت: نخستین سلولِ دلاری را قیمتِ خرید بگیر.
        for c in cells:
            if "$" in c:
                buy = _first_price(c)
                if buy:
                    break
    add(sym, hz, buy, sell)
