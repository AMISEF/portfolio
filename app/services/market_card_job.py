"""
زمان‌بندِ تصویر «نمای کلی بازار» و ارسال آن به گروه/تاپیک تلگرام.

هر settings.market_card_interval_hours ساعت یک‌بار (پیش‌فرض ۴ ساعت)، تصویر ۴K
عمودی ساخته و با ربات portfolio_Cryptosmart_bot (توکن .env: SIGNALS_BOT_TOKEN) در
گروهِ settings.market_card_chat_id و تاپیکِ settings.market_card_topic_id منتشر
می‌شود. ارسال به‌صورت «فایل» (sendDocument) انجام می‌شود تا کیفیت 4K حفظ شود
(تلگرام عکس‌های sendPhoto را فشرده می‌کند).
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.services import market_card

_API = "https://api.telegram.org"
_OUT = Path("data/market_card/overview.png")


async def send_image(png: Path, caption: str = "", *, chat_id: str | None = None,
                     topic_id: int | None = None, as_document: bool | None = None) -> dict[str, Any]:
    """ارسال تصویر به گروه/تاپیک.

    as_document=True ⇒ sendDocument (بدون فشرده‌سازی، حفظ کیفیت 4K).
    topic_id ⇒ message_thread_id برای ارسال داخل تاپیکِ گروه.
    """
    token = settings.signals_bot_token
    chat = chat_id if chat_id is not None else settings.market_card_chat_id
    if as_document is None:
        as_document = settings.market_card_as_document
    if topic_id is None:
        topic_id = settings.market_card_topic_id
    if not token or not chat:
        return {"ok": False, "error": "missing_token_or_chat"}
    data = png.read_bytes()
    form: dict[str, str] = {"chat_id": str(chat), "caption": caption}
    if topic_id:
        form["message_thread_id"] = str(topic_id)
    method = "sendDocument" if as_document else "sendPhoto"
    field = "document" if as_document else "photo"
    async with httpx.AsyncClient(timeout=httpx.Timeout(90.0)) as client:
        r = await client.post(
            f"{_API}/bot{token}/{method}",
            data=form,
            files={field: ("market-overview.png", data, "image/png")},
        )
    try:
        body = r.json()
    except Exception:  # noqa: BLE001
        body = {"raw": r.text[:300]}
    return {"ok": bool(r.is_success and body.get("ok")), "status": r.status_code, "response": body}


# سازگاری عقب‌رو: نام قبلی همچنان کار می‌کند (ارسال با تنظیماتِ پیش‌فرضِ گروه/تاپیک).
async def send_to_channel(png: Path, caption: str = "") -> dict[str, Any]:
    return await send_image(png, caption)


def _caption() -> str:
    return (f"📊 نمای کلی بازار — {market_card.shamsi_today()}\n"
            f"@Portfolio_CryptoSmart")


async def generate_and_send() -> dict[str, Any]:
    """ساخت تصویر با آخرین قیمت‌ها و ارسال آن به گروه/تاپیک (یک‌بار)."""
    await market_card.render_png(_OUT)
    return await send_image(_OUT, _caption())


# ساعت‌های اجرا به وقت تهران (۲۴ساعته)
_RUN_HOURS = [11, 13]

def _seconds_until_next_run() -> float:
    """ثانیه تا نزدیک‌ترین اجرای بعدی در ساعت‌های ثابتِ _RUN_HOURS به وقت تهران."""
    import datetime as _dt
    now = market_card.tehran_now()
    candidates = []
    for h in _RUN_HOURS:
        target = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if target <= now:
            target += _dt.timedelta(days=1)
        candidates.append(target)
    target = min(candidates)
    return max(1.0, (target - now).total_seconds())


async def periodic_loop() -> None:
    """حلقهٔ دوره‌ای: هر market_card_interval_hours ساعت تصویر را می‌سازد و می‌فرستد."""
    if not settings.signals_bot_token:
        return
    while True:
        try:
            await asyncio.sleep(_seconds_until_next_run())
            await generate_and_send()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            # خطا نباید حلقه را متوقف کند؛ تا اجرای بعدی صبر می‌کنیم.
            await asyncio.sleep(60)


# سازگاری عقب‌رو با main.py (نام قبلی daily_loop).
daily_loop = periodic_loop
