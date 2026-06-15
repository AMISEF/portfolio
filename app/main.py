"""
نقطهٔ ورود برنامهٔ CryptoSmart Hub (FastAPI).
اجرا:  uvicorn app.main:app --reload   یا   python run.py
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.db import init_db
from app.routers import auth, journal, market, pages, portfolio


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    max_age=settings.session_max_age,
    same_site="lax",
    https_only=False,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(pages.router)
app.include_router(market.router)
app.include_router(auth.router)
app.include_router(portfolio.router)
app.include_router(journal.router)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name}
