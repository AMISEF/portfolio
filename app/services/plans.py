"""
پلن‌های اشتراک CryptoSmart Hub — منبع واحد (single source of truth).

چهار پلن:
  • برنزی   (رایگان)        — ۱ تحلیل سبد/ماه، بدون تحلیل اختصاصی
  • نقره‌ای  (۹۹٬۰۰۰/ماه)   — ۲ تحلیل/ماه + تحلیل اختصاصی
  • طلایی   (۱۹۹٬۰۰۰/ماه)  — نامحدود + تحلیل اختصاصی + گزارش هفتگی + پشتیبانی اختصاصی
  • الماسی  (سالانه ۱٬۱۹۹٬۰۰۰ با تخفیف از ۲٬۴۰۰٬۰۰۰) — همهٔ امکانات طلایی + ارتباط مستقیم با مدیر

خرید واقعی از طریق تلگرام (https://t.me/cryptosmart_sup) انجام می‌شود و فعال‌سازی
توسط ادمین است؛ این ماژول فقط تعریف پلن‌ها، سهمیهٔ تحلیل هوش مصنوعی، امکانات و
نرمال‌سازی لایهٔ legacy (free/pro/vip) را برعهده دارد.
"""
from __future__ import annotations

import datetime as _dt
from typing import Any

# نشانی خرید اشتراک در تلگرام (پشتیبانی)
PURCHASE_URL = "https://t.me/cryptosmart_sup"

# تعریف پلن‌ها به‌ترتیب صعودی. ai_quota = None ⇒ نامحدود.
PLANS: dict[str, dict[str, Any]] = {
    "bronze": {
        "key": "bronze", "order": 0, "name_fa": "برنزی",
        "price": 0, "price_label": "رایگان", "period": "month",
        "best_for": "شروع مدیریت سرمایه", "highlight": False,
        "ai_quota": 1, "exclusive": False, "weekly_report": False,
        "support": "عمومی", "direct_manager": False,
    },
    "silver": {
        "key": "silver", "order": 1, "name_fa": "نقره‌ای",
        "price": 99000, "price_label": "۹۹٬۰۰۰ تومان", "period": "month",
        "best_for": " سرمایه‌گذار فعال", "highlight": False,
        "ai_quota": 2, "exclusive": True, "weekly_report": False,
        "support": "تیمی", "direct_manager": False,
    },
    "gold": {
        "key": "gold", "order": 2, "name_fa": "طلایی",
        "price": 199000, "price_label": "۱۹۹٬۰۰۰ تومان", "period": "month",
        "best_for": "تریدر حرفه‌ای", "highlight": True,
        "ai_quota": None, "exclusive": True, "weekly_report": True,
        "support": "اختصاصی", "direct_manager": False,
    },
    "diamond": {
        "key": "diamond", "order": 3, "name_fa": "الماسی",
        "price": 1199000, "original_price": 2400000,
        "price_label": "۱٬۱۹۹٬۰۰۰ تومان", "period": "year",
        "best_for": "دسترسی کامل + مدیر", "highlight": False,
        "ai_quota": None, "exclusive": True, "weekly_report": True,
        "support": "اختصاصی", "direct_manager": True,
    },
}

# پلن‌های پولی (غیر رایگان).
PAID_TIERS = {"silver", "gold", "diamond"}
# پلن‌هایی که دسترسی به «تحلیل اختصاصی» دارند.
EXCLUSIVE_TIERS = {"silver", "gold", "diamond"}

# نگاشت لایهٔ legacy → پلن جدید (بدون بازنویسی مخرب رکوردهای قدیمی).
_LEGACY_MAP = {"free": "bronze", "": "bronze", "pro": "silver", "vip": "gold"}


def tier_key(subscription: str | None) -> str:
    """نرمال‌سازی مقدار subscription ذخیره‌شده به کلید پلنِ جدید."""
    s = (subscription or "").strip().lower()
    if s in PLANS:
        return s
    return _LEGACY_MAP.get(s, "bronze")


def _is_expired(sub_expires_at: str | None) -> bool:
    """آیا تاریخ انقضای متنی من گذشته است؟ None/خالی ⇒ نامحدود (منقضی‌نشده)."""
    if not sub_expires_at:
        return False
    try:
        dt = _dt.datetime.fromisoformat(str(sub_expires_at).replace(" ", "T"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_dt.timezone.utc)
        return dt <= _dt.datetime.now(_dt.timezone.utc)
    except (ValueError, TypeError):
        return False


def tier_of(user: dict[str, Any] | None) -> str:
    """پلن مؤثر کاربر، با درنظرگرفتن انقضا. پلن پولیِ منقضی ⇒ برنزی."""
    if not user:
        return "bronze"
    key = tier_key(user.get("subscription"))
    if key in PAID_TIERS and _is_expired(user.get("sub_expires_at")):
        return "bronze"
    return key


def is_paid_active(user: dict[str, Any] | None) -> bool:
    """آیا کاربر اشتراک پولیِ منقضی‌نشده دارد؟ (نقش ادمین/پشتیبان هم True)."""
    if not user:
        return False
    if (user.get("role") or "member") in ("admin", "support"):
        return True
    return tier_of(user) in PAID_TIERS


def can_access_exclusive(user: dict[str, Any] | None) -> bool:
    """دسترسی به بخش «تحلیل اختصاصی»: نقره‌ای/طلایی/الماسی (+ ادمین)."""
    if not user:
        return False
    if (user.get("role") or "member") in ("admin", "support"):
        return True
    return tier_of(user) in EXCLUSIVE_TIERS


def ai_quota_for(tier: str) -> int | None:
    """سهمیهٔ ماهانهٔ تحلیل هوش مصنوعی (None ⇒ نامحدود)."""
    return PLANS.get(tier_key(tier), PLANS["bronze"])["ai_quota"]


def tehran_month_key() -> str:
    """کلید ماه جاری به وقت تهران (YYYY-MM) برای شمارش سهمیه."""
    now = _dt.datetime.utcnow() + _dt.timedelta(hours=3, minutes=30)
    return now.strftime("%Y-%m")


def tier_info(user: dict[str, Any] | None, ai_used: int = 0) -> dict[str, Any]:
    """بستهٔ کامل اطلاعات پلن برای فرانت‌اند و API.

    شامل: کلید، نام فارسی، قیمت/دوره، is_paid، exclusive، سهمیهٔ تحلیل و تعداد
    باقی‌مانده (None = نامحدود). برای کارکنان (ادمین/پشتیبان) به‌عنوان طلایی گزارش
    می‌شود تا دسترسیِ کامل در UI باز باشد.
    """
    if user and (user.get("role") or "member") in ("admin", "support"):
        tier = "gold"
    else:
        tier = tier_of(user)
    plan = PLANS[tier]
    quota = plan["ai_quota"]
    remaining = None if quota is None else max(quota - int(ai_used or 0), 0)
    out: dict[str, Any] = {
        "tier": tier,
        "tier_name_fa": plan["name_fa"],
        "price_label": plan["price_label"],
        "period": plan["period"],
        "is_paid": tier in PAID_TIERS,
        "exclusive": tier in EXCLUSIVE_TIERS,
        "weekly_report": plan["weekly_report"],
        "direct_manager": plan["direct_manager"],
        "ai_quota": quota,
        "ai_used": int(ai_used or 0),
        "ai_remaining": remaining,
        "sub_expires_at": (user or {}).get("sub_expires_at"),
    }
    return out


def plans_payload(user: dict[str, Any] | None = None, ai_used: int = 0) -> dict[str, Any]:
    """فهرست چهار پلن برای صفحهٔ قیمت‌گذاری + وضعیت کاربر."""
    info = tier_info(user, ai_used)
    plans = []
    for key in ["bronze", "silver", "gold", "diamond"]:
        p = PLANS[key]
        plans.append({
            "key": key, "name_fa": p["name_fa"], "order": p["order"],
            "price_label": p["price_label"], "period": p["period"],
            "best_for": p["best_for"], "highlight": p["highlight"],
            "original_price": p.get("original_price"),
            "ai_quota": p["ai_quota"], "ai_quota_label": (
                "نامحدود" if p["ai_quota"] is None else f"{p['ai_quota']} تحلیل در ماه"),
            "exclusive": p["exclusive"], "weekly_report": p["weekly_report"],
            "support": p["support"], "direct_manager": p["direct_manager"],
            "purchase_url": PURCHASE_URL,
        })
    return {"plans": plans, "current": info, "purchase_url": PURCHASE_URL}
