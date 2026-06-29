"""
نقطهٔ ورود CryptoSmart Hub (FastAPI).
اجرا:  uvicorn app.main:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import asyncio

from app import db
from app.config import settings
from app.routers import admin, advisor, auth, market, pages, portfolio
from app.services import telegram_signals

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(pages.router)
app.include_router(market.router)
app.include_router(portfolio.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(advisor.router)


@app.on_event("startup")
async def _startup() -> None:
    db.init_db()
    # ثبت وب‌هوکِ ربات سیگنال‌ها و پاک‌سازی تحلیل‌های منقضی (بدون بلوکه‌کردن استارت‌آپ).
    if settings.signals_bot_token:
        async def _init_signals() -> None:
            try:
                await telegram_signals.register_webhook()
            except Exception:  # noqa: BLE001
                pass
            telegram_signals.purge_expired()
        asyncio.create_task(_init_signals())


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "build": "p2-portfolio-1"}
