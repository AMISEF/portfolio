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
from app.services import auth, crypto_box, mailer

router = APIRouter(prefix="/api/auth", tags=["auth"])

_SESSION_COOKIE = "cs_session"
_UID_COOKIE = "cs_uid"
_UID_MAX_AGE = 60 * 60 * 24 * 365 * 2


def _err(msg: str, status: int = 400, **extra: Any) -> JSONResponse:
    return JSONResponse({"error": msg, **extra}, status_code=status)


def current_user(request: Request) -> dict[str, Any] | None:
    """کاربرِ نشستِ فعلی از روی کوکی cs_session (یا None)."""
    token = request.cookies.get(_SESSION_COOKIE)
    if not token:
        return None
    return db.get_session_user(token)


def has_active_subscription(user: dict[str, Any] | None) -> bool:
    """آیا کاربر اشتراک فعال (pro/vip و منقضی‌نشده) دارد؟

    کارکنان (ادمین/پشتیبان) همیشه دسترسی کامل دارند. اشتراک رایگان دسترسی ندارد.
    انقضای NULL به‌معنای نامحدود است (ادمین بدون تعیین تاریخ، فعال کرده)."""
    if not user:
        return False
    if (user.get("role") or "member") in ("admin", "support"):
        return True
    tier = (user.get("subscription") or "free").lower()
    if tier in ("", "free"):
        return False
    exp = user.get("sub_expires_at")
    if not exp:
        return True
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(str(exp).replace(" ", "T"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt > datetime.now(timezone.utc)
    except (ValueError, TypeError):
        return True


def account_display_name(request: Request) -> str | None:
    """نام نمایشیِ کاربرِ نشستِ فعلی برای دکمهٔ حساب در هدر (یا None اگر مهمان است).
    سمت سرور رندر می‌شود تا نام بلافاصله و در همهٔ صفحات نمایش داده شود."""
    user = current_user(request)
    if not user:
        return None
    full = user.get("name") or " ".join(
        x for x in (user.get("first_name"), user.get("last_name")) if x
    )
    return (full or user.get("username") or user.get("email") or "").strip() or None


def _role_for(email: str, current: str | None = None) -> str:
    """نقش کاربر: ایمیل‌های فهرستِ ادمین همیشه «admin» می‌شوند."""
    if email and email.lower() in settings.admin_email_list:
        return "admin"
    return current or "member"


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    """اطلاعات عمومیِ کاربر برای فرانت‌اند (بدون رمز).

    نکتهٔ امنیتی: شناسهٔ کاربری (user_code) و نقش (role) فقط برای کارکنان
    (ادمین/پشتیبان) برگردانده می‌شود؛ کاربران عادی این اطلاعات را نمی‌بینند."""
    role = user.get("role") or "member"
    is_staff = role in ("admin", "support")
    full = user.get("name") or " ".join(
        x for x in (user.get("first_name"), user.get("last_name")) if x
    ) or None
    data: dict[str, Any] = {
        "id": user["id"],
        "email": user["email"],
        "username": user.get("username"),
        "name": full,
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
        "phone": user.get("phone"),
        "subscription": user.get("subscription") or "free",
        "sub_expires_at": user.get("sub_expires_at"),
        "is_staff": is_staff,
    }
    if is_staff:
        data["user_code"] = user.get("user_code")
        data["role"] = role
    return data


def _login_response(user: dict[str, Any], request: Request, body: dict | None = None) -> JSONResponse:
    """نشست می‌سازد، کوکی‌ها را ست می‌کند و داده‌های ناشناس را به حساب منتقل می‌کند."""
    # بوت‌استرپِ نقش ادمین از روی فهرست ایمیل‌ها
    desired_role = _role_for(user["email"], user.get("role"))
    if desired_role != (user.get("role") or "member"):
        db.set_user_role(int(user["id"]), desired_role)
        user["role"] = desired_role

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

    resp = JSONResponse({"ok": True, "user": _public_user(user)})
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
    first_name = (payload.get("first_name") or "").strip() or None
    last_name = (payload.get("last_name") or "").strip() or None
    username = auth.normalize_username(payload.get("username"))
    phone = auth.normalize_phone(payload.get("phone"))
    password = payload.get("password") or ""
    confirm = payload.get("confirm_password")

    # اعتبارسنجی فیلدها
    if not first_name:
        return _err("نام را وارد کنید.")
    if not last_name:
        return _err("نام خانوادگی را وارد کنید.")
    if not auth.valid_email(email):
        return _err("ایمیل نامعتبر است.")
    if (u_err := auth.username_problem(username)):
        return _err(u_err)
    if (p_err := auth.phone_problem(phone)):
        return _err(p_err)
    if (pw_err := auth.password_problem(password)):
        return _err(pw_err)
    if confirm is not None and confirm != password:
        return _err("رمز عبور و تکرار آن یکسان نیستند.")

    existing = db.get_user_by_email(email)
    if existing and existing["verified"]:
        return _err("این ایمیل قبلاً ثبت شده است. لطفاً وارد شوید.", 409)

    # یکتایی نام کاربری و شماره تماس (مالکِ آن کاربرِ دیگری نباشد)
    by_username = db.get_user_by_username(username)
    if by_username and by_username["email"] != email:
        return _err("این نام کاربری قبلاً استفاده شده است.", 409)
    by_phone = db.get_user_by_phone(phone)
    if by_phone and by_phone["email"] != email:
        return _err("این شماره تماس قبلاً ثبت شده است.", 409)

    pw_hash = auth.hash_password(password)
    pw_enc = crypto_box.encrypt(password)
    if existing:                       # تأییدنشده: اطلاعات را بازنویسی کن
        db.update_user_registration(
            int(existing["id"]), first_name=first_name, last_name=last_name,
            username=username, phone=phone, password_hash=pw_hash, password_enc=pw_enc,
        )
    else:
        anon_uid = request.cookies.get(_UID_COOKIE)
        db.create_user(
            email, pw_hash, first_name=first_name, last_name=last_name,
            username=username, phone=phone, password_enc=pw_enc,
            role=_role_for(email), uid=anon_uid, verified=False,
        )

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
    # شناسهٔ ورود می‌تواند ایمیل، شماره تماس، نام کاربری یا شناسهٔ کاربری باشد.
    raw_ident = (payload.get("identifier") or payload.get("email") or "").strip()
    password = payload.get("password") or ""
    if not raw_ident:
        return _err("شناسهٔ ورود را وارد کنید.")

    phone = auth.normalize_phone(raw_ident)
    user = db.get_user_by_login(raw_ident, phone=phone)
    if not user or not auth.verify_password(password, user["password_hash"]):
        return _err("شناسهٔ کاربری یا رمز عبور نادرست است.", 401)
    if not user["verified"]:
        try:
            await _send_code(user["email"], "verify")
        except Exception:  # noqa: BLE001
            pass
        return _err("حساب شما هنوز تأیید نشده است. کد تأیید برایتان ارسال شد.",
                    403, stage="verify", email=user["email"])
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
    db.update_user_password(int(user["id"]), auth.hash_password(password),
                            crypto_box.encrypt(password))
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
    return JSONResponse({"user": _public_user(user)})
