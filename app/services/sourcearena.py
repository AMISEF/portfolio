"""
سرویس SourceArena — طلا و فلزات گران‌بها.

پاسخ این API یک شیء تخت (dict) است که مقادیر آن به «تومان» هستند (تأییدشده:
usd ≈ ۱۶۰٬۵۰۰ تومان). از این پاسخ استخراج می‌کنیم:
  • 18ayar      → طلای ۱۸ عیار هر گرم (تومان) — بدون هیچ تبدیلی
  • usd_xau     → انس طلای جهانی (دلار)
  • xag         → انس نقره (تومان) → با نرخ دلار به دلار تبدیل می‌شود
  • usd         → نرخ دلار آزاد (تومان) برای تبدیل نقره

طبق درخواست، فقط هر نیم ساعت یک‌بار به‌روزرسانی می‌شود (TTL = ۱۸۰۰).
برای دسترسی از سرور خارج از ایران از پراکسی sa.resicard.ir استفاده می‌شود.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.services import mock_data


async def get_metals() -> dict[str, Any]:
    timeout = httpx.Timeout(settings.http_timeout)
    url = f"{settings.sourcearena_base_url}/"
    params = {"token": settings.sourcearena_token, "currency": "", "v2": ""}
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    if not isinstance(data, dict) or "18ayar" not in data:
        raise RuntimeError("SourceArena: unexpected response shape")

    usd_toman = _v(data, "usd") or _v(data, "usd_sherkat") or 0.0
    gold18 = _v(data, "18ayar")          # تومان، هر گرم
    xau_usd = _v(data, "usd_xau")        # دلار، هر انس
    xag_toman = _v(data, "xag")          # تومان، هر انس
    xag_usd = round(xag_toman / usd_toman, 2) if usd_toman else 0.0

    if gold18 <= 0:
        raise RuntimeError("SourceArena: gold 18k missing")

    return {
        "source": "live",
        "gold_18k": {"name": "طلای ۱۸ عیار", "sub": "هر گرم", "price": round(gold18), "change_24h": _c(data, "18ayar")},
        "commodities": {
            "XAU": {"name": "طلای جهانی", "sub": "اونس", "price": xau_usd, "change_24h": _c(data, "usd_xau")},
            "XAG": {"name": "نقره", "sub": "اونس", "price": xag_usd, "change_24h": _c(data, "xag")},
        },
    }


async def metals() -> dict[str, Any]:
    from app.cache import cached
    return await cached("sourcearena:metals", settings.sourcearena_ttl, get_metals, mock_data.sourcearena_metals)


def _v(data: dict, key: str) -> float:
    return _f(data.get(key) or {}, "value")


def _c(data: dict, key: str) -> float:
    return _f(data.get(key) or {}, "change_pct", "change_percent")


def _f(d: dict, *keys: str) -> float:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(str(d[k]).replace(",", ""))
            except (TypeError, ValueError):
                continue
    return 0.0
