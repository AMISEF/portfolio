"""
نقطهٔ ورود CryptoSmart Hub (FastAPI).
اجرا:  uvicorn app.main:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import market, pages

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(pages.router)
app.include_router(market.router)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "build": "p1-cmc-12"}
