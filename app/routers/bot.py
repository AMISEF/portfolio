"""اندپوینت‌های ربات تلگرام «الگو هاب» و هشدارهای قیمتِ خرید.

  • POST /api/bot/algohub/webhook — وب‌هوک تلگرام (اتصال حساب + دکمه‌های اشتراک)
  • GET  /api/bot/link            — وضعیت اتصال + لینکِ deep-link ربات
  • POST /api/bot/unlink          — قطعِ اتصال
  • GET/POST/DELETE /api/alerts   — مدیریتِ هشدارهای قیمتِ خرید
"""
from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from app import db
from app.config import settings
from app.routers.auth import current_user
from app.services import algohub_bot

router = APIRouter()

_HORIZONS = {"short", "mid", "long"}


def _401() -> JSONResponse:
    return JSONResponse({"error": "برای این کار باید وارد حساب خود شوید."},
                        status_code=401)


# ───────────────────────── وب‌هوک تلگرام ─────────────────────────
@router.post("/api/bot/algohub/webhook")
async def algohub_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    """وب‌هوکِ ربات الگو هاب. مثل ربات سیگنال‌ها با هدرِ secret تأیید می‌شود و
    همیشه ۲۰۰ برمی‌گرداند تا تلگرام آپدیت را دوباره صف نکند."""
    expected = settings.signals_webhook_secret_effective
    if not (x_telegram_bot_api_secret_token
            and hmac.compare_digest(x_telegram_bot_api_secret_token, expected)):
        return JSONResponse({"ok": False}, status_code=403)
    try:
        update = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse({"ok": True})
    try:
        await algohub_bot.process_update(update)
    except Exception:  # noqa: BLE001
        pass
    return JSONResponse({"ok": True})


# ───────────────────────── اتصالِ حساب به ربات ─────────────────────────
@router.get("/api/bot/link")
async def bot_link(request: Request):
    """وضعیتِ اتصالِ کاربر + لینکی که با زدنش حساب به ربات وصل می‌شود."""
    user = current_user(request)
    if not user:
        return _401()
    uid = int(user["id"])
    chat_id = db.tg_chat_id(uid)
    if chat_id:
        return JSONResponse({"linked": True, "bot_url": settings.algohub_bot_url,
                             "enabled": algohub_bot.is_enabled()})
    token = algohub_bot.new_link_token(uid)
    return JSONResponse({
        "linked": False,
        "link_url": algohub_bot.link_url(token),
        "bot_url": settings.algohub_bot_url,
        "enabled": algohub_bot.is_enabled(),
    })


@router.post("/api/bot/unlink")
async def bot_unlink(request: Request):
    user = current_user(request)
    if not user:
        return _401()
    db.tg_unlink(int(user["id"]))
    return JSONResponse({"ok": True, "linked": False})


# ───────────────────────── هشدارهای قیمتِ خرید ─────────────────────────
@router.get("/api/alerts")
async def list_alerts(request: Request):
    user = current_user(request)
    if not user:
        return _401()
    uid = int(user["id"])
    return JSONResponse({
        "alerts": db.alerts_list(uid),
        "linked": bool(db.tg_chat_id(uid)),
        "enabled": algohub_bot.is_enabled(),
    })


@router.post("/api/alerts")
async def save_alert(request: Request):
    """ثبت/به‌روزرسانیِ هشدارِ یک ارز (یا غیرفعال‌کردنِ آن با active=false)."""
    user = current_user(request)
    if not user:
        return _401()
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        body = {}

    symbol = str(body.get("symbol") or "").strip().upper()
    if not symbol:
        return JSONResponse({"error": "نماد ارز مشخص نشده است."}, status_code=400)
    horizon = str(body.get("horizon") or "short").strip()
    if horizon not in _HORIZONS:
        horizon = "short"
    try:
        target = float(body.get("target_price") or 0)
    except (TypeError, ValueError):
        target = 0.0
    if target <= 0:
        return JSONResponse({"error": "قیمت هدف باید عددی بزرگ‌تر از صفر باشد."},
                            status_code=400)

    active = bool(body.get("active", True))
    name = (body.get("name") or None)
    uid = int(user["id"])
    db.alert_upsert(uid, symbol, horizon, target, name=name, active=active)
    return JSONResponse({"ok": True, "alerts": db.alerts_list(uid),
                         "linked": bool(db.tg_chat_id(uid))})


@router.delete("/api/alerts/{alert_id}")
async def delete_alert(alert_id: int, request: Request):
    user = current_user(request)
    if not user:
        return _401()
    uid = int(user["id"])
    db.alert_delete(uid, alert_id)
    return JSONResponse({"ok": True, "alerts": db.alerts_list(uid)})
