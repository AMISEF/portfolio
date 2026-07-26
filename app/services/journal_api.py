"""کلاینتِ اندپوینت‌های سرویسِ پنل ژورنال تریدینگ.

پنلِ ادمینِ داخلِ ربات با این ماژول اشتراکِ کاربرانِ ژورنال را فعال می‌کند و
گزارشِ عملکردِ آن سایت را می‌گیرد. احراز هویت با هدرِ ``X-Service-Token`` انجام
می‌شود که باید با ``SERVICE_TOKEN`` سرویسِ ژورنال یکی باشد.

نکتهٔ مهم دربارهٔ آدرس: خودِ این اپلیکیشن روی ``127.0.0.1:8000`` بالا می‌آید و
بک‌اندِ ژورنال روی ``127.0.0.1:8001``. اگر ``JOURNAL_API_BASE`` اشتباه (۸۰۰۰)
باشد، درخواست به خودِ همین اپ می‌خورد و ۴۰۴ می‌گیرد. برای همین اینجا چند پایهٔ
کاندید امتحان می‌شود و اولین پایه‌ای که پاسخ بدهد کش می‌شود؛ همچنین پیامِ ۴۰۴
دیگر بی‌قید «کاربر یافت نشد» نیست و به مسیرِ درخواست بستگی دارد.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings

TIERS = [("bronze", "برنزی"), ("silver", "نقره‌ای"), ("gold", "طلایی")]
DURATIONS = [(1, "۱ ماهه"), (3, "۳ ماهه"), (6, "۶ ماهه"), (12, "سالانه")]

# پورتِ درستِ بک‌اندِ ژورنال ۸۰۰۱ است (ecosystem.config.js پروژهٔ ژورنال).
_FALLBACK_BASES = ("http://127.0.0.1:8001", "http://localhost:8001")

# پایه‌ای که آخرین بار جواب داد (برای صرفه‌جویی در تلاش‌های بعدی).
_resolved_base: str | None = None


def is_enabled() -> bool:
    return bool(settings.journal_service_token
                and (settings.journal_api_base or _FALLBACK_BASES))


def _headers() -> dict[str, str]:
    return {"X-Service-Token": settings.journal_service_token}


def _candidate_bases() -> list[str]:
    """ترتیبِ آزمایشِ آدرس‌ها: پایهٔ کش‌شده، مقدارِ تنظیمات، سپس پورت ۸۰۰۱."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in (_resolved_base, settings.journal_api_base, *_FALLBACK_BASES):
        base = str(raw or "").strip().rstrip("/")
        if base and base not in seen:
            seen.add(base)
            out.append(base)
    return out


def _is_user_path(path: str) -> bool:
    """مسیرهایی که ۴۰۴ آن‌ها واقعاً یعنی «کاربر پیدا نشد»."""
    return "/users/" in path or path.endswith("/users/lookup")


def _not_found_message(path: str) -> str:
    if _is_user_path(path):
        return "کاربر در پنل ژورنال یافت نشد."
    return ("سرویسِ ژورنال در این آدرس پیدا نشد (HTTP 404). "
            "مقدارِ JOURNAL_API_BASE را بررسی کنید؛ "
            "بک‌اندِ ژورنال روی http://127.0.0.1:8001 اجرا می‌شود.")


def _parse(r: httpx.Response, path: str) -> tuple[bool, Any]:
    if r.status_code == 403:
        return False, "توکنِ سرویسِ ژورنال نامعتبر است."
    if r.status_code == 503:
        return False, "سرویسِ ژورنال هنوز توکنِ سرویس را تنظیم نکرده است."
    if r.status_code == 404:
        return False, _not_found_message(path)
    if r.status_code != 200:
        return False, f"خطای سرویس ژورنال (HTTP {r.status_code})."
    try:
        return True, r.json()
    except ValueError:
        return False, "پاسخ نامعتبر از سرویس ژورنال."


async def _request(method: str, path: str, **kw) -> tuple[bool, Any]:
    global _resolved_base
    if not settings.journal_service_token:
        return False, "ارتباط با سرویس ژورنال پیکربندی نشده است (JOURNAL_SERVICE_TOKEN)."

    bases = _candidate_bases()
    if not bases:
        return False, "آدرسِ سرویسِ ژورنال تنظیم نشده است (JOURNAL_API_BASE)."

    last: tuple[bool, Any] = (False, "ارتباط با سرویس ژورنال برقرار نشد.")
    for index, base in enumerate(bases):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
                r = await client.request(method, f"{base}{path}",
                                         headers=_headers(), **kw)
        except httpx.HTTPError as exc:
            last = (False, f"خطای شبکه در ارتباط با سرویس ژورنال: {exc}")
            continue

        # ۴۰۴ می‌تواند نشانهٔ آدرسِ نادرست باشد (مثلاً پورت ۸۰۰۰ که خودِ همین اپ
        # است)؛ پس پایه‌های بعدی هم امتحان می‌شوند.
        if r.status_code == 404 and index + 1 < len(bases):
            last = (False, _not_found_message(path))
            continue

        if r.status_code != 404:
            _resolved_base = base
        return _parse(r, path)

    return last


async def lookup(term: str) -> tuple[bool, Any]:
    return await _request("GET", "/api/service/users/lookup", params={"q": term})


async def set_plan(user_id: int, plan: str, months: int | None) -> tuple[bool, Any]:
    return await _request("POST", f"/api/service/users/{user_id}/set-plan",
                          json={"plan": plan, "durationMonths": months})


async def stats(period: str) -> tuple[bool, Any]:
    return await _request("GET", "/api/service/stats", params={"period": period})
