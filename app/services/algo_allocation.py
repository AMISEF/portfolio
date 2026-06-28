"""
سبدچینی با هوش مصنوعی (ALGO SMART).

این ماژول سه کار می‌کند:
  ۱) محاسبهٔ موجودی تتر کاربر و انتخاب «چنل پیشنهادی» (برنزی/نقره‌ای/طلایی).
  ۲) تعیین «جهان دارایی‌های مجاز» بر اساس ریسک‌پذیری کاربر.
  ۳) فراخوانی ورک‌فلوِ Dify که با Gemini سبد نهایی را می‌سازد.

نکتهٔ معماری: تحلیل تکنیکال و دادهٔ بازار از طریق ابزارِ موجود
(/api/advisor/context) به ورک‌فلو Dify داده می‌شود؛ این ماژول فقط زمینهٔ کاربر
(ریسک + موجودی + چنل) را آماده و ورک‌فلو را اجرا می‌کند.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings

# آستانه‌های چنل بر حسب ارزش دلاری موجودی تتر کاربر.
#   < ۱۰۰۰  → برنزی   |   < ۱۰٬۰۰۰ → نقره‌ای   |   ≥ ۱۰٬۰۰۰ → طلایی
CHANNELS: dict[str, dict[str, Any]] = {
    "bronze": {
        "key": "bronze", "name": "چنل برنزی", "emoji": "🥉",
        "perks": [
            "دسترسی کامل به ربات الگواسمارت",
            "معرفی موقعیت‌های جذاب اسپات",
            "لایو استریم و تحلیل هفتگی مارکت",
            "پشتیبانی و مدیریت پوزیشن‌ها",
        ],
    },
    "silver": {
        "key": "silver", "name": "چنل نقره‌ای", "emoji": "🥈",
        "perks": [
            "تمام خدمات برنزی",
            "سیگنال‌های پامپی و هولدهای فیوچرز با تارگت ۱۰۰۰٪",
            "لایو ترید اختصاصی",
            "معرفی سبد هولد اسپات هوشمند",
            "تحلیل روزانهٔ بازارهای داخلی",
            "پشتیبانی پوزیشن‌های شخصی شما",
        ],
    },
    "gold": {
        "key": "gold", "name": "گروه طلایی", "emoji": "🥇",
        "perks": [
            "تمام خدمات نقره‌ای",
            "دسترسی به پوزیشن‌ها و کپی‌تریدهای شخصی مجموعه",
            "کوچینگ حرفه‌ای و آنالیز کامل پرتفوی توسط دکتر کامیاب",
            "دسترسی نامحدود به ربات «الگو آنالایزر» و اندیکاتورهای اختصاصی",
            "پشتیبانی پوزیشن‌های شخصی شما",
        ],
    },
}


def tether_usd(valued: dict[str, Any]) -> float:
    """ارزش دلاری موجودی تتر کاربر (مجموع دارایی‌های kind == usdt)."""
    total = 0.0
    for it in valued.get("items", []):
        if (it.get("kind") or "") == "usdt":
            total += float(it.get("value_usd") or it.get("amount") or 0)
    return round(total, 2)


def recommend_channel(tether: float) -> dict[str, Any]:
    """انتخاب چنل بر اساس موجودی تتر (دلار)."""
    if tether < 1000:
        ch = CHANNELS["bronze"]
    elif tether < 10000:
        ch = CHANNELS["silver"]
    else:
        ch = CHANNELS["gold"]
    return {**ch, "signup_url": settings.algo_signup_bot_url,
            "channel_url": settings.algo_channel_url, "tether_usd": tether}


def allowed_universe(risk_pct: float) -> dict[str, Any]:
    """دارایی‌های مجاز بر اساس ریسک‌پذیری:

      کم‌ریسک (<۴۰)   : فقط طلا، دلار، تتر
      متوسط (۴۰–۶۰)   : + بیت‌کوین و اتریوم
      پرریسک (≥۶۰)    : + آلت‌کوین‌ها
    """
    base = ["طلا", "دلار", "تتر"]
    if risk_pct < 40:
        return {"level": "low", "assets": base,
                "note": "به‌دلیل ریسک‌پذیری پایین، تنها دارایی‌های کم‌نوسان پیشنهاد می‌شود."}
    if risk_pct < 60:
        return {"level": "medium", "assets": base + ["بیت‌کوین", "اتریوم"],
                "note": "ترکیبی متعادل از دارایی‌های امن و دو ارز بزرگ بازار."}
    return {"level": "high", "assets": base + ["بیت‌کوین", "اتریوم", "آلت‌کوین‌ها"],
            "note": "به‌دلیل ریسک‌پذیری بالا، آلت‌کوین‌ها نیز به سبد افزوده می‌شوند."}


async def run_workflow(inputs: dict[str, Any], user: str) -> dict[str, Any]:
    """اجرای ورک‌فلوِ Dify و استخراج متن سبد پیشنهادی.

    خروجی: {"ok": bool, "text": str, "error": str|None, "raw": dict}
    """
    if not settings.dify_allocation_key:
        return {"ok": False, "text": "", "error": "no_key",
                "raw": {}}
    url = f"{settings.dify_allocation_base}/workflows/run"
    body = {"inputs": inputs, "response_mode": "blocking", "user": user}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            r = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.dify_allocation_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as exc:
        # بدنهٔ پاسخ خطا را برای تشخیص (کلید نامعتبر، ورک‌فلو منتشرنشده، …) برمی‌گردانیم.
        detail = (exc.response.text or "")[:300]
        return {"ok": False, "text": "",
                "error": f"http_{exc.response.status_code}: {detail}", "raw": {}}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "text": "", "error": str(exc), "raw": {}}

    inner = data.get("data") or {}
    # اگر ورک‌فلو داخلی شکست خورده باشد (مثلاً نود HTTP یا LLM)، Dify status=failed
    # و یک پیام error می‌دهد؛ آن را سطحی می‌کنیم تا علت معلوم شود.
    status = inner.get("status")
    if status and status != "succeeded":
        return {"ok": False, "text": "",
                "error": f"workflow_{status}: {inner.get('error') or ''}".strip(),
                "raw": inner.get("outputs") or {}}

    outputs = inner.get("outputs") or {}
    field = settings.dify_allocation_output
    text = outputs.get(field)
    if text is None:
        # تلاش برای یافتن اولین فیلد متنیِ خروجی
        for v in outputs.values():
            if isinstance(v, str) and v.strip():
                text = v
                break
    if not text:
        # خروجی خالی: احتمالاً نام فیلد End node با DIFY_ALLOCATION_OUTPUT یکی نیست.
        keys = ", ".join(outputs.keys()) or "—"
        return {"ok": False, "text": "",
                "error": f"empty (فیلدِ '{field}' یافت نشد؛ فیلدهای موجود: {keys})",
                "raw": outputs}
    return {"ok": True, "text": text, "error": None, "raw": outputs}
