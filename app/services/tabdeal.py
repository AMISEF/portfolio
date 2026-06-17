"""
سرویس Tabdeal — قیمت لحظه‌ای تتر تومانی (USDT/IRT).

⚠️ مهم: طبق درخواست، قیمت بازگشتی همان «تومان» است و هیچ تبدیلی (تقسیم بر ۱۰
یا مشابه) روی آن انجام نمی‌شود. عدد دقیقاً همان‌طور که از صرافی می‌آید نمایش
داده می‌شود.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.services import mock_data


async def get_usdt() -> dict[str, Any]:
    timeout = httpx.Timeout(settings.http_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(
            f"{settings.tabdeal_base_url}/r/api/v1/depth/", params={"symbol": "USDTIRT"}
        )
        resp.raise_for_status()
        data = resp.json()

    bids = data.get("bids") or []
    asks = data.get("asks") or []
    best_bid = float(bids[0][0]) if bids else 0.0
    best_ask = float(asks[0][0]) if asks else 0.0
    mid = (best_bid + best_ask) / 2 if (best_bid and best_ask) else (best_bid or best_ask)
    if not mid:
        raise RuntimeError("Tabdeal depth empty")

    # بدون هیچ تبدیلی — همان تومان.
    return {"source": "live", "usdt_irt": {"name": "تتر / تومان", "price": round(mid), "change_24h": 0.0}}


async def usdt() -> dict[str, Any]:
    from app.cache import cached
    return await cached("tabdeal:usdt", settings.tabdeal_ttl, get_usdt, mock_data.tabdeal_usdt)
