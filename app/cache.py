"""
کش درون‌حافظه‌ای با TTL + شمارندهٔ پایدار بودجهٔ کردیت CryptoRank.

* کش سمت سرور باعث می‌شود فرانت‌اند هرگز مستقیم به APIها وصل نشود و همهٔ
  کاربران از یک نتیجهٔ مشترک استفاده کنند (مصرف کردیت کنترل‌شده).
* شمارندهٔ کردیت روی دیسک ذخیره می‌شود تا با ری‌استارت هم سقف ماهانهٔ
  ۱۰٬۰۰۰ کردیت CryptoRank حفظ شود.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from app.config import settings


class TTLCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            expires_at, value = item
            if time.time() > expires_at:
                return None
            return value

    def get_stale(self, key: str) -> Optional[Any]:
        with self._lock:
            item = self._store.get(key)
            return item[1] if item else None

    def set(self, key: str, value: Any, ttl: float) -> None:
        with self._lock:
            self._store[key] = (time.time() + ttl, value)


class CreditBudget:
    """پایش مصرف کردیت یک منبع در سه بازه: دقیقه، روز، ماه.

    سقف‌ها هنگام ساخت داده می‌شوند تا برای چند منبع (CryptoRank، CoinMarketCap)
    قابل استفاده باشد. اگر سقفی داده نشود از تنظیمات CryptoRank استفاده می‌شود
    (سازگاری عقب‌رو)."""

    def __init__(self, state_file: str, per_min: int | None = None,
                 daily: int | None = None, monthly: int | None = None) -> None:
        self._path = Path(state_file)
        self._lock = threading.Lock()
        self._per_min = per_min if per_min is not None else settings.cryptorank_per_min_credits
        self._daily = daily if daily is not None else settings.cryptorank_daily_credits
        self._monthly = monthly if monthly is not None else settings.cryptorank_monthly_credits
        self._state = self._load()

    def _load(self) -> dict[str, Any]:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text("utf-8"))
            except Exception:
                pass
        return {"minute": {}, "day": {}, "month": {}}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), "utf-8")
        except OSError:
            pass

    @staticmethod
    def _keys(now: datetime) -> tuple[str, str, str]:
        return (now.strftime("%Y-%m-%d %H:%M"), now.strftime("%Y-%m-%d"), now.strftime("%Y-%m"))

    def _used(self, bucket: str, key: str) -> int:
        return int(self._state.get(bucket, {}).get(key, 0))

    def can_spend(self, cost: int) -> bool:
        now = datetime.now(timezone.utc)
        m_key, d_key, mo_key = self._keys(now)
        with self._lock:
            if self._used("minute", m_key) + cost > self._per_min:
                return False
            if self._used("day", d_key) + cost > self._daily:
                return False
            if self._used("month", mo_key) + cost > self._monthly:
                return False
            return True

    def spend(self, cost: int) -> None:
        now = datetime.now(timezone.utc)
        m_key, d_key, mo_key = self._keys(now)
        with self._lock:
            for bucket, key in (("minute", m_key), ("day", d_key), ("month", mo_key)):
                b = self._state.setdefault(bucket, {})
                b[key] = self._used(bucket, key) + cost
            self._prune(now)
            self._save()

    def _prune(self, now: datetime) -> None:
        m_key, _d_key, mo_key = self._keys(now)
        self._state["minute"] = {m_key: self._state.get("minute", {}).get(m_key, 0)}
        day = self._state.get("day", {})
        self._state["day"] = {k: v for k, v in day.items() if k[:7] == mo_key}

    def usage(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        m_key, d_key, mo_key = self._keys(now)
        return {
            "minute": {"used": self._used("minute", m_key), "limit": self._per_min},
            "day": {"used": self._used("day", d_key), "limit": self._daily},
            "month": {"used": self._used("month", mo_key), "limit": self._monthly},
        }


cache = TTLCache()
credit_budget = CreditBudget(settings.credit_state_file)
cmc_budget = CreditBudget(
    settings.cmc_state_file,
    per_min=settings.cmc_per_min_credits,
    daily=settings.cmc_daily_credits,
    monthly=settings.cmc_monthly_credits,
)


async def cached(key: str, ttl: float, fetcher: Callable, fallback: Callable):
    """مقدار را از کش بده؛ در نبود، fetcher را صدا بزن؛ در خطا، کش کهنه یا نمونه."""
    hit = cache.get(key)
    if hit is not None:
        return hit
    try:
        value = await fetcher()
        cache.set(key, value, ttl)
        return value
    except Exception:
        stale = cache.get_stale(key)
        if stale is not None:
            return stale
        return fallback()
