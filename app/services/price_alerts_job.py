"""پایشِ قیمت و ارسالِ هشدارِ «ارز به قیمتِ خرید رسید».

هر PRICE_ALERT_INTERVAL ثانیه قیمتِ لحظه‌ایِ ارزها خوانده می‌شود و هر هشدارِ
فعالِ شلیک‌نشده که قیمتش به هدف رسیده (قیمتِ بازار ≤ قیمتِ هدفِ خرید) برای
کاربرِ متصل به ربات تلگرام ارسال و «شلیک‌شده» علامت می‌خورد.

هشدارِ خرید است، پس شرط «رسیدن» یعنی قیمت تا هدف پایین آمده باشد. برای اینکه
هشدارِ ارزی که همین حالا هم زیرِ هدف است از دست نرود، مقایسه ≤ است.
"""
from __future__ import annotations

import asyncio
import logging

from app import db
from app.config import settings
from app.services import algohub_bot, instruments

logger = logging.getLogger("app.price_alerts")


async def check_once() -> dict[str, int]:
    """یک دورِ بررسی. خروجی: شمارشِ بررسی‌شده/ارسال‌شده (برای لاگ و تست)."""
    pending = db.alerts_pending()
    if not pending or not algohub_bot.is_enabled():
        return {"checked": len(pending), "sent": 0}

    try:
        table = await instruments.price_table()
    except Exception:  # noqa: BLE001
        logger.exception("price table fetch failed")
        return {"checked": len(pending), "sent": 0}

    prices = _usd_prices(table)
    sent = 0
    for a in pending:
        sym = str(a.get("symbol") or "").upper()
        price = prices.get(sym)
        target = float(a.get("target_price") or 0)
        if price is None or target <= 0:
            continue
        if price > target:
            continue  # هنوز به قیمتِ خرید نرسیده
        text = algohub_bot.buy_alert_message(
            symbol=sym,
            name=a.get("name"),
            target=target,
            price=price,
            horizon=str(a.get("horizon") or "short"),
        )
        if await algohub_bot.send_message(str(a["chat_id"]), text):
            db.alert_mark_triggered(int(a["id"]))
            sent += 1
    return {"checked": len(pending), "sent": sent}


def _usd_prices(table: dict) -> dict[str, float]:
    """نگاشتِ نماد ⇒ قیمتِ دلاری. جدولِ ابزارها ارزها را به‌صورت
    {BTC: {price_usd, …}} می‌دهد؛ تتر هم همیشه ۱ دلار است."""
    out: dict[str, float] = {}
    crypto = table.get("crypto") or {}
    if isinstance(crypto, dict):
        for sym, row in crypto.items():
            usd = (row or {}).get("price_usd")
            if isinstance(usd, (int, float)) and usd > 0:
                out[str(sym).upper()] = float(usd)
    out.setdefault("USDT", 1.0)
    return out


async def loop() -> None:
    """حلقهٔ پس‌زمینه؛ خطاها هرگز حلقه را متوقف نمی‌کنند."""
    interval = max(30, int(settings.price_alert_interval or 120))
    while True:
        try:
            await asyncio.sleep(interval)
            await check_once()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("price alert loop iteration failed")
            await asyncio.sleep(60)
