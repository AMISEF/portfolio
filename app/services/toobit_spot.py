"""کلاینتِ امضاشدهٔ اسپاتِ صرافی توبیت (کلید اختصاصیِ هر کاربر).

احراز هویت طبق مستندات توبیت (هم‌خانوادهٔ Binance/BHEX):
  • هدر ``X-BB-APIKEY: <api key>``
  • ``signature`` = HMAC-SHA256(secret, <همان کوئری‌ای که می‌فرستیم، شاملِ
    timestamp>) به‌صورت hex، که در انتهای کوئری اضافه می‌شود.

فقط اندپوینت‌های خواندنیِ لازم برای واردکردنِ داراییِ اسپات استفاده می‌شوند:
  • /api/v1/account   ⇒ موجودی هر ارز
  • /api/v1/myTrades  ⇒ تاریخچهٔ معاملات، برای محاسبهٔ میانگینِ قیمتِ خرید

⚠️ کلیدِ کاربر باید فقط دسترسیِ «خواندن» داشته باشد؛ برداشت هرگز لازم نیست.
"""
from __future__ import annotations

import hashlib
import hmac
import time
import urllib.parse
from typing import Any

import httpx

DEFAULT_BASE = "https://api.toobit.com"

# ارزهایی که واحدِ پول هستند و به‌عنوان «دارایی کریپتو» وارد نمی‌شوند.
_STABLE = {"USDT", "USDC", "BUSD", "TUSD", "DAI"}


class ToobitSpotError(RuntimeError):
    """هر خطایی در گفتگو با توبیت (شبکه، وضعیت HTTP یا بدنهٔ خطای API)."""


class ToobitSpotClient:
    def __init__(self, api_key: str, secret_key: str, *,
                 base_url: str = DEFAULT_BASE, recv_window: int = 5000,
                 timeout: float = 15.0) -> None:
        self._key = api_key
        self._secret = secret_key.encode("utf-8")
        self._base = base_url.rstrip("/")
        self._recv_window = recv_window
        self._timeout = httpx.Timeout(timeout, connect=10.0)

    def _sign(self, query: str) -> str:
        return hmac.new(self._secret, query.encode("utf-8"), hashlib.sha256).hexdigest()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        params = {k: v for k, v in (params or {}).items() if v is not None}
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = self._recv_window
        # همان چیزی امضا می‌شود که دقیقاً فرستاده می‌شود.
        query = urllib.parse.urlencode(params)
        url = f"{self._base}{path}?{query}&signature={self._sign(query)}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(url, headers={"X-BB-APIKEY": self._key})
        except httpx.HTTPError as exc:
            raise ToobitSpotError(f"خطای شبکه در ارتباط با توبیت: {exc}") from exc
        if resp.status_code in (401, 403):
            raise ToobitSpotError("کلید API نامعتبر است یا دسترسی لازم را ندارد.")
        if resp.status_code != 200:
            raise ToobitSpotError(f"خطای توبیت (HTTP {resp.status_code}): {resp.text[:200]}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise ToobitSpotError("پاسخ نامعتبر از توبیت دریافت شد.") from exc
        if isinstance(data, dict) and data.get("code") not in (None, 0, "0", 200):
            raise ToobitSpotError(f"خطای توبیت {data.get('code')}: {data.get('msg')}")
        return data

    async def balances(self) -> list[dict[str, Any]]:
        """موجودیِ اسپات: [{asset, free, locked, total}] فقط با موجودیِ مثبت."""
        data = await self._get("/api/v1/account")
        rows = data.get("balances") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            rows = data if isinstance(data, list) else []
        out: list[dict[str, Any]] = []
        for b in rows:
            if not isinstance(b, dict):
                continue
            asset = str(b.get("asset") or b.get("coin") or b.get("currency") or "").upper()
            free = _f(b, "free", "available", "availableBalance")
            locked = _f(b, "locked", "frozen", "freeze")
            total = free + locked
            if asset and total > 0:
                out.append({"asset": asset, "free": free, "locked": locked, "total": total})
        return out

    async def my_trades(self, symbol: str, limit: int = 500) -> list[dict[str, Any]]:
        data = await self._get("/api/v1/myTrades", {"symbol": symbol, "limit": limit})
        if isinstance(data, list):
            return [t for t in data if isinstance(t, dict)]
        if isinstance(data, dict):
            for key in ("data", "list", "rows"):
                inner = data.get(key)
                if isinstance(inner, list):
                    return [t for t in inner if isinstance(t, dict)]
        return []

    async def avg_buy_price(self, asset: str, quote: str = "USDT") -> float | None:
        """میانگینِ وزنیِ قیمتِ خریدِ یک ارز از تاریخچهٔ معاملات.

        خریدها جمع می‌شوند و فروش‌ها به‌روشِ میانگینِ متحرک از موجودی کم می‌شوند،
        تا میانگینِ قیمتِ تمام‌شدهٔ موجودیِ فعلی به دست آید. اگر تاریخچه در دسترس
        نباشد None برمی‌گردد (کاربر می‌تواند دستی وارد کند).
        """
        try:
            trades = await self.my_trades(f"{asset}{quote}")
        except ToobitSpotError:
            return None
        if not trades:
            return None
        trades.sort(key=lambda t: int(t.get("time") or t.get("transactTime") or 0))
        qty_held = 0.0
        cost = 0.0
        for t in trades:
            price = _f(t, "price", "p")
            qty = _f(t, "qty", "quantity", "q", "executedQty")
            if price <= 0 or qty <= 0:
                continue
            if _is_buy(t):
                qty_held += qty
                cost += price * qty
            else:
                if qty_held <= 0:
                    continue
                avg = cost / qty_held
                sold = min(qty, qty_held)
                qty_held -= sold
                cost -= avg * sold
        if qty_held <= 0 or cost <= 0:
            return None
        return cost / qty_held


def _is_buy(trade: dict[str, Any]) -> bool:
    if "isBuyer" in trade:
        return bool(trade["isBuyer"])
    side = str(trade.get("side") or trade.get("S") or "").upper()
    return side == "BUY"


def _f(d: dict[str, Any], *keys: str) -> float:
    for k in keys:
        v = d.get(k)
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return 0.0


def is_stable(asset: str) -> bool:
    return asset.upper() in _STABLE
