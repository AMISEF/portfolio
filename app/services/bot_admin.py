"""پنلِ ادمینِ داخلِ ربات تلگرام «الگو هاب».

فقط برای شناسه‌های تلگرامیِ ادمین باز می‌شود (مالک همیشه ادمین است) و شاملِ
چهار بخش است:

  👤 مدیریت ادمین‌ها   — افزودن/حذف با شناسهٔ عددی یا نام کاربری
  🎟 فعال‌سازی اشتراک  — برای هر دو سایت، هر پلن و هر مدت؛ کاربر با ایمیل/
                          نام کاربری/شناسه پیدا می‌شود
  📊 گزارش عملکرد      — روزانه/هفتگی/ماهانه، برای هر سایت جداگانه
  📢 پیام همگانی       — هر نوع محتوای تلگرام، با تأییدِ «بله/خیر» و ارسالِ
                          کنترل‌شده و صف‌بندی‌شده (سقفِ ساعتی)

گفتگوهای چندمرحله‌ای در جدولِ bot_state نگه داشته می‌شوند تا ربات بدون حافظهٔ
درون‌فرایندی هم درست کار کند.
"""
from __future__ import annotations

from typing import Any

from app import db
from app.config import settings
from app.services import bot_chats, broadcast_job, journal_api

# ── برچسبِ دکمه‌ها ──────────────────────────────────────────────────────────
BTN_ADMIN = "🛠 پنل ادمین"
BTN_ADMINS = "👤 مدیریت ادمین‌ها"
BTN_SUBS = "🎟 فعال‌سازی اشتراک"
BTN_REPORTS = "📊 گزارش عملکرد سایت"
BTN_BROADCAST = "📢 ارسال پیام همگانی"
BTN_BACK = "🔙 بازگشت به منوی اصلی"

_PERIOD_FA = {"day": "روزانه", "week": "هفتگی", "month": "ماهانه"}
_PERIOD_DAYS = {"day": 1, "week": 7, "month": 30}

# پلن‌های پنل مدیریت سرمایه (از منبعِ واحدِ plans.py خوانده می‌شود).
PORTFOLIO_TIERS = [("bronze", "برنزی"), ("silver", "نقره‌ای"),
                   ("gold", "طلایی"), ("diamond", "الماسی")]
DURATIONS = [(1, "۱ ماهه"), (3, "۳ ماهه"), (6, "۶ ماهه"), (12, "سالانه")]


def config_admin_ids() -> set[str]:
    """ادمین‌های ثابتِ پیکربندی‌شده در .env (به‌علاوهٔ مالک)."""
    ids = {s.strip() for s in (settings.algohub_admin_ids or "").split(",") if s.strip()}
    owner = str(settings.algohub_owner_id or "").strip()
    if owner:
        ids.add(owner)
    return ids


def is_admin(tg_id: str | int | None) -> bool:
    """ادمین = مالک، یا در فهرستِ ثابتِ .env، یا در جدولِ bot_admins."""
    if tg_id is None:
        return False
    if str(tg_id) in config_admin_ids():
        return True
    return db.is_bot_admin(tg_id)


def is_owner(tg_id: str | int | None) -> bool:
    return str(tg_id) == str(settings.algohub_owner_id)


# ── کیبوردها ────────────────────────────────────────────────────────────────
def admin_menu_keyboard() -> dict[str, Any]:
    return {
        "keyboard": [[{"text": BTN_ADMINS}, {"text": BTN_SUBS}],
                     [{"text": BTN_REPORTS}, {"text": BTN_BROADCAST}],
                     [{"text": BTN_BACK}]],
        "resize_keyboard": True,
    }


def _inline(rows: list[list[tuple[str, str]]]) -> dict[str, Any]:
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row]
                                for row in rows]}


# ── متن‌ها ──────────────────────────────────────────────────────────────────
ADMIN_WELCOME = (
    "🛠 <b>پنل مدیریت الگو هاب</b>\n\n"
    "به پنل ادمین خوش آمدید. یکی از بخش‌های زیر را انتخاب کنید."
)

NOT_ADMIN = "⛔️ شما به پنل ادمین دسترسی ندارید."


def admins_text() -> str:
    rows = db.bot_admins()
    lines = ["👤 <b>مدیریت ادمین‌ها</b>", "",
             f"👑 مالک (غیرقابل حذف): <code>{settings.algohub_owner_id}</code>"]
    fixed = sorted(config_admin_ids() - {str(settings.algohub_owner_id or "").strip()})
    if fixed:
        lines.append("")
        lines.append("<b>ادمین‌های ثابت (از تنظیمات سرور):</b>")
        lines += [f"• <code>{i}</code>" for i in fixed]
    if rows:
        lines.append("")
        lines.append("<b>ادمین‌های افزوده‌شده:</b>")
        for r in rows:
            uname = f" — @{str(r['username']).lstrip('@')}" if r.get("username") else ""
            lines.append(f"• <code>{r['tg_id']}</code>{uname}")
    else:
        lines += ["", "هنوز ادمین دیگری اضافه نشده است."]
    lines += ["", "برای افزودن یا حذف، یکی از دکمه‌های زیر را بزنید."]
    return "\n".join(lines)


# ردیفِ «بازگشت» که به همهٔ کیبوردهای شیشه‌ای اضافه می‌شود تا کاربر هیچ‌وقت
# مجبور نشود برای برگشتن دوباره /start بزند.
BACK_ADMIN = ("🔙 بازگشت به پنل ادمین", "nav:admin")
BACK_HOME = ("🔙 بازگشت به منوی اصلی", "nav:home")


def admins_keyboard() -> dict[str, Any]:
    return _inline([
        [("➕ افزودن ادمین", "adm:add"), ("➖ حذف ادمین", "adm:del")],
        [("🔄 تازه‌سازی", "adm:list")],
        [BACK_ADMIN],
    ])


def sites_keyboard(prefix: str) -> dict[str, Any]:
    return _inline([
        [("💼 پنل مدیریت سرمایه", f"{prefix}:portfolio")],
        [("📊 پنل ژورنال تریدینگ", f"{prefix}:journal")],
        [BACK_ADMIN],
    ])


def tiers_keyboard(site: str) -> dict[str, Any]:
    tiers = PORTFOLIO_TIERS if site == "portfolio" else journal_api.TIERS
    rows = [[(fa, f"sub:tier:{site}:{key}")] for key, fa in tiers]
    rows.append([("🔙 انتخاب کاربرِ دیگر", f"sub:site:{site}")])
    rows.append([BACK_ADMIN])
    return _inline(rows)


def durations_keyboard(site: str, tier: str) -> dict[str, Any]:
    if tier == "bronze":
        # پلنِ رایگان مدت ندارد.
        return _inline([[("ثبت پلن رایگان", f"sub:dur:{site}:{tier}:0")],
                        [("🔙 انتخاب پلنِ دیگر", f"sub:back-tier:{site}")],
                        [BACK_ADMIN]])
    rows = [[(fa, f"sub:dur:{site}:{tier}:{m}")] for m, fa in DURATIONS]
    rows.append([("🔙 انتخاب پلنِ دیگر", f"sub:back-tier:{site}")])
    rows.append([BACK_ADMIN])
    return _inline(rows)


def periods_keyboard(site: str) -> dict[str, Any]:
    return _inline([
        [(_PERIOD_FA[p], f"rep:{site}:{p}") for p in ("day", "week", "month")],
        [("🔙 انتخاب سایتِ دیگر", "rep:pick")],
        [BACK_ADMIN],
    ])


def confirm_keyboard() -> dict[str, Any]:
    return _inline([[("✅ بله، ارسال کن", "bc:yes"), ("❌ خیر، لغو", "bc:no")]])


def cancel_keyboard() -> dict[str, Any]:
    """کیبوردِ تک‌دکمه‌ایِ انصراف برای گام‌هایی که کاربر باید متن بفرستد."""
    return _inline([[("🔙 انصراف و بازگشت به پنل ادمین", "nav:admin")]])


def broadcast_status_keyboard() -> dict[str, Any]:
    return _inline([[("🔄 وضعیت ارسال", "bc:status")], [BACK_ADMIN]])


# ── گزارش‌ها ────────────────────────────────────────────────────────────────
def _fa(n: Any) -> str:
    s = f"{int(n):,}" if isinstance(n, (int, float)) else str(n)
    fa = "۰۱۲۳۴۵۶۷۸۹"
    return "".join(fa[int(c)] if c.isdigit() else c for c in s).replace(",", "٬")


def _tier_fa(key: str, site: str) -> str:
    table = dict(PORTFOLIO_TIERS if site == "portfolio" else journal_api.TIERS)
    return table.get(key, key)


def portfolio_report(period: str) -> str:
    days = _PERIOD_DAYS.get(period, 1)
    s = db.portfolio_stats(days)
    u, a, al, lk = s["users"], s["assets"], s["alerts"], s["links"]
    lines = [
        f"💼 <b>گزارش عملکرد — پنل مدیریت سرمایه</b>",
        f"🗓 بازه: <b>{_PERIOD_FA.get(period, period)}</b>", "",
        "👥 <b>کاربران</b>",
        f"• کل کاربران: <b>{_fa(u['total'])}</b>",
        f"• کاربران جدید در این بازه: <b>{_fa(u['new'])}</b>",
        f"• دارای اشتراک فعال: <b>{_fa(u['paid'])}</b>", "",
        "🎟 <b>اشتراک‌ها به تفکیک پلن</b>",
    ]
    for key, fa in PORTFOLIO_TIERS:
        lines.append(f"• {fa}: <b>{_fa(s['by_tier'].get(key, 0))}</b>")
    lines += ["", "⏳ <b>اشتراک‌ها به تفکیک مدت</b>"]
    for fa, n in s["by_duration"].items():
        lines.append(f"• {fa}: <b>{_fa(n)}</b>")
    lines += [
        "", "📈 <b>فعالیت</b>",
        f"• دارایی ثبت‌شده در این بازه: <b>{_fa(a['new'])}</b> (کل: {_fa(a['total'])})",
        f"• آزمون ریسک تکمیل‌شده: <b>{_fa(s['risk_profiles'])}</b>",
        f"• سبدچینی هوش مصنوعی (دورهٔ جاری): <b>{_fa(s['ai_allocations'])}</b>",
        f"• هشدار فعال: <b>{_fa(al['active'])}</b> — شلیک‌شده در بازه: <b>{_fa(al['fired'])}</b>",
        "", "🔗 <b>اتصال‌ها</b>",
        f"• متصل به ربات تلگرام: <b>{_fa(lk['telegram'])}</b>",
        f"• کاربرانِ ثبت‌شدهٔ ربات (مقصدِ پیام همگانی): <b>{_fa(bot_chats.count())}</b>",
        f"• متصل به API توبیت: <b>{_fa(lk['toobit'])}</b>",
        f"• دارای سبد پیشنهادی ذخیره‌شده: <b>{_fa(lk['picks'])}</b>",
    ]
    return "\n".join(lines)


def journal_report(period: str, s: dict[str, Any]) -> str:
    u, t, ai = s["users"], s["trades"], s["ai"]
    lines = [
        "📊 <b>گزارش عملکرد — پنل ژورنال تریدینگ</b>",
        f"🗓 بازه: <b>{_PERIOD_FA.get(period, period)}</b>", "",
        "👥 <b>کاربران</b>",
        f"• کل کاربران: <b>{_fa(u['total'])}</b>",
        f"• کاربران جدید در این بازه: <b>{_fa(u['new'])}</b>",
        f"• دارای اشتراک فعال: <b>{_fa(u['paid'])}</b>", "",
        "🎟 <b>اشتراک‌ها به تفکیک پلن</b>",
    ]
    for key, fa in journal_api.TIERS:
        lines.append(f"• {fa}: <b>{_fa(s['by_tier'].get(key, 0))}</b>")
    lines += ["", "⏳ <b>اشتراک‌ها به تفکیک مدت</b>"]
    for fa, n in s["by_duration"].items():
        lines.append(f"• {fa}: <b>{_fa(n)}</b>")
    lines += [
        "", "📒 <b>ژورنال‌ها</b>",
        f"• ثبت‌شده در این بازه: <b>{_fa(t['created'])}</b>",
        f"• مجموع ژورنال‌ها: <b>{_fa(t['total'])}</b>",
        "", "🤖 <b>تحلیل هوش مصنوعی در این بازه</b>",
        f"• تحلیل تک‌معامله: <b>{_fa(ai['trade'])}</b>",
        f"• مربی هوش مصنوعی: <b>{_fa(ai['coach'])}</b>",
        f"• گزارش نهادی: <b>{_fa(ai['report'])}</b>",
        f"• مجموع: <b>{_fa(ai['total'])}</b>",
    ]
    return "\n".join(lines)


# ── فعال‌سازیِ اشتراک ────────────────────────────────────────────────────────
def portfolio_lookup(term: str) -> list[dict[str, Any]]:
    """جستجوی کاربرِ پنل مدیریت سرمایه با ایمیل/نام کاربری/شناسه."""
    term = (term or "").strip().lower()
    if not term:
        return []
    out = []
    for u in db.list_users():
        hay = " ".join(str(u.get(k) or "").lower()
                       for k in ("email", "username", "user_code", "id"))
        if term in hay:
            out.append(u)
        if len(out) >= 10:
            break
    return out


def user_line(u: dict[str, Any], site: str) -> str:
    if site == "portfolio":
        from app.services import plans
        tier = plans.tier_of(u)
        name = " ".join(x for x in [u.get("first_name"), u.get("last_name")] if x) or "—"
        return (f"👤 <b>{name}</b>\n"
                f"✉️ <code>{u.get('email') or '—'}</code>\n"
                f"🆔 {u.get('user_code') or u.get('id')} • پلن فعلی: "
                f"<b>{_tier_fa(tier, site)}</b>")
    name = u.get("fullName") or u.get("username") or "—"
    return (f"👤 <b>{name}</b>\n"
            f"✉️ <code>{u.get('email') or '—'}</code>\n"
            f"🆔 {u.get('id')} • پلن فعلی: <b>{_tier_fa(u.get('tier') or '', site)}</b>")


def apply_portfolio_plan(user_id: int, tier: str, months: int) -> str:
    """اعمالِ پلن روی کاربرِ پنل مدیریت سرمایه و بازگرداندنِ خلاصهٔ نتیجه."""
    import datetime as _dt
    fields: dict[str, Any] = {"subscription": tier}
    if tier == "bronze" or not months:
        fields["sub_expires_at"] = None
        exp_fa = "بدون انقضا"
    else:
        exp = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(days=round(months * 30.44))
        fields["sub_expires_at"] = exp.strftime("%Y-%m-%d %H:%M:%S")
        exp_fa = exp.strftime("%Y-%m-%d")
    db.admin_update_user(int(user_id), fields)
    return exp_fa


# ── پیام همگانی ─────────────────────────────────────────────────────────────
BROADCAST_PROMPT = (
    "📢 <b>ارسال پیام همگانی</b>\n\n"
    "پیام موردنظر خود را همین‌جا بفرستید. هر نوع محتوایی پشتیبانی می‌شود:\n"
    "متن، عکس، ویدیو، ویس، فایل، استیکر، گیف، ایموجی متحرک، لینک و …\n\n"
    "پس از ارسال، پیش از انتشار از شما تأیید گرفته می‌شود.\n"
    "برای انصراف، دکمهٔ «🔙 بازگشت» را بزنید."
)


def broadcast_targets() -> list[str]:
    """مقصدهای پیامِ همگانی: هر چتی که تاکنون با ربات تعامل داشته است.

    این فهرست دائمی است؛ کاربر لازم نیست برای هر پیامِ همگانیِ جدید دوباره ربات
    را استارت کند.
    """
    return bot_chats.known_chats()


def broadcast_confirm_text(n: int | None = None) -> str:
    """متنِ تأیید. شمارش از همان منبعِ مقصدهای ارسال خوانده می‌شود تا عددِ
    نمایش‌داده‌شده و تعدادِ واقعیِ دریافت‌کنندگان یکی باشد."""
    total = len(broadcast_targets())
    eta = broadcast_job.eta_minutes(total)
    return (
        "⚠️ <b>تأیید ارسال پیام همگانی</b>\n\n"
        f"این پیام برای <b>{_fa(total)}</b> کاربرِ ربات ارسال خواهد شد.\n"
        f"⚙️ ارسال کنترل‌شده است: حداکثر <b>{_fa(broadcast_job.HOURLY_LIMIT)}</b> "
        "پیام در هر ساعت، تا سرور تحت فشار قرار نگیرد.\n"
        f"⏱ زمان تقریبی تکمیل: <b>{_fa(eta)}</b> دقیقه\n\n"
        "آیا از ارسال این پیام مطمئن هستید؟"
    )


def broadcast_enqueue(from_chat: str, message_id: int,
                      created_by: str | int | None = None) -> dict[str, Any]:
    """ثبتِ پیام در صفِ ارسالِ کنترل‌شده (ارسالِ واقعی در پس‌زمینه انجام می‌شود)."""
    return broadcast_job.enqueue(from_chat, int(message_id),
                                 broadcast_targets(), created_by)


def broadcast_queued_text(info: dict[str, Any]) -> str:
    return (
        "🚀 <b>ارسال پیام همگانی آغاز شد</b>\n\n"
        f"👥 مقصدها: <b>{_fa(info.get('total', 0))}</b> کاربر\n"
        f"⚙️ سقف ارسال: <b>{_fa(broadcast_job.HOURLY_LIMIT)}</b> پیام در ساعت\n"
        f"⏱ زمان تقریبی تکمیل: <b>{_fa(info.get('eta_minutes', 0))}</b> دقیقه\n\n"
        "ارسال در پس‌زمینه و به‌صورت تدریجی انجام می‌شود؛ می‌توانید ربات را ببندید.\n"
        "در پایان، خلاصهٔ نتیجه برای شما ارسال خواهد شد.\n"
        "برای دیدنِ پیشرفت، دکمهٔ «🔄 وضعیت ارسال» را بزنید."
    )


_JOB_STATUS_FA = {"running": "در حال ارسال", "done": "تکمیل‌شده",
                  "cancelled": "لغوشده"}


def broadcast_status_text() -> str:
    """وضعیتِ لحظه‌ایِ آخرین ارسالِ همگانی."""
    p = broadcast_job.progress()
    if not p:
        return ("📭 هنوز هیچ پیام همگانی‌ای ارسال نشده است.\n\n"
                f"👥 مقصدهای فعلی: <b>{_fa(len(broadcast_targets()))}</b> کاربر")
    status_fa = _JOB_STATUS_FA.get(str(p.get("status")), str(p.get("status")))
    lines = [
        "📊 <b>وضعیت ارسال پیام همگانی</b>", "",
        f"🔖 وضعیت: <b>{status_fa}</b>",
        f"👥 مجموع مقصدها: <b>{_fa(p.get('total', 0))}</b>",
        f"📨 ارسال‌شده: <b>{_fa(p.get('sent', 0))}</b>",
        f"🕓 در انتظار: <b>{_fa(p.get('pending', 0))}</b>",
        f"⚠️ ناموفق: <b>{_fa(p.get('failed', 0))}</b>",
    ]
    if p.get("status") == "running":
        lines += [
            "",
            f"⚙️ سقف ساعتی: <b>{_fa(p.get('hourly_limit', 0))}</b> پیام",
            f"🎟 سهمیهٔ باقی‌ماندهٔ این ساعت: <b>{_fa(p.get('quota_left', 0))}</b>",
            f"⏱ زمان تقریبی باقی‌مانده: <b>{_fa(p.get('eta_minutes', 0))}</b> دقیقه",
        ]
    return "\n".join(lines)


async def broadcast(copy_from_chat: str, message_id: int, send_copy=None) -> dict[str, int]:
    """سازگاری با گذشته: پیام را در صف می‌گذارد (ارسال در پس‌زمینه انجام می‌شود)."""
    info = broadcast_enqueue(copy_from_chat, int(message_id))
    return {"sent": 0, "failed": 0, "queued": int(info.get("total", 0)),
            "total": int(info.get("total", 0)), "job_id": int(info.get("job_id", 0))}
