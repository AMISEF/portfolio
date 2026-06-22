"""
روتر احراز هویت ایمیلی.

جریان‌ها:
  • ثبت‌نام: کاربر نام/ایمیل/رمز می‌دهد → کد ۶ رقمی به ایمیلش ارسال می‌شود →
    با وارد کردن کد، حساب «تأیید» و وارد می‌شود.
  • ورود: ایمیل + رمز.
  • فراموشی رمز: ارسال کد به ایمیل → وارد کردن کد + رمز جدید.

API:
  POST /api/auth/register   {name,email,password}      → ارسال کد تأیید
  POST /api/auth/verify     {email,code}               → تأیید + ورود
  POST /api/auth/resend     {email,purpose}            → ارسال مجدد کد
  POST /api/auth/login      {email,password}           → ورود
  POST /api/auth/forgot     {email}                    → ارسال کد بازیابی
  POST /api/auth/reset      {email,code,password}      → تنظیم رمز جدید + ورود
  POST /api/auth/logout                                → خروج
  GET  /api/auth/me                                    → کاربر فعلی

هویت پورتفولیو: پس از ورود، کوکی cs_uid برابر شناسهٔ پایدار کاربر می‌شود تا
داده‌های سبد بدون تغییر در سایر روترها کار کند؛ داده‌های ناشناسِ همان دستگاه هم
به حساب کاربر منتقل می‌شوند.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from app import db
from app.config import settings
from app.services import auth, mailer

router = APIRouter(prefix="/api/auth", tags=["auth"])

_SESSION_COOKIE = "cs_session"
_UID_COOKIE = "cs_uid"
_UID_MAX_AGE = 60 * 60 * 24 * 365 * 2


def _err(msg: str, status: int = 400, **extra: Any) -> JSONResponse:
    return JSONResponse({"error": msg, **extra}, status_code=status)


def _login_response(user: dict[str, Any], request: Request, body: dict | None = None) -> JSONResponse:
    """نشست می‌سازد، کوکی‌ها را ست می‌کند و داده‌های ناشناس را به حساب منتقل می‌کند."""
    target_uid = user.get("uid") or f"u{user['id']}"
    # انتقال داده‌های ناشناسِ این دستگاه به شناسهٔ کاربر
    current_uid = request.cookies.get(_UID_COOKIE)
    if current_uid and current_uid != target_uid:
        try:
            db.reassign_assets(current_uid, target_uid)
        except Exception:  # noqa: BLE001
            pass

    token = auth.gen_session_token()
    db.create_session(token, int(user["id"]), settings.session_ttl_days)

    resp = JSONResponse({
        "ok": True,
        "user": {"id": user["id"], "email": user["email"], "name": user.get("name")},
    })
    secure = request.url.scheme == "https"
    resp.set_cookie(_SESSION_COOKIE, token, max_age=settings.session_ttl_days * 86400,
                    httponly=True, samesite="lax", secure=secure)
    resp.set_cookie(_UID_COOKIE, target_uid, max_age=_UID_MAX_AGE,
                    httponly=True, samesite="lax", secure=secure)
    return resp


async def _send_code(email: str, purpose: str) -> str | None:
    """کد می‌سازد، ذخیره و ایمیل می‌کند. در صورت محدودیت زمانی، پیام خطا برمی‌گرداند."""
    age = db.latest_code_age_seconds(email, purpose)
    if age is not None and age < settings.auth_code_cooldown:
        wait = int(settings.auth_code_cooldown - age)
        return f"لطفاً {wait} ثانیه دیگر برای دریافت کد جدید صبر کنید."

    code = auth.gen_code()
    db.add_code(email, auth.hash_code(code), purpose, settings.auth_code_ttl)
    if purpose == "verify":
        subject, html, text = mailer.verify_email_content(code)
    else:
        subject, html, text = mailer.reset_email_content(code)
    await mailer.send_email(email, subject, html, text)
    return None


# ───────────────────────── ثبت‌نام ─────────────────────────
@router.post("/register")
async def register(request: Request, payload: dict[str, Any] = Body(...)):
    email = auth.normalize_email(payload.get("email"))
    name = (payload.get("name") or "").strip() or None
    password = payload.get("password") or ""

    if not auth.valid_email(email):
        return _err("ایمیل نامعتبر است.")
    if (pw_err := auth.password_problem(password)):
        return _err(pw_err)

    existing = db.get_user_by_email(email)
    if existing and existing["verified"]:
        return _err("این ایمیل قبلاً ثبت شده است. لطفاً وارد شوید.", 409)

    pw_hash = auth.hash_password(password)
    if existing:                       # تأییدنشده: اطلاعات را به‌روزرسانی کن
        db.update_user_credentials(int(existing["id"]), name, pw_hash)
    else:
        anon_uid = request.cookies.get(_UID_COOKIE)
        db.create_user(email, name, pw_hash, uid=anon_uid, verified=False)

    try:
        if (msg := await _send_code(email, "verify")):
            return _err(msg, 429)
    except mailer.MailNotConfigured:
        return _err("سرویس ایمیل هنوز روی سرور پیکربندی نشده است.", 503)
    except Exception:  # noqa: BLE001
        return _err("ارسال ایمیل ناموفق بود. لطفاً بعداً تلاش کنید.", 502)

    return JSONResponse({"ok": True, "stage": "verify", "email": email})


@router.post("/verify")
async def verify(request: Request, payload: dict[str, Any] = Body(...)):
    email = auth.normalize_email(payload.get("email"))
    code = (payload.get("code") or "").strip()
    user = db.get_user_by_email(email)
    if not user:
        return _err("حسابی با این ایمیل یافت نشد.", 404)

    active = db.get_active_code(email, "verify")
    if not active:
        return _err("کد منقضی شده یا یافت نشد. لطفاً کد جدید بخواهید.", 410)
    if active["attempts"] >= settings.auth_code_max_attempts:
        return _err("تعداد تلاش‌ها بیش از حد مجاز است. کد جدید بخواهید.", 429)
    if not auth.verify_code(code, active["code_hash"]):
        left = settings.auth_code_max_attempts - db.bump_code_attempts(int(active["id"]))
        return _err(f"کد نادرست است. {max(left, 0)} تلاش باقی مانده.", 401)

    db.consume_code(int(active["id"]))
    db.set_user_verified(int(user["id"]))
    return _login_response(db.get_user_by_id(int(user["id"])), request)


@router.post("/resend")
async def resend(payload: dict[str, Any] = Body(...)):
    email = auth.normalize_email(payload.get("email"))
    purpose = payload.get("purpose") if payload.get("purpose") in ("verify", "reset") else "verify"
    user = db.get_user_by_email(email)
    # برای جلوگیری از افشای وجود ایمیل، همیشه ok می‌دهیم
    if user:
        try:
            if (msg := await _send_code(email, purpose)):
                return _err(msg, 429)
        except mailer.MailNotConfigured:
            return _err("سرویس ایمیل هنوز روی سرور پیکربندی نشده است.", 503)
        except Exception:  # noqa: BLE001
            return _err("ارسال ایمیل ناموفق بود.", 502)
    return JSONResponse({"ok": True})


# ───────────────────────── ورود ─────────────────────────
@router.post("/login")
async def login(request: Request, payload: dict[str, Any] = Body(...)):
    email = auth.normalize_email(payload.get("email"))
    password = payload.get("password") or ""
    user = db.get_user_by_email(email)
    if not user or not auth.verify_password(password, user["password_hash"]):
        return _err("ایمیل یا رمز عبور نادرست است.", 401)
    if not user["verified"]:
        try:
            await _send_code(email, "verify")
        except Exception:  # noqa: BLE001
            pass
        return _err("حساب شما هنوز تأیید نشده است. کد تأیید برایتان ارسال شد.",
                    403, stage="verify", email=email)
    return _login_response(user, request)


# ───────────────────────── فراموشی رمز ─────────────────────────
@router.post("/forgot")
async def forgot(payload: dict[str, Any] = Body(...)):
    email = auth.normalize_email(payload.get("email"))
    if not auth.valid_email(email):
        return _err("ایمیل نامعتبر است.")
    user = db.get_user_by_email(email)
    if user and user["verified"]:
        try:
            if (msg := await _send_code(email, "reset")):
                return _err(msg, 429)
        except mailer.MailNotConfigured:
            return _err("سرویس ایمیل هنوز روی سرور پیکربندی نشده است.", 503)
        except Exception:  # noqa: BLE001
            return _err("ارسال ایمیل ناموفق بود.", 502)
    # پاسخ یکسان صرف‌نظر از وجود ایمیل (ضد شمارش حساب)
    return JSONResponse({"ok": True, "stage": "reset", "email": email})


@router.post("/reset")
async def reset(request: Request, payload: dict[str, Any] = Body(...)):
    email = auth.normalize_email(payload.get("email"))
    code = (payload.get("code") or "").strip()
    password = payload.get("password") or ""
    if (pw_err := auth.password_problem(password)):
        return _err(pw_err)

    user = db.get_user_by_email(email)
    if not user:
        return _err("حسابی با این ایمیل یافت نشد.", 404)
    active = db.get_active_code(email, "reset")
    if not active:
        return _err("کد منقضی شده یا یافت نشد. لطفاً کد جدید بخواهید.", 410)
    if active["attempts"] >= settings.auth_code_max_attempts:
        return _err("تعداد تلاش‌ها بیش از حد مجاز است. کد جدید بخواهید.", 429)
    if not auth.verify_code(code, active["code_hash"]):
        left = settings.auth_code_max_attempts - db.bump_code_attempts(int(active["id"]))
        return _err(f"کد نادرست است. {max(left, 0)} تلاش باقی مانده.", 401)

    db.consume_code(int(active["id"]))
    db.update_user_password(int(user["id"]), auth.hash_password(password))
    return _login_response(db.get_user_by_id(int(user["id"])), request)


# ───────────────────────── نشست ─────────────────────────
@router.post("/logout")
async def logout(request: Request):
    token = request.cookies.get(_SESSION_COOKIE)
    if token:
        db.delete_session(token)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(_SESSION_COOKIE)
    return resp


@router.get("/me")
async def me(request: Request):
    token = request.cookies.get(_SESSION_COOKIE)
    if not token:
        return JSONResponse({"user": None})
    user = db.get_session_user(token)
    if not user:
        return JSONResponse({"user": None})
    return JSONResponse({"user": {"id": user["id"], "email": user["email"], "name": user.get("name")}})
