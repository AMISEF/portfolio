"""
سرویس ارسال ایمیل — رله از طریق SMTP جیمیل.

چرا رله به‌جای میل‌سرور محلی؟ ارسال مستقیم از IP تازهٔ سرور تقریباً همیشه در
پوشهٔ اسپم می‌افتد و IP خیلی زود در بلاک‌لیست‌ها قرار می‌گیرد. ارسال از زیرساخت
جیمیل تحویل‌پذیری بسیار بهتری دارد.

تنظیمات حساس (به‌ویژه App Password جیمیل) فقط از .env سرور خوانده می‌شوند و هرگز
در کد یا مخزن قرار نمی‌گیرند.
"""
from __future__ import annotations

import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from app.config import settings


class MailNotConfigured(RuntimeError):
    """وقتی کلید/رمز SMTP در .env تنظیم نشده باشد."""


def _send_sync(to_email: str, subject: str, html: str, text: str) -> None:
    if not (settings.smtp_user and settings.smtp_password):
        raise MailNotConfigured("SMTP credentials not set (.env)")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
    msg["To"] = to_email
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    if settings.smtp_starttls:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as srv:
            srv.ehlo()
            srv.starttls(context=ctx)
            srv.login(settings.smtp_user, settings.smtp_password)
            srv.send_message(msg)
    else:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20, context=ctx) as srv:
            srv.login(settings.smtp_user, settings.smtp_password)
            srv.send_message(msg)


async def send_email(to_email: str, subject: str, html: str, text: str) -> None:
    """ارسال ایمیل بدون بلوکه‌کردن حلقهٔ async (smtplib در threadpool)."""
    await asyncio.to_thread(_send_sync, to_email, subject, html, text)


# ---------- قالب‌های فارسی RTL ----------
def _wrap(title: str, body_html: str) -> str:
    return f"""\
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;background:#eef2f7;font-family:Tahoma,Arial,sans-serif;direction:rtl;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:28px 12px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="max-width:460px;background:#ffffff;border-radius:18px;overflow:hidden;
                    box-shadow:0 10px 30px -12px rgba(22,47,85,.25);">
        <tr><td style="background:linear-gradient(135deg,#19C3B3,#128F84);padding:22px;text-align:center;">
          <span style="color:#04201D;font-size:20px;font-weight:bold;">کریپتو اسمارت</span>
        </td></tr>
        <tr><td style="padding:28px 26px;color:#1f2b3a;line-height:2;font-size:15px;">
          <h2 style="margin:0 0 14px;color:#162F55;font-size:18px;">{title}</h2>
          {body_html}
        </td></tr>
        <tr><td style="padding:16px 26px;background:#f3f6f9;color:#8a96a3;font-size:12px;text-align:center;">
          این ایمیل به‌صورت خودکار ارسال شده است؛ لطفاً به آن پاسخ ندهید.<br>
          © کریپتو اسمارت — cryptosmart.site
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def _code_block(code: str) -> str:
    return (
        f'<div style="margin:18px 0;text-align:center;">'
        f'<span style="display:inline-block;letter-spacing:8px;font-size:30px;font-weight:bold;'
        f'color:#128F84;background:#e7f7f5;padding:12px 22px;border-radius:12px;">{code}</span>'
        f'</div>'
    )


def verify_email_content(code: str) -> tuple[str, str, str]:
    """(موضوع، HTML، متن) برای کد تأیید ثبت‌نام."""
    subject = "کد تأیید ثبت‌نام — کریپتو اسمارت"
    minutes = settings.auth_code_ttl // 60
    html = _wrap(
        "به کریپتو اسمارت خوش آمدید 👋",
        "<p>برای تکمیل ثبت‌نام، کد تأیید زیر را در سایت وارد کنید:</p>"
        + _code_block(code)
        + f"<p>این کد تا <b>{minutes} دقیقه</b> معتبر است. اگر شما درخواست ثبت‌نام نداده‌اید، "
        "این ایمیل را نادیده بگیرید.</p>",
    )
    text = (f"کد تأیید ثبت‌نام شما در کریپتو اسمارت: {code}\n"
            f"این کد تا {minutes} دقیقه معتبر است.")
    return subject, html, text


def reset_email_content(code: str) -> tuple[str, str, str]:
    """(موضوع، HTML، متن) برای کد بازیابی رمز عبور."""
    subject = "کد بازیابی رمز عبور — کریپتو اسمارت"
    minutes = settings.auth_code_ttl // 60
    html = _wrap(
        "بازیابی رمز عبور 🔑",
        "<p>برای تنظیم رمز عبور جدید، کد زیر را در سایت وارد کنید:</p>"
        + _code_block(code)
        + f"<p>این کد تا <b>{minutes} دقیقه</b> معتبر است. اگر شما درخواست تغییر رمز نداده‌اید، "
        "رمز شما همچنان امن است و نیازی به اقدام نیست.</p>",
    )
    text = (f"کد بازیابی رمز عبور شما در کریپتو اسمارت: {code}\n"
            f"این کد تا {minutes} دقیقه معتبر است.")
    return subject, html, text
