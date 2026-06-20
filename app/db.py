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
            """
        )


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


# تضمین وجود جداول حتی بدون رویداد startup (idempotent).
init_db()
