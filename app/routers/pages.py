"""روتر صفحات HTML (رندر سمت سرور با Jinja2)."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.routers.auth import account_display_name, current_user
from app.services import plans
from app import db

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


STATIC_V = _static_version()
templates.env.globals["static_v"] = STATIC_V


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


@router.get("/subscription", response_class=HTMLResponse)
async def subscription_page(request: Request):
    """صفحهٔ خرید/مدیریت اشتراک — چهار پلن + وضعیت اشتراک جاری کاربر."""
    user = current_user(request)
    ai_used = db.ai_used_count(int(user["id"]), plans.usage_key(user)) if user else 0
    ctx = _ctx(request, "subscription")
    ctx["title_fa"] = "اشتراک"
    ctx["subtitle_fa"] = "مدیریت اشتراک"
    ctx["is_authed"] = bool(user)
    ctx["plans_data"] = plans.plans_payload(user, ai_used)
    return templates.TemplateResponse("subscription.html", ctx)


@router.get("/exclusive", response_class=HTMLResponse)
async def exclusive_page(request: Request):
    """بخش «تحلیل اختصاصی» (placeholder فاز بعد). گیت‌دار برای پلن‌های پولی."""
    user = current_user(request)
    ctx = _ctx(request, "exclusive")
    ctx["title_fa"] = "تحلیل اختصاصی"
    ctx["subtitle_fa"] = "تحلیل‌های بازار داخلی و خارجی"
    ctx["is_authed"] = bool(user)
    ctx["can_access"] = plans.can_access_exclusive(user)
    ctx["is_admin"] = bool(user and (user.get("role") or "member") in ("admin", "support"))
    return templates.TemplateResponse("exclusive.html", ctx)


_EXC_FILTERS = {"all", "external", "internal", "btc_eth"}


@router.get("/api/exclusive/signals")
async def exclusive_signals(request: Request, filter: str = "all", page: int = 1):
    """خوراکِ کانالِ «تحلیل اختصاصی» — تحلیل‌های تصویری کانال تلگرام با کپشن.

    گیت‌دار: فقط اعضای دارای اشتراک (نقره‌ای/طلایی/الماسی + ادمین) دسترسی دارند.
    صفحه‌بندی ۱۰ تحلیل در هر صفحه؛ فیلترِ دسته: all / external / internal / btc_eth.
    """
    user = current_user(request)
    if not plans.can_access_exclusive(user):
        return JSONResponse({"error": "forbidden"}, status_code=403)

    cat = filter if filter in _EXC_FILTERS else "all"
    data = db.list_signals_feed(category=cat, page=page, per_page=10)

    posts = []
    for r in data["items"]:
        mid = r.get("message_id")
        n = len(r.get("image_list") or [])
        images = [f"/api/advisor/signal-image/{mid}?i={k}" for k in range(1, n + 1)]
        posts.append({
            "id": mid,
            "ts": r.get("ts"),
            "text": r.get("text") or "",
            "hashtags": r.get("tags") or [],
            "is_internal": bool(r.get("is_internal")),
            "is_btc_eth": bool(r.get("is_btc_eth")),
            "images": images,
            "image_url": images[0] if images else None,
        })
    return JSONResponse({
        "channel": {
            "name": "کریپتو اسمارت | Crypto Smart",
            "handle": "Portfolio_CryptoSmart",
            "url": settings.signals_channel_url,
            "avatar": "/static/img/channel-avatar.png",
        },
        "filter": cat,
        "page": data["page"],
        "per_page": data["per_page"],
        "total": data["total"],
        "total_pages": data["total_pages"],
        "posts": posts,
    })


@router.get("/api/subscription/plans")
async def subscription_plans(request: Request):
    """فهرست چهار پلن + وضعیت اشتراک جاری کاربر (برای صفحهٔ قیمت‌گذاری)."""
    user = current_user(request)
    ai_used = 0
    if user:
        ai_used = db.ai_used_count(int(user["id"]), plans.usage_key(user))
    return JSONResponse(plans.plans_payload(user, ai_used))
