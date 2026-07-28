"""
پاک‌سازیِ خودکارِ تحلیل‌های «تحلیل اختصاصی» پس از پایانِ اعتبار.

هر تحلیلِ کانال (و هر تحلیلِ دستیِ ادمین) با ستون expires_at ذخیره می‌شود که
هنگام درج برابرِ settings.signals_ttl_days (پیش‌فرض ۷ روز) تنظیم می‌گردد. این
ماژول تنها مرجعِ حذف است و سه کار انجام می‌دهد:

  ۱) ردیف‌هایی که اعتبارشان تمام شده (یا از سنِ مجاز گذشته‌اند) را از دیتابیس
     حذف می‌کند — پس هم از سایت و هم از خوراکِ سبد هوش مصنوعی ناپدید می‌شوند.
  ۲) «همهٔ» تصاویرِ آلبومِ آن تحلیل را از data/signals پاک می‌کند (نه فقط تصویرِ
     نخست؛ پیش‌تر تصاویرِ دوم به بعد روی دیسک جا می‌ماندند).
  ۳) فایل‌های یتیمِ باقی‌مانده در data/signals را که به هیچ ردیفی وصل نیستند
     جارو می‌کند تا فضای سرور آزاد بماند.

حلقهٔ loop() هر ساعت این پاک‌سازی را اجرا می‌کند؛ پس حذف به رسیدنِ پستِ جدید یا
ری‌استارتِ برنامه وابسته نیست.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

from app import db
from app.config import settings

_SIGNALS_DIR = Path("data/signals")
# فاصلهٔ اجرای پاک‌سازیِ خودکار (ثانیه).
_TICK_SECONDS = 3600
# فایلِ تازه‌ساخته‌شده (در حالِ دانلود/آپلود) هنوز در دیتابیس ثبت نشده است؛ پس
# فقط فایل‌های قدیمی‌تر از این سن به‌عنوان یتیم حذف می‌شوند.
_ORPHAN_MIN_AGE = 3600


def ttl_days() -> int:
    """سنِ مجازِ نگه‌داری یک تحلیل (روز)."""
    try:
        return max(1, int(settings.signals_ttl_days or 7))
    except (TypeError, ValueError):
        return 7


_WHERE_EXPIRED = (
    "expires_at <= datetime('now') "
    "OR created_at <= datetime('now', ?) "
    "OR (ts > 0 AND ts <= ?)"
)


def purge(days: int | None = None) -> dict[str, int]:
    """حذفِ کاملِ تحلیل‌های منقضی (ردیف + تصاویر) و جاروی فایل‌های یتیم.

    شرطِ حذف سه‌گانه است تا هیچ ردیفی جا نماند: پایانِ expires_at، سنِ درج
    (created_at) و زمانِ خودِ پست (ts). ردیف‌های قدیمی که پیش از افزوده‌شدنِ
    ستون‌ها ساخته شده‌اند هم با همین شرط پاک می‌شوند.
    """
    d = int(days or ttl_days())
    cutoff_sql = f"-{d} days"
    cutoff_ts = int(time.time()) - d * 86400

    paths: list[str] = []
    rows_deleted = 0
    with db._LOCK, db._conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM channel_signals WHERE {_WHERE_EXPIRED}",
            (cutoff_sql, cutoff_ts),
        ).fetchall()
        for r in rows:
            paths.extend(db._images_of(dict(r)))
        cur = conn.execute(
            f"DELETE FROM channel_signals WHERE {_WHERE_EXPIRED}",
            (cutoff_sql, cutoff_ts),
        )
        rows_deleted = int(cur.rowcount or 0)

    files_deleted = 0
    for p in paths:
        try:
            Path(p).unlink(missing_ok=True)
            files_deleted += 1
        except OSError:
            pass

    files_deleted += sweep_orphan_files()
    return {"rows": rows_deleted, "files": files_deleted}


def sweep_orphan_files(min_age_seconds: int = _ORPHAN_MIN_AGE) -> int:
    """حذفِ فایل‌های تصویرِ بی‌صاحب در data/signals (به هیچ تحلیلی وصل نیستند)."""
    if not _SIGNALS_DIR.exists():
        return 0

    keep: set[str] = set()
    with db._LOCK, db._conn() as conn:
        rows = conn.execute(
            "SELECT images, image_path, image_path2 FROM channel_signals"
        ).fetchall()
    for r in rows:
        for p in db._images_of(dict(r)):
            try:
                keep.add(str(Path(p).resolve()))
            except OSError:
                keep.add(str(p))

    now = time.time()
    removed = 0
    try:
        entries = list(_SIGNALS_DIR.iterdir())
    except OSError:
        return 0
    for f in entries:
        try:
            if not f.is_file():
                continue
            if str(f.resolve()) in keep:
                continue
            if now - f.stat().st_mtime < min_age_seconds:
                continue
            f.unlink()
            removed += 1
        except OSError:
            pass
    return removed


async def loop() -> None:
    """حلقهٔ ساعتیِ پاک‌سازی (بدون بلوکه‌کردنِ رویدادلوپ؛ SQLite همگام است)."""
    while True:
        try:
            await asyncio.to_thread(purge)
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(_TICK_SECONDS)
