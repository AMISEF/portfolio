"""
سرویس SourceArena — قیمت طلای ۱۸ عیار (هر گرم).

* برای دسترسی از سرور خارج از ایران از پراکسی sa.resicard.ir استفاده می‌شود.
* قیمت فقط هر نیم ساعت یک‌بار به‌روزرسانی می‌گردد (TTL = ۱۸۰۰ ثانیه).
* سورس‌آرنا قیمت را به «ریال» می‌دهد؛ برای نمایش به «تومان» تقسیم بر ۱۰ می‌شود.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.services import mock_data

# نام/اسلاگ‌های محتمل طلای ۱۸ عیار در پاسخ سورس‌آرنا
_GOLD18_KEYS = ("18ayar", "geram18", "gold18", "18 عیار", "۱۸ عیار", "طلای 18", "طلای ۱۸")


async def get_gold18() -> dict[str, Any]:
    timeout = httpx.Timeout(settings.http_timeout)
    url = f"{settings.sourcearena_base_url}/"
    params = {"token": settings.sourcearena_token, "currency": "", "v2": ""}
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    items = data if isinstance(data, list) else data.get("data") or data.get("result") or []
    for it in items:
        slug = str(it.get("slug") or it.get("name") or it.get("title") or "").strip().lower()
        if any(k in slug for k in _GOLD18_KEYS):
            price_rial = _f(it, "price", "p", "value", "sell", "buy")
            change = _f(it, "change", "change_percent", "dp", "changePercent")
            # ریال → تومان
            price_toman = round(price_rial / 10)
            return {
                "source": "live",
                "gold_18k": {"name": "طلای ۱۸ عیار", "sub": "هر گرم", "price": price_toman, "change_24h": change},
            }
    raise RuntimeError("Gold 18k not found in SourceArena response")


async def gold18() -> dict[str, Any]:
    from app.cache import cached
    return await cached("sourcearena:gold18", settings.sourcearena_ttl, get_gold18, mock_data.sourcearena_gold)


def _f(d: dict, *keys: str) -> float:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(str(d[k]).replace(",", ""))
            except (TypeError, ValueError):
                continue
    return 0.0
