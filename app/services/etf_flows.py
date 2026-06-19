"""
سرویس «جریان خالص ETFهای کریپتو» (Crypto ETFs Net Flow).

منبع رایگان: Farside Investors — جدول HTML روزانهٔ ورود/خروج صندوق‌های ETF
بیت‌کوین (/btc/) و اتریوم (/eth/). چون منبع رایگان است و در برابر کلاینت‌های
غیرمرورگری حساس است:
  • با User-Agent مرورگری درخواست می‌زنیم.
  • پارس مقاوم است (ساختار جدول ممکن است کمی تغییر کند).
  • در هر خطا به دادهٔ نمونه برمی‌گردیم (source="sample").

⚠️ میزبان farside.co.uk باید در allowlist شبکهٔ سرور باشد، وگرنه همیشه نمونه
نمایش داده می‌شود.

خروجی نرمال‌شده:
  {"source": "live",
   "updated": "2026-06-16",
   "points": [{"date": "2026-05-20", "label": "20 May",
               "btc": -123.4, "eth": 5.6, "total": -117.8}, ...]}  # میلیون دلار
"""
from __future__ import annotations

import asyncio
import re
import urllib.parse
from datetime import datetime
from typing import Any

import httpx

from app.cache import cache
from app.config import settings

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Farside پشت Cloudflare است و درخواست مستقیم سرور را ۴۰۳ می‌کند؛ پس از چند
# پراکسی عمومی هم به‌عنوان پشتیبان استفاده می‌کنیم. اولی تلاش مستقیم است.
_PROXIES = [
    "",
    "https://api.allorigins.win/raw?url=",
    "https://corsproxy.io/?url=",
    "https://thingproxy.freeboard.io/fetch/",
]

_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_DATE_RE = re.compile(r"^\d{1,2}\s+[A-Za-z]{3}\s+\d{4}$")


def _num(s: str) -> float | None:
    """عدد سلول جدول؛ منفی به‌صورت (x) یا -x، خالی/خط‌تیره ⇒ صفر."""
    s = s.strip().replace(",", "").replace("$", "").replace("−", "-")
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").strip()
    if s in ("", "-", "—", "n/a", "N/A"):
        return 0.0
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def _parse_table(html: str) -> dict[str, float]:
    """نگاشت «تاریخِ متن» → جریان خالص کل روز (آخرین ستون عددی هر ردیفِ دارای تاریخ)."""
    out: dict[str, float] = {}
    for rowm in _ROW_RE.finditer(html):
        cells = [_TAG_RE.sub("", c).replace("&nbsp;", " ").strip()
                 for c in _CELL_RE.findall(rowm.group(1))]
        if not cells or not _DATE_RE.match(cells[0]):
            continue
        total = None
        for c in reversed(cells[1:]):
            v = _num(c)
            if v is not None:
                total = v
                break
        if total is not None:
            out[cells[0]] = total
    return out


async def _fetch(path: str) -> str:
    """صفحهٔ Farside را مستقیم و سپس از طریق پراکسی‌های عمومی تلاش می‌کند."""
    timeout = httpx.Timeout(7.0)
    headers = {"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml"}
    target = f"{settings.farside_base_url}{path}"
    last = "?"
    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as client:
        for px in _PROXIES:
            url = (px + urllib.parse.quote(target, safe="")) if px else target
            try:
                resp = await client.get(url)
                if resp.status_code == 200 and "<tr" in resp.text.lower():
                    return resp.text
                last = str(resp.status_code)
            except Exception as e:  # noqa: BLE001
                last = f"{type(e).__name__}"
    raise RuntimeError(f"Farside unreachable (last={last})")


async def get_flows() -> dict[str, Any]:
    btc_html, eth_html = await asyncio.gather(_fetch("/btc/"), _fetch("/eth/"))
    btc = _parse_table(btc_html)
    eth = _parse_table(eth_html)
    if not btc and not eth:
        raise RuntimeError("Farside: no rows parsed (layout changed or blocked)")

    dates = set(btc) | set(eth)
    rows = []
    for ds in dates:
        try:
            dt = datetime.strptime(ds, "%d %b %Y")
        except ValueError:
            continue
        b = round(btc.get(ds, 0.0), 1)
        e = round(eth.get(ds, 0.0), 1)
        rows.append((dt, b, e))
    if not rows:
        raise RuntimeError("Farside: no parseable dates")

    rows.sort(key=lambda r: r[0])
    rows = rows[-settings.etf_days:]
    points = [{
        "date": dt.strftime("%Y-%m-%d"),
        "label": "%d %s" % (dt.day, dt.strftime("%b")),
        "btc": b, "eth": e, "total": round(b + e, 1),
    } for (dt, b, e) in rows]
    return {"source": "live", "updated": points[-1]["date"], "points": points}


async def flows() -> dict[str, Any]:
    """بدون دادهٔ نمونه: اگر Farside در دسترس نبود، «بدون داده» برمی‌گردد."""
    hit = cache.get("etf:flows")
    if hit is not None:
        return hit
    try:
        value = await get_flows()
        cache.set("etf:flows", value, settings.etf_ttl)
        return value
    except Exception:
        stale = cache.get_stale("etf:flows")
        return stale if stale is not None else {"source": "unavailable", "points": []}
