"""
مدل‌های دیتابیس (SQLModel).

فاز ۰: User
فاز ۲: Holding (دارایی پورتفولیو)
فاز ۴ (پایه): JournalEntry (معاملهٔ ژورنال)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.utcnow()


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    # ورود با ایمیل یا نام کاربری
    email: Optional[str] = Field(default=None, index=True, unique=True)
    username: Optional[str] = Field(default=None, index=True)
    password_hash: Optional[str] = None
    display_name: Optional[str] = None
    # احراز هویت تلگرام
    telegram_id: Optional[int] = Field(default=None, index=True, unique=True)
    photo_url: Optional[str] = None
    # پلن کاربر (free / pro / vip) — برای فاز درآمدزایی
    plan: str = Field(default="free")
    created_at: datetime = Field(default_factory=_now)


class Holding(SQLModel, table=True):
    """یک دارایی در پورتفولیو کاربر (ورود دستی)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    symbol: str = Field(index=True)          # مثل BTC
    name: Optional[str] = None
    amount: float = 0.0                       # مقدار نگه‌داری‌شده
    avg_buy_price: float = 0.0                # میانگین قیمت خرید (دلار)
    note: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class JournalEntry(SQLModel, table=True):
    """ثبت یک معامله در ژورنال (فاز ۴ — پایه)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="user.id")
    pair: str = Field(index=True)             # مثل BTCUSDT
    side: str = "long"                         # long / short
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    size: float = 0.0
    pnl: Optional[float] = None                # سود/زیان (دلار)
    strategy: Optional[str] = None
    emotion: Optional[str] = None
    note: Optional[str] = None
    opened_at: datetime = Field(default_factory=_now)
    closed_at: Optional[datetime] = None
