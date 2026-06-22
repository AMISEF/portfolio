"""
رمزنگاری برگشت‌پذیرِ سبک — فقط برای ذخیرهٔ نسخه‌ای از گذرواژه که «ادمین» بتواند
آن را ببیند (طبق درخواست مالک محصول).

هشدار امنیتی: این جدا از هشِ یک‌طرفهٔ PBKDF2 است که برای احراز هویت به‌کار می‌رود.
گذرواژهٔ اصلی هرگز به‌صورت متن‌ساده ذخیره نمی‌شود؛ این نسخه با کلید مخفیِ سرور
(ADMIN_SECRET_KEY در .env) رمز می‌شود. اگر هم دیتابیس و هم کلید لو بروند، گذرواژه‌ها
قابل بازیابی‌اند — پس کلید باید قوی و خارج از مخزن نگه‌داری شود.

بدون وابستگی بیرونی: رمزِ جریانی مبتنی بر HMAC-SHA256 در حالت شمارنده + برچسب
اصالت (MAC). کافی برای این کاربردِ داخلی، بدون نیاز به کتابخانهٔ cryptography.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os

from app.config import settings


def _key() -> bytes:
    return hashlib.sha256(settings.admin_secret_key.encode("utf-8")).digest()


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out += hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        counter += 1
    return bytes(out[:length])


def encrypt(plaintext: str) -> str:
    """متن → رشتهٔ base64 (nonce|mac|ciphertext)."""
    key = _key()
    nonce = os.urandom(16)
    data = plaintext.encode("utf-8")
    ks = _keystream(key, nonce, len(data))
    ct = bytes(a ^ b for a, b in zip(data, ks))
    mac = hmac.new(key, nonce + ct, hashlib.sha256).digest()[:16]
    return base64.b64encode(nonce + mac + ct).decode("ascii")


def decrypt(token: str | None) -> str | None:
    """بازگشت متن اصلی یا None در صورت نبودن/خرابی/دستکاری."""
    if not token:
        return None
    try:
        raw = base64.b64decode(token)
        nonce, mac, ct = raw[:16], raw[16:32], raw[32:]
        key = _key()
        expected = hmac.new(key, nonce + ct, hashlib.sha256).digest()[:16]
        if not hmac.compare_digest(mac, expected):
            return None
        ks = _keystream(key, nonce, len(ct))
        return bytes(a ^ b for a, b in zip(ct, ks)).decode("utf-8")
    except Exception:  # noqa: BLE001
        return None
