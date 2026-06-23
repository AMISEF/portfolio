"""
ارزش‌گذاری زندهٔ دارایی‌های پورتفولیو (تومان و دلار) + تغییر ۲۴ساعته و ۳۰روزه.

قیمت‌های واحد از جدول قیمت مرکزی (app.services.instruments) می‌آیند که همهٔ
ابزارها را پوشش می‌دهد: ارزهای Toobit، طلای ۱۸/۲۴، سکه‌ها، نقره، نفت، تتر و
تومان. این ماژول فقط ارزش‌گذاری سبدِ کاربر و محاسبهٔ سود/زیان و سهم درصدی را
انجام می‌دهد.
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.config import settings
from app.services import instruments


async def value_portfolio(assets: list[dict[str, Any]]) -> dict[str, Any]:
    """ارزش‌گذاری کامل سبد: هر دارایی + جمع کل (تومان/دلار) + سهم درصدی."""
    table = await instruments.price_table()
    usd_toman = table.get("usd_toman") or 0.0

    # تغییر ۳۰روزهٔ ارزهای موجود در سبد (یک‌بار، کش‌شده)
    crypto_syms = sorted({(a.get("symbol") or "").upper() for a in assets
                          if a.get("kind") == "crypto"})
    chg30 = await _changes_30d(crypto_syms) if crypto_syms else {}

    items: list[dict[str, Any]] = []
    total_toman = 0.0
    for a in assets:
        kind = a.get("kind")
        symbol = a.get("symbol")
        purity = a.get("purity")
        unit_toman = instruments.unit_price_toman(kind, symbol, purity, table)
        amount = a.get("amount") or 0.0
        value_toman = unit_toman * amount
        total_toman += value_toman
        unit_usd = (unit_toman / usd_toman) if usd_toman else 0.0
        buy = a.get("buy_price") or 0.0
        pnl_pct = round((unit_toman - buy) / buy * 100, 2) if buy else None
        items.append({
            "id": a.get("id"),
            "kind": kind, "symbol": symbol, "name": a.get("name"),
            "purity": purity, "horizon": a.get("horizon"),
            "group": _group(kind),
            "amount": amount, "buy_price": buy or None,
            "unit_price_toman": round(unit_toman),
            "unit_price_usd": round(unit_usd, 4),
            "value_toman": round(value_toman),
            "value_usd": round(value_toman / usd_toman, 2) if usd_toman else 0.0,
            "pnl_pct": pnl_pct,
            "change_24h": instruments.change_24h_for(kind, symbol, purity, table),
            "change_30d": chg30.get((symbol or "").upper()) if kind == "crypto" else None,
        })

    for it in items:
        it["weight"] = round(it["value_toman"] / total_toman * 100, 2) if total_toman else 0.0

    return {
        "items": items,
        "total_toman": round(total_toman),
        "total_usd": round(total_toman / usd_toman, 2) if usd_toman else 0.0,
        "usd_toman": round(usd_toman),
    }


def _group(kind: str | None) -> str:
    return {"crypto": "crypto", "gold": "gold", "coin": "coin", "silver": "silver",
            "oil": "oil", "usdt": "cash", "toman": "cash"}.get(kind or "", "other")


async def _changes_30d(symbols: list[str]) -> dict[str, float]:
    """تغییر ۳۰روزهٔ هر نماد از کندل روزانهٔ Toobit (کش‌شده ۱۰ دقیقه)."""
    from app.cache import cache
    key = "pf:chg30:" + ",".join(symbols)
    hit = cache.get(key)
    if isinstance(hit, dict):
        return hit
    out: dict[str, float] = {}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.http_timeout)) as client:
            sem = asyncio.Semaphore(6)

            async def _one(sym: str):
                async with sem:
                    try:
                        r = await client.get(
                            f"{settings.toobit_base_url}/quote/v1/klines",
                            params={"symbol": sym + "USDT", "interval": "1d", "limit": "31"})
                        r.raise_for_status()
                        rows = r.json()
                    except Exception:  # noqa: BLE001
                        return
                    closes = [float(k[4]) for k in rows if isinstance(k, list) and len(k) >= 5]
                    if len(closes) >= 2 and closes[0] > 0:
                        out[sym] = round((closes[-1] - closes[0]) / closes[0] * 100, 2)

            await asyncio.gather(*[_one(s) for s in symbols])
    except Exception:  # noqa: BLE001
        pass
    cache.set(key, out, 600)
    return out
