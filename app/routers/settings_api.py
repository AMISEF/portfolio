"""تنظیماتِ حسابِ کاربر: تغییر رمز عبور و اتصال به API اسپاتِ توبیت.

API:
  POST   /api/settings/password/code   → ارسال کد تأیید به ایمیلِ خودِ کاربر
  POST   /api/settings/password        {code, password} → تنظیم رمز جدید
  GET    /api/settings/toobit          → وضعیت اتصال (بدون افشای کلیدها)
  POST   /api/settings/toobit          {api_key, secret_key} → اعتبارسنجی و ذخیره
  DELETE /api/settings/toobit          → حذف کلیدها
  POST   /api/settings/toobit/sync     → واردکردن/به‌روزرسانی داراییِ اسپات
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from app import db
from app.config import settings
from app.routers.auth import current_user
from app.services import auth as auth_svc, crypto_box, mailer, toobit_sync

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _err(msg: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": msg}, status_code=status)


def _401() -> JSONResponse:
    return _err("برای این کار باید وارد حساب خود شوید.", 401)


def _mask(value: str | None) -> str:
    """نمایشِ امنِ کلید: فقط چند کاراکترِ ابتدا و انتها."""
    v = value or ""
    if len(v) <= 8:
        return "••••"
    return f"{v[:4]}••••{v[-4:]}"


# ───────────────────────── تغییر رمز عبور ─────────────────────────
@router.post("/password/code")
async def send_password_code(request: Request):
    """ارسالِ کدِ تأیید به ایمیلِ ثبت‌شدهٔ خودِ کاربر (نه ایمیلِ دلخواه)."""
    user = current_user(request)
    if not user:
        return _401()
    email = user["email"]
    # از همان جریانِ «reset» استفاده می‌شود تا محدودیتِ زمانی و انقضا یکسان بماند.
    from app.routers.auth import _send_code
    try:
        if (msg := await _send_code(email, "reset")):
            return _err(msg, 429)
    except mailer.MailNotConfigured:
        return _err("سرویس ایمیل هنوز روی سرور پیکربندی نشده است.", 503)
    except Exception:  # noqa: BLE001
        return _err("ارسال ایمیل ناموفق بود. لطفاً بعداً تلاش کنید.", 502)
    return JSONResponse({"ok": True, "email": email})


@router.post("/password")
async def change_password(request: Request, payload: dict[str, Any] = Body(...)):
    user = current_user(request)
    if not user:
        return _401()
    code = (payload.get("code") or "").strip()
    password = payload.get("password") or ""
    if (pw_err := auth_svc.password_problem(password)):
        return _err(pw_err)

    email = user["email"]
    active = db.get_active_code(email, "reset")
    if not active:
        return _err("کد منقضی شده یا یافت نشد. لطفاً کد جدید بخواهید.", 410)
    if active["attempts"] >= settings.auth_code_max_attempts:
        return _err("تعداد تلاش‌ها بیش از حد مجاز است. کد جدید بخواهید.", 429)
    if not auth_svc.verify_code(code, active["code_hash"]):
        left = settings.auth_code_max_attempts - db.bump_code_attempts(int(active["id"]))
        return _err(f"کد نادرست است. {max(left, 0)} تلاش باقی مانده.", 401)

    db.consume_code(int(active["id"]))
    db.update_user_password(int(user["id"]), auth_svc.hash_password(password),
                            crypto_box.encrypt(password))
    return JSONResponse({"ok": True})


# ───────────────────────── API توبیت (اسپات) ─────────────────────────
@router.get("/toobit")
async def toobit_status(request: Request):
    user = current_user(request)
    if not user:
        return _401()
    row = db.toobit_keys_get(int(user["id"]))
    if not row:
        return JSONResponse({"connected": False})
    return JSONResponse({
        "connected": True,
        "api_key_masked": _mask(crypto_box.decrypt(row.get("api_key_enc"))),
        "synced_at": row.get("synced_at"),
        "sync_error": row.get("sync_error"),
    })


@router.post("/toobit")
async def toobit_save(request: Request, payload: dict[str, Any] = Body(...)):
    """اعتبارسنجیِ کلید با یک فراخوانیِ خواندنی، سپس ذخیرهٔ رمزگذاری‌شده."""
    user = current_user(request)
    if not user:
        return _401()
    api_key = (payload.get("api_key") or "").strip()
    secret = (payload.get("secret_key") or "").strip()
    if not api_key or not secret:
        return _err("هر دو مقدارِ Access Key و Secret Key لازم است.")

    ok, err = await toobit_sync.verify(api_key, secret)
    if not ok:
        return _err(f"اتصال به توبیت برقرار نشد: {err}")

    db.toobit_keys_set(int(user["id"]), crypto_box.encrypt(api_key),
                       crypto_box.encrypt(secret))
    return JSONResponse({"ok": True, "connected": True,
                         "api_key_masked": _mask(api_key)})


@router.delete("/toobit")
async def toobit_delete(request: Request):
    user = current_user(request)
    if not user:
        return _401()
    db.toobit_keys_delete(int(user["id"]))
    return JSONResponse({"ok": True, "connected": False})


@router.post("/toobit/sync")
async def toobit_sync_now(request: Request):
    user = current_user(request)
    if not user:
        return _401()
    uid = user.get("uid") or f"u{user['id']}"
    result = await toobit_sync.sync_user(int(user["id"]), uid)
    if not result.get("ok"):
        return _err(result.get("error") or "همگام‌سازی ناموفق بود.", 502)
    return JSONResponse(result)
