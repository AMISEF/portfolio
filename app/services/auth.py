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
    """پیام خطای فارسی اگر رمز ضعیف باشد، در غیر این صورت None."""
    if len(password or "") < 8:
        return "رمز عبور باید حداقل ۸ کاراکتر باشد."
    return None
