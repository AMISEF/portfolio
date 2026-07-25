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
from app.services import plans

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


async def _answer_callback(callback_id: str) -> None:
    token = _token()
    if not token:
        return
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            await client.post(f"{_API}/bot{token}/answerCallbackQuery",
                              data={"callback_query_id": callback_id})
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
    """پیامِ رسمیِ آماده که در پیویِ پشتیبانی نوشته می‌شود."""
    return (
        "سلام؛ وقت بخیر.\n"
        f"مایل به تهیهٔ اشتراک «{plan_name}» {product} "
        f"({period_fa} — {price_fa}) هستم.\n"
        "لطفاً راهنمایی بفرمایید. سپاسگزارم."
    )


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
    lines += ["", "💳 برای خرید، روی پلنِ موردنظر بزنید تا به پشتیبانی وصل شوید."]
    buttons.append([{"text": "💬 گفتگو با پشتیبانی", "url": settings.support_url}])
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
        "💳 برای خرید، روی پلنِ موردنظر بزنید تا به پشتیبانی وصل شوید.",
    ]
    buttons.append([{"text": "💬 گفتگو با پشتیبانی", "url": settings.support_url}])
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


# ───────────────────────── پردازشِ آپدیت‌ها ─────────────────────────
def _menu_keyboard() -> dict[str, Any]:
    return {
        "keyboard": [[{"text": BTN_PORTFOLIO_SUB}], [{"text": BTN_JOURNAL_SUB}]],
        "resize_keyboard": True,
    }


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
        await _answer_callback(str(cb.get("id") or ""))
        return True

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

    if text.startswith("/start"):
        # /start <token> ⇒ اتصالِ حسابِ پنل به این چت
        parts = text.split(maxsplit=1)
        payload = parts[1].strip() if len(parts) > 1 else ""
        if payload:
            link = db.tg_link_by_token(payload)
            if link:
                db.tg_complete_link(int(link["user_id"]), str(chat_id),
                                    from_user.get("username"))
                await send_message(chat_id, _with_footer(_LINKED),
                                   reply_markup=_menu_keyboard())
                return True
        await send_message(chat_id, _with_footer(_WELCOME),
                           reply_markup=_menu_keyboard())
        return True

    if text == BTN_PORTFOLIO_SUB:
        body, kb = portfolio_subscription_message()
        await send_message(chat_id, body, reply_markup=kb)
        return True

    if text == BTN_JOURNAL_SUB:
        body, kb = journal_subscription_message()
        await send_message(chat_id, body, reply_markup=kb)
        return True

    await send_message(chat_id, _with_footer(_WELCOME),
                       reply_markup=_menu_keyboard())
    return True
