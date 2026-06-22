"""
ابزارهای احراز هویت — هش رمز عبور و تولید/بررسی کد یک‌بارمصرف.

فقط با کتابخانهٔ استاندارد پایتون (بدون وابستگی اضافه):
  • رمز عبور با PBKDF2-HMAC-SHA256 و نمک تصادفی هش می‌شود.
  • کد یک‌بارمصرف (۶ رقمی) به‌صورت هش‌شده ذخیره می‌شود تا حتی در صورت نشت
    دیتابیس، کدها لو نروند.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets

_PBKDF2_ROUNDS = 200_000
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
_PHONE_RE = re.compile(r"^0\d{10}$")  # موبایل ایران: ۱۱ رقم با صفر ابتدایی

# نگاشت ارقام فارسی/عربی به اَسکی (برای نرمال‌سازی شماره تماس)
_DIGIT_MAP = {ord(p): str(i) for i, p in enumerate("۰۱۲۳۴۵۶۷۸۹")}
_DIGIT_MAP.update({ord(p): str(i) for i, p in enumerate("٠١٢٣٤٥٦٧٨٩")})


# ---------- رمز عبور ----------
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt, digest = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(dk.hex(), digest)
    except (ValueError, TypeError):
        return False


# ---------- کد یک‌بارمصرف ----------
def gen_code() -> str:
    """کد عددی ۶ رقمی (۰۰۰۰۰۰ تا ۹۹۹۹۹۹)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def verify_code(code: str, code_hash: str) -> bool:
    return hmac.compare_digest(hashlib.sha256(code.encode()).hexdigest(), code_hash)


def gen_session_token() -> str:
    return secrets.token_urlsafe(32)


# ---------- اعتبارسنجی ورودی ----------
def valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match((email or "").strip()))


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def password_problem(password: str) -> str | None:
    """پیام خطای فارسی اگر رمز شرایط امنیتی را نداشته باشد، در غیر این صورت None.

    سیاست: حداقل ۸ کاراکتر + حرف کوچک + حرف بزرگ + عدد. نمادها اختیاری‌اند.
    """
    p = password or ""
    if len(p) < 8:
        return "رمز عبور باید حداقل ۸ کاراکتر باشد."
    if not re.search(r"[a-z]", p):
        return "رمز عبور باید شامل حرف کوچک انگلیسی (a-z) باشد."
    if not re.search(r"[A-Z]", p):
        return "رمز عبور باید شامل حرف بزرگ انگلیسی (A-Z) باشد."
    if not re.search(r"[0-9]", p):
        return "رمز عبور باید شامل حداقل یک عدد باشد."
    return None


def normalize_phone(phone: str) -> str:
    """ارقام فارسی/عربی → اَسکی، حذف فاصله/خط‌تیره و تبدیل +98/0098/98 به 0."""
    s = (phone or "").translate(_DIGIT_MAP)
    s = re.sub(r"[\s\-()]+", "", s)
    if s.startswith("+98"):
        s = "0" + s[3:]
    elif s.startswith("0098"):
        s = "0" + s[4:]
    elif s.startswith("98") and len(s) == 12:
        s = "0" + s[2:]
    return s


def phone_problem(phone: str) -> str | None:
    """شماره تماس باید با ۰ شروع شود و ۱۱ رقم باشد (مثل 09123456789)."""
    s = normalize_phone(phone)
    if not s:
        return "شماره تماس را وارد کنید."
    if not s.startswith("0"):
        return "شماره تماس باید با ۰ شروع شود (مثال: 09121234567)."
    if not _PHONE_RE.match(s):
        return "شماره تماس باید ۱۱ رقم و با ۰ شروع شود (مثال: 09121234567)."
    return None


def username_problem(username: str) -> str | None:
    """نام کاربری: ۳ تا ۲۰ کاراکتر، فقط حروف انگلیسی/عدد/زیرخط."""
    u = (username or "").strip()
    if not u:
        return "نام کاربری را وارد کنید."
    if not _USERNAME_RE.match(u):
        return "نام کاربری باید ۳ تا ۲۰ کاراکتر و فقط شامل حروف انگلیسی، عدد و _ باشد."
    return None


def normalize_username(username: str) -> str:
    return (username or "").strip()


def looks_like_email(ident: str) -> bool:
    return "@" in (ident or "")
