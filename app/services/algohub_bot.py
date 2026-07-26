"""ربات تلگرام «الگو هاب» (Algohub_Cryptosmart_bot).

این ربات، ربات کاربریِ پنل مدیریت سرمایه است و سه کار می‌کند:

  ۱) اتصالِ حساب: کاربر در پنل دکمهٔ اتصال را می‌زند و لینکِ
     https://t.me/<bot>?start=<token> باز می‌شود؛ ربات chat_id او را ذخیره
     می‌کند تا بتوان هشدار فرستاد.
  ۲) هشدارِ قیمتِ خرید: وقتی ارزِ پیشنهادیِ سبدچینیِ هوش مصنوعی به قیمتِ هدف
     رسید، پیامِ رسمی با ایموجی، نام ارز و قیمت برای کاربر ارسال می‌شود.
  ۳) خرید اشتراک: دو دکمه (مدیریت سرمایه / ژورنال تریدینگ) که فهرستِ قیمت‌ها را
     با دکمه‌های شیشه‌ایِ (inline) هر پلن نشان می‌دهند؛ کلیک روی هر پلن کاربر را
     با یک پیامِ رسمیِ آماده به پیویِ پشتیبانی می‌برد.

توکن فقط از .env خوانده می‌شود (ALGOHUB_BOT_TOKEN) و هرگز در کد نیست.
"""
from __future__ import annotations

import json
import secrets
from typing import Any
from urllib.parse import quote

import httpx

from app import db
from app.config import settings
from app.services import bot_admin as ba, journal_api, plans

_API = "https://api.telegram.org"
_ALLOWED_UPDATES = ["message", "callback_query"]

BTN_PORTFOLIO_SUB = "💼 خرید اشتراک مدیریت سرمایه الگو هاب"
BTN_JOURNAL_SUB = "📊 خرید اشتراک ژورنال تریدینگ الگو هاب"


def _token() -> str:
    return settings.algohub_bot_token or ""


def is_enabled() -> bool:
    return bool(_token())


# ───────────────────────── پاورقیِ مشترکِ همهٔ پیام‌ها ─────────────────────────
def footer() -> str:
    """پاورقیِ نقل‌قولیِ (blockquote) تلگرام: شناسهٔ کانال + وب‌سایت."""
    ch = settings.algohub_channel_username
    site = settings.algohub_website_url
    return (
        "<blockquote>"
        f"🆔 {_esc(ch)}\n"
        f'🌐 <a href="{_esc(site)}">Website</a>'
        "</blockquote>"
    )


def _esc(s: Any) -> str:
    """گریزِ کاراکترهای HTML برای parse_mode=HTML تلگرام."""
    return (
        str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _with_footer(body: str) -> str:
    return f"{body}\n\n{footer()}"


# ───────────────────────── ارسال پیام ─────────────────────────
async def send_message(chat_id: str | int, text: str,
                       reply_markup: dict | None = None) -> bool:
    token = _token()
    if not token:
        return False
    data: dict[str, Any] = {
        "chat_id": str(chat_id),
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }
    if reply_markup is not None:
        data["reply_markup"] = json.dumps(reply_markup)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
            r = await client.post(f"{_API}/bot{token}/sendMessage", data=data)
            return r.is_success
    except Exception:  # noqa: BLE001
        return False


async def copy_message(to_chat: str | int, from_chat: str | int,
                       message_id: int) -> bool:
    """کپیِ یک پیام به چتِ دیگر — هر نوع محتوایی را بدون برچسبِ فوروارد می‌فرستد."""
    token = _token()
    if not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
            r = await client.post(f"{_API}/bot{token}/copyMessage", data={
                "chat_id": str(to_chat),
                "from_chat_id": str(from_chat),
                "message_id": int(message_id),
            })
            return r.is_success
    except Exception:  # noqa: BLE001
        return False


async def _answer_callback(callback_id: str, text: str = "") -> None:
    token = _token()
    if not token:
        return
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            data = {"callback_query_id": callback_id}
            if text:
                data["text"] = text
            await client.post(f"{_API}/bot{token}/answerCallbackQuery", data=data)
    except Exception:  # noqa: BLE001
        pass


# ───────────────────────── ثبت وب‌هوک ─────────────────────────
async def register_webhook() -> dict[str, Any]:
    """ثبتِ idempotentِ وب‌هوک. بدون توکن کاری نمی‌کند."""
    token = _token()
    if not token:
        return {"ok": False, "skipped": "no_token"}
    url = f"{settings.public_base_url.rstrip('/')}/api/bot/algohub/webhook"
    secret = settings.signals_webhook_secret_effective
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
            info = await client.get(f"{_API}/bot{token}/getWebhookInfo")
            cur = (info.json().get("result") or {}) if info.is_success else {}
            if (cur.get("url") == url
                    and set(cur.get("allowed_updates") or []) == set(_ALLOWED_UPDATES)):
                return {"ok": True, "already": True, "url": url}
            r = await client.post(
                f"{_API}/bot{token}/setWebhook",
                json={
                    "url": url,
                    "secret_token": secret,
                    "allowed_updates": _ALLOWED_UPDATES,
                    "drop_pending_updates": False,
                },
            )
            return {"ok": r.is_success, "url": url, "response": r.json()}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


# ───────────────────────── اتصالِ حسابِ پنل ─────────────────────────
def new_link_token(user_id: int) -> str:
    """ساختِ توکنِ یک‌بارمصرفِ اتصال و بازگرداندنِ لینکِ deep-link ربات."""
    token = secrets.token_urlsafe(16)
    db.tg_set_link_token(int(user_id), token)
    return token


def link_url(token: str) -> str:
    return f"{settings.algohub_bot_url.rstrip('/')}?start={quote(token)}"


# ───────────────────────── فهرست قیمت اشتراک‌ها ─────────────────────────
def _fa_digits(s: Any) -> str:
    fa = "۰۱۲۳۴۵۶۷۸۹"
    return "".join(fa[int(c)] if c.isdigit() else c for c in str(s))


def _toman(n: int) -> str:
    # جداکنندهٔ هزارگانِ فارسی (٬) به‌جای کاماى لاتین.
    return _fa_digits(f"{int(n):,}").replace(",", "٬") + " تومان"


# پلن‌های پنل ژورنال تریدینگ (قیمت ماهانه). با صفحهٔ اشتراکِ ژورنال هم‌راستاست.
JOURNAL_PLANS = [
    {"key": "silver", "name": "نقره‌ای", "emoji": "🥈", "monthly": 349000},
    {"key": "gold", "name": "طلایی", "emoji": "🥇", "monthly": 999000},
]


def _portfolio_plans() -> list[dict[str, Any]]:
    """پلن‌های پولیِ پنل مدیریت سرمایه از منبعِ واحدِ plans.py."""
    emoji = {"silver": "🥈", "gold": "🥇", "diamond": "💎"}
    out = []
    for key in ("silver", "gold", "diamond"):
        p = plans.PLANS.get(key)
        if not p:
            continue
        out.append({
            "key": key,
            "name": p["name_fa"],
            "emoji": emoji.get(key, "✨"),
            "price": int(p["price"]),
            "period_fa": "سالانه" if p.get("period") == "year" else "ماهانه",
            "desc": p.get("desc_fa", ""),
        })
    return out


def _support_link(message: str) -> str:
    """لینکِ پیویِ پشتیبانی با پیامِ از پیش نوشته‌شده."""
    return f"{settings.support_url.rstrip('/')}?text={quote(message)}"


def _purchase_message(plan_name: str, product: str, period_fa: str, price_fa: str) -> str:
    """پیامِ رسمیِ آماده که در پیویِ پشتیبانی نوشته می‌شود.

    کاربر پس از واریز روی دکمهٔ پلن می‌زند؛ این متن در پیویِ پشتیبانی نوشته
    می‌شود و بلافاصله می‌تواند تصویرِ رسیدِ واریز را همان‌جا بفرستد.
    """
    return (
        "سلام؛ وقت بخیر.\n"
        f"مایل به تهیهٔ اشتراک «{plan_name}» {product} "
        f"({period_fa} — {price_fa}) هستم.\n"
        "مبلغ را واریز کرده‌ام و رسید پرداخت را در همین گفتگو ارسال می‌کنم.\n"
        "لطفاً راهنمایی بفرمایید. سپاسگزارم."
    )


# ───────────────────────── راهنمای پرداخت ─────────────────────────
# آدرس‌های واریز و شناسهٔ توبیت — در هر دو پیامِ اشتراک نمایش داده می‌شوند.
USDT_TRC20 = "TKnDWJ6PXt7CAjXEEvUnoJbD9QwnCwGyCL"
USDT_BEP20 = "0x723B04ABAAFF8524F98d4b60B20Fff67920A48A5"
TOOBIT_UID = "129107184"


def payment_block() -> list[str]:
    """بخشِ «روش‌های پرداخت» با ایموجی و لحنِ رسمی.

    آدرس‌ها داخلِ <code> می‌آیند تا در تلگرام با یک لمس کپی شوند.
    """
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


def portfolio_subscription_message() -> tuple[str, dict]:
    """متن + کیبوردِ شیشه‌ایِ اشتراک‌های پنل مدیریت سرمایه."""
    rows = _portfolio_plans()
    lines = [
        "💼 <b>اشتراک‌های پنل مدیریت سرمایه الگو هاب</b>",
        "",
        "با فعال‌سازی اشتراک، به سبدچینی هوش مصنوعی، تحلیل‌های اختصاصی بازار و "
        "پشتیبانی تیم الگو هاب دسترسی خواهید داشت.",
        "",
    ]
    buttons = []
    for p in rows:
        price_fa = _toman(p["price"])
        lines.append(f"{p['emoji']} <b>{_esc(p['name'])}</b> — {_esc(price_fa)} ({p['period_fa']})")
        if p["desc"]:
            lines.append(f"    ↳ {_esc(p['desc'])}")
        msg = _purchase_message(p["name"], "پنل مدیریت سرمایه الگو هاب",
                                p["period_fa"], price_fa)
        buttons.append([{
            "text": f"{p['emoji']} اشتراک {p['name']} — {price_fa}",
            "url": _support_link(msg),
        }])
    lines += [""] + payment_block()
    buttons.append([{"text": "💬 گفتگو با پشتیبانی", "url": settings.support_url}])
    buttons.append([{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "nav:home"}])
    return _with_footer("\n".join(lines)), {"inline_keyboard": buttons}


def journal_subscription_message() -> tuple[str, dict]:
    """متن + کیبوردِ شیشه‌ایِ اشتراک‌های پنل ژورنال تریدینگ."""
    lines = [
        "📊 <b>اشتراک‌های پنل ژورنال تریدینگ الگو هاب</b>",
        "",
        "ثبت حرفه‌ایِ معاملات، داشبورد و منحنی سرمایه، تحلیل هوش مصنوعی روی تک‌تک "
        "معاملات و اتصال مستقیم به صرافی توبیت.",
        "",
    ]
    buttons = []
    for p in JOURNAL_PLANS:
        price_fa = _toman(p["monthly"])
        lines.append(f"{p['emoji']} <b>{_esc(p['name'])}</b> — {_esc(price_fa)} (ماهانه)")
        msg = _purchase_message(p["name"], "پنل ژورنال تریدینگ الگو هاب",
                                "ماهانه", price_fa)
        buttons.append([{
            "text": f"{p['emoji']} اشتراک {p['name']} — {price_fa}",
            "url": _support_link(msg),
        }])
    lines += [
        "",
        "🎁 پلن برنزی همیشه رایگان است.",
        "💡 با خرید ۳، ۶ یا ۱۲ ماهه تا ۳۳٪ تخفیف بگیرید — برای دورهٔ بلندتر با "
        "پشتیبانی در ارتباط باشید.",
        "",
    ] + payment_block()
    buttons.append([{"text": "💬 گفتگو با پشتیبانی", "url": settings.support_url}])
    buttons.append([{"text": "🔙 بازگشت به منوی اصلی", "callback_data": "nav:home"}])
    return _with_footer("\n".join(lines)), {"inline_keyboard": buttons}


# ───────────────────────── هشدارِ قیمتِ خرید ─────────────────────────
def _price_fa(v: float) -> str:
    """قالب‌بندیِ قیمتِ دلاری با دقتِ متناسب با بزرگیِ عدد."""
    if v >= 100:
        s = f"{v:,.2f}"
    elif v >= 1:
        s = f"{v:,.4f}"
    else:
        s = f"{v:.8f}".rstrip("0").rstrip(".")
    return _fa_digits(s).replace(",", "٬")


_HORIZON_FA = {"short": "کوتاه‌مدت", "mid": "میان‌مدت", "long": "بلندمدت"}


def buy_alert_message(symbol: str, name: str | None, target: float,
                      price: float, horizon: str) -> str:
    """پیامِ رسمیِ «ارز به قیمتِ خرید رسید»."""
    title = _esc(name or symbol)
    hz = _HORIZON_FA.get(horizon, horizon)
    body = (
        "🔔 <b>هشدار قیمت خرید</b>\n\n"
        f"💎 ارز <b>{_esc(symbol.upper())}</b> ({title}) به قیمتِ هدفِ خرید رسید.\n\n"
        f"🎯 قیمت هدف: <b>${_price_fa(target)}</b>\n"
        f"💵 قیمت لحظه‌ای: <b>${_price_fa(price)}</b>\n"
        f"⏳ افق سرمایه‌گذاری: <b>{hz}</b>\n\n"
        "📈 بر اساس سبدچینیِ هوش مصنوعیِ الگو هاب، هم‌اکنون موقعیتِ مناسبی برای "
        "خرید این ارز فراهم است. لطفاً پیش از هر اقدام، مدیریت سرمایه و "
        "حد ضرر خود را رعایت فرمایید.\n\n"
        "🙏 با آرزوی معاملاتی پرسود برای شما."
    )
    return _with_footer(body)


def sell_alert_message(symbol: str, name: str | None, target: float,
                       price: float, horizon: str) -> str:
    """پیامِ رسمیِ «ارز به قیمتِ فروش رسید»."""
    title = _esc(name or symbol)
    hz = _HORIZON_FA.get(horizon, horizon)
    body = (
        "🔕 <b>هشدار قیمت فروش</b>\n\n"
        f"💎 ارز <b>{_esc(symbol.upper())}</b> ({title}) به قیمتِ هدفِ فروش رسید.\n\n"
        f"🎯 قیمت هدف: <b>${_price_fa(target)}</b>\n"
        f"💵 قیمت لحظه‌ای: <b>${_price_fa(price)}</b>\n"
        f"⏳ افق سرمایه‌گذاری: <b>{hz}</b>\n\n"
        "📊 بر اساس سبدچینیِ هوش مصنوعیِ الگو هاب، قیمت به هدفِ سودِ تعیین‌شده "
        "رسیده است و می‌توانید نسبت به شناساییِ سود اقدام فرمایید. تصمیمِ نهایی "
        "بر عهدهٔ شما و بر پایهٔ استراتژیِ شخصیِ شماست.\n\n"
        "🙏 سود شما را تبریک می‌گوییم."
    )
    return _with_footer(body)


def alert_message(kind: str, symbol: str, name: str | None, target: float,
                  price: float, horizon: str) -> str:
    fn = sell_alert_message if kind == "sell" else buy_alert_message
    return fn(symbol, name, target, price, horizon)


# ───────────────────────── پردازشِ آپدیت‌ها ─────────────────────────
def _menu_keyboard(tg_id: str | int | None = None) -> dict[str, Any]:
    rows = [[{"text": BTN_PORTFOLIO_SUB}], [{"text": BTN_JOURNAL_SUB}]]
    if ba.is_admin(tg_id):
        rows.append([{"text": ba.BTN_ADMIN}])
    return {"keyboard": rows, "resize_keyboard": True}


_WELCOME = (
    "🌟 <b>به ربات الگو هاب خوش آمدید</b>\n\n"
    "از این پس هشدارِ رسیدنِ ارزهای پیشنهادیِ سبدچینیِ هوش مصنوعی به قیمتِ خرید، "
    "همین‌جا به شما اطلاع داده می‌شود.\n\n"
    "برای مشاهدهٔ تعرفه‌ها، یکی از دکمه‌های زیر را انتخاب کنید."
)

_LINKED = (
    "✅ <b>حساب شما با موفقیت متصل شد</b>\n\n"
    "از این پس هشدارهای قیمتِ خریدِ ارزهای سبدِ پیشنهادیِ شما به همین چت ارسال "
    "می‌شود. می‌توانید هر زمان از پنل، هشدارها را فعال یا غیرفعال کنید."
)


async def process_update(update: dict[str, Any]) -> bool:
    """یک آپدیتِ تلگرام را پردازش می‌کند (پیامِ خصوصی یا کلیکِ دکمهٔ شیشه‌ای)."""
    cb = update.get("callback_query")
    if isinstance(cb, dict):
        return await _handle_callback(cb)

    msg = update.get("message")
    if not isinstance(msg, dict):
        return False
    chat = msg.get("chat") or {}
    if chat.get("type") != "private":
        return False
    chat_id = chat.get("id")
    if chat_id is None:
        return False
    text = (msg.get("text") or "").strip()
    from_user = msg.get("from") or {}
    tg_id = from_user.get("id")

    if text.startswith("/start"):
        db.bot_state_set(chat_id, None)
        # /start <token> ⇒ اتصالِ حسابِ پنل به این چت
        parts = text.split(maxsplit=1)
        payload = parts[1].strip() if len(parts) > 1 else ""
        if payload:
            link = db.tg_link_by_token(payload)
            if link:
                db.tg_complete_link(int(link["user_id"]), str(chat_id),
                                    from_user.get("username"))
                await send_message(chat_id, _with_footer(_LINKED),
                                   reply_markup=_menu_keyboard(tg_id))
                return True
        await send_message(chat_id, _with_footer(_WELCOME),
                           reply_markup=_menu_keyboard(tg_id))
        return True

    if text == BTN_PORTFOLIO_SUB:
        db.bot_state_set(chat_id, None)
        body, kb = portfolio_subscription_message()
        await send_message(chat_id, body, reply_markup=kb)
        return True

    if text == BTN_JOURNAL_SUB:
        db.bot_state_set(chat_id, None)
        body, kb = journal_subscription_message()
        await send_message(chat_id, body, reply_markup=kb)
        return True

    # ── پنل ادمین ──
    if text == ba.BTN_ADMIN:
        db.bot_state_set(chat_id, None)
        if not ba.is_admin(tg_id):
            await send_message(chat_id, ba.NOT_ADMIN)
            return True
        await send_message(chat_id, ba.ADMIN_WELCOME,
                           reply_markup=ba.admin_menu_keyboard())
        return True

    if text == ba.BTN_BACK:
        db.bot_state_set(chat_id, None)
        await send_message(chat_id, _with_footer(_WELCOME),
                           reply_markup=_menu_keyboard(tg_id))
        return True

    if ba.is_admin(tg_id) and text in (ba.BTN_ADMINS, ba.BTN_SUBS,
                                       ba.BTN_REPORTS, ba.BTN_BROADCAST):
        db.bot_state_set(chat_id, None)
        if text == ba.BTN_ADMINS:
            await send_message(chat_id, ba.admins_text(),
                               reply_markup=ba.admins_keyboard())
        elif text == ba.BTN_SUBS:
            await send_message(chat_id, "🎟 <b>فعال‌سازی اشتراک</b>\n\nابتدا سایت موردنظر را انتخاب کنید:",
                               reply_markup=ba.sites_keyboard("sub:site"))
        elif text == ba.BTN_REPORTS:
            await send_message(chat_id, "📊 <b>گزارش عملکرد</b>\n\nگزارشِ کدام سایت را می‌خواهید؟",
                               reply_markup=ba.sites_keyboard("rep:site"))
        else:
            db.bot_state_set(chat_id, {"flow": "broadcast"})
            await send_message(chat_id, ba.BROADCAST_PROMPT,
                               reply_markup=ba.cancel_keyboard())
        return True

    # ── ادامهٔ گفتگوهای چندمرحله‌ای ──
    state = db.bot_state_get(chat_id)
    if state and ba.is_admin(tg_id):
        if await _handle_flow(chat_id, tg_id, state, msg, text):
            return True

    await send_message(chat_id, _with_footer(_WELCOME),
                       reply_markup=_menu_keyboard(tg_id))
    return True


async def _handle_flow(chat_id, tg_id, state: dict, msg: dict, text: str) -> bool:
    """گام‌های متنیِ گفتگوهای پنل ادمین."""
    flow = state.get("flow")

    if flow == "admin_add":
        ident = text.strip()
        if not ident:
            return False
        uname = ident if ident.startswith("@") else None
        new_id = ident.lstrip("@")
        if not new_id.isdigit() and uname is None:
            await send_message(chat_id, "شناسه باید عددی باشد یا با @ شروع شود. دوباره بفرستید.")
            return True
        if not new_id.isdigit():
            await send_message(
                chat_id,
                "⚠️ تلگرام اجازهٔ یافتنِ شناسهٔ عددی از روی نام کاربری را به ربات نمی‌دهد.\n"
                "لطفاً <b>شناسهٔ عددی</b> کاربر را بفرستید (با ربات @userinfobot قابل دریافت است).")
            return True
        db.bot_admin_add(new_id, uname, str(tg_id))
        db.bot_state_set(chat_id, None)
        await send_message(chat_id, f"✅ ادمین جدید افزوده شد: <code>{_esc(new_id)}</code>\n\n"
                           + ba.admins_text(), reply_markup=ba.admins_keyboard())
        return True

    if flow == "admin_del":
        ident = text.strip()
        if not ident:
            return False
        if ident.lstrip("@").isdigit():
            target = ident.lstrip("@")
            if ba.is_owner(target):
                await send_message(chat_id, "⛔️ مالک قابل حذف نیست.")
                return True
            ok = db.bot_admin_remove(target)
        else:
            removed = db.bot_admin_remove_by_username(ident)
            ok = removed is not None
        db.bot_state_set(chat_id, None)
        head = "✅ ادمین حذف شد." if ok else "❌ چنین ادمینی یافت نشد."
        await send_message(chat_id, head + "\n\n" + ba.admins_text(),
                           reply_markup=ba.admins_keyboard())
        return True

    if flow == "sub_lookup":
        site = state.get("site") or "portfolio"
        term = text.strip()
        if not term:
            return False
        if site == "portfolio":
            rows = ba.portfolio_lookup(term)
            found = [{"id": u["id"], "label": ba.user_line(u, site)} for u in rows]
        else:
            ok, data = await journal_api.lookup(term)
            if not ok:
                await send_message(chat_id, f"❌ {_esc(data)}")
                return True
            found = [{"id": u["id"], "label": ba.user_line(u, site)} for u in data]
        if not found:
            await send_message(chat_id, "کاربری با این مشخصات یافت نشد. دوباره تلاش کنید یا «🔙 بازگشت» را بزنید.")
            return True
        rows_kb = [[(f"{i + 1}) انتخاب", f"sub:user:{site}:{u['id']}")]
                   for i, u in enumerate(found[:8])]
        body = "🔎 <b>نتیجهٔ جستجو</b>\n\n" + "\n\n".join(
            f"<b>{i + 1}.</b> {u['label']}" for i, u in enumerate(found[:8]))
        db.bot_state_set(chat_id, None)
        await send_message(chat_id, body + "\n\nکاربر موردنظر را انتخاب کنید:",
                           reply_markup={"inline_keyboard":
                                         [[{"text": t, "callback_data": d} for t, d in r]
                                          for r in rows_kb]})
        return True

    if flow == "broadcast":
        # هر پیامی که ادمین بفرستد، نامزدِ ارسالِ همگانی است.
        mid = msg.get("message_id")
        if mid is None:
            return False
        db.bot_state_set(chat_id, {"flow": "broadcast_confirm",
                                   "from_chat": str(chat_id), "message_id": int(mid)})
        n = len(db.bot_known_chats())
        await send_message(chat_id, ba.broadcast_confirm_text(n),
                           reply_markup=ba.confirm_keyboard())
        return True

    return False


async def _handle_callback(cb: dict[str, Any]) -> bool:
    """کلیکِ دکمه‌های شیشه‌ایِ پنل ادمین."""
    cb_id = str(cb.get("id") or "")
    data = str(cb.get("data") or "")
    msg = cb.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    tg_id = (cb.get("from") or {}).get("id")

    if not data or chat_id is None:
        await _answer_callback(cb_id)
        return True

    parts = data.split(":")
    head = parts[0]

    # ── ناوبری (بازگشت) — برای همه در دسترس است ──
    if head == "nav":
        await _answer_callback(cb_id)
        db.bot_state_set(chat_id, None)
        where = parts[1] if len(parts) > 1 else "home"
        if where == "admin" and ba.is_admin(tg_id):
            await send_message(chat_id, ba.ADMIN_WELCOME,
                               reply_markup=ba.admin_menu_keyboard())
        else:
            await send_message(chat_id, _with_footer(_WELCOME),
                               reply_markup=_menu_keyboard(tg_id))
        return True

    # بقیهٔ دکمه‌های شیشه‌ای فقط برای ادمین است (دکمه‌های خرید لینکی‌اند).
    if not ba.is_admin(tg_id):
        await _answer_callback(cb_id, "دسترسی ندارید")
        return True

    await _answer_callback(cb_id)

    # ── مدیریت ادمین‌ها ──
    if head == "adm":
        action = parts[1] if len(parts) > 1 else "list"
        if action == "add":
            db.bot_state_set(chat_id, {"flow": "admin_add"})
            await send_message(chat_id,
                               "➕ <b>افزودن ادمین</b>\n\nشناسهٔ عددیِ تلگرامِ ادمین جدید را بفرستید.\n"
                               "<i>کاربر می‌تواند شناسهٔ خود را از @userinfobot بگیرد.</i>",
                               reply_markup=ba.cancel_keyboard())
        elif action == "del":
            db.bot_state_set(chat_id, {"flow": "admin_del"})
            await send_message(chat_id,
                               "➖ <b>حذف ادمین</b>\n\nشناسهٔ عددی یا نام کاربری (@user) ادمین موردنظر را بفرستید.",
                               reply_markup=ba.cancel_keyboard())
        else:
            await send_message(chat_id, ba.admins_text(),
                               reply_markup=ba.admins_keyboard())
        return True

    # ── فعال‌سازی اشتراک ──
    if head == "sub":
        step = parts[1] if len(parts) > 1 else ""
        if step == "site":
            site = parts[2]
            db.bot_state_set(chat_id, {"flow": "sub_lookup", "site": site})
            label = "پنل مدیریت سرمایه" if site == "portfolio" else "پنل ژورنال تریدینگ"
            await send_message(chat_id,
                               f"🎟 <b>فعال‌سازی اشتراک — {label}</b>\n\n"
                               "ایمیل، نام کاربری یا شناسهٔ کاربر را بفرستید:",
                               reply_markup=ba.cancel_keyboard())
            return True
        if step == "user":
            site, user_id = parts[2], parts[3]
            db.bot_state_set(chat_id, {"flow": "sub_tier", "site": site, "user_id": user_id})
            await send_message(chat_id, "پلنِ موردنظر را انتخاب کنید:",
                               reply_markup=ba.tiers_keyboard(site))
            return True
        if step == "back-tier":
            site = parts[2]
            st = db.bot_state_get(chat_id)
            if not st.get("user_id"):
                await send_message(chat_id, "نشستِ فعال‌سازی منقضی شد. دوباره شروع کنید:",
                                   reply_markup=ba.sites_keyboard("sub:site"))
                return True
            st["flow"] = "sub_tier"
            db.bot_state_set(chat_id, st)
            await send_message(chat_id, "پلنِ موردنظر را انتخاب کنید:",
                               reply_markup=ba.tiers_keyboard(site))
            return True
        if step == "tier":
            site, tier = parts[2], parts[3]
            st = db.bot_state_get(chat_id)
            st.update({"flow": "sub_dur", "site": site, "tier": tier})
            db.bot_state_set(chat_id, st)
            await send_message(chat_id, "مدتِ اشتراک را انتخاب کنید:",
                               reply_markup=ba.durations_keyboard(site, tier))
            return True
        if step == "dur":
            site, tier, months = parts[2], parts[3], int(parts[4])
            st = db.bot_state_get(chat_id)
            user_id = st.get("user_id")
            db.bot_state_set(chat_id, None)
            if not user_id:
                await send_message(chat_id, "❌ نشستِ فعال‌سازی منقضی شد. دوباره از ابتدا شروع کنید.")
                return True
            tier_fa = ba._tier_fa(tier, site)
            dur_fa = dict(ba.DURATIONS).get(months, "بدون انقضا")
            if site == "portfolio":
                exp = ba.apply_portfolio_plan(int(user_id), tier, months)
                await send_message(
                    chat_id,
                    f"✅ <b>اشتراک فعال شد</b>\n\n"
                    f"🏢 سایت: پنل مدیریت سرمایه\n🆔 کاربر: <code>{_esc(user_id)}</code>\n"
                    f"🎟 پلن: <b>{tier_fa}</b>\n⏳ مدت: <b>{dur_fa}</b>\n"
                    f"📅 انقضا: <b>{_esc(exp)}</b>",
                    reply_markup=ba.admin_menu_keyboard())
            else:
                ok, res = await journal_api.set_plan(int(user_id), tier, months or None)
                if not ok:
                    await send_message(chat_id, f"❌ {_esc(res)}")
                    return True
                exp = str(res.get("expiresAt") or "بدون انقضا")[:10]
                await send_message(
                    chat_id,
                    f"✅ <b>اشتراک فعال شد</b>\n\n"
                    f"🏢 سایت: پنل ژورنال تریدینگ\n"
                    f"✉️ کاربر: <code>{_esc(res.get('email') or user_id)}</code>\n"
                    f"🎟 پلن: <b>{tier_fa}</b>\n⏳ مدت: <b>{dur_fa}</b>\n"
                    f"📅 انقضا: <b>{_esc(exp)}</b>",
                    reply_markup=ba.admin_menu_keyboard())
            return True

    # ── گزارش‌ها ──
    if head == "rep":
        if parts[1] == "pick":
            await send_message(chat_id, "📊 <b>گزارش عملکرد</b>\n\nگزارشِ کدام سایت را می‌خواهید؟",
                               reply_markup=ba.sites_keyboard("rep:site"))
            return True
        if parts[1] == "site":
            site = parts[2]
            await send_message(chat_id, "بازهٔ گزارش را انتخاب کنید:",
                               reply_markup=ba.periods_keyboard(site))
            return True
        site, period = parts[1], parts[2]
        if site == "portfolio":
            await send_message(chat_id, ba.portfolio_report(period),
                               reply_markup=ba.periods_keyboard(site))
        else:
            ok, data_ = await journal_api.stats(period)
            if not ok:
                await send_message(chat_id, f"❌ {_esc(data_)}")
                return True
            await send_message(chat_id, ba.journal_report(period, data_),
                               reply_markup=ba.periods_keyboard(site))
        return True

    # ── تأییدِ پیام همگانی ──
    if head == "bc":
        st = db.bot_state_get(chat_id)
        db.bot_state_set(chat_id, None)
        if parts[1] == "no":
            await send_message(chat_id, "❌ ارسال پیام همگانی لغو شد.",
                               reply_markup=ba.admin_menu_keyboard())
            return True
        if st.get("flow") != "broadcast_confirm" or not st.get("message_id"):
            await send_message(chat_id, "❌ پیامی برای ارسال یافت نشد. دوباره تلاش کنید.",
                               reply_markup=ba.admin_menu_keyboard())
            return True
        await send_message(chat_id, "⏳ در حال ارسال پیام همگانی…")
        result = await ba.broadcast(st["from_chat"], int(st["message_id"]), copy_message)
        await send_message(
            chat_id,
            f"✅ <b>ارسال پیام همگانی پایان یافت</b>\n\n"
            f"📨 ارسال‌شده: <b>{ba._fa(result['sent'])}</b>\n"
            f"⚠️ ناموفق: <b>{ba._fa(result['failed'])}</b>",
            reply_markup=ba.admin_menu_keyboard())
        return True

    return True
