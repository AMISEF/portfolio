"""
کالاهای جهانی (طلا/نقره/نفت) از Yahoo Finance — رایگان، بدون کلید.

  GC=F → طلای جهانی (اونس)      SI=F → نقره (اونس)      CL=F → نفت خام WTI (بشکه)

برای هر نماد، آخرین قیمت و تغییر ۲۴ساعته نسبت به بستهٔ قبلی از endpoint نمودار
Yahoo گرفته می‌شود. در هر خطا به دادهٔ نمونه برمی‌گردیم.

⚠️ میزبان query1.finance.yahoo.com باید در allowlist شبکهٔ سرور باشد، وگرنه
نمونه نمایش داده می‌شود.
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.config import settings
from app.services import mock_data

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# کلید خروجی → (نماد Yahoo، نام فارسی، واحد)
_SYMS = {
    "XAU": ("GC=F", "طلای جهانی", "اونس"),
    "XAG": ("SI=F", "نقره", "اونس"),
    "OIL": ("CL=F", "نفت خام", "بشکه"),
}


async def _one(client: httpx.AsyncClient, key: str, sym: str, name: str, sub: str):
    resp = await client.get(
        f"{settings.yahoo_base_url}/v8/finance/chart/{sym}",
        params={"interval": "1d", "range": "5d"},
    )
    resp.raise_for_status()
    result = (((resp.json().get("chart") or {}).get("result") or [{}])[0]) or {}
    meta = result.get("meta") or {}
    price = _f(meta, "regularMarketPrice", "previousClose")
    prev = _f(meta, "chartPreviousClose", "previousClose")
    if price <= 0:
        raise RuntimeError(f"Yahoo: empty price for {sym}")
    change = round((price - prev) / prev * 100, 2) if prev else 0.0
    return key, {"name": name, "sub": sub, "price": round(price, 2), "change_24h": change}


async def get_commodities() -> dict[str, Any]:
    timeout = httpx.Timeout(settings.http_timeout)
    async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": _UA}) as client:
        results = await asyncio.gather(
            *[_one(client, k, sym, name, sub) for k, (sym, name, sub) in _SYMS.items()],
            return_exceptions=True,
        )
    out: dict[str, Any] = {}
    for res in results:
        if isinstance(res, tuple):
            out[res[0]] = res[1]
    if not out:
        raise RuntimeError("Yahoo: no commodities parsed")
    return {"source": "live", "commodities": out}


async def commodities() -> dict[str, Any]:
    from app.cache import cached
    return await cached("yahoo:commodities", settings.commodities_ttl,
                        get_commodities, mock_data.commodities)


def _f(d: dict, *keys: str) -> float:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                continue
    return 0.0
