"""
روتر پورتفولیو / مدیریت سرمایه.

صفحات:
  GET /portfolio            ← آزمون ریسک‌پذیری (اگر انجام نشده) یا نتیجه + شروع
  GET /portfolio/assistant  ← چت‌بات مدیریت سرمایه + ورود دارایی‌ها + نمودار

API (فرانت‌اند فقط با این‌ها صحبت می‌کند):
  GET    /api/portfolio/risk/questions  ← پرسش‌نامه
  POST   /api/portfolio/risk            ← ثبت پاسخ‌ها + محاسبهٔ درصد و طبقه
  GET    /api/portfolio/risk            ← پروفایل ریسک ذخیره‌شده
  GET    /api/portfolio/assets          ← فهرست دارایی‌ها + ارزش‌گذاری زنده
  POST   /api/portfolio/assets          ← افزودن دارایی
  DELETE /api/portfolio/assets/{id}     ← حذف دارایی

هویت کاربر: تا فعال‌شدن احراز هویت واقعی، هر کاربر با شناسهٔ ناشناسِ کوکی‌محور
(cs_uid) شناخته می‌شود.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Body, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from app import db
from app.config import settings
from app.services import portfolio_valuation, risk

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

_COOKIE = "cs_uid"
_COOKIE_MAX_AGE = 60 * 60 * 24 * 365 * 2   # دو سال


def _uid(request: Request) -> tuple[str, bool]:
    """(شناسهٔ کاربر، آیا تازه ساخته شد). شناسه از کوکی cs_uid خوانده می‌شود."""
    uid = request.cookies.get(_COOKIE)
    if uid:
        return uid, False
    return uuid.uuid4().hex, True


def _attach_uid(resp: Response, uid: str, is_new: bool) -> Response:
    if is_new:
        resp.set_cookie(_COOKIE, uid, max_age=_COOKIE_MAX_AGE,
                        httponly=True, samesite="lax")
    return resp


def _json(data: Any, uid: str, is_new: bool, status: int = 200) -> JSONResponse:
    return _attach_uid(JSONResponse(data, status_code=status), uid, is_new)


def _ctx(request: Request, active: str) -> dict:
    return {
        "request": request,
        "brand_fa": settings.app_brand_fa,
        "title_fa": settings.app_title_fa,
        "subtitle_fa": settings.app_subtitle_fa,
        "active": active,
    }


# ───────────────────────── صفحات ─────────────────────────
@router.get("/portfolio", response_class=HTMLResponse)
async def portfolio_page(request: Request):
    uid, is_new = _uid(request)
    resp = templates.TemplateResponse("portfolio.html", _ctx(request, "portfolio"))
    return _attach_uid(resp, uid, is_new)


@router.get("/portfolio/assistant", response_class=HTMLResponse)
async def assistant_page(request: Request):
    uid, is_new = _uid(request)
    resp = templates.TemplateResponse("portfolio_assistant.html", _ctx(request, "portfolio"))
    return _attach_uid(resp, uid, is_new)


# ───────────────────────── API: ریسک ─────────────────────────
@router.get("/api/portfolio/risk/questions")
async def risk_questions():
    return {"questions": risk.questions_payload(), "count": len(risk.QUESTIONS)}


@router.post("/api/portfolio/risk")
async def submit_risk(request: Request, payload: dict[str, Any] = Body(...)):
    uid, is_new = _uid(request)
    answers = payload.get("answers")
    if not isinstance(answers, list):
        return _json({"error": "پاسخ‌ها نامعتبر است"}, uid, is_new, 400)
    try:
        result = risk.score_answers([int(x) for x in answers])
    except (ValueError, TypeError) as e:
        return _json({"error": str(e)}, uid, is_new, 400)
    db.save_risk(uid, result, json.dumps(answers, ensure_ascii=False))
    return _json(result, uid, is_new)


@router.get("/api/portfolio/risk")
async def get_risk(request: Request):
    uid, is_new = _uid(request)
    return _json({"profile": db.get_risk(uid)}, uid, is_new)


# ───────────────────────── API: دارایی‌ها ─────────────────────────
_KINDS = {"crypto", "gold", "usdt", "toman"}


@router.post("/api/portfolio/assets")
async def add_asset(request: Request, payload: dict[str, Any] = Body(...)):
    uid, is_new = _uid(request)
    kind = (payload.get("kind") or "").strip()
    if kind not in _KINDS:
        return _json({"error": "نوع دارایی نامعتبر است"}, uid, is_new, 400)
    try:
        amount = float(payload.get("amount") or 0)
    except (TypeError, ValueError):
        return _json({"error": "مقدار نامعتبر است"}, uid, is_new, 400)
    if amount <= 0:
        return _json({"error": "مقدار باید بزرگ‌تر از صفر باشد"}, uid, is_new, 400)

    buy_price = payload.get("buy_price")
    try:
        buy_price = float(buy_price) if buy_price not in (None, "") else None
    except (TypeError, ValueError):
        buy_price = None

    asset = {
        "kind": kind,
        "symbol": (payload.get("symbol") or kind).strip().upper(),
        "name": (payload.get("name") or payload.get("symbol") or kind).strip(),
        "amount": amount,
        "buy_price": buy_price,
        "purity": payload.get("purity"),
        "horizon": payload.get("horizon"),
    }
    asset_id = db.add_asset(uid, asset)
    return _json({"id": asset_id, "ok": True}, uid, is_new)


@router.get("/api/portfolio/assets")
async def get_assets(request: Request):
    uid, is_new = _uid(request)
    valued = await portfolio_valuation.value_portfolio(db.list_assets(uid))
    return _json(valued, uid, is_new)


@router.delete("/api/portfolio/assets/{asset_id}")
async def remove_asset(request: Request, asset_id: int):
    uid, is_new = _uid(request)
    return _json({"ok": db.delete_asset(uid, asset_id)}, uid, is_new)
