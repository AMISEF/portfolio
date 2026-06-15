"""
محاسبهٔ آمار ژورنال معاملاتی (همگی در سرور — طبق اصل پروپوزال).

شاخص‌ها: نرخ برد، تعداد معاملات، فاکتور سود، میانگین سود/زیان،
نسبت ریسک به ریوارد میانگین، بیشترین افت سرمایه (Drawdown) و منحنی سرمایه.
"""
from __future__ import annotations

from typing import Any

from app.models import JournalEntry


def compute_pnl(entry: JournalEntry) -> float | None:
    """سود/زیان یک معامله. اگر کاربر pnl داده باشد همان؛ وگرنه از قیمت‌ها."""
    if entry.exit_price is None:
        return entry.pnl
    direction = 1 if (entry.side or "long").lower() == "long" else -1
    return (entry.exit_price - entry.entry_price) * entry.size * direction


def stats(entries: list[JournalEntry]) -> dict[str, Any]:
    closed = []
    for e in entries:
        p = compute_pnl(e)
        if p is not None:
            closed.append(p)

    n = len(closed)
    wins = [p for p in closed if p > 0]
    losses = [p for p in closed if p < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    total_pnl = sum(closed)

    # منحنی سرمایه + بیشترین افت
    equity, peak, max_dd = [], 0.0, 0.0
    cum = 0.0
    for p in closed:
        cum += p
        equity.append(round(cum, 2))
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)

    avg_win = (gross_profit / len(wins)) if wins else 0.0
    avg_loss = (gross_loss / len(losses)) if losses else 0.0

    return {
        "total_trades": n,
        "open_trades": len(entries) - n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": (len(wins) / n * 100) if n else 0.0,
        "total_pnl": total_pnl,
        "profit_factor": (gross_profit / gross_loss) if gross_loss else (gross_profit if gross_profit else 0.0),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "avg_rr": (avg_win / avg_loss) if avg_loss else 0.0,
        "best": max(closed) if closed else 0.0,
        "worst": min(closed) if closed else 0.0,
        "max_drawdown": max_dd,
        "equity_curve": equity,
    }
