"""
تحلیل ریسک و تنوع سبد — قاعده‌محور و کاملاً در سرور.

طبق اصل پروپوزال، اعداد و شاخص‌ها در کد محاسبه می‌شوند. در فاز ۳ کامل،
لایهٔ مدل هوش مصنوعی فقط این اعداد را «تفسیر» می‌کند (نیازمند کلید مدل).
تا آن زمان، بینش‌های قاعده‌محور فارسی تولید می‌شود.
"""
from __future__ import annotations

from typing import Any

_STABLES = {"USDT", "USDC", "DAI", "FDUSD", "TUSD", "USDE"}


def analyze(holdings: list[dict[str, Any]], total_value: float) -> dict[str, Any]:
    if not holdings or total_value <= 0:
        return {"risk_level": "—", "score": 0, "insights": [
            {"type": "info", "text": "هنوز دارایی‌ای ثبت نشده است. برای تحلیل، چند دارایی اضافه کنید."}
        ], "metrics": {}}

    allocs = [(h["symbol"], h.get("allocation", 0.0)) for h in holdings]
    top_sym, top_pct = max(allocs, key=lambda x: x[1])
    hhi = sum((a / 100) ** 2 for _, a in allocs)  # شاخص تمرکز هرفیندال (۰..۱)
    stable_pct = sum(a for s, a in allocs if s in _STABLES)
    count = len(holdings)
    # تغییر وزنی ۲۴ساعتهٔ سبد
    change_24h = sum(h.get("change_24h", 0.0) * (h.get("allocation", 0.0) / 100) for h in holdings)

    # سطح ریسک (۰ کم‌ریسک .. ۱۰۰ پرریسک)
    score = 0
    score += min(top_pct, 100) * 0.5          # تمرکز روی یک دارایی
    score += max(0, (4 - count)) * 8           # تنوع کم
    score -= min(stable_pct, 50) * 0.4         # استیبل‌کوین ریسک را کم می‌کند
    score = max(0, min(100, score))
    level = "بالا" if score >= 60 else "متوسط" if score >= 35 else "پایین"

    insights: list[dict[str, str]] = []
    if top_pct > 50:
        insights.append({"type": "warn", "text": f"تمرکز بالا: {_fa(top_pct)}٪ سبد در {top_sym} است. برای کاهش ریسک، تنوع بیشتری در نظر بگیرید."})
    if count < 3:
        insights.append({"type": "warn", "text": "تنوع پایین: سبد شما کمتر از ۳ دارایی دارد؛ افزودن دارایی‌های غیرهم‌بسته ریسک را کاهش می‌دهد."})
    if stable_pct < 5:
        insights.append({"type": "info", "text": "بدون سپر نقدینگی: سهم استیبل‌کوین بسیار کم است؛ نگهداری بخشی به‌صورت تتر در نوسانات شدید کمک می‌کند."})
    elif stable_pct > 60:
        insights.append({"type": "info", "text": f"سبد بسیار محافظه‌کار: {_fa(stable_pct)}٪ در استیبل‌کوین؛ برای رشد بلندمدت می‌توانید سهم دارایی‌های رشدی را افزایش دهید."})
    if score < 35 and count >= 3 and top_pct <= 40:
        insights.append({"type": "good", "text": "سبد متعادل: تنوع و توزیع مناسبی دارید. آفرین! 👌"})
    if not insights:
        insights.append({"type": "info", "text": "وضعیت سبد در محدودهٔ معمول است. به پایش دوره‌ای ادامه دهید."})

    insights.append({"type": "muted", "text": "تحلیل خودکار و قاعده‌محور است؛ توصیهٔ سرمایه‌گذاری نیست. لایهٔ تحلیل هوش مصنوعی در فاز بعدی فعال می‌شود."})

    return {
        "risk_level": level,
        "score": round(score),
        "insights": insights,
        "metrics": {
            "concentration_hhi": round(hhi, 3),
            "top_symbol": top_sym,
            "top_pct": round(top_pct, 1),
            "stable_pct": round(stable_pct, 1),
            "assets": count,
            "change_24h": round(change_24h, 2),
        },
    }


def _fa(n: float) -> str:
    s = f"{n:.1f}".rstrip("0").rstrip(".")
    return s.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))
