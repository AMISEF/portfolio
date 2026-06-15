"""
سرویس Tabdeal — قیمت لحظه‌ای تتر تومانی (USDT/IRT).

تشخیص خودکار واحد: اگر عدد خیلی بزرگ بود (ریال) به تومان تبدیل می‌شود؛
وگرنه همان تومان فرض می‌شود. چند اندپوینت محتمل امتحان می‌شود.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.services import mock_data


def _to_toman(value: float) -> int:
    """اگر مقدار به ریال باشد (خیلی بزرگ)، به تومان تبدیل کن."""
    if value > 500_000:      # تتر در تومان ~۱۰۰هزار؛ در ریال ~۱میلیون
        return round(value / 10)
    return round(value)


async def _from_depth(client: httpx.AsyncClient) -> float:
    r = await client.get(f"{settings.tabdeal_base_url}/r/api/v1/depth/", params={"symbol": "USDTIRT"})
    r.raise_for_status()
    d = r.json()
    bids = d.get("bids") or []
    asks = d.get("asks") or []
    bb = float(bids[0][0]) if bids else 0.0
    ba = float(asks[0][0]) if asks else 0.0
    if bb and ba:
        return (bb + ba) / 2
    return bb or ba


async def _from_markets(client: httpx.AsyncClient) -> float:
    """اندپوینت خلاصهٔ بازارها (اگر depth کار نکرد)."""
    for url in (
        f"{settings.tabdeal_base_url}/r/api/v1/market/",
        f"{settings.tabdeal_base_url}/api/v1/market/",
    ):
        try:
            r = await client.get(url)
            if r.status_code != 200:
                continue
            j = r.json()
            items = j if isinstance(j, list) else (j.get("data") or j.get("markets") or [])
            for it in items:
                sym = str(it.get("symbol") or it.get("pair") or "").upper().replace("-", "").replace("_", "")
                if sym in ("USDTIRT", "USDTTMN"):
                    p = it.get("price") or it.get("last") or it.get("lastPrice")
                    if p:
                        return float(p)
        except Exception:  # noqa: BLE001
            continue
    return 0.0


async def get_usdt() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=httpx.Timeout(settings.http_timeout)) as client:
        raw = 0.0
        try:
            raw = await _from_depth(client)
        except Exception:  # noqa: BLE001
            raw = 0.0
        if not raw:
            raw = await _from_markets(client)
    if not raw:
        raise RuntimeError("Tabdeal: USDT price not found")
    return {"source": "live", "usdt_irt": {"name": "تتر / تومان", "price": _to_toman(raw), "change_24h": 0.0}}


async def usdt() -> dict[str, Any]:
    from app.cache import cached
    return await cached("tabdeal:usdt", settings.tabdeal_ttl, get_usdt, mock_data.tabdeal_usdt)


async def probe() -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.http_timeout)) as client:
            r = await client.get(f"{settings.tabdeal_base_url}/r/api/v1/depth/", params={"symbol": "USDTIRT"})
            out["depth"] = {"url": str(r.url), "status": r.status_code, "raw": _trim(r.text)}
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def _trim(s: str, n: int = 1200) -> str:
    return s if len(s) <= n else s[:n] + " …[truncated]"
