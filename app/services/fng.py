"""
سرویس شاخص ترس و طمع (Fear & Greed) از alternative.me.
خروجی در کش ذخیره می‌شود تا سرویس CryptoRank هم بتواند از آن استفاده کند.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.cache import cache
from app.config import settings

_LABELS_FA = {
    "Extreme Fear": "ترس شدید",
    "Fear": "ترس",
    "Neutral": "خنثی",
    "Greed": "طمع",
    "Extreme Greed": "طمع شدید",
}


async def get_fng() -> dict[str, Any]:
    timeout = httpx.Timeout(settings.http_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(settings.fng_base_url)
        resp.raise_for_status()
        item = resp.json()["data"][0]
    value = int(item["value"])
    label_en = item.get("value_classification", "Neutral")
    fng = {"value": value, "label_en": label_en, "label_fa": _LABELS_FA.get(label_en, label_en)}
    cache.set("fng", fng, settings.fng_ttl)
    return fng


async def fng() -> dict[str, Any]:
    from app.services import mock_data
    from app.cache import cached
    return await cached("fng", settings.fng_ttl, get_fng, lambda: mock_data.macro()["fear_greed"])
