"""روتر صفحات HTML (رندر سمت سرور با Jinja2)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import settings

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


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
