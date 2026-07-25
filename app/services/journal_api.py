"""کلاینتِ اندپوینت‌های سرویسِ پنل ژورنال تریدینگ.

پنلِ ادمینِ داخلِ ربات با این ماژول اشتراکِ کاربرانِ ژورنال را فعال می‌کند و
گزارشِ عملکردِ آن سایت را می‌گیرد. احراز هویت با هدرِ ``X-Service-Token`` انجام
می‌شود که باید با ``SERVICE_TOKEN`` سرویسِ ژورنال یکی باشد.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings

TIERS = [("bronze", "برنزی"), ("silver", "نقره‌ای"), ("gold", "طلایی")]
DURATIONS = [(1, "۱ ماهه"), (3, "۳ ماهه"), (6, "۶ ماهه"), (12, "سالانه")]


def is_enabled() -> bool:
    return bool(settings.journal_service_token and settings.journal_api_base)


def _headers() -> dict[str, str]:
    return {"X-Service-Token": settings.journal_service_token}


async def _request(method: str, path: str, **kw) -> tuple[bool, Any]:
    if not is_enabled():
        return False, "ارتباط با سرویس ژورنال پیکربندی نشده است (JOURNAL_SERVICE_TOKEN)."
    url = f"{settings.journal_api_base.rstrip('/')}{path}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
            r = await client.request(method, url, headers=_headers(), **kw)
    except httpx.HTTPError as exc:
        return False, f"خطای شبکه در ارتباط با سرویس ژورنال: {exc}"
    if r.status_code == 403:
        return False, "توکنِ سرویسِ ژورنال نامعتبر است."
    if r.status_code == 503:
        return False, "سرویسِ ژورنال هنوز توکنِ سرویس را تنظیم نکرده است."
    if r.status_code == 404:
        return False, "کاربر در پنل ژورنال یافت نشد."
    if r.status_code != 200:
        return False, f"خطای سرویس ژورنال (HTTP {r.status_code})."
    try:
        return True, r.json()
    except ValueError:
        return False, "پاسخ نامعتبر از سرویس ژورنال."


async def lookup(term: str) -> tuple[bool, Any]:
    return await _request("GET", "/api/service/users/lookup", params={"q": term})


async def set_plan(user_id: int, plan: str, months: int | None) -> tuple[bool, Any]:
    return await _request("POST", f"/api/service/users/{user_id}/set-plan",
                          json={"plan": plan, "durationMonths": months})


async def stats(period: str) -> tuple[bool, Any]:
    return await _request("GET", "/api/service/stats", params={"period": period})
