"""
کاتالوگ کامل دارایی‌های قابل‌سرمایه‌گذاری + جدول قیمت مرکزی.

این ماژول همهٔ ابزارهای قابل‌قیمت‌گذاری را یکجا فراهم می‌کند تا هم انتخابگرِ
«افزودن دارایی» و هم ارزش‌گذاری سبد از یک منبع تغذیه شوند:

  • همهٔ ارزهای دیجیتالِ Toobit (جفت‌های USDT) با قیمت دلاری و تغییر ۲۴ساعته
  • طلای ۱۸ و ۲۴ عیار (تومان/گرم)
  • سکه‌های ایرانی: امامی(تمام)، بهار آزادی، نیم، ربع، گرمی
        (قیمت معاملاتیِ شاملِ حباب از SourceArena؛ نبودِ کلید ⇒ تخمین ارزش ذوب)
  • نقره (تومان/گرم) از انس نقره
  • نفت خام (بشکه)
  • تتر (USDT) و تومان نقد

نرخ‌ها از SourceArena (طلا/سکه/نقره/نفت)، Toobit (کریپتو) و Tabdeal (دلار) با
کش داخلی می‌آیند؛ این ماژول فقط آن‌ها را تجمیع و نرمال می‌کند.
"""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.config import settings
from app.services import commodities as commodities_svc
from app.services import sourcearena, tabdeal

GRAMS_PER_OUNCE = 31.1034768
PURITY_24K_FACTOR = 1.0 / 0.75          # ۱۸ع ⇒ ۲۴ع

# مشخصات سکه‌ها: گرمِ طلای خالص (برای تخمین ارزش ذوب وقتی قیمت زنده نباشد).
# سکه‌های ایرانی عیار ۰٫۹۰۰ هستند (تمام = ۸٫۱۳۳ گرم ناخالص).
COIN_SPECS: dict[str, dict[str, Any]] = {
    "emami":   {"name": "سکه امامی (تمام)", "pure_g": 7.3224, "group": "coin"},
    "bahar":   {"name": "سکه بهار آزادی",   "pure_g": 7.3224, "group": "coin"},
    "half":    {"name": "نیم سکه",          "pure_g": 3.6598, "group": "coin"},
    "quarter": {"name": "ربع سکه",          "pure_g": 1.8299, "group": "coin"},
    "gram":    {"name": "سکه گرمی",         "pure_g": 0.9000, "group": "coin"},
}

# نام فارسی چند ارز پرتکرار (بقیه با نماد نمایش داده می‌شوند).
_CRYPTO_NAMES = {
    "BTC": "بیت‌کوین", "ETH": "اتریوم", "USDT": "تتر", "BNB": "بایننس کوین",
    "SOL": "سولانا", "XRP": "ریپل", "ADA": "کاردانو", "DOGE": "دوج‌کوین",
    "TRX": "ترون", "TON": "تون‌کوین", "AVAX": "آوالانچ", "LINK": "چین‌لینک",
    "DOT": "پولکادات", "MATIC": "پالیگان", "LTC": "لایت‌کوین", "SHIB": "شیبا",
    "PEPE": "پپه", "SUI": "سویی", "BCH": "بیت‌کوین کش", "NEAR": "نییر",
}

_STABLES = {"USDT", "USDC", "DAI", "FDUSD", "TUSD", "BUSD", "USDD", "USDP"}


# ───────────────────────── جدول قیمت مرکزی ─────────────────────────
async def get_price_table() -> dict[str, Any]:
    """همهٔ قیمت‌های واحد به تومان/دلار + تغییر ۲۴ساعته، در یک ساختار."""
    crypto, metals, comm, usdt = await asyncio.gather(
        _crypto_tickers(), _safe(sourcearena.metals()),
        _safe(commodities_svc.commodities()), _safe(tabdeal.usdt()),
    )

    usd_toman = 0.0
    if isinstance(usdt, dict):
        irt = usdt.get("usdt_irt") or {}
        usd_toman = irt.get("price") or 0.0
    if not usd_toman and isinstance(metals, dict):
        usd_toman = metals.get("usd_toman") or 0.0

    gold18 = xau_usd = xag_usd = oil_usd = 0.0
    gold18_chg = xau_chg = xag_chg = oil_chg = usd_chg = 0.0
    sa_usd_toman = 0.0          # دلار نقدی/آزاد از SourceArena (اسکناس)
    coins_raw: dict[str, float] = {}
    if isinstance(metals, dict):
        g = metals.get("gold_18k") or {}
        gold18 = g.get("price") or 0.0
        gold18_chg = g.get("change_24h") or 0.0
        usd_chg = metals.get("usd_change_24h") or 0.0
        sa_usd_toman = metals.get("usd_toman") or 0.0
        coins_raw = metals.get("coins") or {}
        cm = metals.get("commodities") or {}
        xau_usd = (cm.get("XAU") or {}).get("price") or 0.0
        xau_chg = (cm.get("XAU") or {}).get("change_24h") or 0.0
        xag_usd = (cm.get("XAG") or {}).get("price") or 0.0
        xag_chg = (cm.get("XAG") or {}).get("change_24h") or 0.0
        oil_usd = (cm.get("OIL") or {}).get("price") or 0.0
        oil_chg = (cm.get("OIL") or {}).get("change_24h") or 0.0
    # تغییر ۳۰روزه از سری یک‌ماههٔ Yahoo (close ابتدا تا انتها)
    xau_chg30 = xag_chg30 = oil_chg30 = None
    if isinstance(comm, dict):
        cc = comm.get("commodities") or {}
        xau_usd = (cc.get("XAU") or {}).get("price") or xau_usd
        xag_usd = (cc.get("XAG") or {}).get("price") or xag_usd
        oil_usd = (cc.get("OIL") or {}).get("price") or oil_usd
        xau_chg30 = _chg30(cc.get("XAU"))
        xag_chg30 = _chg30(cc.get("XAG"))
        oil_chg30 = _chg30(cc.get("OIL"))

    gold24 = gold18 * PURITY_24K_FACTOR
    silver_gram = (xag_usd / GRAMS_PER_OUNCE * usd_toman) if (xag_usd and usd_toman) else 0.0

    metals_tbl: dict[str, dict[str, Any]] = {}
    metals_tbl["gold18"] = _row("طلای ۱۸ عیار", "هر گرم", gold18, usd_toman, gold18_chg, "gold", xau_chg30)
    metals_tbl["gold24"] = _row("طلای ۲۴ عیار", "هر گرم", gold24, usd_toman, gold18_chg, "gold", xau_chg30)
    metals_tbl["silver"] = _row("نقره", "هر گرم", silver_gram, usd_toman, xag_chg, "silver", xag_chg30)
    if oil_usd and usd_toman:
        metals_tbl["oil"] = _row("نفت خام", "بشکه", oil_usd * usd_toman, usd_toman, oil_chg, "oil", oil_chg30)
    metals_tbl["usdt"] = _row("تتر (USDT)", "USDT", usd_toman, usd_toman, usd_chg, "cash")
    metals_tbl["toman"] = _row("تومان نقد", "نقد", 1.0, usd_toman, 0.0, "cash")
    # دلار نقدی (اسکناس) از SourceArena؛ نبودِ منبع ⇒ همان نرخ تتر
    usd_cash_toman = sa_usd_toman or usd_toman
    metals_tbl["usd_cash"] = _row("دلار نقدی", "اسکناس", usd_cash_toman, usd_toman, usd_chg, "cash")

    # سکه‌ها: قیمت زنده (با حباب) از SourceArena؛ نبود ⇒ ارزش ذوب از طلای ۲۴ع.
    for kind, spec in COIN_SPECS.items():
        live = coins_raw.get(kind) or 0.0
        melt = spec["pure_g"] * gold24
        price = live or melt
        row = _row(spec["name"], "عدد", price, usd_toman, gold18_chg, "coin", xau_chg30)
        row["estimated"] = not bool(live)        # True یعنی از ارزش ذوب تخمین زده شده
        metals_tbl[f"coin_{kind}"] = row

    return {"usd_toman": round(usd_toman), "crypto": crypto, "metals": metals_tbl}


async def price_table() -> dict[str, Any]:
    from app.cache import cached
    return await cached("instruments:price_table", 15, get_price_table,
                        lambda: {"usd_toman": 0, "crypto": {}, "metals": {}})


# ───────────────────────── کاتالوگ برای انتخابگر ─────────────────────────
async def catalog() -> dict[str, Any]:
    """فهرست تخت همهٔ ابزارها برای جستجو در «افزودن دارایی»."""
    t = await price_table()
    usd_toman = t["usd_toman"] or 0.0
    out: list[dict[str, Any]] = []

    # فلزات/سکه/نفت/تتر
    for iid, row in t["metals"].items():
        kind, purity, symbol = _decode_id(iid)
        out.append({
            "id": iid, "kind": kind, "purity": purity, "symbol": symbol,
            "name": row["name"], "sub": row["sub"], "group": row["group"],
            "price_toman": row["price_toman"], "price_usd": row["price_usd"],
            "change_24h": row["change_24h"], "estimated": row.get("estimated", False),
        })

    # کریپتو (همهٔ ارزهای Toobit)
    for sym, c in sorted(t["crypto"].items(), key=lambda kv: kv[1].get("volume", 0), reverse=True):
        usd = c.get("price_usd") or 0.0
        out.append({
            "id": f"crypto:{sym}", "kind": "crypto", "purity": None, "symbol": sym,
            "name": _CRYPTO_NAMES.get(sym, sym), "sub": sym, "group": "crypto",
            "price_toman": round(usd * usd_toman) if usd_toman else 0,
            "price_usd": usd, "change_24h": c.get("change_24h"), "estimated": False,
        })

    return {"usd_toman": round(usd_toman), "count": len(out), "instruments": out}


# ───────────────────────── قیمت واحدِ یک دارایی ─────────────────────────
def unit_price_toman(kind: str, symbol: str | None, purity: str | None,
                     table: dict[str, Any]) -> float:
    """قیمت لحظه‌ای هر واحد دارایی به تومان (برای ارزش‌گذاری)."""
    usd_toman = table.get("usd_toman") or 0.0
    metals = table.get("metals") or {}
    if kind == "crypto":
        c = (table.get("crypto") or {}).get((symbol or "").upper()) or {}
        return (c.get("price_usd") or 0.0) * usd_toman
    if kind == "usdt":
        return usd_toman
    if kind == "usd_cash":
        return (metals.get("usd_cash") or {}).get("price_toman", 0.0)
    if kind == "toman":
        return 1.0
    if kind == "gold":
        key = "gold24" if purity == "24" else "gold18"
        return (metals.get(key) or {}).get("price_toman", 0.0)
    if kind == "coin":
        return (metals.get(f"coin_{purity}") or {}).get("price_toman", 0.0)
    if kind == "silver":
        return (metals.get("silver") or {}).get("price_toman", 0.0)
    if kind == "oil":
        return (metals.get("oil") or {}).get("price_toman", 0.0)
    return 0.0


def change_24h_for(kind: str, symbol: str | None, purity: str | None,
                   table: dict[str, Any]) -> float | None:
    if kind == "crypto":
        c = (table.get("crypto") or {}).get((symbol or "").upper()) or {}
        return c.get("change_24h")
    iid = _encode_id(kind, purity)
    row = (table.get("metals") or {}).get(iid)
    return row.get("change_24h") if row else None


def change_30d_for(kind: str, symbol: str | None, purity: str | None,
                   table: dict[str, Any]) -> float | None:
    """تغییر ۳۰روزهٔ دارایی‌های غیر‌کریپتو (طلا/نقره/نفت/سکه) از جدول مرکزی."""
    if kind == "crypto":
        return None
    iid = _encode_id(kind, purity)
    row = (table.get("metals") or {}).get(iid)
    return row.get("change_30d") if row else None


# ───────────────────────── کمکی‌ها ─────────────────────────
async def _crypto_tickers() -> dict[str, dict[str, Any]]:
    """همهٔ جفت‌های USDT توبیت: نماد ⇒ {price_usd, change_24h, volume}."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.http_timeout)) as client:
            r = await client.get(f"{settings.toobit_base_url}/quote/v1/ticker/24hr")
            r.raise_for_status()
            data = r.json()
    except Exception:  # noqa: BLE001
        return {}
    out: dict[str, dict[str, Any]] = {}
    for t in (data if isinstance(data, list) else []):
        sym = (t.get("s") or t.get("symbol") or "").upper()
        if not sym.endswith("USDT"):
            continue
        base = sym[:-4]
        price = _f(t, "c", "lastPrice", "close")
        if price <= 0:
            continue
        chg = _f(t, "pcp", "priceChangePercent", "P")
        out[base] = {
            "price_usd": price,
            "change_24h": round(chg * 100 if abs(chg) < 1 else chg, 2),
            "volume": _f(t, "qv", "quoteVolume", "q"),
        }
    return out


def _row(name: str, sub: str, price_toman: float, usd_toman: float,
         chg: float | None, group: str, chg30: float | None = None) -> dict[str, Any]:
    return {
        "name": name, "sub": sub, "group": group,
        "price_toman": round(price_toman) if price_toman else 0,
        "price_usd": round(price_toman / usd_toman, 4) if (price_toman and usd_toman) else 0.0,
        "change_24h": round(chg, 2) if chg is not None else None,
        "change_30d": round(chg30, 2) if chg30 is not None else None,
    }


def _chg30(item: dict[str, Any] | None) -> float | None:
    """درصد تغییر ۳۰روزه از سری روزانهٔ یک‌ماهه (spark): (آخر − اول) / اول."""
    sp = (item or {}).get("spark") or []
    if len(sp) >= 2 and sp[0]:
        return round((sp[-1] - sp[0]) / sp[0] * 100, 2)
    return None


def _encode_id(kind: str, purity: str | None) -> str:
    if kind == "gold":
        return "gold24" if purity == "24" else "gold18"
    if kind == "coin":
        return f"coin_{purity}"
    return kind          # silver | oil | usdt | toman


def _decode_id(iid: str) -> tuple[str, str | None, str]:
    """شناسهٔ کاتالوگ ⇒ (kind, purity, symbol) برای ذخیره در assets."""
    if iid == "gold18":
        return "gold", "18", "GOLD18"
    if iid == "gold24":
        return "gold", "24", "GOLD24"
    if iid.startswith("coin_"):
        return "coin", iid[5:], iid.upper()
    if iid in ("silver", "oil", "usdt", "toman", "usd_cash"):
        return iid, None, iid.upper()
    return iid, None, iid.upper()


async def _safe(coro):
    try:
        return await coro
    except Exception:  # noqa: BLE001
        return {}


def _f(d: dict, *keys: str) -> float:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                continue
    return 0.0
