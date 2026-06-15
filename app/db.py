"""
لایهٔ دیتابیس — SQLModel روی SQLite (فایل‌محور، بدون نیاز به سرویس بیرونی).

در فاز بعدی می‌توان به‌راحتی به PostgreSQL مهاجرت کرد (فقط database_url عوض می‌شود).
انتخاب SQLite برای سادگی توسعه و دیباگ در فازهای اولیه است.
"""
from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

# اطمینان از وجود پوشهٔ data برای فایل دیتابیس
if settings.database_url.startswith("sqlite"):
    db_path = settings.database_url.split("///")[-1]
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=False, connect_args=_connect_args)


def init_db() -> None:
    """ساخت جدول‌ها در اولین اجرا. مدل‌ها باید قبل از فراخوانی import شده باشند."""
    from app import models  # noqa: F401  (ثبت مدل‌ها در متادیتا)
    SQLModel.metadata.create_all(engine)


def get_session():
    """وابستگی FastAPI برای نشست دیتابیس."""
    with Session(engine) as session:
        yield session
