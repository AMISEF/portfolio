"""
روتر پورتفولیو (فاز ۲) — CRUD دارایی‌ها + ارزش‌گذاری لحظه‌ای، سود/زیان و تخصیص.

محاسبات عددی همگی در سرور انجام می‌شوند (طبق اصل پروپوزال: مدل هوش مصنوعی
فقط تفسیر می‌کند، نه محاسبهٔ عدد).
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.deps import current_user
from app.models import Holding, User
from app.services import prices, risk

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class HoldingIn(BaseModel):
    symbol: str
    amount: float
    avg_buy_price: float = 0.0
    note: str = ""


def _require(user: User | None) -> User:
    if not user:
        raise HTTPException(401, "ابتدا وارد حساب کاربری شوید.")
    return user


@router.get("/summary")
async def summary(user: User = Depends(current_user), session: Session = Depends(get_session)):
    user = _require(user)
    holdings = session.exec(select(Holding).where(Holding.user_id == user.id)).all()
    pm = await prices.price_map()
    toman = await prices.usdt_toman()

    items = []
    total_value = total_cost = 0.0
    for h in holdings:
        info = pm.get(h.symbol.upper(), {})
        price = float(info.get("price", 0.0))
        value = price * h.amount
        cost = h.avg_buy_price * h.amount
        pnl = value - cost
        pnl_pct = (pnl / cost * 100) if cost else 0.0
        total_value += value
        total_cost += cost
        items.append({
            "id": h.id, "symbol": h.symbol.upper(), "name": info.get("name", h.symbol),
            "icon": info.get("icon", ""), "amount": h.amount, "avg_buy_price": h.avg_buy_price,
            "price": price, "change_24h": info.get("change_24h", 0.0),
            "value": value, "cost": cost, "pnl": pnl, "pnl_pct": pnl_pct, "note": h.note,
        })

    # درصد تخصیص هر دارایی
    for it in items:
        it["allocation"] = (it["value"] / total_value * 100) if total_value else 0.0
    items.sort(key=lambda x: x["value"], reverse=True)

    total_pnl = total_value - total_cost
    return {
        "totals": {
            "value_usd": total_value,
            "cost_usd": total_cost,
            "pnl_usd": total_pnl,
            "pnl_pct": (total_pnl / total_cost * 100) if total_cost else 0.0,
            "value_toman": total_value * toman if toman else 0.0,
            "usdt_toman": toman,
            "count": len(items),
        },
        "holdings": items,
        "risk": risk.analyze(items, total_value),
    }


@router.post("/holdings")
async def add_holding(data: HoldingIn, user: User = Depends(current_user), session: Session = Depends(get_session)):
    user = _require(user)
    if data.amount <= 0:
        raise HTTPException(400, "مقدار باید بزرگ‌تر از صفر باشد.")
    h = Holding(
        user_id=user.id, symbol=data.symbol.upper().strip(),
        amount=data.amount, avg_buy_price=max(data.avg_buy_price, 0.0), note=data.note,
    )
    session.add(h)
    session.commit()
    session.refresh(h)
    return {"id": h.id}


@router.put("/holdings/{holding_id}")
async def update_holding(holding_id: int, data: HoldingIn, user: User = Depends(current_user), session: Session = Depends(get_session)):
    user = _require(user)
    h = session.get(Holding, holding_id)
    if not h or h.user_id != user.id:
        raise HTTPException(404, "دارایی یافت نشد.")
    h.symbol = data.symbol.upper().strip()
    h.amount = data.amount
    h.avg_buy_price = max(data.avg_buy_price, 0.0)
    h.note = data.note
    h.updated_at = datetime.utcnow()
    session.add(h)
    session.commit()
    return {"ok": True}


@router.delete("/holdings/{holding_id}")
async def delete_holding(holding_id: int, user: User = Depends(current_user), session: Session = Depends(get_session)):
    user = _require(user)
    h = session.get(Holding, holding_id)
    if not h or h.user_id != user.id:
        raise HTTPException(404, "دارایی یافت نشد.")
    session.delete(h)
    session.commit()
    return {"ok": True}
