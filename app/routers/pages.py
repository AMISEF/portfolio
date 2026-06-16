"""روتر صفحات HTML (رندر سمت سرور با Jinja2)."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import settings

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _static_version() -> str:
    """نسخهٔ فایل‌های استاتیک = بزرگ‌ترین زمان تغییر در پوشهٔ static.
    با هر استقرار (که فایل‌ها را به‌روز و سرویس را ری‌استارت می‌کند) عوض می‌شود،
    پس کش مرورگر/Nginx خودبه‌خود باطل می‌گردد و تغییرات بلافاصله دیده می‌شوند."""
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


# نسخه یک‌بار هنگام راه‌اندازی محاسبه می‌شود (هر استقرار سرویس را ری‌استارت می‌کند).
templates.env.globals["static_v"] = _static_version()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "brand_fa": settings.app_brand_fa,
            "title_fa": settings.app_title_fa,
            "active": "home",
        },
    )
