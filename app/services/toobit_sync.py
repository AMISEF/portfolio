"""واردکردنِ داراییِ اسپاتِ توبیت به سبدِ کاربر.

موجودیِ هر ارز از توبیت خوانده می‌شود و به‌صورت داراییِ «crypto» در سبد ثبت/به‌روز
می‌گردد. میانگینِ قیمتِ خرید از تاریخچهٔ معاملاتِ همان ارز محاسبه و به تومان تبدیل
می‌شود تا سود/زیانِ هر دارایی در پنل دیده شود.

نکتهٔ واحد: قیمتِ خریدِ سبد در پنل به «تومان» نگهداری می‌شود، اما میانگینِ خریدِ
توبیت دلاری است. تبدیل با نرخِ دلارِ لحظهٔ ورودِ اطلاعات انجام می‌شود؛ بنابراین
سود/زیانِ نمایش‌داده‌شده شاملِ اثرِ تغییرِ نرخِ دلار نیست و مبنای آن قیمتِ دلاریِ
خرید است.
"""
from __future__ import annotations

import logging
from typing import Any

from app import db
from app.services import crypto_box, instruments
from app.services.toobit_spot import ToobitSpotClient, ToobitSpotError, is_stable

logger = logging.getLogger("app.toobit_sync")

# منبعِ داراییِ واردشده از توبیت — برای تشخیص از دارایی‌های دستی.
SOURCE_TAG = "toobit"


def client_for(user_id: int) -> ToobitSpotClient | None:
    """کلاینتِ توبیتِ کاربر از کلیدهای رمزگذاری‌شده، یا None اگر ثبت نشده باشد."""
    row = db.toobit_keys_get(int(user_id))
    if not row:
        return None
    key = crypto_box.decrypt(row.get("api_key_enc"))
    secret = crypto_box.decrypt(row.get("secret_enc"))
    if not key or not secret:
        return None
    return ToobitSpotClient(key, secret)


async def verify(api_key: str, secret: str) -> tuple[bool, str]:
    """اعتبارسنجیِ کلید پیش از ذخیره: یک فراخوانیِ خواندنیِ ساده."""
    try:
        await ToobitSpotClient(api_key, secret).balances()
    except ToobitSpotError as exc:
        return False, str(exc)
    except Exception as exc:  # noqa: BLE001
        return False, f"خطای غیرمنتظره: {exc}"
    return True, ""


async def sync_user(user_id: int, uid: str) -> dict[str, Any]:
    """همگام‌سازیِ داراییِ اسپاتِ کاربر با سبدِ پنل.

    خروجی: {"ok", "imported", "updated", "skipped", "error"}
    """
    client = client_for(user_id)
    if client is None:
        return {"ok": False, "error": "کلید API توبیت ثبت نشده است."}

    try:
        balances = await client.balances()
    except ToobitSpotError as exc:
        db.toobit_mark_sync(user_id, str(exc))
        return {"ok": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        logger.exception("toobit balances failed")
        db.toobit_mark_sync(user_id, str(exc))
        return {"ok": False, "error": f"خطای غیرمنتظره: {exc}"}

    table = await instruments.price_table()
    usd_toman = float(table.get("usd_toman") or 0)
    existing = {(a.get("symbol") or "").upper(): a for a in db.list_assets(uid)}

    imported = updated = skipped = 0
    for b in balances:
        asset = b["asset"]
        amount = float(b["total"])
        if amount <= 0:
            continue
        if is_stable(asset):
            # تتر/استیبل‌ها به‌عنوان داراییِ «usdt» ثبت می‌شوند، بدون قیمتِ خرید.
            kind, buy_toman = "usdt", None
        else:
            kind = "crypto"
            avg_usd = await client.avg_buy_price(asset)
            buy_toman = round(avg_usd * usd_toman) if (avg_usd and usd_toman) else None

        cur = existing.get(asset)
        if cur:
            db.update_asset(uid, int(cur["id"]), amount=amount,
                            buy_price=buy_toman if buy_toman is not None else "__keep__")
            updated += 1
        else:
            try:
                db.add_asset(uid, {
                    "kind": kind, "symbol": asset, "name": asset,
                    "amount": amount, "buy_price": buy_toman,
                    "purity": None, "horizon": None,
                })
                imported += 1
            except Exception:  # noqa: BLE001
                skipped += 1

    db.toobit_mark_sync(user_id, None)
    return {"ok": True, "imported": imported, "updated": updated, "skipped": skipped}
