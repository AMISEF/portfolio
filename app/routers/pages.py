"""روتر صفحات HTML (رندر سمت سرور با Jinja2)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.deps import current_user
from app.models import User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _ctx(request: Request, user: User | None, active: str, **extra) -> dict:
    base = {
        "request": request,
        "brand_fa": settings.app_brand_fa,
        "title_fa": settings.app_title_fa,
        "active": active,
        "user": user,
    }
    base.update(extra)
    return base


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, user: User = Depends(current_user)):
    return templates.TemplateResponse("home.html", _ctx(request, user, "home"))


@router.get("/portfolio", response_class=HTMLResponse)
async def portfolio_page(request: Request, user: User = Depends(current_user)):
    return templates.TemplateResponse("portfolio.html", _ctx(request, user, "portfolio"))


@router.get("/journal", response_class=HTMLResponse)
async def journal_page(request: Request, user: User = Depends(current_user)):
    return templates.TemplateResponse("journal.html", _ctx(request, user, "journal"))


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, user: User = Depends(current_user)):
    return templates.TemplateResponse("settings.html", _ctx(request, user, "settings"))
