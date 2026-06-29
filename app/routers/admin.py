"""
پنل مدیریت (ادمین/پشتیبان).

دسترسی‌ها:
  • ادمین: مشاهده، ویرایش کاملِ کاربر (شاملِ رمز)، تغییر نقش، حذف، اشتراک، خروجی.
  • پشتیبان: مشاهده، مدیریت اشتراک (ارتقا/تمدید/حذف)، خروجی.

صفحه:
  GET  /admin                         ← پنل مدیریت (HTML)

API:
  GET    /api/admin/users             ← فهرست کامل کاربران (+ رمزِ رمزگشایی‌شده)
  GET    /api/admin/users/{id}/assets ← دارایی‌های یک کاربر
  POST   /api/admin/users/{id}        ← ویرایش مشخصات (ادمین)
  POST   /api/admin/users/{id}/role   ← تغییر نقش (ادمین)
  POST   /api/admin/users/{id}/subscription ← ارتقا/تمدید/حذف اشتراک (ادمین+پشتیبان)
  DELETE /api/admin/users/{id}        ← حذف کاربر (ادمین)
  POST   /api/admin/export            ← خروجی اکسل کاربرانِ انتخاب‌شده (ادمین+پشتیبان)
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Body, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app import db
from app.config import settings
from app.routers.auth import account_display_name, current_user
from app.services import auth as auth_svc
from app.services import crypto_box, portfolio_valuation, xlsx

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
# نسخهٔ استاتیک مشترک با روتر صفحات تا با هر استقرار، کش CSS/JS باطل شود
# (وگرنه {{ static_v }} اینجا خالی می‌ماند و مرورگر CSS قدیمی را برای /admin کش می‌کند)
from app.routers.pages import STATIC_V  # noqa: E402
templates.env.globals["static_v"] = STATIC_V

_ROLES = {"admin", "support", "member"}
_TIERS = {"free", "pro", "vip"}


def _staff(request: Request) -> dict[str, Any] | None:
    u = current_user(request)
    if u and (u.get("role") or "member") in ("admin", "support"):
        return u
    return None


def _is_admin(u: dict[str, Any] | None) -> bool:
    return bool(u and (u.get("role") or "member") == "admin")


def _deny(msg: str = "دسترسی غیرمجاز.", status: int = 403) -> JSONResponse:
    return JSONResponse({"error": msg}, status_code=status)


def _ctx(request: Request, active: str, user: dict[str, Any]) -> dict:
    return {
        "request": request,
        "brand_fa": settings.app_brand_fa,
        "title_fa": "پنل مدیریت",
        "subtitle_fa": "مدیریت کاربران و اشتراک‌ها",
        "active": active,
        "account_name": account_display_name(request),
        "me": {"name": user.get("name"), "role": user.get("role"),
               "is_admin": _is_admin(user)},
    }


# ───────────────────────── صفحه ─────────────────────────
@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    user = _staff(request)
    if not user:
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("admin.html", _ctx(request, "admin", user))


# ───────────────────────── فهرست کاربران ─────────────────────────
def _user_row(u: dict[str, Any], can_see_pw: bool) -> dict[str, Any]:
    pw = crypto_box.decrypt(u.get("password_enc")) if can_see_pw else None
    return {
        "id": u["id"],
        "user_code": u.get("user_code"),
        "username": u.get("username"),
        "first_name": u.get("first_name"),
        "last_name": u.get("last_name"),
        "full_name": u.get("name") or " ".join(
            x for x in (u.get("first_name"), u.get("last_name")) if x) or "",
        "email": u.get("email"),
        "phone": u.get("phone"),
        "role": u.get("role") or "member",
        "subscription": u.get("subscription") or "free",
        "sub_expires_at": u.get("sub_expires_at"),
        "verified": bool(u.get("verified")),
        "asset_count": u.get("asset_count", 0),
        "created_at": u.get("created_at"),
        # رمز فقط برای ادمین؛ اگر کاربر پیش از فعال‌سازی این قابلیت ساخته شده باشد None است
        "password": pw if can_see_pw else None,
    }


@router.get("/api/admin/users")
async def list_users(request: Request):
    user = _staff(request)
    if not user:
        return _deny()
    can_see_pw = _is_admin(user)
    rows = [_user_row(u, can_see_pw) for u in db.list_users()]
    return JSONResponse({"users": rows, "me": {"id": user["id"], "role": user.get("role"),
                                               "is_admin": can_see_pw}})


@router.get("/api/admin/users/{user_id}/assets")
async def user_assets(request: Request, user_id: int):
    if not _staff(request):
        return _deny()
    assets = db.user_assets(user_id)
    return JSONResponse({"assets": assets, "count": len(assets)})


# ───────────────────────── ویرایش کاربر (ادمین) ─────────────────────────
@router.post("/api/admin/users/{user_id}")
async def edit_user(request: Request, user_id: int, payload: dict[str, Any] = Body(...)):
    actor = _staff(request)
    if not actor:
        return _deny()
    if not _is_admin(actor):
        return _deny("فقط ادمین می‌تواند مشخصات کاربر را ویرایش کند.")

    target = db.get_user_by_id(user_id)
    if not target:
        return _deny("کاربر یافت نشد.", 404)

    fields: dict[str, Any] = {}
    if "first_name" in payload:
        fields["first_name"] = (payload.get("first_name") or "").strip() or None
    if "last_name" in payload:
        fields["last_name"] = (payload.get("last_name") or "").strip() or None
    if "first_name" in payload or "last_name" in payload:
        fn = fields.get("first_name", target.get("first_name"))
        ln = fields.get("last_name", target.get("last_name"))
        fields["name"] = " ".join(x for x in (fn, ln) if x) or None

    if "email" in payload:
        email = auth_svc.normalize_email(payload.get("email"))
        if not auth_svc.valid_email(email):
            return _deny("ایمیل نامعتبر است.", 400)
        other = db.get_user_by_email(email)
        if other and other["id"] != user_id:
            return _deny("این ایمیل برای کاربر دیگری ثبت شده است.", 409)
        fields["email"] = email

    if "username" in payload:
        username = auth_svc.normalize_username(payload.get("username"))
        if (err := auth_svc.username_problem(username)):
            return _deny(err, 400)
        other = db.get_user_by_username(username)
        if other and other["id"] != user_id:
            return _deny("این نام کاربری برای کاربر دیگری ثبت شده است.", 409)
        fields["username"] = username

    if "phone" in payload:
        phone = auth_svc.normalize_phone(payload.get("phone"))
        if (err := auth_svc.phone_problem(phone)):
            return _deny(err, 400)
        other = db.get_user_by_phone(phone)
        if other and other["id"] != user_id:
            return _deny("این شماره تماس برای کاربر دیگری ثبت شده است.", 409)
        fields["phone"] = phone

    if "verified" in payload:
        fields["verified"] = 1 if payload.get("verified") else 0

    new_password = payload.get("password")
    if new_password:
        if (err := auth_svc.password_problem(new_password)):
            return _deny(err, 400)
        fields["password_hash"] = auth_svc.hash_password(new_password)
        fields["password_enc"] = crypto_box.encrypt(new_password)

    db.admin_update_user(user_id, fields)
    return JSONResponse({"ok": True})


@router.post("/api/admin/users/{user_id}/role")
async def change_role(request: Request, user_id: int, payload: dict[str, Any] = Body(...)):
    actor = _staff(request)
    if not actor:
        return _deny()
    if not _is_admin(actor):
        return _deny("فقط ادمین می‌تواند نقش کاربر را تغییر دهد.")
    role = (payload.get("role") or "").strip()
    if role not in _ROLES:
        return _deny("نقش نامعتبر است.", 400)
    if user_id == actor["id"] and role != "admin":
        return _deny("نمی‌توانید نقش ادمینِ خودتان را پایین بیاورید.", 400)
    db.set_user_role(user_id, role)
    return JSONResponse({"ok": True, "role": role})


# ───────────────────────── اشتراک (ادمین + پشتیبان) ─────────────────────────
@router.post("/api/admin/users/{user_id}/subscription")
async def manage_subscription(request: Request, user_id: int, payload: dict[str, Any] = Body(...)):
    if not _staff(request):
        return _deny()
    target = db.get_user_by_id(user_id)
    if not target:
        return _deny("کاربر یافت نشد.", 404)

    action = (payload.get("action") or "").strip()
    if action == "upgrade":
        tier = (payload.get("tier") or "pro").strip()
        if tier not in _TIERS:
            return _deny("سطح اشتراک نامعتبر است.", 400)
        exp = db.renew_subscription(user_id, int(payload.get("days") or settings.subscription_renew_days))
        db.set_subscription(user_id, subscription=tier)
        return JSONResponse({"ok": True, "subscription": tier, "sub_expires_at": exp})
    if action == "renew":
        days = int(payload.get("days") or settings.subscription_renew_days)
        exp = db.renew_subscription(user_id, days)
        return JSONResponse({"ok": True, "sub_expires_at": exp})
    if action == "remove":
        db.set_subscription(user_id, subscription="free", sub_expires_at=None)
        return JSONResponse({"ok": True, "subscription": "free", "sub_expires_at": None})
    return _deny("عملیات نامعتبر است.", 400)


# ───────────────────────── حذف کاربر (ادمین) ─────────────────────────
@router.delete("/api/admin/users/{user_id}")
async def remove_user(request: Request, user_id: int):
    actor = _staff(request)
    if not actor:
        return _deny()
    if not _is_admin(actor):
        return _deny("فقط ادمین می‌تواند کاربر را حذف کند.")
    if user_id == actor["id"]:
        return _deny("نمی‌توانید حساب خودتان را حذف کنید.", 400)
    db.delete_user(user_id)
    return JSONResponse({"ok": True})


# ───────────────────────── سبد کاربر (ادمین) ─────────────────────────
@router.get("/admin/user-portfolio/{user_id}", response_class=HTMLResponse)
async def admin_user_portfolio_page(request: Request, user_id: int):
    user = _staff(request)
    if not user:
        return RedirectResponse("/", status_code=302)
    target = db.get_user_by_id(user_id)
    if not target:
        return JSONResponse({"error": "کاربر یافت نشد."}, status_code=404)
    ctx = {
        "request": request,
        "brand_fa": settings.app_brand_fa,
        "title_fa": "مدیریت سرمایه",
        "active": "portfolio",
        "account_name": account_display_name(request),
        "admin_user_id": user_id,
        "admin_user_name": target.get("name") or target.get("email") or f"کاربر {user_id}",
    }
    return templates.TemplateResponse("portfolio_assistant.html", ctx)


@router.get("/api/admin/users/{user_id}/portfolio/value")
async def admin_user_portfolio_value(request: Request, user_id: int):
    if not _staff(request):
        return _deny()
    assets = db.user_assets(user_id)
    valued = await portfolio_valuation.value_portfolio(assets)
    return JSONResponse(valued)


@router.get("/api/admin/users/{user_id}/portfolio/history")
async def admin_user_portfolio_history(request: Request, user_id: int, days: int = 365):
    if not _staff(request):
        return _deny()
    u = db.get_user_by_id(user_id)
    if not u:
        return _deny("کاربر یافت نشد.", 404)
    uid = u.get("uid") or f"u{user_id}"
    history = db.get_portfolio_history(uid, days)
    return JSONResponse({"history": history})


# ───────────────────────── خروجی اکسل ─────────────────────────
_EXPORT_HEADERS = [
    "شناسه کاربری", "نام کاربری", "نام", "نام خانوادگی", "ایمیل",
    "شماره تماس", "نقش", "اشتراک", "انقضای اشتراک", "تأیید ایمیل",
    "تعداد دارایی", "گذرواژه", "تاریخ ثبت‌نام",
]
_ROLE_FA = {"admin": "ادمین", "support": "پشتیبان", "member": "عضو ساده"}
_TIER_FA = {"free": "رایگان", "pro": "حرفه‌ای", "vip": "ویژه"}


@router.post("/api/admin/export")
async def export_users(request: Request, payload: dict[str, Any] = Body(...)):
    actor = _staff(request)
    if not actor:
        return _deny()
    ids = payload.get("ids") or []
    id_set = {int(x) for x in ids} if ids else None
    can_see_pw = _is_admin(actor)

    rows: list[list[object]] = []
    for u in db.list_users():
        if id_set is not None and u["id"] not in id_set:
            continue
        pw = crypto_box.decrypt(u.get("password_enc")) if can_see_pw else None
        rows.append([
            u.get("user_code") or "",
            u.get("username") or "",
            u.get("first_name") or "",
            u.get("last_name") or "",
            u.get("email") or "",
            # شماره تماس به‌صورت متن نوشته می‌شود تا صفرِ ابتدایی حفظ شود
            u.get("phone") or "",
            _ROLE_FA.get(u.get("role") or "member", u.get("role") or ""),
            _TIER_FA.get(u.get("subscription") or "free", u.get("subscription") or ""),
            u.get("sub_expires_at") or "",
            "بله" if u.get("verified") else "خیر",
            u.get("asset_count", 0),
            (pw or "—") if can_see_pw else "—",
            u.get("created_at") or "",
        ])

    data = xlsx.build_xlsx(_EXPORT_HEADERS, rows, sheet_name="Users")
    filename = "cryptosmart-users.xlsx"
    headers = {
        "Content-Disposition": f"attachment; filename=\"{filename}\"; "
                               f"filename*=UTF-8''{quote(filename)}",
    }
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


# ───────────────────────── تصویر روزانهٔ «نمای کلی بازار» ─────────────────────────
@router.post("/api/admin/market-card/send")
async def market_card_send(request: Request):
    """ساخت فوریِ تصویر نمای کلی بازار و ارسالِ نمونه به کانال (فقط ادمین)."""
    u = current_user(request)
    if not _is_admin(u):
        return _deny()
    from app.services import market_card_job
    try:
        res = await market_card_job.generate_and_send()
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": f"{type(e).__name__}: {e}"}, status_code=500)
    return JSONResponse(res, status_code=200 if res.get("ok") else 502)


@router.get("/api/admin/market-card/preview.png")
async def market_card_preview(request: Request):
    """پیش‌نمایش تصویر در مرورگر بدون ارسال به کانال (فقط ادمین)."""
    u = current_user(request)
    if not _is_admin(u):
        return _deny()
    from pathlib import Path
    from app.services import market_card
    out = Path("data/market_card/preview.png")
    try:
        await market_card.render_png(out)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": f"{type(e).__name__}: {e}"}, status_code=500)
    return Response(content=out.read_bytes(), media_type="image/png")
