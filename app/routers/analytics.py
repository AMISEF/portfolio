"""
API قیف محصول برای پنل مدیریت.

  GET /api/admin/funnel?days=30   ← گزارش کامل قیف (ادمین/پشتیبان)
  POST /api/track                 ← ثبت رویداد از سمت کلاینت (اختیاری)
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from app.routers.auth import current_user
from app.services import analytics

router = APIRouter()

_ALLOWED_EVENTS = {"cta_click", "signup_start", "plan_view", "install_prompt"}


def _staff(request: Request) -> dict[str, Any] | None:
    u = current_user(request)
    if u and (u.get("role") or "member") in ("admin", "support"):
        return u
    return None


@router.get("/api/admin/funnel")
async def admin_funnel(request: Request, days: int = 30):
    if not _staff(request):
        return JSONResponse({"error": "\u062f\u0633\u062a\u0631\u0633\u06cc \u063a\u06cc\u0631\u0645\u062c\u0627\u0632."}, status_code=403)
    try:
        data = analytics.funnel(days)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)
    return JSONResponse(data)


@router.post("/api/track")
async def track(request: Request, payload: dict[str, Any] = Body(default={})):
    """ثبت رویدادهای تعاملی از سمت مرورگر (بدون احراز هویت)."""
    kind = str(payload.get("kind") or "").strip()
    if kind not in _ALLOWED_EVENTS:
        return JSONResponse({"ok": False}, status_code=400)
    user = current_user(request)
    analytics.record_event(
        kind,
        user_id=int(user["id"]) if user else None,
        vid=request.cookies.get("ah_vid"),
        path=str(payload.get("path") or ""),
    )
    return JSONResponse({"ok": True})
