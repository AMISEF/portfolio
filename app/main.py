"""
نقطهٔ ورود CryptoSmart Hub (FastAPI).
اجرا:  uvicorn app.main:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import asyncio

from app import db
from app.config import settings
from app.routers import (admin, advisor, auth, bot, market, pages, portfolio,
                         settings_api)
from app.services import (algohub_bot, broadcast_job, market_card_job,
                          price_alerts_job, signals_retention, telegram_signals)

app = FastAPI(title=settings.app_name, debug=settings.debug)

# پشتیبانِ فشرده‌سازی برای زمانی که uvicorn مستقیم (بدونِ gzipِ nginx) پاسخ می‌دهد.
app.add_middleware(GZipMiddleware, minimum_size=512)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


# ── اپلیکیشن نصب‌شدنی ALGO HUB (PWA) ──────────────────────────────
# منیفست و سرویس‌وورکر باید روی ریشهٔ دامنه سرو شوند تا دامنهٔ پوشش «/»
# باشد و ژورنال (زیرِ /journal) هم بخشی از همان اپ ALGO HUB دیده شود.
@app.get("/manifest.webmanifest", include_in_schema=False)
async def pwa_manifest() -> FileResponse:
    return FileResponse(
        "app/static/manifest.webmanifest",
        media_type="application/manifest+json",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/sw.js", include_in_schema=False)
async def pwa_service_worker() -> FileResponse:
    return FileResponse(
        "app/static/sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
    )


# لوگوی رسمی اپ ALGO HUB. فایلِ اصلی در مخزنِ ژورنال قرار دارد؛ برای همین
# چند مسیر احتمالی به ترتیب بررسی می‌شود تا هر جا بود همان سرو شود.
_LOGO_CANDIDATES = [
    os.getenv("ALGOHUB_LOGO_PATH", ""),
    "app/static/img/algohub-logo.png",
    "/var/www/trading-journal/ALGOHUB-LOGO.png",
    "../trading-journal/ALGOHUB-LOGO.png",
    "app/static/img/logo.png",
]


@app.get("/app-icon", include_in_schema=False)
async def pwa_app_icon() -> FileResponse:
    for candidate in _LOGO_CANDIDATES:
        if candidate and Path(candidate).is_file():
            return FileResponse(
                candidate,
                media_type="image/png",
                headers={"Cache-Control": "public, max-age=86400"},
            )
    raise HTTPException(status_code=404, detail="app icon not found")


@app.get("/offline", include_in_schema=False)
async def pwa_offline() -> FileResponse:
    return FileResponse("app/static/offline.html", media_type="text/html")


app.include_router(pages.router)
app.include_router(market.router)
app.include_router(portfolio.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(advisor.router)
app.include_router(bot.router)
app.include_router(settings_api.router)


@app.on_event("startup")
async def _startup() -> None:
    db.init_db()
    # پاک‌سازیِ تحلیل‌های منقضی: یک‌بار در استارت‌آپ و سپس هر ساعت.
    asyncio.create_task(signals_retention.loop())

    # ثبت وب‌هوکِ ربات سیگنال‌ها (بدون بلوکه‌کردن استارت‌آپ).
    if settings.signals_bot_token:
        async def _init_signals() -> None:
            try:
                await telegram_signals.register_webhook()
            except Exception:  # noqa: BLE001
                pass
        asyncio.create_task(_init_signals())
        # زمان‌بندِ روزانهٔ تصویر «نمای کلی بازار» (هر روز ۱۱:۰۰ تهران).
        asyncio.create_task(market_card_job.daily_loop())

    # ربات «الگو هاب»: ثبتِ وب‌هوک + حلقهٔ پایشِ قیمت برای هشدارهای خرید.
    if settings.algohub_bot_token:
        async def _init_algohub() -> None:
            try:
                await algohub_bot.register_webhook()
            except Exception:  # noqa: BLE001
                pass
        asyncio.create_task(_init_algohub())
        asyncio.create_task(price_alerts_job.loop())
        # کارگرِ صفِ پیام همگانی: ارسالِ تدریجی با سقفِ ساعتی.
        asyncio.create_task(broadcast_job.loop())


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "build": "p2-portfolio-1"}
