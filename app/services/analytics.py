"""
اندازه‌گیری قیف محصول (Product Funnel) برای پنل مدیریت.

چرا این فایل جداست؟ تا لایهٔ دیتابیس اصلی (app/db.py) دست‌نخورده بماند.
همین فایل دیتابیس SQLite را باز می‌کند، یک جدول رویداد می‌سازد و
محاسبات قیف را انجام می‌دهد.

مراحل قیف:
  ۱) بازدید لندینگ  → بازدیدکنندهٔ یکتا (کوکی ah_vid)
  ۲) ثبت‌نام        → ردیف در users
  ۳) فعال‌سازی      → اولین دارایی ثبت‌شده در سبد (مهم‌ترین عدد محصول)
  ۴) خرید          → پلن غیررایگان (نقره‌ای/طلایی/الماسی)

نکته: مراحل ۲ تا ۴ از جدول‌های موجود (users / assets) محاسبه می‌شوند،
پس آمار این مراحل از روز اول سایت کامل است. فقط بازدید لندینگ از
لحظهٔ نصب این قابلیت شروع به جمع‌شدن می‌کند.
"""
from __future__ import annotations

import re
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

from app.config import settings

_LOCK = threading.Lock()
_DB_PATH = Path(settings.portfolio_db_file)

# مسیرهایی که بازدید انسانی نیستند و نباید در قیف شمرده شوند.
_SKIP_PREFIX = (
    "/api/", "/static/", "/app-icon", "/app-splash", "/sw.js", "/health",
    "/manifest", "/offline", "/favicon", "/robots.txt", "/sitemap",
    "/admin", "/bot/",
)

# ربات‌های خزنده و پایشگرها — جداگانه شمرده می‌شوند، نه در قیف.
_BOT_RE = re.compile(
    r"bot|crawl|spider|slurp|bing|yandex|duckduck|baidu|ahrefs|semrush|"
    r"facebookexternalhit|telegrambot|whatsapp|preview|monitor|uptime|curl|wget|python-requests",
    re.I,
)

_MOBILE_RE = re.compile(r"android|iphone|ipod|mobile|windows phone", re.I)
_TABLET_RE = re.compile(r"ipad|tablet", re.I)

_TIERS_PAID = ("silver", "gold", "diamond", "pro", "vip")


def _conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """ساخت جدول رویدادها (idempotent)."""
    with _LOCK, _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS analytics_events (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                ts        TEXT NOT NULL DEFAULT (datetime('now')),
                day       TEXT NOT NULL DEFAULT (date('now')),
                kind      TEXT NOT NULL,       -- view | signup | activation | purchase
                vid       TEXT,                -- شناسهٔ بازدیدکننده (کوکی)
                user_id   INTEGER,
                path      TEXT,
                referrer  TEXT,
                source    TEXT,                -- google | telegram | instagram | direct | ...
                campaign  TEXT,                -- utm_campaign
                device    TEXT,                -- mobile | tablet | desktop | bot
                is_bot    INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_ev_day  ON analytics_events(day, kind);
            CREATE INDEX IF NOT EXISTS idx_ev_vid  ON analytics_events(vid, day);
            CREATE INDEX IF NOT EXISTS idx_ev_kind ON analytics_events(kind, ts);
            """
        )


def new_visitor_id() -> str:
    return uuid.uuid4().hex[:24]


def should_track(path: str) -> bool:
    p = (path or "/").split("?")[0]
    return not any(p.startswith(prefix) for prefix in _SKIP_PREFIX)


def _device(ua: str) -> str:
    if _BOT_RE.search(ua or ""):
        return "bot"
    if _TABLET_RE.search(ua or ""):
        return "tablet"
    if _MOBILE_RE.search(ua or ""):
        return "mobile"
    return "desktop"


def classify_source(referrer: str | None, utm_source: str | None) -> str:
    """دسته‌بندی منبع ورودی برای گزارش بازاریابی."""
    if utm_source:
        return utm_source.strip().lower()[:40]
    ref = (referrer or "").lower()
    if not ref:
        return "direct"
    table = {
        "google": "google", "bing": "bing", "duckduckgo": "duckduckgo",
        "yandex": "yandex", "t.me": "telegram", "telegram": "telegram",
        "instagram": "instagram", "youtube": "youtube", "aparat": "aparat",
        "twitter": "twitter", "x.com": "twitter", "linkedin": "linkedin",
        "whatsapp": "whatsapp", "facebook": "facebook",
    }
    for needle, label in table.items():
        if needle in ref:
            return label
    if "cryptosmart" in ref:
        return "internal"
    return "referral"


def record_view(*, vid: str, path: str, referrer: str | None,
                user_agent: str, utm_source: str | None = None,
                utm_campaign: str | None = None,
                user_id: int | None = None) -> None:
    """ثبت یک بازدید صفحه. خطا هرگز به بیرون درز نمی‌کند."""
    device = _device(user_agent)
    try:
        with _LOCK, _conn() as conn:
            conn.execute(
                "INSERT INTO analytics_events "
                "(kind, vid, user_id, path, referrer, source, campaign, device, is_bot) "
                "VALUES ('view', ?, ?, ?, ?, ?, ?, ?, ?)",
                (vid, user_id, (path or "/")[:200], (referrer or "")[:200],
                 classify_source(referrer, utm_source),
                 (utm_campaign or "")[:60] or None, device,
                 1 if device == "bot" else 0),
            )
    except Exception:  # noqa: BLE001
        pass


def record_event(kind: str, *, user_id: int | None = None,
                 vid: str | None = None, path: str | None = None) -> None:
    """ثبت یک رویداد معنادار (ثبت‌نام، فعال‌سازی، خرید)."""
    try:
        with _LOCK, _conn() as conn:
            conn.execute(
                "INSERT INTO analytics_events (kind, vid, user_id, path, device) "
                "VALUES (?, ?, ?, ?, 'app')",
                (kind, vid, user_id, (path or "")[:200] or None),
            )
    except Exception:  # noqa: BLE001
        pass


def _pct(part: float, whole: float) -> float:
    return round((part / whole) * 100, 1) if whole else 0.0


def _rows(conn: sqlite3.Connection, sql: str, args: tuple = ()) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def _one(conn: sqlite3.Connection, sql: str, args: tuple = ()) -> int:
    row = conn.execute(sql, args).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def funnel(days: int = 30) -> dict[str, Any]:
    """گزارش کامل قیف برای یک بازهٔ زمانی."""
    init_db()
    days = max(1, min(int(days), 365))
    since = f"-{days} days"
    prev_since = f"-{days * 2} days"

    with _LOCK, _conn() as conn:
        # ── مرحلهٔ ۱: بازدید لندینگ ──
        visitors = _one(
            conn,
            "SELECT COUNT(DISTINCT vid) FROM analytics_events "
            "WHERE kind = 'view' AND is_bot = 0 AND ts >= datetime('now', ?)",
            (since,))
        pageviews = _one(
            conn,
            "SELECT COUNT(*) FROM analytics_events "
            "WHERE kind = 'view' AND is_bot = 0 AND ts >= datetime('now', ?)",
            (since,))
        bot_hits = _one(
            conn,
            "SELECT COUNT(*) FROM analytics_events "
            "WHERE kind = 'view' AND is_bot = 1 AND ts >= datetime('now', ?)",
            (since,))
        prev_visitors = _one(
            conn,
            "SELECT COUNT(DISTINCT vid) FROM analytics_events "
            "WHERE kind = 'view' AND is_bot = 0 AND ts >= datetime('now', ?) "
            "AND ts < datetime('now', ?)",
            (prev_since, since))

        # ── مرحلهٔ ۲ تا ۴: از دادهٔ واقعی کاربران ──
        signups = _one(
            conn, "SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', ?)",
            (since,))
        prev_signups = _one(
            conn,
            "SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', ?) "
            "AND created_at < datetime('now', ?)",
            (prev_since, since))

        # فعال‌سازی = کاربرانی که در همین بازه ثبت‌نام کردند و حداقل
        # یک دارایی ثبت کردند (معادل «اولین معامله» در ژورنال).
        activated = _one(
            conn,
            "SELECT COUNT(*) FROM users u WHERE u.created_at >= datetime('now', ?) "
            "AND EXISTS (SELECT 1 FROM assets a "
            "            WHERE a.uid = u.uid OR a.uid = 'u' || u.id)",
            (since,))
        risk_done = _one(
            conn,
            "SELECT COUNT(*) FROM users u WHERE u.created_at >= datetime('now', ?) "
            "AND EXISTS (SELECT 1 FROM risk_profiles r "
            "            WHERE r.uid = u.uid OR r.uid = 'u' || u.id)",
            (since,))
        paid = _one(
            conn,
            "SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', ?) "
            "AND lower(COALESCE(subscription,'bronze')) IN "
            "    ('silver','gold','diamond','pro','vip')",
            (since,))
        verified = _one(
            conn,
            "SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', ?) "
            "AND verified = 1",
            (since,))

        # ── اعداد کلی (همهٔ تاریخ) ──
        total_users = _one(conn, "SELECT COUNT(*) FROM users")
        total_activated = _one(
            conn,
            "SELECT COUNT(*) FROM users u WHERE EXISTS "
            "(SELECT 1 FROM assets a WHERE a.uid = u.uid OR a.uid = 'u' || u.id)")
        total_paid = _one(
            conn,
            "SELECT COUNT(*) FROM users WHERE lower(COALESCE(subscription,'bronze')) "
            "IN ('silver','gold','diamond','pro','vip')")

        # ── ریزش (churn) ──
        # مشترکینی که در ۳۰ روز گذشته اشتراکشان تمام شده و تمدید نکرده‌اند.
        active_paid = _one(
            conn,
            "SELECT COUNT(*) FROM users WHERE lower(COALESCE(subscription,'bronze')) "
            "IN ('silver','gold','diamond','pro','vip') "
            "AND (sub_expires_at IS NULL OR sub_expires_at > datetime('now'))")
        expired_recent = _one(
            conn,
            "SELECT COUNT(*) FROM users WHERE sub_expires_at IS NOT NULL "
            "AND sub_expires_at <= datetime('now') "
            "AND sub_expires_at >= datetime('now', '-30 days')")
        expiring_soon = _one(
            conn,
            "SELECT COUNT(*) FROM users WHERE sub_expires_at IS NOT NULL "
            "AND sub_expires_at > datetime('now') "
            "AND sub_expires_at <= datetime('now', '+7 days')")

        # ── روند روزانه ──
        daily_views = _rows(
            conn,
            "SELECT day, COUNT(DISTINCT vid) AS visitors, COUNT(*) AS views "
            "FROM analytics_events WHERE kind = 'view' AND is_bot = 0 "
            "AND ts >= datetime('now', ?) GROUP BY day ORDER BY day",
            (since,))
        daily_signups = {
            r["day"]: r["n"] for r in _rows(
                conn,
                "SELECT date(created_at) AS day, COUNT(*) AS n FROM users "
                "WHERE created_at >= datetime('now', ?) GROUP BY day",
                (since,))
        }
        trend = []
        for row in daily_views:
            trend.append({
                "day": row["day"],
                "visitors": row["visitors"],
                "views": row["views"],
                "signups": daily_signups.get(row["day"], 0),
            })
        # روزهایی که ثبت‌نام داشتند اما بازدیدی ثبت نشده (قبل از نصب رهگیری)
        seen_days = {row["day"] for row in trend}
        for day, count in daily_signups.items():
            if day not in seen_days:
                trend.append({"day": day, "visitors": 0, "views": 0, "signups": count})
        trend.sort(key=lambda item: item["day"])

        # ── منابع ورودی ──
        sources = _rows(
            conn,
            "SELECT COALESCE(source,'direct') AS source, "
            "       COUNT(DISTINCT vid) AS visitors, COUNT(*) AS views "
            "FROM analytics_events WHERE kind = 'view' AND is_bot = 0 "
            "AND ts >= datetime('now', ?) "
            "GROUP BY source ORDER BY visitors DESC LIMIT 12",
            (since,))
        devices = _rows(
            conn,
            "SELECT device, COUNT(DISTINCT vid) AS visitors FROM analytics_events "
            "WHERE kind = 'view' AND is_bot = 0 AND ts >= datetime('now', ?) "
            "GROUP BY device ORDER BY visitors DESC",
            (since,))
        pages = _rows(
            conn,
            "SELECT path, COUNT(*) AS views, COUNT(DISTINCT vid) AS visitors "
            "FROM analytics_events WHERE kind = 'view' AND is_bot = 0 "
            "AND ts >= datetime('now', ?) "
            "GROUP BY path ORDER BY views DESC LIMIT 10",
            (since,))
        campaigns = _rows(
            conn,
            "SELECT campaign, COUNT(DISTINCT vid) AS visitors FROM analytics_events "
            "WHERE kind = 'view' AND campaign IS NOT NULL AND is_bot = 0 "
            "AND ts >= datetime('now', ?) "
            "GROUP BY campaign ORDER BY visitors DESC LIMIT 8",
            (since,))

        # ── کوهورت ماهانه (۶ ماه اخیر) ──
        cohorts = _rows(
            conn,
            "SELECT strftime('%Y-%m', u.created_at) AS month, "
            "       COUNT(*) AS signups, "
            "       SUM(CASE WHEN EXISTS (SELECT 1 FROM assets a "
            "           WHERE a.uid = u.uid OR a.uid = 'u' || u.id) "
            "           THEN 1 ELSE 0 END) AS activated, "
            "       SUM(CASE WHEN lower(COALESCE(u.subscription,'bronze')) IN "
            "           ('silver','gold','diamond','pro','vip') THEN 1 ELSE 0 END) AS paid "
            "FROM users u WHERE u.created_at >= datetime('now', '-190 days') "
            "GROUP BY month ORDER BY month DESC LIMIT 6")

        # ── میانهٔ زمان تا فعال‌سازی (ساعت) ──
        gaps = [
            r["hours"] for r in _rows(
                conn,
                "SELECT (julianday(( SELECT MIN(a.created_at) FROM assets a "
                "        WHERE a.uid = u.uid OR a.uid = 'u' || u.id )) "
                "        - julianday(u.created_at)) * 24 AS hours "
                "FROM users u WHERE u.created_at >= datetime('now', '-190 days') "
                "AND EXISTS (SELECT 1 FROM assets a "
                "            WHERE a.uid = u.uid OR a.uid = 'u' || u.id)")
            if r["hours"] is not None and r["hours"] >= 0
        ]

    gaps.sort()
    median_hours = round(gaps[len(gaps) // 2], 1) if gaps else None

    for c in cohorts:
        c["activation_rate"] = _pct(c.get("activated") or 0, c.get("signups") or 0)
        c["paid_rate"] = _pct(c.get("paid") or 0, c.get("signups") or 0)

    steps = [
        {"key": "visit", "label": "\u0628\u0627\u0632\u062f\u06cc\u062f \u0644\u0646\u062f\u06cc\u0646\u06af",
         "value": visitors, "rate": 100.0, "of": None,
         "hint": "\u0628\u0627\u0632\u062f\u06cc\u062f\u06a9\u0646\u0646\u062f\u0647\u0654 \u06cc\u06a9\u062a\u0627"},
        {"key": "signup", "label": "\u062b\u0628\u062a\u200c\u0646\u0627\u0645", "value": signups,
         "rate": _pct(signups, visitors), "of": "\u0628\u0627\u0632\u062f\u06cc\u062f",
         "hint": "\u062f\u0631\u0635\u062f \u062a\u0628\u062f\u06cc\u0644 \u0628\u0627\u0632\u062f\u06cc\u062f \u0628\u0647 \u062b\u0628\u062a\u200c\u0646\u0627\u0645"},
        {"key": "activation",
         "label": "\u0627\u0648\u0644\u06cc\u0646 \u062f\u0627\u0631\u0627\u06cc\u06cc \u062f\u0631 \u0633\u0628\u062f",
         "value": activated, "rate": _pct(activated, signups),
         "of": "\u062b\u0628\u062a\u200c\u0646\u0627\u0645",
         "hint": "\u0645\u0647\u0645\u200c\u062a\u0631\u06cc\u0646 \u0639\u062f\u062f \u0645\u062d\u0635\u0648\u0644"},
        {"key": "purchase", "label": "\u062e\u0631\u06cc\u062f \u0627\u0634\u062a\u0631\u0627\u06a9", "value": paid,
         "rate": _pct(paid, activated),
         "of": "\u0641\u0639\u0627\u0644\u200c\u0634\u062f\u0647",
         "hint": "\u062f\u0631\u0635\u062f \u062a\u0628\u062f\u06cc\u0644 \u0641\u0639\u0627\u0644 \u0628\u0647 \u0645\u0634\u062a\u0631\u06cc"},
    ]

    return {
        "days": days,
        "steps": steps,
        "headline": {
            "visit_to_signup": _pct(signups, visitors),
            "signup_to_activation": _pct(activated, signups),
            "activation_to_paid": _pct(paid, activated),
            "visit_to_paid": _pct(paid, visitors),
            "monthly_churn": _pct(expired_recent, active_paid + expired_recent),
        },
        "counts": {
            "visitors": visitors,
            "pageviews": pageviews,
            "bot_hits": bot_hits,
            "signups": signups,
            "verified": verified,
            "activated": activated,
            "risk_done": risk_done,
            "paid": paid,
            "pages_per_visitor": round(pageviews / visitors, 1) if visitors else 0,
        },
        "lifetime": {
            "users": total_users,
            "activated": total_activated,
            "paid": total_paid,
            "activation_rate": _pct(total_activated, total_users),
            "paid_rate": _pct(total_paid, total_users),
        },
        "retention": {
            "active_paid": active_paid,
            "expired_30d": expired_recent,
            "expiring_7d": expiring_soon,
            "monthly_churn": _pct(expired_recent, active_paid + expired_recent),
        },
        "growth": {
            "visitors": _pct(visitors - prev_visitors, prev_visitors) if prev_visitors else None,
            "signups": _pct(signups - prev_signups, prev_signups) if prev_signups else None,
        },
        "trend": trend,
        "sources": sources,
        "devices": devices,
        "pages": pages,
        "campaigns": campaigns,
        "cohorts": cohorts,
        "median_hours_to_activate": median_hours,
        "tracking_since": _tracking_since(),
    }


def _tracking_since() -> str | None:
    try:
        with _LOCK, _conn() as conn:
            row = conn.execute(
                "SELECT MIN(day) AS d FROM analytics_events WHERE kind = 'view'"
            ).fetchone()
            return row["d"] if row else None
    except Exception:  # noqa: BLE001
        return None


# تضمین وجود جدول حتی بدون رویداد startup.
init_db()
