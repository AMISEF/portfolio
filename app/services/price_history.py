"""
تاریخچهٔ قیمت پایدار (روی دیسک) برای محاسبهٔ درصد تغییر ۲۴ساعته.

چرا؟ پراکسیِ SourceArena فیلد «تغییر» را صفر برمی‌گرداند و Yahoo از سرور اغلب در
دسترس نیست؛ پس درصد تغییر را خودمان از روی قیمت‌های واقعیِ ثبت‌شده حساب می‌کنیم.
ذخیره در data/price_history.json است تا با ری‌استارت pm2 از بین نرود (کش حافظه‌ای
با هر ری‌استارت پاک می‌شد و درصد تغییر دوباره صفر می‌شد).

برای هر کلید، نمونه‌های (زمان، قیمت) تا حدود ۵۰ ساعت نگه داشته می‌شود و درصد تغییر
نسبت به نزدیک‌ترین نمونهٔ حدوداً ۲۴ساعت‌پیش محاسبه می‌گردد.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

_PATH = Path("data/price_history.json")
_LOCK = threading.Lock()
_MAX_AGE = 50 * 3600          # نگه‌داری ۵۰ ساعت
_MIN_GAP = 240                # حداقل فاصلهٔ ثبت دو نمونه (ثانیه)
_WINDOW = 24 * 3600           # پنجرهٔ ۲۴ساعته


def _load() -> dict:
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save(data: dict) -> None:
    try:
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(_PATH)
    except Exception:  # noqa: BLE001
        pass


def record_and_change(key: str, price: float, window: int = _WINDOW) -> float:
    """قیمت فعلی را ثبت می‌کند و درصد تغییر نسبت به حدود `window` ثانیهٔ پیش را برمی‌گرداند.

    اگر هنوز نمونهٔ ۲۴ساعت‌پیش نداشته باشیم، نسبت به قدیمی‌ترین نمونهٔ موجود حساب
    می‌شود (تا هرگز روی صفر گیر نکند و با حرکت بازار به‌روز شود).
    """
    try:
        price = float(price)
    except (TypeError, ValueError):
        return 0.0
    if price <= 0:
        return 0.0

    now = time.time()
    target = now - window
    with _LOCK:
        data = _load()
        series = [p for p in data.get(key, []) if isinstance(p, list) and len(p) == 2
                  and now - p[0] <= _MAX_AGE]

        # نمونهٔ مرجع: جدیدترین نمونه‌ای که حداقل `window` ثانیه قدمت دارد؛
        # وگرنه قدیمی‌ترین نمونهٔ موجود.
        ref = None
        older = [p for p in series if p[0] <= target]
        if older:
            ref = older[-1][1]
        elif series:
            ref = series[0][1]

        # ثبت نمونهٔ جدید (با محدودیت فاصله تا فایل بی‌جهت بزرگ نشود)
        if not series or now - series[-1][0] >= _MIN_GAP:
            series.append([now, price])
        data[key] = series
        _save(data)

    if ref and ref > 0:
        return round((price - ref) / ref * 100, 2)
    return 0.0
