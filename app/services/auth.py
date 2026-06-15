"""
سرویس احراز هویت.

* هش رمز عبور با pbkdf2 (کتابخانهٔ استاندارد — بدون وابستگی اضافی، دیباگ آسان).
* اعتبارسنجی initData مینی‌اپ تلگرام طبق الگوریتم رسمی (HMAC-SHA256).
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Optional
from urllib.parse import parse_qsl

from sqlmodel import Session, select

from app.config import settings
from app.models import User

_ITERATIONS = 200_000


# ---------------- رمز عبور ----------------
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt}${dk.hex()}"


def verify_password(password: str, stored: Optional[str]) -> bool:
    if not stored:
        return False
    try:
        algo, iters, salt, digest = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(dk.hex(), digest)
    except (ValueError, TypeError):
        return False


# ---------------- کاربر ----------------
def get_user_by_login(session: Session, login: str) -> Optional[User]:
    login = (login or "").strip().lower()
    return session.exec(
        select(User).where((User.email == login) | (User.username == login))
    ).first()


def create_user(session: Session, *, login: str, password: str, display_name: str = "") -> User:
    login = login.strip()
    is_email = "@" in login
    user = User(
        email=login.lower() if is_email else None,
        username=None if is_email else login.lower(),
        password_hash=hash_password(password),
        display_name=display_name or login.split("@")[0],
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def authenticate(session: Session, login: str, password: str) -> Optional[User]:
    user = get_user_by_login(session, login)
    if user and verify_password(password, user.password_hash):
        return user
    return None


# ---------------- تلگرام ----------------
def verify_telegram_init_data(init_data: str) -> Optional[dict]:
    """اعتبارسنجی initData مینی‌اپ تلگرام. در صورت معتبر بودن، dict کاربر را برمی‌گرداند."""
    if not settings.telegram_bot_token or not init_data:
        return None
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None
    data_check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", settings.telegram_bot_token.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, received_hash):
        return None
    import json
    try:
        return json.loads(pairs.get("user", "{}"))
    except json.JSONDecodeError:
        return None


def get_or_create_telegram_user(session: Session, tg: dict) -> User:
    tg_id = tg.get("id")
    user = session.exec(select(User).where(User.telegram_id == tg_id)).first()
    if user:
        return user
    user = User(
        telegram_id=tg_id,
        username=tg.get("username"),
        display_name=" ".join(filter(None, [tg.get("first_name"), tg.get("last_name")])) or tg.get("username"),
        photo_url=tg.get("photo_url"),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
