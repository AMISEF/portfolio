"""
سرویس SourceArena — طلا و فلزات گران‌بها.

پاسخ این API یک شیء تخت (dict) است که مقادیر آن به «تومان» هستند (تأییدشده:
usd ≈ ۱۶۰٬۵۰۰ تومان). از این پاسخ استخراج می‌کنیم:
  • 18ayar      → طلای ۱۸ عیار هر گرم (تومان) — بدون هیچ تبدیلی
  • usd_xau     → انس طلای جهانی (دلار)
  • xag         → انس نقره (تومان) → با نرخ دلار به دلار تبدیل می‌شود
  • usd         → نرخ دلار آزاد (تومان) برای تبدیل نقره

طبق درخواست، فقط هر نیم ساعت یک‌بار به‌روزرسانی می‌شود (TTL = ۱۸۰۰).
برای دسترسی از سرور خارج از ایران از پراکسی sa.resicard.ir استفاده می‌شود.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.services import mock_data


async def get_metals() -> dict[str, Any]:
    timeout = httpx.Timeout(settings.http_timeout)
    url = f"{settings.sourcearena_base_url}/"
    params = {"token": settings.sourcearena_token, "currency": "", "v2": ""}
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    if not isinstance(data, dict) or "18ayar" not in data:
        raise RuntimeError("SourceArena: unexpected response shape")

    usd_toman = _v(data, "usd") or _v(data, "usd_sherkat") or 0.0
    gold18 = _v(data, "18ayar")          # تومان، هر گرم
    xau_usd = _v(data, "usd_xau")        # دلار، هر انس
    xag_toman = _v(data, "xag")          # تومان، هر انس
    xag_usd = round(xag_toman / usd_toman, 2) if usd_toman else 0.0

    if gold18 <= 0:
        raise RuntimeError("SourceArena: gold 18k missing")

    commodities = {
        "XAU": {"name": "طلای جهانی", "sub": "اونس", "price": xau_usd, "change_24h": _ck(data, "usd_xau")},
        "XAG": {"name": "نقره", "sub": "اونس", "price": xag_usd, "change_24h": _ck(data, "xag")},
    }

    # نفت خام از همان منبع SourceArena (کلیدهای محتمل بررسی می‌شوند). مقدار ممکن
    # است به تومان باشد؛ اگر بزرگ بود با نرخ دلار به دلار بشکه تبدیل می‌شود.
    oil_val, oil_key = _first(data, "oil", "oil_brent", "brent", "oil_wti", "wti", "crude_oil", "naft")
    if oil_val > 0:
        oil_usd = round(oil_val / usd_toman, 2) if (oil_val > 1000 and usd_toman) else round(oil_val, 2)
        commodities["OIL"] = {"name": "نفت خام", "sub": "بشکه", "price": oil_usd,
                              "change_24h": _ck(data, oil_key)}

    return {
        "source": "live",
        # تغییر دلار آزاد (تومان) ≈ تغییر ۲۴ساعتهٔ تتر/تومان — برای ردیف تتر استفاده می‌شود
        "usd_change_24h": _ck(data, "usd") or _ck(data, "usd_sherkat"),
        "gold_18k": {"name": "طلای ۱۸ عیار", "sub": "هر گرم", "price": round(gold18), "change_24h": _ck(data, "18ayar")},
        "commodities": commodities,
    }


async def metals() -> dict[str, Any]:
    """طلا/فلزات با نشانگر «تازگی». داخل TTL ⇒ تازه. پس از انقضا تلاش مجدد؛ در
    صورت خطا، آخرین دادهٔ کش با fresh=False برمی‌گردد (برای کوتاه‌مدت دوباره کش
    می‌شود تا API ازکارافتاده هر درخواست صدا زده نشود)."""
    from app.cache import cache
    hit = cache.get("sourcearena:metals")
    if hit is not None:
        return hit
    try:
        value = await get_metals()
        value["fresh"] = True
        cache.set("sourcearena:metals", value, settings.sourcearena_ttl)
        return value
    except Exception:
        stale = cache.get_stale("sourcearena:metals")
        result = dict(stale) if isinstance(stale, dict) else dict(mock_data.sourcearena_metals())
        result["fresh"] = False
        # تلاش مجدد حداکثر هر ۶۰ ثانیه (نه هر درخواست)
        cache.set("sourcearena:metals", result, 60)
        return result


# ─── تخمین زندهٔ طلای ۱۸ عیار از انس جهانی + دلار (برای وقتی SourceArena کهنه است) ───
GRAMS_PER_OUNCE = 31.1034768
PURITY_18K = 0.750


def estimate_gold_18k_toman(xau_usd: float, usd_toman: float, factor: float = 1.0) -> float:
    """ارزش ذوبِ هر گرم طلای ۱۸ عیار (تومان) از انس جهانی (دلار) و نرخ دلار (تومان).
    ضریب factor پرمیوم بازار ایران را اعمال می‌کند (از آخرین دادهٔ تازهٔ SourceArena)."""
    if xau_usd <= 0 or usd_toman <= 0:
        return 0.0
    return xau_usd / GRAMS_PER_OUNCE * PURITY_18K * usd_toman * factor



def _v(data: dict, key: str) -> float:
    item = data.get(key)
    if isinstance(item, dict):
        return _f(item, "value", "price", "last", "p")
    return _num(item)  # برخی پاسخ‌ها مقدار را مستقیم (نه در dict) می‌دهند


def _first(data: dict, *keys: str) -> tuple[float, str]:
    """اولین کلید موجود با مقدار مثبت را برمی‌گرداند: (مقدار، نام‌کلید)."""
    for k in keys:
        if k in data:
            v = _v(data, k)
            if v > 0:
                return v, k
    return 0.0, keys[0]


# نام‌های محتملِ فیلد درصد تغییر در پاسخ SourceArena (هم در dict آیتم، هم با
# پسوند روی کلید سطح‌بالا مثل «18ayar_change»).
_CHANGE_FIELDS = ("change_pct", "change_percent", "changePercent", "percent",
                  "diff_percent", "change", "d", "dp", "today_change",
                  "change_amount", "changeAmount", "p_change", "pc")


def _ck(data: dict, key: str) -> float:
    """درصد تغییر ۲۴ساعتهٔ آیتم key؛ هم داخل dict آیتم، هم کلیدهای هم‌نام با پسوند."""
    item = data.get(key)
    if isinstance(item, dict):
        v = _f(item, *_CHANGE_FIELDS)
        if v:
            return v
    for suf in ("_change_pct", "_change_percent", "_change", "_percent", "_pct"):
        v = _num(data.get(key + suf))
        if v:
            return v
    return 0.0


def _num(x) -> float:
    if x is None:
        return 0.0
    try:
        return float(str(x).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _f(d: dict, *keys: str) -> float:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(str(d[k]).replace(",", "").replace("%", "").strip())
            except (TypeError, ValueError):
                continue
    return 0.0
