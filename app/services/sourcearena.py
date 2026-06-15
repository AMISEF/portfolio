"""
سرویس SourceArena — قیمت طلای ۱۸ عیار (پراکسی دسترسی خارج، هر ۳۰ دقیقه).

پاسخ سورس‌آرنا فهرستی از آیتم‌هاست؛ آیتم طلای ۱۸ عیار با slug/name شناسایی
و عدد آن (با حذف کاما) پارس می‌شود. تشخیص خودکار ریال/تومان انجام می‌شود.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.services import mock_data

_GOLD18_HINTS = ("18ayar", "geram18", "gold18", "18 عیار", "۱۸ عیار", "طلای 18")


def _f(d: dict, *keys: str) -> float:
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] is not None:
            try:
                return float(str(d[k]).replace(",", "").strip())
            except (TypeError, ValueError):
                pass
    return 0.0


def _to_toman(value: float) -> int:
    # طلای ۱۸ع گرمی در تومان چند میلیون است؛ در ریال ده‌ها میلیون
    if value > 20_000_000:
        return round(value / 10)
    return round(value)


async def get_gold18() -> dict[str, Any]:
    params = {"token": settings.sourcearena_token, "currency": "", "v2": ""}
    async with httpx.AsyncClient(timeout=httpx.Timeout(settings.http_timeout)) as client:
        r = await client.get(f"{settings.sourcearena_base_url}/", params=params)
        r.raise_for_status()
        data = r.json()

    items = data if isinstance(data, list) else (data.get("data") or data.get("result") or [])
    for it in items:
        text = " ".join(str(it.get(k, "")) for k in ("slug", "name", "title", "namefa", "symbol")).lower()
        if any(h in text for h in _GOLD18_HINTS):
            price = _f(it, "price", "p", "value", "sell", "buy")
            change = _f(it, "change", "change_percent", "dp", "changePercent")
            return {
                "source": "live",
                "gold_18k": {"name": "طلای ۱۸ عیار (گرم)", "price": _to_toman(price), "change_24h": change, "unit": "تومان"},
            }
    raise RuntimeError("SourceArena: gold 18k item not found")


async def gold18() -> dict[str, Any]:
    from app.cache import cached
    return await cached("sourcearena:gold18", settings.sourcearena_ttl, get_gold18, mock_data.sourcearena_gold)


async def probe() -> dict[str, Any]:
    out: dict[str, Any] = {"token_set": bool(settings.sourcearena_token)}
    try:
        params = {"token": settings.sourcearena_token, "currency": "", "v2": ""}
        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.http_timeout)) as client:
            r = await client.get(f"{settings.sourcearena_base_url}/", params=params)
            out["response"] = {"url": str(r.url).replace(settings.sourcearena_token, "***"), "status": r.status_code, "raw": _trim(r.text)}
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def _trim(s: str, n: int = 2000) -> str:
    return s if len(s) <= n else s[:n] + " …[truncated]"
