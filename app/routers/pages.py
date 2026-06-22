"""روتر صفحات HTML (رندر سمت سرور با Jinja2)."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.routers.auth import account_display_name

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _static_version() -> str:
    """نسخهٔ فایل‌های استاتیک = بزرگ‌ترین زمان تغییر در پوشهٔ static.
    با هر استقرار عوض می‌شود و کش مرورگر/Nginx را خودبه‌خود باطل می‌کند."""
    base = Path(__file__).resolve().parent.parent / "static"
    latest = 0.0
    try:
        for root, _dirs, files in os.walk(base):
            for f in files:
                m = os.path.getmtime(os.path.join(root, f))
                if m > latest:
                    latest = m
    except OSError:
        pass
    return str(int(latest))


templates.env.globals["static_v"] = _static_version()


def _ctx(request: Request, active: str) -> dict:
    return {
        "request": request,
        "brand_fa": settings.app_brand_fa,
        "title_fa": settings.app_title_fa,
        "subtitle_fa": settings.app_subtitle_fa,
        "active": active,
        "account_name": account_display_name(request),
    }


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("home.html", _ctx(request, "home"))
