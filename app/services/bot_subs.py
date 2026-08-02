"""متن‌ها و فهرستِ پلن‌های اشتراکِ ربات «الگو هاب».

این ماژول از algohub_bot.py جدا شده تا متن‌های بلندِ فارسی در یک جای مشخص
نگهداری شوند:

  • JOURNAL_PLANS — پلن‌های پنل ژورنال تریدینگ (هم‌راستا با
    frontend/src/lib/plans.ts و backend/app/services/plans.py پروژهٔ ژورنال).
  • پلن‌های پنل مدیریت سرمایه از منبعِ واحدِ app/services/plans.py ساخته می‌شوند.
  • بلوکِ روش‌های پرداخت و پیامِ آمادهٔ پیویِ پشتیبانی.

نکتهٔ پلن رایگان (برنزی) ژورنال: ۲۰ ژورنال، ۱ تحلیل تک‌معامله و ۱ بار مربی هوش
مصنوعی — پس از آن کاربر باید اشتراک تهیه کند.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

from app.config import settings
from app.services import plans


# ──────────────────────── کمکی‌های قالب‌بندی ───────────────────────
def esc(s: Any) -> str:
    """گریزِ کاراکترهای HTML برای parse_mode=HTML تلگرام."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fa_digits(s: Any) -> str:
    fa = "۰۱۲۳۴۵۶۷۸۹"
    return "".join(fa[int(c)] if c.isdigit() else c for c in str(s))


def toman(n: int) -> str:
    # جداکنندهٔ هزارگانِ فارسی (٬) به‌جای کاماى لاتین.
    return fa_digits(f"{int(n):,}").replace(",", "٬") + " تومان"


def footer() -> str:
    """پاورقیِ نقل‌قولیِ (blockquote) تلگرام: شناسهٔ کانال + وب‌سایت."""
    ch = settings.algohub_channel_username
    site = settings.algohub_website_url
    return (
        "<blockquote>"
        f"🆔 {esc(ch)}\n"
        f'🌐 <a href="{esc(site)}">Website</a>'
        "</blockquote>"
    )


def with_footer(body: str) -> str:
    return f"{body}\n\n{footer()}"


# ──────────────────────── پلن‌های پنل ژورنال ───────────────────────
# قیمتِ ماهانه — هر تغییری در frontend/src/lib/plans.ts باید اینجا هم بازتاب یابد.
JOURNAL_PLANS = [
    {
        "key": "bronze", "name": "برنزی", "emoji": "🥉", "monthly": 0,
        "tagline": "شروعِ رایگان: ۲۰ ژورنال و یک بار چشیدنِ تحلیلِ هوش مصنوعی",
        "features": [
            "ثبت ۲۰ معامله با تمام جزئیات: ورود پله‌ای، حد ضرر، تارگت، تصویر چارت، چک‌لیست و احساسات",
            "۱ تحلیل تک‌معامله با هوش مصنوعی — یک بار، برای آشنایی با کیفیت تحلیل",
            "۱ بار مربی هوش مصنوعی روی کل ژورنال: نقاط قوت، نشتی‌های پول و برنامهٔ بهبود",
            "داشبورد کامل: وین‌ریت، فاکتور سود، R:R و منحنی رشد سرمایه",
            "پس از این سقف، برای ثبت معاملهٔ بیشتر و تحلیلِ بیشتر باید یکی از پلن‌های اشتراکی تهیه شود",
        ],
    },
    {
        "key": "silver", "name": "نقره‌ای", "emoji": "🥈", "monthly": 349000,
        "tagline": "هر هفته یک گزارش که می‌گوید پولت از کجا نشت می‌کند",
        "features": [
            "ثبت تا ۱۰۰ معامله با تمام جزئیات",
            "تحلیل نامحدود هوش مصنوعی روی هر معامله",
            "مربی هوش مصنوعی روی کل ژورنال، هفته‌ای ۱ بار: نقاط قوت، نشتی‌های پول و برنامهٔ ۷ روزهٔ بهبود",
            "گفتگوی نامحدود با مربی دربارهٔ همان تحلیل‌ها",
        ],
    },
    {
        "key": "gold", "name": "طلایی", "emoji": "🥇", "monthly": 999000,
        "tagline": "ریتمِ تریدرِ تمام‌وقت: بازخوردِ روزانه پیش از اشتباهِ بعدی",
        "features": [
            "ثبت نامحدود معامله — بدون هیچ سقفی",
            "تحلیل نامحدود هوش مصنوعی روی تک‌تک معاملات",
            "مربی هوش مصنوعی، هر روز ۱ بار: عیب‌یابیِ روزانه پیش از باز کردن پوزیشن بعدی",
            "گزارش نهادی و بانکی، هفته‌ای ۱ بار — همان استانداردی که پراپ‌فرم‌ها با آن سرمایه می‌دهند",
            "خروجی PDF گزارش نهادی برای ارائه به سرمایه‌گذار",
        ],
    },
    {
        "key": "diamond", "name": "الماسی", "emoji": "💎", "monthly": 1999000,
        "tagline": "بدون سقف، بدون صف، بدون ثبت دستی — کل میزِ تحلیل در اختیار تو",
        "features": [
            "ثبت نامحدود معامله و تحلیل نامحدود هوش مصنوعی روی هر معامله",
            "مربی هوش مصنوعی نامحدود: بعد از هر معامله، هر ساعت، بدون هیچ صف انتظاری",
            "گزارش نهادی و بانکی نامحدود: اثرِ هر تغییرِ استراتژی را بلافاصله بسنج",
            "اتصال مستقیم به صرافی توبیت (فقط در این پلن): معاملات فیوچرز خودکار ژورنال می‌شوند — بدون نیاز به ثبت دستی ژورنال",
            "خروجی PDF نهادی برای ارائه به سرمایه‌گذار و پراپ‌فرم",
        ],
    },
]


# ──────────────────────── پلن‌های پنل مدیریت سرمایه ───────────────────────
def _portfolio_features(p: dict[str, Any]) -> list[str]:
    """امکاناتِ هر پلنِ مدیریت سرمایه، ساخته‌شده از منبعِ واحدِ plans.py."""
    quota = p.get("ai_quota")
    per_fa = "سال" if p.get("ai_period") == "year" else "ماه"
    out: list[str] = []
    if quota is None:
        out.append("سبدچینی نامحدود با هوش مصنوعی")
    elif not quota:
        out.append("بدون سبدچینی هوش مصنوعی")
    else:
        out.append(f"{fa_digits(quota)} اعتبار سبدچینی هوش مصنوعی در {per_fa}")
    out.append("دسترسی به بخش «تحلیل اختصاصی»" if p.get("exclusive")
               else "بدون دسترسی به بخش «تحلیل اختصاصی»")
    out.append("ثبت و مدیریت نامحدود دارایی + سود و زیان لحظه‌ای")
    if p.get("weekly_report"):
        out.append("گزارش هفتگی وضعیت سبد")
    if p.get("direct_manager"):
        out.append("ارتباط مستقیم با مدیر مجموعه")
    out.append(f"پشتیبانی: {p.get('support') or 'عمومی'}")
    return out


def portfolio_plans() -> list[dict[str, Any]]:
    """همهٔ پلن‌های پنل مدیریت سرمایه از منبعِ واحدِ plans.py."""
    emoji = {"bronze": "🥉", "silver": "🥈", "gold": "🥇", "diamond": "💎"}
    out = []
    for key in ("bronze", "silver", "gold", "diamond"):
        p = plans.PLANS.get(key)
        if not p:
            continue
        out.append({
            "key": key,
            "name": p["name_fa"],
            "emoji": emoji.get(key, "✨"),
            "price": int(p["price"]),
            "original_price": p.get("original_price"),
            "period_fa": "سالانه" if p.get("period") == "year" else "ماهانه",
            "tagline": p.get("best_for", ""),
            "desc": p.get("desc_fa", ""),
            "features": _portfolio_features(p),
        })
    return out


# ──────────────────────── پیامِ خرید و بلوکِ پلن ───────────────────────
def support_link(message: str) -> str:
    """لینکِ پیویِ پشتیبانی با پیامِ از پیش نوشته‌شده."""
    return f"{settings.support_url.rstrip('/')}?text={quote(message)}"


def purchase_message(plan_name: str, product: str, period_fa: str,
                     price_fa: str) -> str:
    """پیامِ رسمیِ آماده که در پیویِ پشتیبانی نوشته می‌شود."""
    return (
        "سلام؛ وقت بخیر.\n"
        f"مایل به تهیهٔ اشتراک «{plan_name}» {product} "
        f"({period_fa} — {price_fa}) هستم.\n"
        "مبلغ را واریز کرده‌ام و رسید پرداخت را در همین گفتگو ارسال می‌کنم.\n"
        "لطفاً راهنمایی بفرمایید. سپاسگزارم."
    )


def plan_block(emoji: str, name: str, price_line: str, tagline: str,
               features: list[str]) -> list[str]:
    """بلوکِ نمایشیِ یک پلن: سرتیتر، شعار و فهرستِ امکانات."""
    lines = [f"{emoji} <b>{esc(name)}</b> — {price_line}"]
    if tagline:
        lines.append(f"<i>{esc(tagline)}</i>")
    lines += [f"   ✅ {esc(f)}" for f in features]
    lines.append("")
    return lines


# ──────────────────────── راهنمای پرداخت ───────────────────────
USDT_TRC20 = "TKnDWJ6PXt7CAjXEEvUnoJbD9QwnCwGyCL"
USDT_BEP20 = "0x723B04ABAAFF8524F98d4b60B20Fff67920A48A5"
TOOBIT_UID = "129107184"


def payment_block() -> list[str]:
    """بخشِ «روش‌های پرداخت» — آدرس‌ها داخلِ <code> تا با یک لمس کپی شوند."""
    return [
        "━━━━━━━━━━━━━━━",
        "💳 <b>روش‌های پرداخت و فعال‌سازی</b>",
        "",
        "💵 <b>پرداخت ارزی — تتر (USDT)</b>",
        "پیش از واریز، از تطابقِ شبکه اطمینان حاصل فرمایید.",
        "",
        "🔹 شبکهٔ <b>TRC20</b> (ترون):",
        f"<code>{USDT_TRC20}</code>",
        "",
        "🔹 شبکهٔ <b>BEP20</b> (بایننس اسمارت چین):",
        f"<code>{USDT_BEP20}</code>",
        "",
        "🪙 <b>انتقال داخلی صرافی توبیت — بدون کارمزد</b>",
        "در صورت استفاده از انتقال داخلی، هیچ کارمزدی از شما کسر نمی‌شود.",
        f"شناسهٔ کاربری (UID): <code>{TOOBIT_UID}</code>",
        "",
        "🛫 <b>پرداخت ریالی</b>",
        "تمامی اشتراک‌ها به‌صورت ریالی نیز قابل تهیه است؛ جهت دریافت شمارهٔ کارت "
        "با پشتیبانی در ارتباط باشید.",
        "",
        "👆 با لمسِ هر آدرس، به‌صورت خودکار کپی می‌شود.",
        "━━━━━━━━━━━━━━━",
        "",
        "📤 <b>پس از واریز:</b> روی دکمهٔ پلنِ موردنظر در پایین بزنید تا به "
        "پشتیبانی متصل شوید؛ پیام درخواست به‌صورت آماده نوشته می‌شود و کافی است "
        "<b>تصویر رسید پرداخت</b> را همان‌جا ارسال کنید.",
    ]


# ──────────────────────── پیام‌های اشتراک ───────────────────────
def portfolio_subscription_message() -> tuple[str, dict]:
    """متن + کیبوردِ شیشه‌ایِ اشتراک‌های پنل مدیریت سرمایه."""
    lines = [
        "💼 <b>اشتراک‌های پنل مدیریت سرمایه الگو هاب</b>",
        "",
        "با فعال‌سازی اشتراک، به سبدچینی هوش مصنوعی، تحلیل‌های اختصاصی بازار و "
        "پشتیبانی تیم الگو هاب دسترسی خواهید داشت.",
        "",
    ]
    buttons: list[list[dict[str, str]]] = []
    for p in portfolio_plans():
        if p["price"] <= 0:
            lines += plan_block(p["emoji"], p["name"], "<b>رایگان</b>",
                                p["tagline"], p["features"])
            continue
        price_fa = toman(p["price"])
        price_line = f"{esc(price_fa)} ({p['period_fa']})"
        if p.get("original_price"):
            price_line = (f"<s>{esc(toman(int(p['original_price'])))}</s> "
                          f"{price_line}")
        lines += plan_block(p["emoji"], p["name"], price_line,
                            p["tagline"], p["features"])
        msg = purchase_message(p["name"], "پنل مدیریت سرمایه الگو هاب",
                               p["period_fa"], price_fa)
        buttons.append([{
            "text": f"{p['emoji']} اشتراک {p['name']} — {price_fa}",
            "url": support_link(msg),
        }])
    lines += payment_block()
    buttons.append([{"text": "💬 گفتگو با پشتیبانی", "url": settings.support_url}])
    buttons.append([{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "nav:home"}])
    return with_footer("\n".join(lines)), {"inline_keyboard": buttons}


def journal_subscription_message() -> tuple[str, dict]:
    """متن + کیبوردِ شیشه‌ایِ اشتراک‌های پنل ژورنال تریدینگ."""
    lines = [
        "📊 <b>اشتراک‌های پنل ژورنال تریدینگ الگو هاب</b>",
        "",
        "ثبت حرفه‌ایِ معاملات، داشبورد و منحنی سرمایه، تحلیل هوش مصنوعی روی تک‌تک "
        "معاملات، مربی هوش مصنوعی و گزارش نهادی.",
        "",
        "🆓 <b>پلن برنزی رایگان است:</b> ۲۰ ژورنال، ۱ تحلیل تک‌معامله و ۱ بار مربی "
        "هوش مصنوعی. پس از آن، برای ادامه باید یکی از پلن‌های زیر را تهیه کنید.",
        "",
    ]
    buttons: list[list[dict[str, str]]] = []
    for p in JOURNAL_PLANS:
        if p["monthly"] <= 0:
            lines += plan_block(p["emoji"], p["name"], "<b>رایگان</b>",
                                p["tagline"], p["features"])
            continue
        price_fa = toman(p["monthly"])
        lines += plan_block(p["emoji"], p["name"], f"{esc(price_fa)} (ماهانه)",
                            p["tagline"], p["features"])
        msg = purchase_message(p["name"], "پنل ژورنال تریدینگ الگو هاب",
                               "ماهانه", price_fa)
        buttons.append([{
            "text": f"{p['emoji']} اشتراک {p['name']} — {price_fa}",
            "url": support_link(msg),
        }])
    lines += [
        "💡 با خرید ۳، ۶ یا ۱۲ ماهه تا ۳۳٪ تخفیف بگیرید — برای دورهٔ بلندتر با "
        "پشتیبانی در ارتباط باشید.",
        "",
    ] + payment_block()
    buttons.append([{"text": "💬 گفتگو با پشتیبانی", "url": settings.support_url}])
    buttons.append([{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "nav:home"}])
    return with_footer("\n".join(lines)), {"inline_keyboard": buttons}
