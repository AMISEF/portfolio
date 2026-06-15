"""روتر ژورنال معاملاتی (فاز ۴) — CRUD معاملات + آمار."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.deps import current_user
from app.models import JournalEntry, User
from app.services import journal_stats

router = APIRouter(prefix="/api/journal", tags=["journal"])


class EntryIn(BaseModel):
    pair: str
    side: str = "long"
    entry_price: float
    exit_price: Optional[float] = None
    size: float
    strategy: str = ""
    emotion: str = ""
    note: str = ""


def _require(user: User | None) -> User:
    if not user:
        raise HTTPException(401, "ابتدا وارد حساب کاربری شوید.")
    return user


def _public(e: JournalEntry) -> dict:
    return {
        "id": e.id, "pair": e.pair, "side": e.side,
        "entry_price": e.entry_price, "exit_price": e.exit_price, "size": e.size,
        "pnl": journal_stats.compute_pnl(e), "strategy": e.strategy,
        "emotion": e.emotion, "note": e.note,
        "opened_at": e.opened_at.isoformat() if e.opened_at else None,
        "is_open": e.exit_price is None,
    }


@router.get("/summary")
async def summary(user: User = Depends(current_user), session: Session = Depends(get_session)):
    user = _require(user)
    entries = session.exec(
        select(JournalEntry).where(JournalEntry.user_id == user.id).order_by(JournalEntry.opened_at)
    ).all()
    return {"stats": journal_stats.stats(entries), "entries": [_public(e) for e in reversed(entries)]}


@router.post("/entries")
async def add_entry(data: EntryIn, user: User = Depends(current_user), session: Session = Depends(get_session)):
    user = _require(user)
    e = JournalEntry(
        user_id=user.id, pair=data.pair.upper().strip(), side=data.side,
        entry_price=data.entry_price, exit_price=data.exit_price, size=data.size,
        strategy=data.strategy, emotion=data.emotion, note=data.note,
        closed_at=datetime.utcnow() if data.exit_price is not None else None,
    )
    e.pnl = journal_stats.compute_pnl(e)
    session.add(e)
    session.commit()
    session.refresh(e)
    return {"id": e.id}


@router.delete("/entries/{entry_id}")
async def delete_entry(entry_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
    user = _require(user)
    e = session.get(JournalEntry, entry_id)
    if not e or e.user_id != user.id:
        raise HTTPException(404, "معامله یافت نشد.")
    session.delete(e)
    session.commit()
    return {"ok": True}
