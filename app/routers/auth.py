"""روتر احراز هویت — JSON API برای ثبت‌نام/ورود/خروج و ورود تلگرام."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session
from app.deps import current_user
from app.models import User
from app.services import auth as auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterIn(BaseModel):
    login: str
    password: str
    display_name: str = ""


class LoginIn(BaseModel):
    login: str
    password: str


class TelegramIn(BaseModel):
    init_data: str


def _public(user: User) -> dict:
    return {
        "id": user.id,
        "display_name": user.display_name,
        "username": user.username,
        "email": user.email,
        "photo_url": user.photo_url,
        "plan": user.plan,
        "is_telegram": user.telegram_id is not None,
    }


@router.post("/register")
async def register(data: RegisterIn, request: Request, session: Session = Depends(get_session)):
    login = data.login.strip()
    if len(login) < 3:
        raise HTTPException(400, "نام کاربری یا ایمیل نامعتبر است.")
    if len(data.password) < 6:
        raise HTTPException(400, "رمز عبور باید حداقل ۶ کاراکتر باشد.")
    if auth_service.get_user_by_login(session, login):
        raise HTTPException(409, "این حساب از قبل وجود دارد.")
    user = auth_service.create_user(session, login=login, password=data.password, display_name=data.display_name)
    request.session["uid"] = user.id
    return _public(user)


@router.post("/login")
async def login(data: LoginIn, request: Request, session: Session = Depends(get_session)):
    user = auth_service.authenticate(session, data.login, data.password)
    if not user:
        raise HTTPException(401, "نام کاربری یا رمز عبور اشتباه است.")
    request.session["uid"] = user.id
    return _public(user)


@router.post("/telegram")
async def telegram(data: TelegramIn, request: Request, session: Session = Depends(get_session)):
    tg = auth_service.verify_telegram_init_data(data.init_data)
    if not tg:
        raise HTTPException(401, "اعتبارسنجی تلگرام ناموفق بود.")
    user = auth_service.get_or_create_telegram_user(session, tg)
    request.session["uid"] = user.id
    return _public(user)


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/me")
async def me(user: User = Depends(current_user)):
    if not user:
        return {"authenticated": False}
    return {"authenticated": True, "user": _public(user)}
