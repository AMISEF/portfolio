"""
جریان خالص ETFهای کریپتو (Crypto ETFs Net Flow).

ترتیب منابع (هر ۲۴ ساعت یک بار):
  ۱) وب‌سایت CoinMarketCap  — صفحهٔ ETF tracker (اسکرپ __NEXT_DATA__)
  ۲) CoinGlass public API   — بدون نیاز به کلید
  ۳) Farside Investors       — پشتیبان آخر (اغلب ۴۰۳ از آی‌پی سرور)
  ۴) "unavailable"           — اگر هیچ‌کدام جواب ندادند

خروجی نرمال‌شده:
  {"source": "live", "provider": "cmc",
   "updated": "2026-06-16",
   "points": [{"date": "2026-05-20", "label": "20 May",
               "btc": -123.4, "eth": 5.6, "total": -117.8}, ...]}
"""
from __future__ import annotations

import asyncio
import json
import re
import urllib.parse
from datetime import datetime
from typing import Any

import httpx

from app.cache import cache
from app.config import settings

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_BROWSER_HDRS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xhtml+xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
    "DNT": "1",
}

_JSON_HDRS = {
    "User-Agent": _UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://coinmarketcap.com/",
}

_DATE_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_NEXT_DATA_RE = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', re.S | re.I
)

_FARSIDE_PROXIES = [
    "",
    "https://api.allorigins.win/raw?url=",
    "https://corsproxy.io/?url=",
]

_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_FSDATE_RE = re.compile(r"^\d{1,2}\s+[A-Za-z]{3}\s+\d{4}$")


# ─────────────────────────── shared helpers ─────────────────────────────────

def _iso_label(iso: str) -> str:
    try:
        dt = datetime.strptime(iso[:10], "%Y-%m-%d")
        return "%d %s" % (dt.day, dt.strftime("%b"))
    except Exception:
        return iso[:10]


def _to_points(btc_usd: dict[str, float], eth_usd: dict[str, float]) -> list[dict]:
    """Convert {ISO: USD} dicts to normalised list (millions USD)."""
    dates = set(btc_usd) | set(eth_usd)
    rows = []
    for d in dates:
        if not _DATE_ISO_RE.match(d[:10]):
            continue
        b = round(btc_usd.get(d, 0.0) / 1_000_000, 1)
        e = round(eth_usd.get(d, 0.0) / 1_000_000, 1)
        rows.append((d[:10], b, e))
    rows.sort(key=lambda r: r[0])
    rows = rows[-settings.etf_days:]
    return [
        {"date": d, "label": _iso_label(d), "btc": b, "eth": e, "total": round(b + e, 1)}
        for d, b, e in rows
    ]


def _deep_extract(obj: Any, out: dict[str, float]) -> None:
    """Recursively search JSON for objects with date + flow fields."""
    if isinstance(obj, dict):
        date_val = flow_val = None
        for k, v in obj.items():
            kl = k.lower()
            if kl in ("date", "timestamp", "recorddate", "flowdate", "tradingdate") and isinstance(v, str):
                date_val = v
            elif kl in ("netflow", "net_flow", "totalnetflow", "total_net_flow",
                        "dailyflow", "flow", "netinflow", "net_inflow") and isinstance(v, (int, float)):
                flow_val = float(v)
        if date_val and flow_val is not None and _DATE_ISO_RE.match(date_val[:10]):
            out.setdefault(date_val[:10], flow_val)
            return
        for v in obj.values():
            _deep_extract(v, out)
    elif isinstance(obj, list):
        for item in obj:
            _deep_extract(item, out)


# ─────────────────────────── source 1: CoinMarketCap ────────────────────────

async def _cmc_flows() -> list[dict]:
    """Scrape CMC bitcoin-etfs / ethereum-etfs pages and parse __NEXT_DATA__."""
    timeout = httpx.Timeout(20.0)
    async with httpx.AsyncClient(
        timeout=timeout, headers=_BROWSER_HDRS, follow_redirects=True
    ) as client:
        btc_r, eth_r = await asyncio.gather(
            client.get("https://coinmarketcap.com/charts/bitcoin-etfs/"),
            client.get("https://coinmarketcap.com/charts/ethereum-etfs/"),
        )

    btc_usd: dict[str, float] = {}
    eth_usd: dict[str, float] = {}

    for resp, series, name in [
        (btc_r, btc_usd, "BTC"),
        (eth_r, eth_usd, "ETH"),
    ]:
        if resp.status_code != 200:
            raise RuntimeError(f"CMC {name} ETF page -> HTTP {resp.status_code}")
        m = _NEXT_DATA_RE.search(resp.text)
        if not m:
            raise RuntimeError(f"CMC {name} ETF page: __NEXT_DATA__ not found")
        _deep_extract(json.loads(m.group(1)), series)

    if not btc_usd and not eth_usd:
        raise RuntimeError("CMC ETF: no flow data found in __NEXT_DATA__")

    pts = _to_points(btc_usd, eth_usd)
    if not pts:
        raise RuntimeError("CMC ETF: parsed zero points")
    return pts


# ─────────────────────────── source 2: CoinGlass ────────────────────────────

async def _coinglass_flows() -> list[dict]:
    """CoinGlass free public API (no key needed for basic endpoints)."""
    timeout = httpx.Timeout(12.0)
    btc_usd: dict[str, float] = {}
    eth_usd: dict[str, float] = {}

    async with httpx.AsyncClient(
        timeout=timeout, headers=_JSON_HDRS, follow_redirects=True
    ) as client:
        try:
            resp = await client.get("https://open-api.coinglass.com/public/v2/etf")
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                _deep_extract(data.get("btcEtfList") or data.get("btcList") or data, btc_usd)
                _deep_extract(data.get("ethEtfList") or data.get("ethList") or {}, eth_usd)
        except Exception:
            pass

        if not btc_usd:
            try:
                r = await client.get(
                    "https://open-api.coinglass.com/public/v2/etf/fund/list",
                    params={"symbol": "BTC"},
                )
                if r.status_code == 200:
                    _deep_extract(r.json().get("data", []), btc_usd)
            except Exception:
                pass

        if not eth_usd:
            try:
                r = await client.get(
                    "https://open-api.coinglass.com/public/v2/etf/fund/list",
                    params={"symbol": "ETH"},
                )
                if r.status_code == 200:
                    _deep_extract(r.json().get("data", []), eth_usd)
            except Exception:
                pass

    if not btc_usd and not eth_usd:
        raise RuntimeError("CoinGlass ETF: no flow data returned")

    pts = _to_points(btc_usd, eth_usd)
    if not pts:
        raise RuntimeError("CoinGlass ETF: parsed zero points")
    return pts


# ─────────────────────────── source 3: Farside ──────────────────────────────

def _fs_num(s: str) -> float | None:
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


def _fs_parse(html: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for rowm in _ROW_RE.finditer(html):
        cells = [
            _TAG_RE.sub("", c).replace("&nbsp;", " ").strip()
            for c in _CELL_RE.findall(rowm.group(1))
        ]
        if not cells or not _FSDATE_RE.match(cells[0]):
            continue
        for c in reversed(cells[1:]):
            v = _fs_num(c)
            if v is not None:
                out[cells[0]] = v
                break
    return out


async def _farside_fetch(path: str) -> str:
    timeout = httpx.Timeout(8.0)
    hdrs = {"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml"}
    target = f"{settings.farside_base_url}{path}"
    last = "?"
    async with httpx.AsyncClient(timeout=timeout, headers=hdrs, follow_redirects=True) as client:
        for px in _FARSIDE_PROXIES:
            url = (px + urllib.parse.quote(target, safe="")) if px else target
            try:
                resp = await client.get(url)
                if resp.status_code == 200 and "<tr" in resp.text.lower():
                    return resp.text
                last = str(resp.status_code)
            except Exception as e:
                last = type(e).__name__
    raise RuntimeError(f"Farside unreachable (last={last})")


async def _farside_flows() -> list[dict]:
    btc_html, eth_html = await asyncio.gather(
        _farside_fetch("/btc/"), _farside_fetch("/eth/")
    )
    btc_raw = _fs_parse(btc_html)
    eth_raw = _fs_parse(eth_html)
    if not btc_raw and not eth_raw:
        raise RuntimeError("Farside: no rows parsed")

    def to_usd(raw: dict[str, float]) -> dict[str, float]:
        out: dict[str, float] = {}
        for ds, v in raw.items():
            try:
                dt = datetime.strptime(ds, "%d %b %Y")
                out[dt.strftime("%Y-%m-%d")] = v * 1_000_000
            except ValueError:
                pass
        return out

    pts = _to_points(to_usd(btc_raw), to_usd(eth_raw))
    if not pts:
        raise RuntimeError("Farside: parsed zero points")
    return pts


# ─────────────────────────── public interface ────────────────────────────────

async def get_flows() -> dict[str, Any]:
    errors: list[str] = []
    for provider, fetch_fn in [
        ("cmc", _cmc_flows),
        ("coinglass", _coinglass_flows),
        ("farside", _farside_flows),
    ]:
        try:
            pts = await fetch_fn()
            updated = pts[-1]["date"] if pts else ""
            return {"source": "live", "provider": provider, "updated": updated, "points": pts}
        except Exception as e:
            errors.append(f"{provider}: {e}")
    raise RuntimeError("All ETF sources failed: " + " | ".join(errors))


async def flows() -> dict[str, Any]:
    """24-hour cache; returns stale data or 'unavailable' on error."""
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
