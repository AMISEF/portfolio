"""وابستگی‌های مشترک FastAPI."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Request
from sqlmodel import Session

from app.db import get_session
from app.models import User


def current_user(request: Request, session: Session = Depends(get_session)) -> Optional[User]:
    """کاربر واردشده از روی نشست کوکی (یا None)."""
    uid = request.session.get("uid")
    if not uid:
        return None
    return session.get(User, uid)
