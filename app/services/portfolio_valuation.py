"""
ارزش‌گذاری زندهٔ دارایی‌های پورتفولیو (تومان و دلار).

برای هر دارایی، قیمت لحظه‌ایِ هر واحد را از منابع موجود می‌گیریم و ارزش کل،
سود/زیان نسبت به قیمت خرید و سهم درصدی از کل سبد را محاسبه می‌کنیم.

منابع قیمت:
  • ارز دیجیتال → Toobit (قیمت دلاری) × نرخ دلار (تتر/تومان از Tabdeal)
  • طلای ۱۸ عیار → SourceArena (تومان/گرم)
  • طلای ۲۴ عیار → طلای ۱۸ع ÷ ۰٫۷۵ (تومان/گرم)
  • انس طلا → Yahoo/SourceArena (دلار/اونس) × نرخ دلار
  • تتر/USDT → ۱ دلار × نرخ دلار
  • تومان نقد → خودِ مبلغ
"""
from __future__ import annotations

import asyncio
from typing import Any

from app.services import commodities as commodities_svc
from app.services import sourcearena, tabdeal, toobit

PURITY_24K_FACTOR = 1.0 / 0.75   # تبدیل قیمت ۱۸ع به ۲۴ع


async def _gather_prices() -> dict[str, Any]:
    usdt, metals, comm, pmap = await asyncio.gather(
        _safe(tabdeal.usdt()), _safe(sourcearena.metals()),
        _safe(commodities_svc.commodities()), _safe(toobit.price_map()),
        return_exceptions=False,
    )
    usd_toman = 0.0
    if isinstance(usdt, dict):
        usd_toman = (usdt.get("usdt_irt") or {}).get("price") or 0.0

    gold18_toman = 0.0
    xau_usd = 0.0
    if isinstance(metals, dict):
        gold18_toman = (metals.get("gold_18k") or {}).get("price") or 0.0
        xau_usd = ((metals.get("commodities") or {}).get("XAU") or {}).get("price") or 0.0
    if isinstance(comm, dict):
        xau_usd = (comm.get("commodities") or {}).get("XAU", {}).get("price") or xau_usd

    crypto = pmap.get("prices", {}) if isinstance(pmap, dict) else {}
    return {"usd_toman": usd_toman, "gold18_toman": gold18_toman,
            "xau_usd": xau_usd, "crypto": crypto}


def _unit_price_toman(asset: dict[str, Any], p: dict[str, Any]) -> float:
    """قیمت لحظه‌ای هر واحد دارایی به تومان."""
    kind = asset["kind"]
    usd_toman = p["usd_toman"]
    if kind == "crypto":
        usd = p["crypto"].get((asset["symbol"] or "").upper(), 0.0)
        return usd * usd_toman
    if kind == "usdt":
        return usd_toman
    if kind == "toman":
        return 1.0
    if kind == "gold":
        purity = asset.get("purity")
        if purity == "24":
            return p["gold18_toman"] * PURITY_24K_FACTOR
        if purity == "ounce":
            return p["xau_usd"] * usd_toman
        return p["gold18_toman"]   # پیش‌فرض: ۱۸ عیار
    return 0.0


async def value_portfolio(assets: list[dict[str, Any]]) -> dict[str, Any]:
    """ارزش‌گذاری کامل سبد: هر دارایی + جمع کل (تومان/دلار) + سهم درصدی."""
    p = await _gather_prices()
    usd_toman = p["usd_toman"] or 0.0

    items: list[dict[str, Any]] = []
    total_toman = 0.0
    for a in assets:
        unit_toman = _unit_price_toman(a, p)
        amount = a.get("amount") or 0.0
        value_toman = unit_toman * amount
        total_toman += value_toman
        unit_usd = (unit_toman / usd_toman) if usd_toman else 0.0
        buy = a.get("buy_price") or 0.0
        pnl_pct = round((unit_toman - buy) / buy * 100, 2) if buy else None
        items.append({
            "id": a.get("id"),
            "kind": a["kind"], "symbol": a["symbol"], "name": a["name"],
            "purity": a.get("purity"), "horizon": a.get("horizon"),
            "amount": amount, "buy_price": buy or None,
            "unit_price_toman": round(unit_toman),
            "unit_price_usd": round(unit_usd, 4),
            "value_toman": round(value_toman),
            "value_usd": round(value_toman / usd_toman, 2) if usd_toman else 0.0,
            "pnl_pct": pnl_pct,
        })

    for it in items:
        it["weight"] = round(it["value_toman"] / total_toman * 100, 2) if total_toman else 0.0

    return {
        "items": items,
        "total_toman": round(total_toman),
        "total_usd": round(total_toman / usd_toman, 2) if usd_toman else 0.0,
        "usd_toman": round(usd_toman),
    }


async def _safe(coro):
    try:
        return await coro
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}
