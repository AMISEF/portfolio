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
from urllib.parse import quote

import httpx

from app.config import settings
from app.services import mock_data
from app.services import price_history


async def get_metals() -> dict[str, Any]:
    timeout = httpx.Timeout(settings.http_timeout)
    # دقیقاً مطابق فرمت مستندِ SourceArena برای دسترسی از سرور خارجی:
    #   /?token=...&currency&v2
    # «currency» و «v2» پرچم‌های خالی بدون «=» هستند؛ httpx با params آن‌ها را
    # «currency=&v2=» می‌سازد که ممکن است متفاوت تفسیر شود — پس کوئری را دستی
    # می‌سازیم تا عیناً برابر باشد.
    url = f"{settings.sourcearena_base_url}/?token={quote(settings.sourcearena_token)}&currency&v2"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url)
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

    # درصد تغییر ۲۴ساعته: اگر خودِ API مقدار داشته باشد همان؛ وگرنه از تاریخچهٔ
    # قیمتِ پایدار محاسبه می‌شود (چون پراکسی فیلد change را صفر می‌دهد).
    xau_change = _ck(data, "usd_xau") or price_history.record_and_change("xau", xau_usd)
    xag_change = _ck(data, "xag") or price_history.record_and_change("xag", xag_usd)
    gold18_change = _ck(data, "18ayar") or price_history.record_and_change("gold18k", gold18)
    usd_change = (_ck(data, "usd") or _ck(data, "usd_sherkat")
                  or price_history.record_and_change("usd", usd_toman))

    commodities = {
        "XAU": {"name": "طلای جهانی", "sub": "اونس", "price": xau_usd, "change_24h": xau_change},
        "XAG": {"name": "نقره", "sub": "اونس", "price": xag_usd, "change_24h": xag_change},
    }

    # نفت خام از همان منبع SourceArena (کلیدهای محتمل بررسی می‌شوند). مقدار ممکن
    # است به تومان باشد؛ اگر بزرگ بود با نرخ دلار به دلار بشکه تبدیل می‌شود.
    oil_val, oil_key = _first(data, "oil", "oil_brent", "brent", "oil_wti", "wti", "crude_oil", "naft")
    if oil_val > 0:
        oil_usd = round(oil_val / usd_toman, 2) if (oil_val > 1000 and usd_toman) else round(oil_val, 2)
        oil_change = _ck(data, oil_key) or price_history.record_and_change("oil", oil_usd)
        commodities["OIL"] = {"name": "نفت خام", "sub": "بشکه", "price": oil_usd,
                              "change_24h": oil_change}

    return {
        "source": "live",
        # تغییر دلار آزاد (تومان) ≈ تغییر ۲۴ساعتهٔ تتر/تومان — برای ردیف تتر استفاده می‌شود
        "usd_change_24h": usd_change,
        "gold_18k": {"name": "طلای ۱۸ عیار", "sub": "هر گرم", "price": round(gold18), "change_24h": gold18_change},
        "commodities": commodities,
        # سکه‌های ایرانی (تومان، قیمت معاملاتی شاملِ حباب). کلیدهای محتمل امتحان
        # می‌شوند؛ هرکدام نبود، instruments.py از ارزش ذوب تخمین می‌زند.
        "coins": _coins(data),
        "usd_toman": round(usd_toman) if usd_toman else 0,
    }


# نگاشت نوع سکه ⇒ کلیدهای محتمل در پاسخ SourceArena
_COIN_KEYS = {
    "emami": ("emami", "sekee", "seke_emami", "seke", "sekeemami", "coin_emami"),
    "bahar": ("bahar", "azadi", "bahar_azadi", "seke_bahar", "old_coin"),
    "half": ("nim", "nim_sekee", "half", "nimsekee", "seke_nim"),
    "quarter": ("rob", "rob_sekee", "quarter", "robsekee", "seke_rob"),
    "gram": ("gerami", "sekee_gerami", "gram_coin", "seke_gerami", "gerami_coin"),
}


def _coins(data: dict) -> dict[str, float]:
    """قیمت معاملاتی سکه‌ها (تومان) از کلیدهای محتمل؛ فقط مقادیر مثبت."""
    out: dict[str, float] = {}
    for kind, keys in _COIN_KEYS.items():
        val, _ = _first(data, *keys)
        if val > 0:
            out[kind] = round(val)
    return out


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
