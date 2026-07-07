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

            -- شمارش ماهانهٔ تحلیل سبد با هوش مصنوعی (سهمیهٔ پلن کاربر).
            -- month = YYYY-MM به وقت تهران؛ کلید روی (user_id, month).
            CREATE TABLE IF NOT EXISTS ai_usage (
                user_id    INTEGER NOT NULL,
                month      TEXT NOT NULL,
                used       INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, month)
            );

            -- تحلیل‌های کانال تلگرام (سیگنال‌ها) با اعتبار محدود (پیش‌فرض ۷ روز).
            -- هر پست کانال = یک تحلیل ارز با نقاط خرید/فروش + تصویر چارت.
            CREATE TABLE IF NOT EXISTS channel_signals (
                message_id  INTEGER PRIMARY KEY,   -- شناسهٔ پیام کانال (یکتا)
                chat_id     TEXT,
                ts          INTEGER NOT NULL,       -- زمان پست (unix از تلگرام)
                text        TEXT NOT NULL DEFAULT '',
                hashtags    TEXT NOT NULL DEFAULT '[]',
                image_path  TEXT,                   -- تصویرِ نخست (سازگاریِ عقب‌رو + خوراکِ سبد AI)
                image_path2 TEXT,                   -- تصویرِ دوم (سازگاریِ عقب‌رو)
                images      TEXT,                    -- آرایهٔ JSON از همهٔ تصاویرِ آلبوم (n تصویر)
                media_group_id TEXT,                -- شناسهٔ آلبومِ تلگرام (برای گروه‌بندی چند‌تصویری)
                source      TEXT NOT NULL DEFAULT 'channel',  -- channel | admin
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                expires_at  TEXT NOT NULL           -- پس از این زمان از پیشنهادها حذف می‌شود
            );
            CREATE INDEX IF NOT EXISTS idx_signals_exp ON channel_signals(expires_at);
            """
        )
        _migrate_users(conn)
        _migrate_signals(conn)


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
    # نرمال‌سازی اشتراکِ legacy: free/خالی → bronze (پلن رایگانِ جدید).
    # مقادیر pro/vip به‌صورت lazy در plans.tier_key نرمال می‌شوند (بدون بازنویسی).
    conn.execute(
        "UPDATE users SET subscription = 'bronze' "
        "WHERE subscription IS NULL OR subscription = '' OR subscription = 'free'"
    )
    # ایندکس‌ها پس از افزوده‌شدن ستون‌ها (روی دیتابیس‌های قدیمی هم امن است)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone)")


def _migrate_signals(conn: sqlite3.Connection) -> None:
    """افزودن ستون‌های جدیدِ channel_signals به دیتابیس‌های موجود (idempotent)."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(channel_signals)").fetchall()}
    add = {
        "image_path2": "TEXT",
        "images": "TEXT",
        "media_group_id": "TEXT",
        "source": "TEXT NOT NULL DEFAULT 'channel'",
    }
    for name, decl in add.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE channel_signals ADD COLUMN {name} {decl}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_group ON channel_signals(media_group_id)")


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


def update_asset(uid: str, asset_id: int, amount: float | None = None,
                 buy_price: Any = "__keep__") -> bool:
    """به‌روزرسانی گزینشیِ مقدار و/یا میانگین قیمت خرید یک دارایی."""
    sets: list[str] = []
    vals: list[Any] = []
    if amount is not None:
        sets.append("amount = ?")
        vals.append(amount)
    if buy_price != "__keep__":
        sets.append("buy_price = ?")
        vals.append(buy_price)
    if not sets:
        return False
    vals.extend([uid, asset_id])
    with _LOCK, _conn() as conn:
        cur = conn.execute(
            f"UPDATE assets SET {', '.join(sets)} WHERE uid = ? AND id = ?", vals
        )
        return cur.rowcount > 0


def clear_assets(uid: str) -> None:
    with _LOCK, _conn() as conn:
        conn.execute("DELETE FROM assets WHERE uid = ?", (uid,))


def merge_assets(uid: str, new_assets: list[dict[str, Any]]) -> None:
    """ادغام دارایی‌های AI با دارایی‌های موجود.

    هر دارایی می‌تواند action داشته باشد:
      "add"    → مقدار را به موجودی اضافه کن (خرید جدید)
      "remove" → دارایی را حذف کن (فروش)
      "set"    → مقدار را جایگزین کن (پیش‌فرض)
    """
    with _LOCK, _conn() as conn:
        for a in new_assets:
            action = (a.get("action") or "set").lower()
            row = conn.execute(
                "SELECT id, amount, buy_price FROM assets WHERE uid = ? AND kind = ? AND symbol = ? "
                "AND (purity IS NULL AND ? IS NULL OR purity = ?)",
                (uid, a["kind"], a["symbol"], a.get("purity"), a.get("purity")),
            ).fetchone()

            if action == "remove":
                if row:
                    conn.execute("DELETE FROM assets WHERE id = ?", (row["id"],))
                continue

            if action == "add" and row:
                old_amount = row["amount"] or 0
                add_amount = a["amount"] or 0
                new_amount = old_amount + add_amount
                sets, vals = ["amount = ?"], [new_amount]
                # میانگین وزنیِ قیمت خرید: (مقدار قبلی×قیمت قبلی + مقدار جدید×قیمت جدید) ÷ مجموع
                new_bp = a.get("buy_price")
                old_bp = row["buy_price"]
                avg_bp: float | None = None
                if new_bp is not None and old_bp is not None and new_amount > 0:
                    avg_bp = (old_amount * old_bp + add_amount * new_bp) / new_amount
                elif new_bp is not None:
                    avg_bp = new_bp
                if avg_bp is not None:
                    sets.append("buy_price = ?")
                    vals.append(avg_bp)
                vals.append(row["id"])
                conn.execute(f"UPDATE assets SET {', '.join(sets)} WHERE id = ?", vals)
            elif row:
                sets, vals = ["amount = ?"], [a["amount"]]
                if a.get("buy_price") is not None:
                    sets.append("buy_price = ?")
                    vals.append(a["buy_price"])
                vals.append(row["id"])
                conn.execute(f"UPDATE assets SET {', '.join(sets)} WHERE id = ?", vals)
            else:
                conn.execute(
                    "INSERT INTO assets (uid, kind, symbol, name, amount, buy_price, purity, horizon) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (uid, a["kind"], a["symbol"], a["name"], a["amount"],
                     a.get("buy_price"), a.get("purity"), a.get("horizon")),
                )


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


# ---- سیگنال‌های کانال تلگرام ----
def _images_of(row: dict[str, Any]) -> list[str]:
    """فهرستِ مرتبِ تصاویرِ یک تحلیل: از ستونِ JSON «images» و در نبودش از
    image_path/image_path2 (سازگاریِ عقب‌رو با ردیف‌های قدیمی)."""
    import json as _json
    raw = row.get("images")
    if raw:
        try:
            lst = _json.loads(raw)
            if isinstance(lst, list):
                out = [str(p) for p in lst if p]
                if out:
                    return out
        except Exception:  # noqa: BLE001
            pass
    return [p for p in (row.get("image_path"), row.get("image_path2")) if p]


def _write_images(conn: sqlite3.Connection, message_id: int, imgs: list[str]) -> None:
    """ذخیرهٔ آرایهٔ تصاویر + همگام‌سازیِ ستون‌های سازگاریِ image_path/image_path2."""
    import json as _json
    conn.execute(
        "UPDATE channel_signals SET images = ?, image_path = ?, image_path2 = ? "
        "WHERE message_id = ?",
        (_json.dumps(imgs, ensure_ascii=False),
         imgs[0] if imgs else None, imgs[1] if len(imgs) > 1 else None, message_id),
    )


def upsert_channel_signal(message_id: int, chat_id: str, ts: int, text: str,
                          hashtags_json: str, image_path: str | None,
                          media_group_id: str | None, ttl_days: int) -> None:
    """درج/به‌روزرسانیِ یک پستِ کانال، با گروه‌بندیِ آلبوم‌های چند‌تصویری (n تصویر).

    تلگرام هر آلبوم را به‌صورت چند «channel_post» جدا (با message_id متفاوت اما
    media_group_id یکسان) می‌فرستد و معمولاً فقط یکی از آن‌ها کپشن دارد. این تابع
    همهٔ تصاویرِ یک آلبوم را در یک ردیف (تحلیلِ واحد) به‌صورت گالری نگه می‌دارد و
    کپشن را از هر پیامی که متن داشته باشد می‌گیرد.
    """
    import json as _json
    with _LOCK, _conn() as conn:
        if media_group_id:
            row = conn.execute(
                "SELECT * FROM channel_signals WHERE media_group_id = ? "
                "ORDER BY message_id LIMIT 1", (media_group_id,),
            ).fetchone()
            if row:
                d = dict(row)
                imgs = _images_of(d)
                if image_path and image_path not in imgs:
                    imgs.append(image_path)
                _write_images(conn, d["message_id"], imgs)
                if text and not (d.get("text") or "").strip():
                    conn.execute(
                        "UPDATE channel_signals SET text = ?, hashtags = ? WHERE message_id = ?",
                        (text, hashtags_json, d["message_id"]))
                return

        existing = conn.execute(
            "SELECT * FROM channel_signals WHERE message_id = ?", (message_id,),
        ).fetchone()
        if existing:
            old_imgs = _images_of(dict(existing))
            imgs = [image_path] if image_path else old_imgs
        else:
            imgs = [image_path] if image_path else []
        images_json = _json.dumps(imgs, ensure_ascii=False)
        conn.execute(
            """
            INSERT INTO channel_signals
                (message_id, chat_id, ts, text, hashtags, image_path, image_path2,
                 images, media_group_id, source, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'channel', datetime('now', ?))
            ON CONFLICT(message_id) DO UPDATE SET
                chat_id=excluded.chat_id, ts=excluded.ts, text=excluded.text,
                hashtags=excluded.hashtags, image_path=excluded.image_path,
                image_path2=excluded.image_path2, images=excluded.images,
                media_group_id=excluded.media_group_id, expires_at=excluded.expires_at
            """,
            (message_id, chat_id, ts, text, hashtags_json,
             imgs[0] if imgs else None, imgs[1] if len(imgs) > 1 else None,
             images_json, media_group_id, f"+{int(ttl_days)} days"),
        )


def upsert_signal(message_id: int, chat_id: str, ts: int, text: str,
                  hashtags_json: str, image_path: str | None, ttl_days: int) -> None:
    """سازگاریِ عقب‌رو: درج/به‌روزرسانیِ سادهٔ یک تحلیل (بدون گروه‌بندیِ آلبوم)."""
    upsert_channel_signal(message_id, chat_id, ts, text, hashtags_json,
                          image_path, None, ttl_days)


def signal_images(message_id: int) -> list[str]:
    """فهرستِ تصاویرِ یک تحلیل (برای سروِ تصویر با اندیس دلخواه)."""
    sig = get_signal(message_id)
    return _images_of(sig) if sig else []


# ---- مدیریتِ تحلیل‌ها توسط ادمین ----
def admin_create_signal(text: str, hashtags_json: str, images: list[str],
                        ttl_days: int, ts: int | None = None) -> int:
    """ساخت یک تحلیلِ دستیِ ادمین با n تصویر. شناسهٔ منفیِ یکتا می‌گیرد تا با
    message_idهای مثبتِ تلگرام تداخل نکند. بازگشت: message_id."""
    import time as _time
    import json as _json
    now = int(_time.time())
    mid = -int(_time.time() * 1000)
    imgs = [p for p in (images or []) if p]
    with _LOCK, _conn() as conn:
        while conn.execute("SELECT 1 FROM channel_signals WHERE message_id = ?", (mid,)).fetchone():
            mid -= 1
        conn.execute(
            """
            INSERT INTO channel_signals
                (message_id, chat_id, ts, text, hashtags, image_path, image_path2,
                 images, source, expires_at)
            VALUES (?, '', ?, ?, ?, ?, ?, ?, 'admin', datetime('now', ?))
            """,
            (mid, int(ts or now), text, hashtags_json,
             imgs[0] if imgs else None, imgs[1] if len(imgs) > 1 else None,
             _json.dumps(imgs, ensure_ascii=False), f"+{int(ttl_days)} days"),
        )
    return mid


def admin_update_signal(message_id: int, *, text: str | None = None,
                        hashtags_json: str | None = None,
                        images: Any = "__keep__") -> bool:
    """ویرایشِ گزینشیِ یک تحلیل (متن/هشتگ/فهرستِ تصاویر). __keep__ یعنی بدون تغییر."""
    import json as _json
    sets: list[str] = []
    vals: list[Any] = []
    if text is not None:
        sets.append("text = ?"); vals.append(text)
    if hashtags_json is not None:
        sets.append("hashtags = ?"); vals.append(hashtags_json)
    if images != "__keep__":
        imgs = [p for p in (images or []) if p]
        sets.append("images = ?"); vals.append(_json.dumps(imgs, ensure_ascii=False))
        sets.append("image_path = ?"); vals.append(imgs[0] if imgs else None)
        sets.append("image_path2 = ?"); vals.append(imgs[1] if len(imgs) > 1 else None)
    if not sets:
        return False
    vals.append(message_id)
    with _LOCK, _conn() as conn:
        cur = conn.execute(
            f"UPDATE channel_signals SET {', '.join(sets)} WHERE message_id = ?", vals)
        return cur.rowcount > 0


def delete_signal(message_id: int) -> list[str]:
    """حذف یک تحلیل؛ بازگشت مسیرِ همهٔ تصاویرش برای پاک‌سازیِ فایل."""
    with _LOCK, _conn() as conn:
        row = conn.execute(
            "SELECT * FROM channel_signals WHERE message_id = ?", (message_id,),
        ).fetchone()
        if not row:
            return []
        paths = _images_of(dict(row))
        conn.execute("DELETE FROM channel_signals WHERE message_id = ?", (message_id,))
        return paths


def admin_list_signals(limit: int = 500) -> list[dict[str, Any]]:
    """همهٔ تحلیل‌ها (جدیدترین اول) برای جدولِ مدیریتِ ادمین، با هشتگ و فهرستِ تصاویر."""
    import json as _json
    with _LOCK, _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM channel_signals ORDER BY ts DESC, message_id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        try:
            d["tags"] = _json.loads(d.get("hashtags") or "[]")
        except Exception:  # noqa: BLE001
            d["tags"] = []
        d["image_list"] = _images_of(d)
        out.append(d)
    return out


def list_active_signals(limit: int = 50, tag: str | None = None) -> list[dict[str, Any]]:
    """تحلیل‌های معتبر (منقضی‌نشده) به ترتیب جدیدترین."""
    with _LOCK, _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM channel_signals WHERE expires_at > datetime('now') "
            "ORDER BY ts DESC LIMIT ?",
            (int(limit) if not tag else 500,),
        ).fetchall()
    out = [dict(r) for r in rows]
    if tag:
        import json as _json
        t = tag.lstrip("#").lower()
        out = [r for r in out if t in (_json.loads(r.get("hashtags") or "[]"))][:limit]
    return out


def get_signal(message_id: int) -> dict[str, Any] | None:
    with _LOCK, _conn() as conn:
        row = conn.execute(
            "SELECT * FROM channel_signals WHERE message_id = ?", (message_id,)
        ).fetchone()
        return dict(row) if row else None


# ── دسته‌بندیِ تحلیل‌ها بر پایهٔ هشتگ (برای بخش‌بندیِ «تحلیل اختصاصی») ──
# «بازار داخلی» = تتر و دلار و طلا (+ انس/نقره/نفت طبق خواستهٔ کاربر).
_INTERNAL_TAGS = {
    "تتر", "طلا", "دلار", "طلای", "سکه", "نقره", "نفت", "انس",
    "usdt", "usd", "tether", "dollar",
    "gold", "gold18", "xau", "xauusd",
    "silver", "xag", "xagusd",
    "oil", "wti", "brent",
}
# «بیت‌کوین و اتریوم».
_BTC_ETH_TAGS = {
    "btc", "eth", "bitcoin", "ethereum", "بیتکوین", "اتریوم",
    "btcusdt", "ethusdt",
}


def _classify_signal(hashtags: list[str]) -> tuple[bool, bool]:
    """(is_internal, is_btc_eth) بر پایهٔ هشتگ‌های یک تحلیل."""
    tags = {str(t).lstrip("#").lower() for t in (hashtags or [])}
    return bool(tags & _INTERNAL_TAGS), bool(tags & _BTC_ETH_TAGS)


def _match_category(hashtags: list[str], category: str) -> bool:
    """آیا تحلیل به دستهٔ خواسته‌شده تعلق دارد؟

    all      → همهٔ تحلیل‌ها
    internal → فقط تتر/دلار/طلا (بازار داخلی)
    external → همه به‌جز بازار داخلی (بازار خارجی: ارز/شاخص/سهام)
    btc_eth  → فقط بیت‌کوین و اتریوم
    """
    is_internal, is_btc_eth = _classify_signal(hashtags)
    if category == "internal":
        return is_internal
    if category == "external":
        return not is_internal
    if category == "btc_eth":
        return is_btc_eth
    return True


def list_signals_feed(category: str = "all", page: int = 1,
                      per_page: int = 10) -> dict[str, Any]:
    """صفحهٔ درخواستی از آرشیو تحلیل‌های کانال (جدیدترین اول) با فیلترِ دسته.

    فیلترِ دسته چون روی هشتگ‌های ذخیره‌شده به‌صورت JSON است در پایتون اعمال
    می‌شود؛ سپس صفحه‌بندی (پیش‌فرض ۱۰ تحلیل در هر صفحه) روی نتیجهٔ فیلتر انجام
    می‌گیرد. بر خلاف list_active_signals، این تابع به expires_at وابسته نیست تا
    آرشیوِ نمایشی تا بازهٔ نگه‌داری کامل در دسترس بماند.
    """
    import json as _json
    with _LOCK, _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM channel_signals ORDER BY ts DESC, message_id DESC"
        ).fetchall()
    items: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        try:
            tags = _json.loads(d.get("hashtags") or "[]")
        except Exception:  # noqa: BLE001
            tags = []
        if not _match_category(tags, category):
            continue
        is_internal, is_btc_eth = _classify_signal(tags)
        d["tags"] = tags
        d["is_internal"] = is_internal
        d["is_btc_eth"] = is_btc_eth
        d["image_list"] = _images_of(d)
        items.append(d)

    per_page = max(1, int(per_page))
    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page) if total else 0
    page = max(1, int(page))
    start = (page - 1) * per_page
    return {
        "items": items[start:start + per_page],
        "total": total,
        "total_pages": total_pages,
        "page": page,
        "per_page": per_page,
    }


def purge_expired_signals(retention_days: int | None = None) -> list[str]:
    """حذف تحلیل‌های قدیمی‌تر از بازهٔ نگه‌داریِ آرشیو؛ بازگشت مسیر تصاویرشان.

    توجه: این با «اعتبار ۷روزهٔ سبد هوش مصنوعی» (expires_at) فرق دارد. آن اعتبار
    فقط در list_active_signals برای پیشنهاد سبد اعمال می‌شود؛ اما تحلیل‌ها برای
    نمایش در «تحلیل اختصاصی» تا این بازهٔ بلندتر در آرشیو نگه داشته می‌شوند.
    """
    days = int(retention_days if retention_days is not None
               else settings.signals_retention_days)
    with _LOCK, _conn() as conn:
        rows = conn.execute(
            "SELECT image_path FROM channel_signals "
            "WHERE created_at <= datetime('now', ?) AND image_path IS NOT NULL",
            (f"-{days} days",),
        ).fetchall()
        paths = [r["image_path"] for r in rows if r["image_path"]]
        conn.execute("DELETE FROM channel_signals WHERE created_at <= datetime('now', ?)",
                     (f"-{days} days",))
        return paths


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
    """فهرست همهٔ کاربران + تعداد دارایی + پروفایل ریسک (برای پنل ادمین)."""
    with _LOCK, _conn() as conn:
        rows = conn.execute(
            "SELECT u.*, "
            "(SELECT COUNT(*) FROM assets a WHERE a.uid = u.uid OR a.uid = 'u' || u.id) AS asset_count, "
            "(SELECT rp.percent FROM risk_profiles rp WHERE rp.uid = u.uid) AS risk_percent, "
            "(SELECT rp.label FROM risk_profiles rp WHERE rp.uid = u.uid) AS risk_label "
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


# ---- شمارش تحلیل هوش مصنوعی (سهمیهٔ پلن) ----
def ai_used_count(user_id: int, month: str) -> int:
    """تعداد تحلیلِ مصرف‌شدهٔ کاربر در ماهِ مشخص (YYYY-MM تهران)."""
    with _LOCK, _conn() as conn:
        row = conn.execute(
            "SELECT used FROM ai_usage WHERE user_id = ? AND month = ?",
            (int(user_id), month),
        ).fetchone()
        return int(row["used"]) if row else 0


def ai_increment(user_id: int, month: str) -> int:
    """افزودن یک واحد به شمارش تحلیلِ ماه جاری و بازگشت مقدار جدید."""
    with _LOCK, _conn() as conn:
        conn.execute(
            "INSERT INTO ai_usage (user_id, month, used) VALUES (?, ?, 1) "
            "ON CONFLICT(user_id, month) DO UPDATE SET used = used + 1",
            (int(user_id), month),
        )
        row = conn.execute(
            "SELECT used FROM ai_usage WHERE user_id = ? AND month = ?",
            (int(user_id), month),
        ).fetchone()
        return int(row["used"]) if row else 1


# تضمین وجود جداول حتی بدون رویداد startup (idempotent).
init_db()
