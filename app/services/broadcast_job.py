"""صفِ ارسالِ کنترل‌شدهٔ پیامِ همگانیِ ربات «الگو هاب».

پیش از این، پیامِ همگانی در یک حلقهٔ پیوسته و بدونِ سقف ارسال می‌شد؛ با زیاد شدنِ
کاربران این کار هم به سرور فشار می‌آورد و هم به محدودیتِ نرخِ تلگرام می‌خورد.

حالا ارسال به‌صورت «کار» (job) در پایگاه‌داده ثبت می‌شود و یک کارگرِ پس‌زمینه آن را
آرام‌آرام خالی می‌کند:

  • سقفِ ساعتی (پیش‌فرض ۵۰۰ پیام در هر ساعت) — از فشارِ ناگهانی جلوگیری می‌کند
  • دسته‌های کوچک در هر چرخه + فاصلهٔ زمانی بین دو ارسال
  • هر مقصدِ ناموفق تا ۳ بار دوباره تلاش می‌شود
  • صف در SQLite است، پس ری‌استارت/دیپلوی آن را از بین نمی‌برد
  • در پایانِ کار، خلاصهٔ نتیجه برای ادمینِ ارسال‌کننده فرستاده می‌شود

مقادیر قابلِ تنظیم (اختیاری، از .env):
  BROADCAST_HOURLY_LIMIT, BROADCAST_BATCH_SIZE,
  BROADCAST_GAP_SECONDS, BROADCAST_TICK_SECONDS
"""
from __future__ import annotations

import asyncio
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from app.config import settings
from app.services import bot_chats

_LOCK = threading.Lock()
_DB_PATH = Path(settings.portfolio_db_file)

_MAX_TRIES = 3


def _cfg(name: str, default: Any) -> Any:
    """خواندنِ تنظیماتِ اختیاری از settings با مقدارِ پیش‌فرضِ امن."""
    raw = getattr(settings, name, None)
    if raw in (None, ""):
        return default
    try:
        return type(default)(raw)
    except (TypeError, ValueError):
        return default


# سقفِ ارسال در هر ساعت (کنترلِ فشار روی سرور و رعایتِ نرخِ تلگرام).
HOURLY_LIMIT: int = _cfg("broadcast_hourly_limit", 500)
# تعدادِ پیام در هر چرخهٔ کارگر.
BATCH_SIZE: int = _cfg("broadcast_batch_size", 20)
# فاصلهٔ زمانیِ بینِ دو ارسال (ثانیه).
GAP_SECONDS: float = _cfg("broadcast_gap_seconds", 1.5)
# فاصلهٔ زمانیِ بینِ دو چرخهٔ کارگر (ثانیه).
TICK_SECONDS: float = _cfg("broadcast_tick_seconds", 10.0)


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    """ساختِ جدول‌ها در صورتِ نبودن (idempotent)."""
    with _LOCK, _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS broadcast_jobs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                from_chat   TEXT NOT NULL,
                message_id  INTEGER NOT NULL,
                created_by  TEXT,
                created_at  INTEGER NOT NULL,
                finished_at INTEGER,
                status      TEXT NOT NULL DEFAULT 'running',
                total       INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS broadcast_targets (
                job_id  INTEGER NOT NULL,
                chat_id TEXT NOT NULL,
                status  TEXT NOT NULL DEFAULT 'pending',
                tries   INTEGER NOT NULL DEFAULT 0,
                sent_at INTEGER,
                PRIMARY KEY (job_id, chat_id)
            );
            CREATE INDEX IF NOT EXISTS idx_bq_job_status
                ON broadcast_targets(job_id, status);
            CREATE INDEX IF NOT EXISTS idx_bq_sent_at
                ON broadcast_targets(sent_at);
            """
        )


# ── ثبتِ کار ────────────────────────────────────────────────────────────────
def enqueue(from_chat: str | int, message_id: int,
            chat_ids: list[str] | None = None,
            created_by: str | int | None = None) -> dict[str, Any]:
    """ثبتِ یک ارسالِ همگانیِ جدید در صف و بازگرداندنِ خلاصهٔ آن.

    اگر کارِ نیمه‌تمامی وجود داشته باشد لغو می‌شود تا صف انبار نشود.
    """
    targets = list(chat_ids if chat_ids is not None else bot_chats.known_chats())
    now = int(time.time())
    with _LOCK, _conn() as conn:
        conn.execute(
            "UPDATE broadcast_jobs SET status = 'cancelled', finished_at = ? "
            "WHERE status = 'running'",
            (now,),
        )
        cur = conn.execute(
            "INSERT INTO broadcast_jobs (from_chat, message_id, created_by, "
            "created_at, status, total) VALUES (?, ?, ?, ?, 'running', ?)",
            (str(from_chat), int(message_id),
             str(created_by) if created_by is not None else None,
             now, len(targets)),
        )
        job_id = int(cur.lastrowid)
        conn.executemany(
            "INSERT OR IGNORE INTO broadcast_targets (job_id, chat_id) VALUES (?, ?)",
            [(job_id, str(c)) for c in targets],
        )
    return {"job_id": job_id, "total": len(targets),
            "eta_minutes": eta_minutes(len(targets))}


def eta_minutes(remaining: int) -> int:
    """تخمینِ زمانِ لازم برای ارسالِ باقی‌مانده (دقیقه)، بر پایهٔ سقفِ ساعتی."""
    if remaining <= 0:
        return 0
    per_hour = max(1, min(HOURLY_LIMIT, int(3600 / max(GAP_SECONDS, 0.1))))
    return max(1, int(round(remaining / per_hour * 60)))


# ── خواندنِ وضعیت ───────────────────────────────────────────────────────────
def active_job() -> dict[str, Any] | None:
    with _LOCK, _conn() as conn:
        row = conn.execute(
            "SELECT * FROM broadcast_jobs WHERE status = 'running' "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def last_job() -> dict[str, Any] | None:
    with _LOCK, _conn() as conn:
        row = conn.execute(
            "SELECT * FROM broadcast_jobs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def progress(job_id: int | None = None) -> dict[str, Any] | None:
    """شمارشِ وضعیتِ مقصدهای یک کار (پیش‌فرض: آخرین کار)."""
    job = None
    if job_id is None:
        job = last_job()
        if not job:
            return None
        job_id = int(job["id"])
    with _LOCK, _conn() as conn:
        if job is None:
            row = conn.execute("SELECT * FROM broadcast_jobs WHERE id = ?",
                               (int(job_id),)).fetchone()
            if not row:
                return None
            job = dict(row)
        counts = {"pending": 0, "sent": 0, "failed": 0}
        for r in conn.execute(
            "SELECT status, COUNT(*) AS n FROM broadcast_targets "
            "WHERE job_id = ? GROUP BY status", (int(job_id),)
        ).fetchall():
            counts[str(r["status"])] = int(r["n"])
    out = dict(job)
    out.update(counts)
    out["eta_minutes"] = eta_minutes(counts["pending"])
    out["hourly_limit"] = HOURLY_LIMIT
    out["quota_left"] = quota_left()
    return out


def quota_left() -> int:
    """سهمیهٔ باقی‌ماندهٔ همین ساعت (پنجرهٔ لغزانِ ۶۰ دقیقه‌ای)."""
    since = int(time.time()) - 3600
    with _LOCK, _conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM broadcast_targets "
            "WHERE sent_at IS NOT NULL AND sent_at >= ?", (since,)
        ).fetchone()
    used = int(row["n"]) if row else 0
    return max(0, HOURLY_LIMIT - used)


# ── کارگرِ پس‌زمینه ─────────────────────────────────────────────────────────
def _pending(job_id: int, limit: int) -> list[str]:
    with _LOCK, _conn() as conn:
        rows = conn.execute(
            "SELECT chat_id FROM broadcast_targets "
            "WHERE job_id = ? AND status = 'pending' ORDER BY tries, rowid LIMIT ?",
            (int(job_id), int(limit)),
        ).fetchall()
    return [str(r["chat_id"]) for r in rows]


def _mark(job_id: int, chat_id: str, ok: bool) -> None:
    now = int(time.time())
    with _LOCK, _conn() as conn:
        if ok:
            conn.execute(
                "UPDATE broadcast_targets SET status = 'sent', sent_at = ?, "
                "tries = tries + 1 WHERE job_id = ? AND chat_id = ?",
                (now, int(job_id), str(chat_id)),
            )
            return
        conn.execute(
            "UPDATE broadcast_targets SET tries = tries + 1, "
            "status = CASE WHEN tries + 1 >= ? THEN 'failed' ELSE 'pending' END "
            "WHERE job_id = ? AND chat_id = ?",
            (_MAX_TRIES, int(job_id), str(chat_id)),
        )


def _finish(job_id: int) -> None:
    with _LOCK, _conn() as conn:
        conn.execute(
            "UPDATE broadcast_jobs SET status = 'done', finished_at = ? WHERE id = ?",
            (int(time.time()), int(job_id)),
        )


async def _notify_done(job: dict[str, Any]) -> None:
    """خلاصهٔ پایانِ کار برای ادمینِ ارسال‌کننده."""
    chat = job.get("created_by")
    if not chat:
        return
    p = progress(int(job["id"])) or {}
    from app.services import algohub_bot, bot_admin as ba  # lazy: جلوگیری از حلقهٔ ایمپورت
    text = (
        "✅ <b>ارسال پیام همگانی کامل شد</b>\n\n"
        f"📨 ارسال‌شده: <b>{ba._fa(p.get('sent', 0))}</b>\n"
        f"⚠️ ناموفق: <b>{ba._fa(p.get('failed', 0))}</b>\n"
        f"👥 مجموع مقصدها: <b>{ba._fa(p.get('total', 0))}</b>"
    )
    try:
        await algohub_bot.send_message(chat, text)
    except Exception:  # noqa: BLE001
        pass


async def tick() -> int:
    """یک چرخهٔ ارسال. تعدادِ پیام‌های ارسال‌شده در این چرخه را برمی‌گرداند."""
    job = active_job()
    if not job:
        return 0
    left = quota_left()
    if left <= 0:
        return 0                      # سهمیهٔ این ساعت تمام شده؛ چرخهٔ بعد
    chats = _pending(int(job["id"]), max(1, min(left, BATCH_SIZE)))
    if not chats:
        _finish(int(job["id"]))
        await _notify_done(job)
        return 0

    from app.services import algohub_bot  # lazy: جلوگیری از حلقهٔ ایمپورت
    sent = 0
    for chat_id in chats:
        try:
            ok = bool(await algohub_bot.copy_message(
                chat_id, job["from_chat"], int(job["message_id"])))
        except Exception:  # noqa: BLE001
            ok = False
        _mark(int(job["id"]), chat_id, ok)
        if ok:
            sent += 1
            bot_chats.mark_sent(chat_id)
        else:
            bot_chats.mark_failed(chat_id)
        await asyncio.sleep(GAP_SECONDS)
    return sent


async def loop() -> None:
    """حلقهٔ همیشگیِ کارگر — در استارت‌آپِ اپلیکیشن اجرا می‌شود."""
    while True:
        try:
            await tick()
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(TICK_SECONDS)


init()
