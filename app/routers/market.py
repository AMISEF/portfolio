"""
روتر JSON بازار — فرانت‌اند فقط با این اندپوینت‌ها صحبت می‌کند و هرگز
مستقیماً به APIهای بیرونی وصل نمی‌شود. هر گروه TTL مخصوص خودش را دارد:

* /api/market/macro     ← CryptoRank (کش ۱۰ دقیقه) + ترس و طمع
* /api/market/gainers   ← Toobit (کش ~۱۲ ثانیه)
* /api/market/internal  ← تتر (تبدیل) + طلای ۱۸ع (سورس‌آرنا، ۳۰ دقیقه) + فیوچرز توبیت
* /api/market/credits   ← وضعیت مصرف کردیت CryptoRank (شفافیت)
"""
from __future__ import annotations

from fastapi import APIRouter

from app.cache import credit_budget
from app.services import cryptorank, fng, sourcearena, tabdeal, toobit

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/macro")
async def macro():
    data = await cryptorank.macro()
    try:
        data["fear_greed"] = await fng.fng()
    except Exception:
        pass
    return data


@router.get("/gainers")
async def gainers():
    return await toobit.gainers()


@router.get("/internal")
async def internal():
    usdt = await tabdeal.usdt()
    gold = await sourcearena.gold18()
    fut = await toobit.futures()
    return {
        "usdt_irt": usdt["usdt_irt"],
        "gold_18k": gold["gold_18k"],
        "futures": fut["futures"],
        "sources": {"usdt": usdt["source"], "gold": gold["source"], "futures": fut["source"]},
    }


@router.get("/credits")
async def credits():
    return credit_budget.usage()


@router.get("/debug")
async def debug():
    """عیب‌یابی روی سرور: نشان می‌دهد هر منبع چه برمی‌گرداند و کجا خطا می‌خورد.
    این را روی سرور صدا بزنید و خروجی را بفرستید تا نگاشت دقیق فیلدها تنظیم شود."""
    result: dict = {}
    for name, fn in (
        ("cryptorank", cryptorank.probe),
        ("toobit", toobit.probe),
        ("tabdeal", tabdeal.probe),
        ("sourcearena", sourcearena.probe),
    ):
        try:
            result[name] = await fn()
        except Exception as e:  # noqa: BLE001
            result[name] = {"error": f"{type(e).__name__}: {e}"}
    # نتیجهٔ نهایی پارس‌شده هم برای مقایسه
    try:
        result["_parsed"] = {
            "macro": (await cryptorank.macro())["source"],
            "gainers": await toobit.gainers(),
            "internal": {"usdt": await tabdeal.usdt(), "gold": await sourcearena.gold18(), "futures": await toobit.futures()},
        }
    except Exception as e:  # noqa: BLE001
        result["_parsed_error"] = f"{type(e).__name__}: {e}"
    return result
