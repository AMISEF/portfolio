"""
لایهٔ دیتابیس سبک پورتفولیو (SQLite، بدون وابستگی اضافه).

* پروفایل ریسک هر کاربر و دارایی‌های پورتفولیوی او ذخیره می‌شود.
* تا پیش از فعال‌شدن احراز هویت واقعی، هر کاربر با شناسهٔ ناشناسِ کوکی‌محور
  (uid) شناخته می‌شود؛ هنگام اتصال احراز هویت، می‌توان رکوردها را مهاجرت داد.
* فایل دیتابیس در data/portfolio.db است و طبق .gitignore هرگز کامیت نمی‌شود.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from app.config import settings

_LOCK = threading.Lock()
_DB_PATH = Path(settings.portfolio_db_file)


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """ساخت جداول در صورت نبودن (اجرا هنگام راه‌اندازی برنامه)."""
    with _LOCK, _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS risk_profiles (
                uid         TEXT PRIMARY KEY,
                raw         INTEGER NOT NULL,
                percent     REAL NOT NULL,
                category    TEXT NOT NULL,
                label       TEXT NOT NULL,
                answers     TEXT NOT NULL,
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS assets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                uid         TEXT NOT NULL,
                kind        TEXT NOT NULL,   -- crypto | gold | usdt | toman
                symbol      TEXT NOT NULL,   -- BTC، ETH، GOLD، ...
                name        TEXT NOT NULL,
                amount      REAL NOT NULL,
                buy_price   REAL,            -- قیمت خرید هر واحد (تومان)
                purity      TEXT,            -- برای طلا: 18 | 24 | ounce
                horizon     TEXT,            -- افق سرمایه‌گذاری (متن)
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_assets_uid ON assets(uid);

            -- کاربران ثبت‌نام‌شده (احراز هویت ایمیلی)
            CREATE TABLE IF NOT EXISTS users (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_code      TEXT UNIQUE,   -- شناسهٔ کاربریِ عمومی (مثل CS-100001)
                username       TEXT UNIQUE,   -- نام کاربری
                email          TEXT UNIQUE NOT NULL,
                name           TEXT,          -- نام کاملِ قدیمی (سازگاری عقب‌رو)
                first_name     TEXT,          -- نام
                last_name      TEXT,          -- نام خانوادگی
                phone          TEXT,          -- شماره تماس (با صفر ابتدایی، متنی)
                password_hash  TEXT NOT NULL,
                password_enc   TEXT,          -- نسخهٔ برگشت‌پذیرِ رمز (برای نمایش به ادمین)
                role           TEXT NOT NULL DEFAULT 'member',   -- admin | support | member
                subscription   TEXT NOT NULL DEFAULT 'free',     -- free | pro | vip
                sub_expires_at TEXT,          -- تاریخ انقضای اشتراک (NULL = نامحدود/رایگان)
                verified       INTEGER NOT NULL DEFAULT 0,
                uid            TEXT,           -- پیوند به شناسهٔ ناشناس cs_uid (مهاجرت داده)
                created_at     TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- کدهای یک‌بارمصرف (تأیید ثبت‌نام / بازیابی رمز) — هش‌شده ذخیره می‌شوند
            CREATE TABLE IF NOT EXISTS auth_codes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                email       TEXT NOT NULL,
                code_hash   TEXT NOT NULL,
                purpose     TEXT NOT NULL,   -- verify | reset
                expires_at  TEXT NOT NULL,
                used        INTEGER NOT NULL DEFAULT 0,
                attempts    INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_codes_email ON auth_codes(email, purpose);

            -- نشست‌های ورود (توکن تصادفی در کوکی)
            CREATE TABLE IF NOT EXISTS sessions (
                token       TEXT PRIMARY KEY,
                user_id     INTEGER NOT NULL,
                expires_at  TEXT NOT NULL,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

            -- تاریخچهٔ ارزش کل سبد (برای نمودار پورتفولیو)
            CREATE TABLE IF NOT EXISTS portfolio_history (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                uid          TEXT NOT NULL,
                ts           TEXT NOT NULL DEFAULT (datetime('now')),
                total_toman  REAL NOT NULL,
                total_usd    REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_pfhist_uid ON portfolio_history(uid, ts);
            """
        )
        _migrate_users(conn)


def _migrate_users(conn: sqlite3.Connection) -> None:
    """افزودن ستون‌های جدیدِ users به دیتابیس‌های موجود (idempotent)."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    add = {
        "user_code": "TEXT",
        "username": "TEXT",
        "first_name": "TEXT",
        "last_name": "TEXT",
        "phone": "TEXT",
        "password_enc": "TEXT",
        "role": "TEXT NOT NULL DEFAULT 'member'",
        "subscription": "TEXT NOT NULL DEFAULT 'free'",
        "sub_expires_at": "TEXT",
    }
    for name, decl in add.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE users ADD COLUMN {name} {decl}")
    # شناسهٔ کاربری برای رکوردهای قدیمیِ بدون user_code
    conn.execute(
        "UPDATE users SET user_code = 'CS-' || (100000 + id) WHERE user_code IS NULL OR user_code = ''"
    )
    # ایندکس‌ها پس از افزوده‌شدن ستون‌ها (روی دیتابیس‌های قدیمی هم امن است)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone)")


def assign_user_code(user_id: int) -> str:
    """تخصیص شناسهٔ کاربریِ یکتا بر اساس id (CS-100001 …)."""
    code = f"CS-{100000 + int(user_id)}"
    with _LOCK, _conn() as conn:
        conn.execute("UPDATE users SET user_code = ? WHERE id = ?", (code, user_id))
    return code


# ---- پروفایل ریسک ----
def save_risk(uid: str, result: dict[str, Any], answers_json: str) -> None:
    with _LOCK, _conn() as conn:
        conn.execute(
            """
            INSERT INTO risk_profiles (uid, raw, percent, category, label, answers)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(uid) DO UPDATE SET
                raw=excluded.raw, percent=excluded.percent, category=excluded.category,
                label=excluded.label, answers=excluded.answers, updated_at=datetime('now')
            """,
            (uid, result["raw"], result["percent"], result["key"], result["label"], answers_json),
        )


def get_risk(uid: str) -> dict[str, Any] | None:
    with _LOCK, _conn() as conn:
        row = conn.execute("SELECT * FROM risk_profiles WHERE uid = ?", (uid,)).fetchone()
        return dict(row) if row else None


# ---- دارایی‌ها ----
def add_asset(uid: str, a: dict[str, Any]) -> int:
    with _LOCK, _conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO assets (uid, kind, symbol, name, amount, buy_price, purity, horizon)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (uid, a["kind"], a["symbol"], a["name"], a["amount"],
             a.get("buy_price"), a.get("purity"), a.get("horizon")),
        )
        return int(cur.lastrowid)


def list_assets(uid: str) -> list[dict[str, Any]]:
    with _LOCK, _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM assets WHERE uid = ? ORDER BY id", (uid,)
        ).fetchall()
        return [dict(r) for r in rows]


def delete_asset(uid: str, asset_id: int) -> bool:
    with _LOCK, _conn() as conn:
        cur = conn.execute("DELETE FROM assets WHERE uid = ? AND id = ?", (uid, asset_id))
        return cur.rowcount > 0


def clear_assets(uid: str) -> None:
    with _LOCK, _conn() as conn:
        conn.execute("DELETE FROM assets WHERE uid = ?", (uid,))


def reassign_assets(from_uid: str, to_uid: str) -> None:
    """انتقال دارایی‌ها و پروفایل ریسک از یک شناسه به شناسهٔ دیگر (هنگام ورود)."""
    with _LOCK, _conn() as conn:
        conn.execute("UPDATE assets SET uid = ? WHERE uid = ?", (to_uid, from_uid))
        conn.execute("UPDATE portfolio_history SET uid = ? WHERE uid = ?", (to_uid, from_uid))


# ---- تاریخچهٔ ارزش سبد ----
def record_portfolio_value(uid: str, total_toman: float, total_usd: float) -> None:
    """ثبت ارزش کل سبد. گلوگاه: حداکثر هر ۱ ساعت یک نمونه برای هر کاربر."""
    with _LOCK, _conn() as conn:
        last = conn.execute(
            "SELECT ts FROM portfolio_history WHERE uid = ? ORDER BY ts DESC LIMIT 1", (uid,)
        ).fetchone()
        if last:
            recent = conn.execute(
                "SELECT (julianday('now') - julianday(?)) * 24 AS hrs", (last["ts"],)
            ).fetchone()
            if recent and recent["hrs"] is not None and recent["hrs"] < 1.0:
                return
        conn.execute(
            "INSERT INTO portfolio_history (uid, total_toman, total_usd) VALUES (?, ?, ?)",
            (uid, float(total_toman), float(total_usd)),
        )


def get_portfolio_history(uid: str, days: int = 365) -> list[dict[str, Any]]:
    with _LOCK, _conn() as conn:
        rows = conn.execute(
            "SELECT ts, total_toman, total_usd FROM portfolio_history "
            "WHERE uid = ? AND ts >= datetime('now', ?) ORDER BY ts",
            (uid, f"-{int(days)} days"),
        ).fetchall()
        return [dict(r) for r in rows]


# ---- کاربران ----
def get_user_by_email(email: str) -> dict[str, Any] | None:
    with _LOCK, _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with _LOCK, _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_user_by_username(username: str) -> dict[str, Any] | None:
    with _LOCK, _conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_phone(phone: str) -> dict[str, Any] | None:
    with _LOCK, _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
        return dict(row) if row else None


def get_user_by_login(ident: str, phone: str | None = None) -> dict[str, Any] | None:
    """یافتن کاربر با ایمیل یا نام کاربری یا شناسهٔ کاربری یا شماره تماس."""
    with _LOCK, _conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ? COLLATE NOCASE "
            "OR username = ? COLLATE NOCASE OR user_code = ? COLLATE NOCASE OR phone = ? "
            "LIMIT 1",
            (ident, ident, ident, phone or ident),
        ).fetchone()
        return dict(row) if row else None


def create_user(email: str, password_hash: str, *,
                first_name: str | None = None, last_name: str | None = None,
                username: str | None = None, phone: str | None = None,
                password_enc: str | None = None, role: str = "member",
                uid: str | None = None, verified: bool = False) -> int:
    full = " ".join(x for x in (first_name, last_name) if x) or None
    with _LOCK, _conn() as conn:
        cur = conn.execute(
            "INSERT INTO users (email, name, first_name, last_name, username, phone, "
            "password_hash, password_enc, role, verified, uid) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (email, full, first_name, last_name, username, phone,
             password_hash, password_enc, role, 1 if verified else 0, uid),
        )
        user_id = int(cur.lastrowid)
        conn.execute("UPDATE users SET user_code = ? WHERE id = ?",
                     (f"CS-{100000 + user_id}", user_id))
        return user_id


def update_user_password(user_id: int, password_hash: str,
                         password_enc: str | None = None) -> None:
    with _LOCK, _conn() as conn:
        if password_enc is not None:
            conn.execute("UPDATE users SET password_hash = ?, password_enc = ? WHERE id = ?",
                         (password_hash, password_enc, user_id))
        else:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                         (password_hash, user_id))


def set_user_verified(user_id: int) -> None:
    with _LOCK, _conn() as conn:
        conn.execute("UPDATE users SET verified = 1 WHERE id = ?", (user_id,))


def set_user_role(user_id: int, role: str) -> None:
    with _LOCK, _conn() as conn:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))


def update_user_registration(user_id: int, *, first_name: str | None, last_name: str | None,
                             username: str | None, phone: str | None,
                             password_hash: str, password_enc: str | None) -> None:
    """بازنویسی اطلاعات کاربرِ ثبت‌نام‌شدهٔ تأییدنشده (ثبت‌نام مجدد پیش از تأیید)."""
    full = " ".join(x for x in (first_name, last_name) if x) or None
    with _LOCK, _conn() as conn:
        conn.execute(
            "UPDATE users SET name = ?, first_name = ?, last_name = ?, username = ?, "
            "phone = ?, password_hash = ?, password_enc = ? WHERE id = ?",
            (full, first_name, last_name, username, phone, password_hash, password_enc, user_id),
        )


# ---- مدیریت کاربران (ادمین) ----
def list_users() -> list[dict[str, Any]]:
    """فهرست همهٔ کاربران + تعداد دارایی‌های هرکدام (برای پنل ادمین)."""
    with _LOCK, _conn() as conn:
        rows = conn.execute(
            "SELECT u.*, "
            "(SELECT COUNT(*) FROM assets a WHERE a.uid = u.uid OR a.uid = 'u' || u.id) "
            "AS asset_count "
            "FROM users u ORDER BY u.id"
        ).fetchall()
        return [dict(r) for r in rows]


def admin_update_user(user_id: int, fields: dict[str, Any]) -> None:
    """به‌روزرسانی گزینشیِ ستون‌های مجاز توسط ادمین."""
    allowed = {"first_name", "last_name", "username", "email", "phone",
               "role", "subscription", "sub_expires_at", "verified",
               "password_hash", "password_enc", "name"}
    sets, vals = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return
    vals.append(user_id)
    with _LOCK, _conn() as conn:
        conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", vals)


def set_subscription(user_id: int, subscription: str | None = None,
                     sub_expires_at: str | None = "__keep__") -> None:
    with _LOCK, _conn() as conn:
        if subscription is not None and sub_expires_at != "__keep__":
            conn.execute("UPDATE users SET subscription = ?, sub_expires_at = ? WHERE id = ?",
                         (subscription, sub_expires_at, user_id))
        elif subscription is not None:
            conn.execute("UPDATE users SET subscription = ? WHERE id = ?", (subscription, user_id))
        elif sub_expires_at != "__keep__":
            conn.execute("UPDATE users SET sub_expires_at = ? WHERE id = ?",
                         (sub_expires_at, user_id))


def renew_subscription(user_id: int, days: int) -> str:
    """تمدید اشتراک به اندازهٔ days از زمان فعلی یا انقضای فعلی (هرکدام دیرتر)."""
    with _LOCK, _conn() as conn:
        row = conn.execute("SELECT sub_expires_at FROM users WHERE id = ?", (user_id,)).fetchone()
        base = "datetime('now')"
        cur_exp = row["sub_expires_at"] if row else None
        if cur_exp:
            conn.execute(
                "UPDATE users SET sub_expires_at = datetime("
                "MAX(sub_expires_at, datetime('now')), ?) WHERE id = ?",
                (f"+{int(days)} days", user_id),
            )
        else:
            conn.execute(
                f"UPDATE users SET sub_expires_at = datetime({base}, ?) WHERE id = ?",
                (f"+{int(days)} days", user_id),
            )
        new = conn.execute("SELECT sub_expires_at FROM users WHERE id = ?", (user_id,)).fetchone()
        return new["sub_expires_at"] if new else ""


def delete_user(user_id: int) -> None:
    """حذف کاربر و نشست‌هایش (دارایی‌ها با uid باقی می‌مانند)."""
    with _LOCK, _conn() as conn:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def user_assets(user_id: int) -> list[dict[str, Any]]:
    """دارایی‌های یک کاربر (با uid کاربر یا الگوی u{id})."""
    u = get_user_by_id(user_id)
    if not u:
        return []
    uid = u.get("uid") or f"u{user_id}"
    with _LOCK, _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM assets WHERE uid = ? OR uid = ? ORDER BY id",
            (uid, f"u{user_id}"),
        ).fetchall()
        return [dict(r) for r in rows]


# ---- کدهای یک‌بارمصرف ----
def latest_code_age_seconds(email: str, purpose: str) -> float | None:
    """سن جدیدترین کد صادرشده (ثانیه)؛ برای کنترل فاصلهٔ ارسال مجدد."""
    with _LOCK, _conn() as conn:
        row = conn.execute(
            "SELECT (julianday('now') - julianday(created_at)) * 86400 AS age "
            "FROM auth_codes WHERE email = ? AND purpose = ? ORDER BY id DESC LIMIT 1",
            (email, purpose),
        ).fetchone()
        return float(row["age"]) if row and row["age"] is not None else None


def add_code(email: str, code_hash: str, purpose: str, ttl_seconds: int) -> None:
    """ثبت کد جدید و باطل‌کردن کدهای قبلیِ همان هدف."""
    with _LOCK, _conn() as conn:
        conn.execute(
            "UPDATE auth_codes SET used = 1 WHERE email = ? AND purpose = ? AND used = 0",
            (email, purpose),
        )
        conn.execute(
            "INSERT INTO auth_codes (email, code_hash, purpose, expires_at) "
            "VALUES (?, ?, ?, datetime('now', ?))",
            (email, code_hash, purpose, f"+{int(ttl_seconds)} seconds"),
        )


def get_active_code(email: str, purpose: str) -> dict[str, Any] | None:
    with _LOCK, _conn() as conn:
        row = conn.execute(
            "SELECT * FROM auth_codes WHERE email = ? AND purpose = ? AND used = 0 "
            "AND expires_at > datetime('now') ORDER BY id DESC LIMIT 1",
            (email, purpose),
        ).fetchone()
        return dict(row) if row else None


def bump_code_attempts(code_id: int) -> int:
    with _LOCK, _conn() as conn:
        conn.execute("UPDATE auth_codes SET attempts = attempts + 1 WHERE id = ?", (code_id,))
        row = conn.execute("SELECT attempts FROM auth_codes WHERE id = ?", (code_id,)).fetchone()
        return int(row["attempts"]) if row else 0


def consume_code(code_id: int) -> None:
    with _LOCK, _conn() as conn:
        conn.execute("UPDATE auth_codes SET used = 1 WHERE id = ?", (code_id,))


# ---- نشست‌ها ----
def create_session(token: str, user_id: int, ttl_days: int) -> None:
    with _LOCK, _conn() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at) "
            "VALUES (?, ?, datetime('now', ?))",
            (token, user_id, f"+{int(ttl_days)} days"),
        )


def get_session_user(token: str) -> dict[str, Any] | None:
    """کاربرِ نشستِ معتبر را برمی‌گرداند (در صورت انقضا None)."""
    with _LOCK, _conn() as conn:
        row = conn.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token = ? AND s.expires_at > datetime('now')",
            (token,),
        ).fetchone()
        return dict(row) if row else None


def delete_session(token: str) -> None:
    with _LOCK, _conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


# تضمین وجود جداول حتی بدون رویداد startup (idempotent).
init_db()
