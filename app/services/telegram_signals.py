"""
دریافت و نگه‌داری تحلیل‌های کانال تلگرام (سیگنال‌ها).

ربات «portfolio_Cryptosmart_bot» باید ادمین کانالِ تحلیل پورتفولیو باشد. تلگرام
هر پست کانال را از طریق وب‌هوک به اندپوینت /api/advisor/telegram/webhook این
برنامه می‌فرستد. این ماژول پست را پردازش می‌کند: متنِ تحلیل + هشتگ‌ها استخراج و
تصویر چارت دانلود و ذخیره می‌شود. هر تحلیل به مدت settings.signals_ttl_days روز
معتبر است و سپس خودکار حذف می‌گردد. این تحلیل‌ها (با وین‌ریت بالا) به ورک‌فلوِ
سبدچینی هوش مصنوعی خورانده می‌شوند تا نقاط خرید/فروش روز در سبد لحاظ شود.

نکات:
  • ربات حتماً باید «ادمین» کانال باشد (عضو ساده نمی‌تواند channel_post بدهد).
  • وب‌هوک هنگام راه‌اندازی برنامه به‌صورت idempotent ثبت می‌شود (register_webhook).
  • توکن ربات فقط از .env (SIGNALS_BOT_TOKEN) خوانده می‌شود.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

from app import db
from app.config import settings

_HASHTAG_RE = re.compile(r"#(\w+)", re.UNICODE)
_SIGNALS_DIR = Path("data/signals")
_API = "https://api.telegram.org"


def _token() -> str:
    return settings.signals_bot_token or ""


def _channel_id() -> int | None:
    try:
        return int(settings.signals_channel_id)
    except (TypeError, ValueError):
        return None


# ───────────────────────── ثبت وب‌هوک ─────────────────────────
async def register_webhook() -> dict[str, Any]:
    """ثبت idempotentِ وب‌هوک تلگرام برای ربات سیگنال‌ها.

    اگر توکن تنظیم نشده باشد کاری نمی‌کند. اگر وب‌هوک از قبل روی همین URL باشد،
    دوباره ثبت نمی‌کند (برای جلوگیری از ریست شدنِ صف بی‌مورد).
    """
    token = _token()
    if not token:
        return {"ok": False, "skipped": "no_token"}
    url = f"{settings.public_base_url.rstrip('/')}/api/advisor/telegram/webhook"
    secret = settings.signals_webhook_secret_effective
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
            info = await client.get(f"{_API}/bot{token}/getWebhookInfo")
            cur = (info.json().get("result") or {}) if info.is_success else {}
            if cur.get("url") == url:
                return {"ok": True, "already": True, "url": url}
            r = await client.post(
                f"{_API}/bot{token}/setWebhook",
                json={
                    "url": url,
                    "secret_token": secret,
                    "allowed_updates": ["channel_post", "edited_channel_post"],
                    "drop_pending_updates": False,
                },
            )
            return {"ok": r.is_success, "url": url, "response": r.json()}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


# ───────────────────────── پردازش پست کانال ─────────────────────────
async def process_update(update: dict[str, Any]) -> bool:
    """یک آپدیت تلگرام را پردازش و در صورت بودنِ پست کانالِ هدف ذخیره می‌کند."""
    post = update.get("channel_post") or update.get("edited_channel_post")
    if not isinstance(post, dict):
        return False

    chat = post.get("chat") or {}
    chan_id = _channel_id()
    if chan_id is not None and chat.get("id") != chan_id:
        return False

    text = (post.get("text") or post.get("caption") or "").strip()
    file_id = _largest_photo_id(post)
    # پستی که نه متن دارد نه تصویر، ارزش ذخیره ندارد.
    if not text and not file_id:
        return False

    message_id = int(post.get("message_id") or 0)
    ts = int(post.get("date") or 0)
    tags = [t.lower() for t in _HASHTAG_RE.findall(text)]

    image_path: str | None = None
    if file_id:
        image_path = await _download_image(file_id, message_id)

    db.upsert_signal(
        message_id=message_id,
        chat_id=str(chat.get("id") or ""),
        ts=ts,
        text=text,
        hashtags_json=json.dumps(tags, ensure_ascii=False),
        image_path=image_path,
        ttl_days=settings.signals_ttl_days,
    )
    purge_expired()
    return True


def _largest_photo_id(post: dict[str, Any]) -> str | None:
    """بزرگ‌ترین نسخهٔ تصویر (photo) یا داکیومنتِ تصویری را برمی‌گرداند."""
    photos = post.get("photo") or []
    if photos:
        return photos[-1].get("file_id")
    doc = post.get("document") or {}
    if str(doc.get("mime_type") or "").startswith("image/"):
        return doc.get("file_id")
    return None


async def _download_image(file_id: str, message_id: int) -> str | None:
    """دانلود تصویر چارت از تلگرام و ذخیره در data/signals/<message_id>.<ext>."""
    token = _token()
    if not token:
        return None
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            gf = await client.get(f"{_API}/bot{token}/getFile",
                                  params={"file_id": file_id})
            gf.raise_for_status()
            file_path = ((gf.json().get("result") or {}).get("file_path")) or ""
            if not file_path:
                return None
            blob = await client.get(f"{_API}/file/bot{token}/{file_path}")
            blob.raise_for_status()
            ext = (file_path.rsplit(".", 1)[-1] or "jpg").lower()
            if len(ext) > 5 or "/" in ext:
                ext = "jpg"
            _SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
            dest = _SIGNALS_DIR / f"{message_id}.{ext}"
            dest.write_bytes(blob.content)
            return str(dest)
    except Exception:  # noqa: BLE001
        return None


# ───────────────────────── پاک‌سازی ─────────────────────────
def purge_expired() -> int:
    """حذف تحلیل‌های منقضی از دیتابیس و پاک‌کردن فایل تصویرشان."""
    paths = db.purge_expired_signals()
    removed = 0
    for p in paths:
        try:
            Path(p).unlink(missing_ok=True)
            removed += 1
        except Exception:  # noqa: BLE001
            pass
    return removed
