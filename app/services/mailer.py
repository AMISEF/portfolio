"""
سرویس ارسال ایمیل — از طریق REST API سرویس Resend (https://resend.com).

چرا Resend؟ تحویل‌پذیری بالا بدون نگه‌داری میل‌سرور؛ ارسال با یک درخواست HTTPS.
از httpx استفاده می‌کنیم (وابستگی موجود) تا نیازی به نصب پکیج اضافه روی سرور نباشد.

کلید API فقط از .env سرور خوانده می‌شود و هرگز در کد/مخزن قرار نمی‌گیرد. برای
ارسال از آدرس دامنه (cryptosmart@cryptosmart.site) باید دامنه در پنل Resend با
رکوردهای DNS تأیید شده باشد؛ در غیر این صورت فقط از onboarding@resend.dev و تنها
به ایمیل مالک حساب می‌توان ارسال کرد.
"""
from __future__ import annotations

import httpx

from app.config import settings


class MailNotConfigured(RuntimeError):
    """وقتی کلید Resend در .env تنظیم نشده باشد."""


async def send_email(to_email: str, subject: str, html: str, text: str) -> None:
    """ارسال ایمیل با Resend API."""
    if not settings.resend_api_key:
        raise MailNotConfigured("RESEND_API_KEY not set (.env)")

    payload = {
        "from": f"{settings.mail_from_name} <{settings.mail_from_email}>",
        "to": [to_email],
        "subject": subject,
        "html": html,
        "text": text,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            settings.resend_api_url,
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if r.status_code >= 300:
        # متن خطا فقط در لاگ سرور دیده می‌شود؛ به کاربر نشت نمی‌کند.
        raise RuntimeError(f"Resend error {r.status_code}: {r.text}")


# ---------- قالب ایمیل (طراحی کارت آبی + جعبهٔ کد، فارسی RTL) ----------
_LOGO = "https://resend-attachments.s3.amazonaws.com/cd477d3a-789a-4ae2-9e27-76f4c4b1cc25"


def _render(heading: str, intro: str, code: str, minutes: int, footer_note: str) -> str:
    return f"""\
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body style="background-color:#eff6ff;margin:0;">
  <table border="0" width="100%" cellpadding="0" cellspacing="0" role="presentation" align="center">
    <tr><td style="font-family:Tahoma,Arial,sans-serif;background-color:#eff6ff;padding:24px 12px;direction:rtl;">
      <table align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation"
             style="max-width:600px;background-color:#ffffff;border-radius:12px;">
        <tr><td style="padding:40px;">
          <table align="center" width="100%" role="presentation"><tr>
            <td align="center"><img alt="کریپتو اسمارت" src="{_LOGO}" width="140"
                style="display:block;border:none;max-width:100%;height:auto;"></td>
          </tr></table>
          <h1 style="font-size:30px;line-height:1.4;font-weight:700;color:#1e3a8a;
                     margin:24px 0 8px;text-align:center;">{heading}</h1>
          <p style="font-size:16px;color:#475569;line-height:1.9;margin:8px 0 24px;text-align:center;">{intro}</p>
          <table width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation"
                 style="background-color:#eff6ff;border-radius:10px;margin:16px 0 24px;text-align:center;">
            <tr><td style="padding:28px 24px;">
              <p style="font-size:13px;color:#475569;letter-spacing:1px;margin:0 0 12px;text-transform:uppercase;">کد تأیید شما</p>
              <h2 style="font-size:38px;line-height:1.4;font-weight:700;color:#1e3a8a;
                         letter-spacing:8px;margin:0 0 12px;direction:ltr;">{code}</h2>
              <p style="font-size:13px;color:#64748b;line-height:1.6;margin:0;">این کد تا {minutes} دقیقه معتبر است.</p>
            </td></tr>
          </table>
          <p style="font-size:14px;color:#64748b;line-height:1.9;margin:32px 0 0;">{footer_note}</p>
          <hr style="border:none;border-top:2px solid #eaeaea;margin:24px 0;">
          <p style="font-size:12px;color:#94a3b8;line-height:1.6;margin:16px 0 0;text-align:center;">
            برای امنیت شما، این کد را هرگز با کسی به اشتراک نگذارید.<br>© کریپتو اسمارت — cryptosmart.site
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def verify_email_content(code: str) -> tuple[str, str, str]:
    """(موضوع، HTML، متن) برای کد تأیید ثبت‌نام."""
    minutes = settings.auth_code_ttl // 60
    subject = "کد تأیید ثبت‌نام — کریپتو اسمارت"
    html = _render(
        "به کریپتو اسمارت خوش آمدید",
        "برای تکمیل ثبت‌نام، کد تأیید زیر را در سایت وارد کنید.",
        code, minutes,
        "اگر شما درخواست ثبت‌نام نداده‌اید، این ایمیل را نادیده بگیرید.",
    )
    text = f"کد تأیید ثبت‌نام شما در کریپتو اسمارت: {code}\nاین کد تا {minutes} دقیقه معتبر است."
    return subject, html, text


def reset_email_content(code: str) -> tuple[str, str, str]:
    """(موضوع، HTML، متن) برای کد بازیابی رمز عبور."""
    minutes = settings.auth_code_ttl // 60
    subject = "کد بازیابی رمز عبور — کریپتو اسمارت"
    html = _render(
        "بازیابی رمز عبور",
        "درخواست بازیابی رمز عبور دریافت شد. برای ادامه، کد زیر را وارد کنید.",
        code, minutes,
        "اگر شما این درخواست را نداده‌اید، رمز شما همچنان امن است و نیازی به اقدام نیست.",
    )
    text = f"کد بازیابی رمز عبور شما در کریپتو اسمارت: {code}\nاین کد تا {minutes} دقیقه معتبر است."
    return subject, html, text
