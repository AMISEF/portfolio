"""شاخص ترس و طمع (Fear & Greed) از alternative.me — منبع رایگان و پایدار."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.services import mock_data

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
        resp = await client.get(settings.fng_base_url, params={"limit": "1"})
        resp.raise_for_status()
        item = resp.json()["data"][0]
    value = int(float(item["value"]))
    label_en = item.get("value_classification", "Neutral")
    return {"value": value, "label_en": label_en, "label_fa": _LABELS_FA.get(label_en, label_en)}


async def fng() -> dict[str, Any]:
    from app.cache import cached
    return await cached("fng", settings.fng_ttl, get_fng, mock_data.fear_greed)
