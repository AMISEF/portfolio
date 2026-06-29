"""
زمان‌بندِ روزانهٔ تصویر «نمای کلی بازار» و ارسال آن به کانال تلگرام.

هر روز ساعت ۱۱:۰۰ به وقت تهران، تصویر ۴K عمودی ساخته و با ربات
portfolio_Cryptosmart_bot (توکن از .env: SIGNALS_BOT_TOKEN) در کانال
Portfolio_CryptoSmart (شناسه از settings.signals_channel_id) منتشر می‌شود.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.services import market_card

_API = "https://api.telegram.org"
_OUT = Path("data/market_card/overview.png")
_RUN_HOUR = 11   # ۱۱ صبح به وقت تهران


async def send_to_channel(png: Path, caption: str = "") -> dict[str, Any]:
    """ارسال تصویر به کانال با sendPhoto (آپلود مالتی‌پارت)."""
    token = settings.signals_bot_token
    chat_id = settings.signals_channel_id
    if not token or not chat_id:
        return {"ok": False, "error": "missing_token_or_channel"}
    data = png.read_bytes()
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        r = await client.post(
            f"{_API}/bot{token}/sendPhoto",
            data={"chat_id": str(chat_id), "caption": caption},
            files={"photo": ("market-overview.png", data, "image/png")},
        )
    try:
        body = r.json()
    except Exception:  # noqa: BLE001
        body = {"raw": r.text[:300]}
    return {"ok": bool(r.is_success and body.get("ok")), "status": r.status_code, "response": body}


def _caption() -> str:
    return (f"📊 نمای کلی بازار — {market_card.shamsi_today()}\n"
            f"@Portfolio_CryptoSmart")


async def generate_and_send() -> dict[str, Any]:
    """ساخت تصویر و ارسال آن به کانال (یک‌بار)."""
    await market_card.render_png(_OUT)
    res = await send_to_channel(_OUT, _caption())
    return res


def _seconds_until_next_run() -> float:
    now = market_card.tehran_now()
    target = now.replace(hour=_RUN_HOUR, minute=0, second=0, microsecond=0)
    if target <= now:
        target += _dt.timedelta(days=1)
    return max(1.0, (target - now).total_seconds())


async def daily_loop() -> None:
    """حلقهٔ روزانه: تا ۱۱:۰۰ تهران می‌خوابد، تصویر را می‌سازد و می‌فرستد، و تکرار می‌کند."""
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
