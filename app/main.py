"""
نقطهٔ ورود CryptoSmart Hub (FastAPI).
اجرا:  uvicorn app.main:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import db
from app.config import settings
from app.routers import admin, advisor, auth, market, pages, portfolio

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


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "build": "p2-portfolio-1"}
