"""چت‌های خصوصیِ ربات «الگو هاب» — مقصدهای پیامِ همگانی.

پیش از این، پیامِ همگانی فقط به چت‌هایی می‌رفت که در جدولِ ``tg_links`` بودند و
آن جدول تنها زمانی پر می‌شود که کاربرِ پنل، دکمهٔ «اتصال به تلگرام» را بزند و
لینکِ ``/start <token>`` را باز کند. در نتیجه کسانی که فقط ربات را استارت کرده
بودند (اکثریتِ کاربرانِ ربات) هیچ‌وقت مقصدِ پیامِ همگانی نمی‌شدند و گزارش همیشه
«ارسال‌شده: ۰ / ناموفق: ۰» بود.

این ماژول هر چتِ خصوصی‌ای که با ربات حرف بزند را در جدولِ ``bot_chats`` ثبت
می‌کند (در سطحِ وب‌هوک، پیش از پردازشِ آپدیت) و فهرستِ مقصدها را از اجتماعِ
``bot_chats`` و ``tg_links`` به‌علاوهٔ چتِ مالک می‌سازد. چتی که چند بار پشت سر هم
ناموفق باشد (کاربر ربات را بلاک یا حسابش را حذف کرده) غیرفعال می‌شود تا دیگر
بی‌جهت تلاش نشود.

همان فایلِ SQLite لایهٔ اصلی (``app/db.py``) استفاده می‌شود.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from app.config import settings

_LOCK = threading.Lock()
_DB_PATH = Path(settings.portfolio_db_file)

# پس از این تعداد شکستِ پشت‌سرهم، چت غیرفعال می‌شود (بلاک/حذفِ حساب).
_MAX_FAILS = 3


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    """ساختِ جدول در صورت نبودن (idempotent)."""
    with _LOCK, _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS bot_chats (
                chat_id    TEXT PRIMARY KEY,
                username   TEXT,
                first_name TEXT,
                active     INTEGER NOT NULL DEFAULT 1,
                fails      INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_seen  TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_bot_chats_active ON bot_chats(active);
            """
        )


def seen(chat_id: str | int | None, username: str | None = None,
         first_name: str | None = None) -> None:
    """ثبت/به‌روزرسانیِ یک چت. هر تماسِ کاربر، چت را دوباره فعال می‌کند."""
    if chat_id in (None, ""):
        return
    with _LOCK, _conn() as conn:
        conn.execute(
            "INSERT INTO bot_chats (chat_id, username, first_name) VALUES (?, ?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET "
            "  username   = COALESCE(excluded.username, bot_chats.username), "
            "  first_name = COALESCE(excluded.first_name, bot_chats.first_name), "
            "  active = 1, fails = 0, last_seen = datetime('now')",
            (str(chat_id), username, first_name),
        )


def remember_update(update: dict[str, Any]) -> str | None:
    """استخراجِ چتِ خصوصی از یک آپدیتِ تلگرام و ثبتِ آن.

    هم پیام‌ها و هم کلیکِ دکمه‌های شیشه‌ای پوشش داده می‌شوند. گروه/کانال ثبت
    نمی‌شود (پیامِ همگانی فقط برای چتِ خصوصیِ کاربران است).
    """
    if not isinstance(update, dict):
        return None
    cb = update.get("callback_query") or {}
    if not isinstance(cb, dict):
        cb = {}
    msg = (update.get("message") or update.get("edited_message")
           or cb.get("message") or {})
    if not isinstance(msg, dict):
        return None
    chat = msg.get("chat") or {}
    if not isinstance(chat, dict) or chat.get("type") != "private":
        return None
    chat_id = chat.get("id")
    if chat_id is None:
        return None
    src = (cb.get("from") if cb else msg.get("from")) or {}
    if not isinstance(src, dict):
        src = {}
    seen(chat_id,
         src.get("username") or chat.get("username"),
         src.get("first_name") or chat.get("first_name"))
    return str(chat_id)


def known_chats() -> list[str]:
    """همهٔ مقصدهای پیامِ همگانی: bot_chats فعال + حساب‌های متصل + چتِ مالک."""
    out: list[str] = []
    picked: set[str] = set()

    def _add(value: Any) -> None:
        cid = str(value or "").strip()
        if cid and cid not in picked:
            picked.add(cid)
            out.append(cid)

    with _LOCK, _conn() as conn:
        try:
            rows = conn.execute(
                "SELECT chat_id FROM bot_chats WHERE active = 1 AND chat_id <> '' "
                "ORDER BY created_at"
            ).fetchall()
        except sqlite3.Error:
            rows = []
        for r in rows:
            _add(r["chat_id"])
        try:
            linked = conn.execute(
                "SELECT DISTINCT chat_id FROM tg_links WHERE chat_id <> ''"
            ).fetchall()
        except sqlite3.Error:
            linked = []
        for r in linked:
            _add(r["chat_id"])

    # مالک همیشه پیام را می‌گیرد (تأییدِ عملیِ ارسال).
    _add(settings.algohub_owner_id)
    return out


def count() -> int:
    return len(known_chats())


def mark_sent(chat_id: str | int) -> None:
    with _LOCK, _conn() as conn:
        conn.execute(
            "UPDATE bot_chats SET fails = 0, active = 1, last_seen = datetime('now') "
            "WHERE chat_id = ?",
            (str(chat_id),),
        )


def mark_failed(chat_id: str | int) -> bool:
    """شمارشِ شکست؛ اگر به سقف رسید چت غیرفعال می‌شود. True = غیرفعال شد."""
    with _LOCK, _conn() as conn:
        conn.execute(
            "INSERT INTO bot_chats (chat_id, fails) VALUES (?, 1) "
            "ON CONFLICT(chat_id) DO UPDATE SET fails = bot_chats.fails + 1",
            (str(chat_id),),
        )
        row = conn.execute(
            "SELECT fails FROM bot_chats WHERE chat_id = ?", (str(chat_id),)
        ).fetchone()
        fails = int(row["fails"]) if row and row["fails"] is not None else 1
        if fails < _MAX_FAILS:
            return False
        conn.execute("UPDATE bot_chats SET active = 0 WHERE chat_id = ?",
                     (str(chat_id),))
        return True


def list_chats(limit: int = 500) -> list[dict[str, Any]]:
    with _LOCK, _conn() as conn:
        try:
            rows = conn.execute(
                "SELECT * FROM bot_chats ORDER BY last_seen DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        except sqlite3.Error:
            return []
        return [dict(r) for r in rows]


# تضمینِ وجودِ جدول حتی بدونِ رویدادِ startup (idempotent).
init()
