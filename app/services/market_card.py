"""
تولید «تصویر نمای کلی بازار» برای انتشار روزانه در کانال تلگرام (استوری اینستاگرام).

خروجی یک PNG عمودی با نسبت ۹:۱۶ (۲۱۶۰×۳۸۴۰، کیفیت 4K) شامل:
  • سرتیتر «نمای کلی بازار» (راست) + تاریخ شمسیِ همان روز (چپ) + شاخص‌های کلان
  • «ارزهای برتر بازار» (آیکون/نام/قیمت/تغییر ۲۴ساعته) — باکس‌های گوشه‌نرم
  • «قیمت‌های کلیدی» (تتر، طلای ۱۸ع، انس طلا، نقره، نفت)
  • «Gainers / Top losers» به‌سبک توبیت (با آیکون واقعی ارز)
  • لوگوی کریپتو‌اسمارت در پایین

روش رِندر: HTML کاملاً خوداتکا (فونت/آیکون/لوگو به base64 جاسازی شده) با Chromium
بدون‌هد و ضریب مقیاس ۳ اسکرین‌شات می‌شود (۷۲۰×۱۲۸۰ × ۳ = ۲۱۶۰×۳۸۴۰). راست‌چین
فارسی و پالت سازمانی کریپتو‌اسمارت رعایت شده‌اند.
"""
from __future__ import annotations

import asyncio
import base64
import datetime as _dt
import os
import shutil
import tempfile
from glob import glob
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.services import mock_data, toobit

_ROOT = Path(__file__).resolve().parents[2]
_STATIC = _ROOT / "app" / "static"
_FONTS = _STATIC / "fonts"
_IMG = _STATIC / "img"
_COINS = _IMG / "coins"
_ICONCACHE = _ROOT / "data" / "iconcache"   # آیکون‌های دانلودی (gitignore: data/)

# ───────────────────────── پالت سازمانی کریپتو‌اسمارت ─────────────────────────
BRAND = {
    "bg0": "#0f2342", "bg1": "#16315a", "bg2": "#1a3a66",
    "card": "#1b3c69", "card2": "#15315a", "line": "rgba(111,149,200,.20)",
    "ink": "#EAF1FB", "muted": "#A9BEDD", "dim": "#7C9AC8",
    "blue": "#2D63B0", "blueLt": "#6F95C8", "navy": "#214E8A",
    "teal": "#19C3B3", "teal2": "#4ED9CC", "glow": "#A6F0E8",
    "up": "#16C784", "down": "#EA3943", "light": "#F3F6F9",
}

# ───────────────────────── تبدیل تاریخ میلادی → شمسی (جلالی) ─────────────────────────
_FA_MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
              "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
_FA_WEEKDAYS = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]


def _g2j(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """تبدیل تاریخ میلادی به جلالی (الگوریتم استاندارد)."""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2, gm2, gd2 = gy - 1600, gm - 1, gd - 1
    g_day_no = 365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
    g_day_no += g_d_m[gm2] + gd2
    if gm2 > 1 and ((gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)):
        g_day_no += 1
    j_day_no = g_day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053
    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461
    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365
    j_d_m = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]
    jm = 0
    while jm < 12 and j_day_no >= j_d_m[jm]:
        j_day_no -= j_d_m[jm]
        jm += 1
    return jy, jm + 1, j_day_no + 1


def tehran_now() -> _dt.datetime:
    """زمان جاری به وقت تهران (ایران از ۲۰۲۲ ساعت تابستانی ندارد ⇒ ثابت +۳:۳۰)."""
    return _dt.datetime.utcnow() + _dt.timedelta(hours=3, minutes=30)


def shamsi_today() -> str:
    now = tehran_now()
    jy, jm, jd = _g2j(now.year, now.month, now.day)
    wd = _FA_WEEKDAYS[now.weekday()]
    return _fa(f"{wd} {jd} {_FA_MONTHS[jm - 1]} {jy}")


# ───────────────────────── قالب‌بندی اعداد ─────────────────────────
_FA_MAP = str.maketrans({"0": "۰", "1": "۱", "2": "۲", "3": "۳", "4": "۴", "5": "۵",
                         "6": "۶", "7": "۷", "8": "۸", "9": "۹",
                         ",": "٬", ".": "٫", "%": "٪", "-": "−"})


def _fa(s: Any) -> str:
    return str(s).translate(_FA_MAP)


def _usd_num(v: float) -> str:
    """فقط عددِ دلاری (بدون علامت $) با دقتِ مناسب."""
    v = float(v or 0)
    if v >= 1000:
        return f"{v:,.0f}"
    if v >= 1:
        return f"{v:,.2f}"
    if v >= 0.1:
        return f"{v:.4f}".rstrip("0").rstrip(".")
    if v >= 0.001:
        return f"{v:.5f}".rstrip("0").rstrip(".")
    return f"{v:.8f}".rstrip("0").rstrip(".")


def usd_fa(v: float) -> str:
    """قیمت دلاری راست‌چین: عددِ فارسی + علامت $ در سمتِ راست (پسوند)."""
    return _fa(_usd_num(v)) + "$"


def toman_fa(v: float) -> str:
    return _fa(f"{round(float(v or 0)):,}") + " ت"


def pct_fa(ch: float) -> str:
    return _fa(f"{float(ch or 0):+.2f}%")


def big_fa(v: float) -> str:
    v = float(v or 0)
    if v >= 1e12:
        s = f"{v / 1e12:.2f}T"
    elif v >= 1e9:
        s = f"{v / 1e9:.2f}B"
    elif v >= 1e6:
        s = f"{v / 1e6:.2f}M"
    else:
        s = f"{v:,.0f}"
    return _fa(s) + "$"


# ───────────────────────── جاسازی دارایی‌ها (base64) ─────────────────────────
def _data_uri(path: Path, mime: str = "image/png") -> str:
    try:
        b = path.read_bytes()
    except Exception:
        return ""
    return f"data:{mime};base64,{base64.b64encode(b).decode()}"


def _file_url(path: Path) -> str:
    """آدرس file:// مطلق — برای تصاویرِ محلیِ بزرگ (به‌جای base64) تا HTML سبک بماند."""
    return "file://" + str(path.resolve())


def _font_css() -> str:
    weights = {"Regular": 400, "Medium": 500, "SemiBold": 600,
               "Bold": 700, "ExtraBold": 800, "Black": 900}
    out = []
    # فونتِ اصلی: «دانا» (Dana) — اگر فایل‌های Dana-*.woff2 در app/static/fonts باشند
    # استفاده می‌شوند؛ در غیر این صورت روی Vazirmatn برمی‌گردد (fallback). برای دریافت
    # روی سرور: راهنمای پایین فایل (یا دانلود از github.com/rastikerdar/dana-font).
    dana_w = {"Regular": 400, "Medium": 500, "DemiBold": 600,
              "Bold": 700, "ExtraBold": 800, "Black": 900}
    for name, w in dana_w.items():
        uri = _data_uri(_FONTS / f"Dana-{name}.woff2", "font/woff2")
        if uri:
            out.append(f"@font-face{{font-family:Dana;src:url({uri}) format('woff2');"
                       f"font-weight:{w};font-style:normal;font-display:block}}")
    for name, w in weights.items():
        uri = _data_uri(_FONTS / f"Vazirmatn-{name}.woff2", "font/woff2")
        if uri:
            out.append(f"@font-face{{font-family:Vaz;src:url({uri}) format('woff2');"
                       f"font-weight:{w};font-style:normal;font-display:block}}")
    # Quicksand — فونت لاتینِ نرم و گرد برای آیدی برند
    for w in (600, 700):
        uri = _data_uri(_FONTS / f"Quicksand-{w}.woff2", "font/woff2")
        if uri:
            out.append(f"@font-face{{font-family:Quick;src:url({uri}) format('woff2');"
                       f"font-weight:{w};font-style:normal;font-display:block}}")
    return "\n".join(out)


def _icon_html(symbol: str, cls: str, icons: dict[str, str | None]) -> str:
    uri = icons.get(symbol)
    if uri:
        return f'<span class="{cls}"><img src="{uri}" alt=""></span>'
    letter = (symbol or "?")[:3].upper()
    return f'<span class="{cls} ic-badge">{letter}</span>'


_METAL_FILE = {"usdt": "usdt.png", "g18": "gold18.png",
               "XAU": "xau.png", "XAG": "xag.png", "OIL": "oil.png"}


def _metal_icon(key: str, cls: str) -> str:
    f = _METAL_FILE.get(key)
    if f and (_IMG / f).exists():
        return f'<span class="{cls}"><img src="{_file_url(_IMG / f)}" alt=""></span>'
    return f'<span class="{cls} ic-badge">?</span>'


# ───────────────────────── دانلود/کش آیکون ارز ─────────────────────────
_PNG_SIG = b"\x89PNG\r\n\x1a\n"


async def _fetch_icon(client: httpx.AsyncClient, sym: str) -> bytes | None:
    """آیکون ارز را از منابع عمومی می‌گیرد (jsdelivr → CoinGecko)."""
    s = sym.lower()
    # ۱) مجموعهٔ cryptocurrency-icons روی jsdelivr (ارزهای شناخته‌شده)
    try:
        r = await client.get(
            f"https://cdn.jsdelivr.net/npm/cryptocurrency-icons@0.18.1/128/color/{s}.png")
        if r.status_code == 200 and r.content[:8] == _PNG_SIG:
            return r.content
    except Exception:
        pass
    # ۲) CoinGecko: جست‌وجوی نماد → تصویر
    try:
        r = await client.get("https://api.coingecko.com/api/v3/search", params={"query": sym})
        if r.status_code == 200:
            coins = (r.json() or {}).get("coins") or []
            match = next((c for c in coins if (c.get("symbol") or "").lower() == s),
                         coins[0] if coins else None)
            img = (match or {}).get("large") or (match or {}).get("thumb")
            if img:
                ir = await client.get(img)
                if ir.status_code == 200 and len(ir.content) > 100:
                    return ir.content
    except Exception:
        pass
    return None


async def _icon_map(symbols: list[str]) -> dict[str, str | None]:
    """نگاشت نماد → data-URI آیکون. ابتدا محلی/کش، سپس دانلود (و ذخیره در کش)."""
    out: dict[str, str | None] = {}
    need: list[str] = []
    for sym in dict.fromkeys(symbols):       # حذف تکراری‌ها با حفظ ترتیب
        s = sym.lower()
        local = _COINS / f"{s}.png"
        cached = _ICONCACHE / f"{s}.png"
        if local.exists():
            out[sym] = _file_url(local)
        elif cached.exists():
            out[sym] = _file_url(cached)
        else:
            need.append(sym)
    if need:
        try:
            _ICONCACHE.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        async with httpx.AsyncClient(timeout=httpx.Timeout(12.0), follow_redirects=True) as client:
            res = await asyncio.gather(*[_fetch_icon(client, s) for s in need],
                                       return_exceptions=True)
        for sym, content in zip(need, res):
            if isinstance(content, (bytes, bytearray)) and content:
                p = _ICONCACHE / f"{sym.lower()}.png"
                try:
                    p.write_bytes(content)
                    out[sym] = _file_url(p)
                except Exception:
                    out[sym] = None
            else:
                out[sym] = None
    return out


# ───────────────────────── گردآوری داده ─────────────────────────
async def _safe(coro):
    try:
        return await coro
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}


async def _fresh_gainers_losers() -> dict[str, Any]:
    """بیشترین رشد/افتِ زنده — بدون کش، با یک تلاشِ مجدد.

    toobit.gainers_losers() کش ۵دقیقه‌ای دارد و در خطای مکرر، آخرین مقدارِ
    موفقِ کش‌شده را برای همیشه برمی‌گرداند (داده‌ی ثابت/قدیمی). چون این تصویر
    باید هر بار «آخرین» گینر/لوزر را نشان دهد، مستقیماً (بدون کش) درخواست
    می‌زنیم؛ در صورت شکستِ اول یک‌بار دیگر امتحان می‌کنیم.
    """
    try:
        return await toobit.get_gainers_losers()
    except Exception:  # noqa: BLE001
        return await toobit.get_gainers_losers()


async def _retry_once(fetcher):
    try:
        return await fetcher()
    except Exception:  # noqa: BLE001
        return await fetcher()


async def _fresh_prices() -> dict[str, Any]:
    """قیمت‌های کلیدی به‌صورتِ زنده — بدون کشِ طولانی‌مدتِ SourceArena/Yahoo.

    sourcearena.metals() و commodities.commodities() در خطای مکرر، آخرین
    مقدارِ موفقِ کش‌شده را برای همیشه برمی‌گردانند (دقیقاً همان باگِ گینر/لوزر؛
    دلیلِ منجمدماندنِ طلای ۱۸ع/انس‌طلا/نقره/نفت). چون این تصویر هر چند ساعت
    یک‌بار ساخته می‌شود (خیلی کمتر از TTLِ آن کش‌ها)، اینجا فِچرهای خام را
    مستقیماً (با یک تلاشِ مجدد) صدا می‌زنیم؛ فقط در شکستِ کامل به نسخهٔ کش‌شده
    برمی‌گردیم تا تتر/تومان و تومانِ طلا و ساختارِ خروجی حفظ شود."""
    from app.services import sourcearena, commodities as commodities_svc, tabdeal

    usdt_d, metals_d, comm_d = await asyncio.gather(
        _safe(tabdeal.usdt()),
        _safe(_retry_once(sourcearena.get_metals)),
        _safe(_retry_once(commodities_svc.get_commodities)),
    )
    if "error" in metals_d:
        metals_d = await sourcearena.metals()  # واپسین‌چاره: کشِ تحمل‌پذیرِ خطا
    if "error" in comm_d:
        comm_d = await commodities_svc.commodities()

    sa_comm = metals_d.get("commodities", {}) if isinstance(metals_d, dict) else {}
    yh_comm = comm_d.get("commodities", {}) if isinstance(comm_d, dict) else {}
    commodities: dict[str, Any] = {}
    for k in ("XAU", "XAG", "OIL"):
        base = dict(sa_comm.get(k) or {})
        yv = yh_comm.get(k) or {}
        if not base:
            base = dict(yv)
        else:
            if yv.get("spark"):
                base["spark"] = yv["spark"]
            if not base.get("change_24h") and yv.get("change_24h"):
                base["change_24h"] = yv["change_24h"]
        if base:
            commodities[k] = base

    usdt_irt = usdt_d.get("usdt_irt") if isinstance(usdt_d, dict) else None
    if isinstance(usdt_irt, dict):
        usd_chg = metals_d.get("usd_change_24h") if isinstance(metals_d, dict) else None
        if usd_chg and not usdt_irt.get("change_24h"):
            usdt_irt["change_24h"] = usd_chg

    gold_18k = metals_d.get("gold_18k") if isinstance(metals_d, dict) else None

    return {"usdt_irt": usdt_irt, "gold_18k": gold_18k, "commodities": commodities}


async def gather() -> dict[str, Any]:
    from app.services import coinmarketcap

    coins_d, prices_d, gl_d, macro_d = await asyncio.gather(
        _safe(toobit.card_coins()),
        _safe(_fresh_prices()),
        _safe(_fresh_gainers_losers()),
        _safe(coinmarketcap.macro()),
    )

    coins = (coins_d.get("coins") if isinstance(coins_d, dict) else None) \
        or mock_data.toobit_card_coins()["coins"]
    coins = coins[:6]
    prices = prices_d if isinstance(prices_d, dict) and "error" not in prices_d else None
    if prices is None:
        m = mock_data.sourcearena_metals()
        t = mock_data.tabdeal_usdt()
        prices = {"usdt_irt": t["usdt_irt"], "gold_18k": m["gold_18k"],
                  "commodities": m["commodities"]}
    gl = gl_d if isinstance(gl_d, dict) and gl_d.get("gainers") else mock_data.toobit_gainers_losers()
    macro = macro_d if isinstance(macro_d, dict) and "error" not in macro_d else mock_data.cmc_macro()

    # آیکونِ همهٔ ارزهای استفاده‌شده (برتر + رشد + افت) — با دانلود و کش
    syms = [c["symbol"] for c in coins]
    syms += [x["symbol"] for x in gl.get("gainers", [])]
    syms += [x["symbol"] for x in gl.get("losers", [])]
    icons = await _icon_map(syms)

    return {"coins": coins, "prices": prices, "gl": gl, "macro": macro,
            "icons": icons, "shamsi": shamsi_today()}


# ───────────────────────── آیکون‌های SVG ─────────────────────────
# آیکون رشد (نمودار صعودی سبز) و افت (نمودار نزولی قرمز) — کنار Gainers/Top losers
_ICON_GAIN = ('<svg viewBox="0 0 24 24" fill="none" stroke="#16C784" stroke-width="2.4" '
              'stroke-linecap="round" stroke-linejoin="round"><path d="M3 17l6-6 4 4 8-8"/>'
              '<path d="M15 7h5v5"/></svg>')
_ICON_LOSE = ('<svg viewBox="0 0 24 24" fill="none" stroke="#EA3943" stroke-width="2.4" '
              'stroke-linecap="round" stroke-linejoin="round"><path d="M3 7l6 6 4-4 8 8"/>'
              '<path d="M15 17h5v-5"/></svg>')
# آیکون‌های شبکه‌های اجتماعی
_SOC_TG = ('<svg viewBox="0 0 24 24" fill="currentColor"><path d="M21.9 4.3l-3.2 15.1c-.2 1-.9 '
           '1.3-1.8.8l-4.9-3.6-2.4 2.3c-.3.3-.5.5-1 .5l.4-5 9.1-8.2c.4-.4-.1-.6-.6-.2L6.2 '
           '13.1 1.4 11.6c-1-.3-1-1 .2-1.5L20.6 3c.9-.3 1.6.2 1.3 1.3z"/></svg>')
_SOC_IG = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect '
           'x="3" y="3" width="18" height="18" rx="5.2"/><circle cx="12" cy="12" r="4"/>'
           '<circle cx="17.4" cy="6.6" r="1.1" fill="currentColor" stroke="none"/></svg>')
_SOC_YT = ('<svg viewBox="0 0 24 24" fill="currentColor"><path d="M23 7.6c-.3-1.1-1-1.9-2.1-2.1C19 '
           '5 12 5 12 5s-7 0-8.9.5C2 5.7 1.3 6.5 1 7.6.5 9.5.5 12 .5 12s0 2.5.5 4.4c.3 1.1 1 1.9 '
           '2.1 2.1C5 19 12 19 12 19s7 0 8.9-.5c1.1-.2 1.8-1 2.1-2.1.5-1.9.5-4.4.5-4.4s0-2.5-.5-4.4z'
           'M9.8 15.3V8.7l5.7 3.3-5.7 3.3z"/></svg>')

# لایهٔ تزئینیِ پس‌زمینه: کرهٔ زمین + کندل‌ها + نمودار صعودیِ پُرشده + گره‌های هوش
# مصنوعی + مدارها + ربات + نمادهای ارز شناور. شفافیتِ متعادل تا از پشت شیشه دیده شود.
_BG_SVG = """<svg viewBox="0 0 720 1280" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice">
 <defs>
  <linearGradient id="ar" x1="0" y1="0" x2="0" y2="1">
   <stop offset="0" stop-color="#19C3B3" stop-opacity="0.22"/>
   <stop offset="1" stop-color="#19C3B3" stop-opacity="0"/>
  </linearGradient>
 </defs>
 <!-- نمودار سطحیِ پُرشده در میانه -->
 <path d="M0,470 L70,440 L140,460 L210,400 L300,430 L380,350 L460,385 L540,320 L640,360 L720,310 L720,640 L0,640 Z" fill="url(#ar)"/>
 <polyline points="0,470 70,440 140,460 210,400 300,430 380,350 460,385 540,320 640,360 720,310"
   stroke="#4ED9CC" fill="none" stroke-width="2" opacity="0.30"/>
 <!-- کرهٔ زمین -->
 <g stroke="#4ED9CC" fill="none" stroke-width="1.5" opacity="0.22">
  <circle cx="565" cy="232" r="98"/>
  <ellipse cx="565" cy="232" rx="98" ry="34"/><ellipse cx="565" cy="232" rx="98" ry="66"/>
  <ellipse cx="565" cy="232" rx="58" ry="98"/><ellipse cx="565" cy="232" rx="92" ry="98"/>
  <line x1="467" y1="232" x2="663" y2="232"/>
 </g>
 <!-- مدارِ نقطه‌چین گردِ کره -->
 <ellipse cx="565" cy="232" rx="128" ry="48" stroke="#19C3B3" fill="none" stroke-width="1.4"
   stroke-dasharray="5 9" opacity="0.20" transform="rotate(-22 565 232)"/>
 <!-- (کندل‌استیکِ سراسریِ پس‌زمینه حذف شد؛ کندلِ سبز/قرمزِ مخصوص داخلِ باکسِ Gainers/Losers است) -->
 <!-- شبکهٔ گره‌های هوش مصنوعی -->
 <g stroke="#6F95C8" fill="#6F95C8" stroke-width="1.4" opacity="0.20">
  <g fill="none"><line x1="115" y1="250" x2="190" y2="198"/><line x1="115" y1="250" x2="165" y2="330"/><line x1="190" y1="198" x2="262" y2="278"/><line x1="165" y1="330" x2="262" y2="278"/><line x1="190" y1="198" x2="250" y2="150"/></g>
  <circle cx="115" cy="250" r="5"/><circle cx="190" cy="198" r="5"/><circle cx="165" cy="330" r="5"/><circle cx="262" cy="278" r="5"/><circle cx="250" cy="150" r="4"/>
  <g fill="none"><line x1="610" y1="900" x2="668" y2="852"/><line x1="610" y1="900" x2="648" y2="978"/><line x1="668" y1="852" x2="700" y2="916"/></g>
  <circle cx="610" cy="900" r="5"/><circle cx="668" cy="852" r="5"/><circle cx="648" cy="978" r="5"/><circle cx="700" cy="916" r="4"/>
 </g>
 <!-- ربات -->
 <g stroke="#4ED9CC" fill="none" stroke-width="1.8" opacity="0.18" stroke-linejoin="round">
  <rect x="70" y="892" width="92" height="76" rx="18"/>
  <line x1="116" y1="892" x2="116" y2="868"/><circle cx="116" cy="861" r="6"/>
  <circle cx="98" cy="924" r="8"/><circle cx="134" cy="924" r="8"/>
  <line x1="90" y1="948" x2="142" y2="948"/>
  <line x1="70" y1="918" x2="58" y2="918"/><line x1="162" y1="918" x2="174" y2="918"/>
 </g>
 <!-- نمادهای ارز شناور -->
 <g fill="none" stroke-width="2" opacity="0.16">
  <g stroke="#F7931A" transform="translate(300 760)"><circle cx="0" cy="0" r="24"/><text x="0" y="9" font-size="26" font-weight="700" fill="#F7931A" stroke="none" text-anchor="middle" font-family="Arial">B</text></g>
  <g stroke="#627EEA" transform="translate(470 560)"><circle cx="0" cy="0" r="20"/><text x="0" y="7" font-size="22" font-weight="700" fill="#627EEA" stroke="none" text-anchor="middle" font-family="Arial">E</text></g>
 </g>
</svg>"""


# کندل‌استیکِ پس‌زمینهٔ باکس Gainers/Top losers (سبزِ صعودی / قرمزِ نزولی).
def _candles_svg(color: str, ys: list[int]) -> str:
    parts = []
    for i, cy in enumerate(ys):
        cx = 24 + i * 42
        parts.append(f'<line x1="{cx}" y1="{cy - 48}" x2="{cx}" y2="{cy + 48}"/>')
        parts.append(f'<rect x="{cx - 13}" y="{cy - 26}" width="26" height="52" rx="3"/>')
    return (f'<svg class="gl__cbg" viewBox="0 0 260 300" preserveAspectRatio="xMidYMid slice" '
            f'xmlns="http://www.w3.org/2000/svg"><g stroke="{color}" stroke-width="3.4" '
            f'fill="{color}" opacity="0.16">' + "".join(parts) + "</g></svg>")


_CBG_UP = _candles_svg("#16C784", [226, 200, 178, 150, 122, 96])    # صعودی (Gainers)
_CBG_DOWN = _candles_svg("#EA3943", [96, 122, 150, 178, 200, 226])  # نزولی (Top losers)


# ───────────────────────── ساخت HTML ─────────────────────────
def _chip(ch: float) -> str:
    cls = "up" if ch > 0 else ("down" if ch < 0 else "flat")
    return f'<span class="chip chip--{cls}">{pct_fa(ch)}</span>'


def _coin_box(g: dict, icons: dict) -> str:
    """باکسِ ارزِ برتر (شبکهٔ ۳×۲): آیکون در گوشهٔ چپ؛ سمتِ راست به‌ترتیبِ عمودی
    نام، قیمت، و درصدِ تغییرِ ۲۴ساعته."""
    sym = g.get("symbol", "")
    return (
        '<div class="coin glass">'
        + _icon_html(sym, "coin__ic", icons)
        + '<div class="coin__txt">'
        + f'<span class="coin__nm">{sym}</span>'
        + f'<span class="coin__price">{usd_fa(g.get("price"))}</span>'
        + _chip(g.get("change_24h", 0))
        + '</div></div>'
    )


def _key_row(key: str, name: str, price_html: str, ch: float,
             rtl_price: bool = False) -> str:
    """ردیفِ افقیِ قیمتِ کلیدی: آیکون+نام در یک‌سو، قیمت+درصدِ تغییر در سویِ دیگر
    (بدون زیرنویسِ واحد، با فونتِ درشت)."""
    pc = "kr__price kr__price--rtl" if rtl_price else "kr__price"
    return (
        '<div class="kr glass">'
        '<div class="kr__r">' + _metal_icon(key, "kr__ic") +
        f'<span class="kr__nm">{name}</span></div>'
        '<div class="kr__l">'
        f'<span class="{pc}">{price_html}</span>' + _chip(ch) + '</div></div>'
    )


def _gl_row(it: dict, icons: dict) -> str:
    """ردیفِ گینر/لوزر: آیکون+نماد سمتِ چپ؛ قیمت وسطِ باکس؛ درصدِ تغییر (به‌صورتِ
    چیپِ سبز/قرمز، هم‌سبکِ بقیهٔ بخش‌ها) سمتِ راستِ قیمت."""
    return (
        '<div class="gl__row">'
        '<span class="gl__l">' + _icon_html(it.get("symbol", ""), "gl__ic", icons) +
        f'<b>{it.get("symbol","")}</b><span class="gl__q">/USDT</span></span>'
        f'<span class="gl__p">{_usd_num(it.get("price"))}</span>'
        + _chip(it.get("change_24h", 0)) +
        '</div>'
    )


def _gl_box(title: str, icon_svg: str, rows: list[dict], kind: str, icons: dict) -> str:
    body = "".join(_gl_row(r, icons) for r in rows[:settings.toobit_gl_count])
    cbg = _CBG_UP if kind == "up" else _CBG_DOWN
    return (
        f'<div class="gl glass gl--{kind}">{cbg}'
        f'<div class="gl__hd"><span class="gl__hi">{icon_svg}</span>'
        f'<span class="gl__t">{title}</span></div>{body}</div>'
    )


def build_html(data: dict[str, Any]) -> str:
    coins, pr, gl, mac = data["coins"], data["prices"], data["gl"], data["macro"]
    icons = data.get("icons", {})

    coin_boxes = "".join(_coin_box(g, icons) for g in coins)

    usdt = pr.get("usdt_irt") or {}
    g18 = pr.get("gold_18k") or {}
    comm = pr.get("commodities") or {}
    xau, xag, oil = comm.get("XAU") or {}, comm.get("XAG") or {}, comm.get("OIL") or {}
    key_rows = (
        _key_row("usdt", "تتر / تومان", toman_fa(usdt.get("price")), usdt.get("change_24h", 0), rtl_price=True)
        + _key_row("g18", "طلای ۱۸ عیار", toman_fa(g18.get("price")), g18.get("change_24h", 0), rtl_price=True)
        + _key_row("XAU", "طلای جهانی", usd_fa(xau.get("price")), xau.get("change_24h", 0))
        + _key_row("XAG", "نقره", usd_fa(xag.get("price")), xag.get("change_24h", 0))
        + _key_row("OIL", "نفت خام", usd_fa(oil.get("price")), oil.get("change_24h", 0))
    )

    gl_html = (_gl_box("Gainers", _ICON_GAIN, gl.get("gainers", []), "up", icons)
               + _gl_box("Top losers", _ICON_LOSE, gl.get("losers", []), "down", icons))

    # لوگو: اگر فایلِ سفیدِ شفافِ شما (logo-white.png) موجود باشد همان استفاده می‌شود؛
    # وگرنه به logo-lockup.png برمی‌گردد. هیچ تغییری روی فایلِ لوگو اعمال نمی‌شود.
    _logo = _IMG / "logo-white.png"
    if not _logo.exists():
        _logo = _IMG / "logo-lockup.png"
    logo = _file_url(_logo)
    B = BRAND
    # ── ناحیهٔ امنِ استوریِ اینستاگرام ──────────────────────────────────────────
    # نوارِ شاخص‌های کلانِ بالا حذف شد و سرتیترِ «نمای کلی بازار» پایین‌تر آمد تا
    # بالای تصویر کاملاً خالی بماند (جای آیدی/لوگوی پیجِ اینستاگرام). پایین هم برای
    # نوارِ کامنت/ریپلای خالی می‌ماند. مقادیر برحسب px طراحی (۷۲۰×۱۲۸۰) ⇒ ×۳ در 4K.
    PAD_TOP = 120   # فضای خالیِ بالای استوری (هدر از این پایین‌تر شروع می‌شود)
    PAD_BOT = 128   # فضای خالیِ پایینِ استوری (نوارِ کامنت/ریپلای)

    return f"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<style>
{_font_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:720px;height:1280px;font-family:Dana,Vaz,sans-serif;
  background:{B['bg0']};color:{B['ink']};-webkit-font-smoothing:antialiased}}
.card{{width:720px;height:1280px;overflow:hidden;position:relative;
  background:
    radial-gradient(720px 440px at 92% -6%, rgba(25,195,179,.14), transparent 60%),
    radial-gradient(660px 480px at 0% 104%, rgba(45,99,176,.22), transparent 55%),
    linear-gradient(160deg, {B['bg0']} 0%, {B['bg1']} 55%, {B['bg2']} 100%)}}
/* لایهٔ تزئینیِ پس‌زمینه (چارت/هوش مصنوعی/کرهٔ زمین) */
.bg{{position:absolute;inset:0;z-index:0;pointer-events:none}}
.bg svg{{width:100%;height:100%;display:block}}
.hd,.body,.ft{{z-index:2}}
/* جلوهٔ شیشه‌ای (Glassmorphism) — شفاف‌تر تا پس‌زمینه کاملاً از پشتِ شیشه دیده شود */
.glass{{background:rgba(255,255,255,.022);
  backdrop-filter:blur(9px) saturate(140%);-webkit-backdrop-filter:blur(9px) saturate(140%);
  border:1px solid rgba(255,255,255,.20);
  box-shadow:0 10px 30px -20px rgba(0,0,0,.6), inset 0 1px 0 rgba(255,255,255,.15)}}
.up{{color:{B['up']}}} .down{{color:{B['down']}}} .flat{{color:{B['dim']}}}
/* هدر: عنوان راست، تاریخ چپ — پایین‌تر آمده تا بالای صفحه برای استوری خالی بماند */
.hd{{position:absolute;top:{PAD_TOP}px;left:24px;right:24px;
  display:flex;justify-content:space-between;align-items:flex-start;direction:rtl}}
.title{{font-size:36px;font-weight:900;color:#fff;letter-spacing:-.4px;line-height:1.05;text-align:right;
  text-shadow:0 2px 14px rgba(0,0,0,.35)}}
.title .ac{{color:{B['teal']}}}
.title small{{display:block;font-size:15px;font-weight:600;color:{B['muted']};margin-top:8px}}
.datepill{{background:linear-gradient(135deg,{B['navy']},{B['blue']});color:#fff;
  font-weight:800;font-size:17px;padding:11px 17px;border-radius:13px;white-space:nowrap;
  border:1px solid rgba(166,240,232,.3);box-shadow:0 6px 18px -8px rgba(0,0,0,.6)}}
/* بدنه */
.body{{position:absolute;top:{PAD_TOP + 80}px;left:24px;right:24px;bottom:{PAD_BOT + 86}px;
  overflow:hidden;display:flex;flex-direction:column;gap:11px}}
.sec{{display:flex;flex-direction:column;min-height:0}}
.sec--coins{{flex:5}} .sec--keys{{flex:7}} .sec--gl{{flex:4}}
.sec h3{{font-size:19px;font-weight:800;color:{B['glow']};margin:0 2px 9px;display:flex;
  align-items:center;gap:9px;text-shadow:0 2px 10px rgba(0,0,0,.3)}}
.sec h3::before{{content:"";width:5px;height:20px;border-radius:3px;
  background:linear-gradient(180deg,{B['teal']},{B['blue']})}}
/* شبکهٔ ۳×۲ ارزهای برتر (باکس‌های مربع شیشه‌ای) */
.coingrid{{flex:1;min-height:0;display:grid;grid-template-columns:repeat(3,1fr);
  grid-template-rows:repeat(2,1fr);gap:11px}}
.coin{{min-height:0;overflow:hidden;border-radius:18px;padding:8px 13px;
  display:flex;align-items:center;gap:12px;direction:ltr}}
.coin__ic{{width:48px;height:48px;border-radius:50%;overflow:hidden;flex:none;display:grid;
  place-items:center;background:rgba(255,255,255,.10)}}
.coin__ic img{{width:100%;height:100%;object-fit:cover}}
.coin__txt{{display:flex;flex-direction:column;align-items:flex-start;gap:6px;min-width:0;line-height:1.08}}
.coin__nm{{font-weight:800;font-size:21px;color:#fff}}
.coin__price{{font-weight:900;font-size:21px;color:#fff;direction:ltr;letter-spacing:-.2px}}
.coin .chip{{font-size:15px;padding:3px 10px}}
/* قیمت‌های کلیدی — آیکونِ چپ، و سمتِ راست: نام / قیمت / درصدِ تغییر (عمودی) */
.list{{flex:1;min-height:0;display:flex;flex-direction:column;gap:8px}}
.kr{{flex:1;min-height:0;overflow:hidden;border-radius:16px;padding:6px 20px;
  display:flex;align-items:center;justify-content:space-between}}
.kr__r{{display:flex;align-items:center;gap:14px;min-width:0}}
.kr__ic{{width:46px;height:46px;border-radius:50%;overflow:hidden;flex:none;display:grid;
  place-items:center;background:rgba(255,255,255,.10)}}
.kr__ic img{{width:100%;height:100%;object-fit:cover}}
.kr__nm{{font-weight:800;font-size:24px;color:#fff}}
.kr__l{{display:flex;align-items:center;gap:12px;direction:ltr}}
.kr__price{{font-weight:900;font-size:25px;color:#fff;letter-spacing:-.3px}}
.kr__price--rtl{{direction:rtl}}
.kr .chip{{font-size:16px;padding:3px 11px}}
.chip{{font-weight:800;font-size:13px;padding:3px 9px;border-radius:8px}}
.chip--up{{color:{B['up']};background:rgba(22,199,132,.16)}}
.chip--down{{color:{B['down']};background:rgba(234,57,67,.16)}}
.chip--flat{{color:{B['dim']};background:rgba(124,154,200,.16)}}
/* Gainers / Top losers — کنار هم؛ پس‌زمینهٔ کندلِ سبز(چپ)/قرمز(راست) */
.glwrap{{flex:1;min-height:0;display:flex;gap:13px;direction:ltr}}
.gl{{position:relative;flex:1;min-height:0;border-radius:16px;overflow:hidden;display:flex;flex-direction:column}}
.gl__cbg{{position:absolute;inset:0;width:100%;height:100%;z-index:0;pointer-events:none}}
.gl__hd{{position:relative;z-index:1;display:flex;align-items:center;gap:9px;padding:10px 15px;font-weight:800;font-size:18px;color:#fff}}
.gl--up .gl__hd{{background:linear-gradient(90deg,rgba(22,199,132,.34),rgba(22,199,132,0))}}
.gl--down .gl__hd{{background:linear-gradient(90deg,rgba(234,57,67,.34),rgba(234,57,67,0))}}
.gl__hi{{width:20px;height:20px;display:grid;place-items:center;flex:none}}
.gl__hi svg{{width:20px;height:20px}}
/* ستون‌بندی: آیکون+نماد (چپ) / قیمت (وسطِ باکس) / چیپِ درصدِ تغییر (راستِ قیمت) */
.gl__row{{position:relative;z-index:1;min-height:0;display:grid;
  grid-template-columns:auto 1fr auto;align-items:center;gap:10px;
  padding:7px 14px;border-top:1px solid rgba(255,255,255,.06)}}
.gl__l{{display:flex;align-items:center;gap:9px;min-width:0}}
.gl__ic{{width:30px;height:30px;border-radius:50%;overflow:hidden;flex:none;display:grid;place-items:center;background:rgba(255,255,255,.10)}}
.gl__ic img{{width:100%;height:100%;object-fit:cover}}
.gl__l b{{font-size:17px;font-weight:800;color:#fff}}
.gl__q{{font-size:12px;color:{B['dim']};font-weight:600}}
.gl__p{{font-weight:800;font-size:17px;color:#fff;text-align:center}}
.gl .chip{{font-size:14px;padding:2px 9px}}
.ic-badge{{color:#fff;font-weight:900;font-size:12px;background:linear-gradient(135deg,{B['blue']},{B['navy']})}}
/* فوتر: شبکه‌های اجتماعی چپ، لوگو راست */
.ft{{position:absolute;left:24px;right:24px;bottom:{PAD_BOT}px;height:74px;
  display:flex;align-items:center;justify-content:space-between;direction:ltr;
  padding-top:10px;border-top:1px solid {B['line']}}}
.ft__social{{display:flex;align-items:center;gap:9px}}
.soc{{width:34px;height:34px;border-radius:9px;display:grid;place-items:center;color:#dbe7f7;
  background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.14)}}
.soc svg{{width:18px;height:18px;display:block}}
.ft__id{{color:{B['teal2']};font-family:Quick,Vaz,sans-serif;font-weight:700;font-size:25px;
  margin-left:6px;letter-spacing:.3px}}
.brand{{background:transparent;padding:0;display:flex;align-items:center}}
.brand img{{height:66px;display:block}}
</style></head>
<body><div class="card">
  <div class="bg">{_BG_SVG}</div>
  <div class="hd">
    <div class="title">نمای کلی <span class="ac">بازار</span>
      <small>گزارش بازار کریپتو · کریپتو‌اسمارت</small></div>
    <div class="datepill">{data['shamsi']}</div>
  </div>
  <div class="body">
    <section class="sec sec--coins"><h3>ارزهای برتر بازار</h3><div class="coingrid">{coin_boxes}</div></section>
    <section class="sec sec--keys"><h3>قیمت‌های کلیدی</h3><div class="list">{key_rows}</div></section>
    <section class="sec sec--gl"><h3>بیشترین رشد و افت بازار</h3><div class="glwrap">{gl_html}</div></section>
  </div>
  <div class="ft">
    <div class="ft__social">
      <span class="soc">{_SOC_TG}</span><span class="soc">{_SOC_IG}</span><span class="soc">{_SOC_YT}</span>
      <span class="ft__id">@Cryptosmart_org</span>
    </div>
    <div class="brand"><img src="{logo}" alt="CryptoSmart"></div>
  </div>
</div></body></html>"""


# ───────────────────────── رِندر با Chromium ─────────────────────────
def _chrome_bin() -> str:
    env = os.environ.get("CHROMIUM_BIN") or os.environ.get("CHROME_BIN")
    if env and Path(env).exists():
        return env
    for g in sorted(glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"), reverse=True):
        return g
    # کرومیومِ غیرِ snap ترجیح دارد: نسخهٔ snap به‌خاطر confinement فایل‌های پروژه
    # (لوگو/فونت/آیکون در /var/www) را نمی‌تواند بخواند و /tmp خصوصی دارد.
    names = ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser")
    snap_fallback = None
    for name in names:
        p = shutil.which(name)
        if not p:
            continue
        if "/snap/" in os.path.realpath(p):
            snap_fallback = snap_fallback or p
            continue
        return p
    if snap_fallback:
        return snap_fallback
    raise RuntimeError("Chromium binary not found (set CHROMIUM_BIN in .env)")


# ابعاد طراحی (CSS px) و ضریب مقیاس برای خروجی عمودیِ ۹:۱۶.
# ضریب پیش‌فرض ۳ ⇒ 4K (۲۱۶۰×۳۸۴۰). روی سرورِ کم‌رم می‌توان با MARKET_CARD_SCALE=2
# آن را به ۱۴۴۰×۲۵۶۰ کاهش داد تا مصرف حافظهٔ کرومیوم کمتر شود.
_W, _H, _SCALE = 720, 1280, 3
# هِدلسِ کرومیوم ارتفاع viewport را حدود ۷۵px کمتر از window می‌گیرد؛ پنجره را
# بلندتر می‌سازیم تا کلِ کارت (با فوتر) داخل viewport بیفتد و بعد دقیق برش می‌زنیم.
_MARGIN = 120
# فقط یک رِندر هم‌زمان (جلوگیری از فشار حافظه/کرش هنگام چند درخواست هم‌زمان).
_RENDER_LOCK = asyncio.Lock()
# مهلتِ سختِ رِندر (ثانیه)؛ اگر کرومیوم گیر کند، کشته می‌شود تا برنامه بلوکه نشود.
_RENDER_TIMEOUT = 75.0


def _render_scale() -> int:
    try:
        return max(1, min(4, int(os.environ.get("MARKET_CARD_SCALE", str(_SCALE)))))
    except Exception:
        return _SCALE


async def render_png(out_path: Path) -> Path:
    """HTML را می‌سازد و با Chromium بدون‌هد، تصویرِ عمودیِ ۹:۱۶ را اسکرین‌شات می‌گیرد.

    رِندرها سریالی می‌شوند، با مهلتِ سخت و پروفایلِ موقتِ مجزا (تا قفلِ پروفایل یا
    گیرکردن کرومیوم هیچ‌گاه برنامه را پایین نیاورد).
    """
    async with _RENDER_LOCK:
        return await _render_once(out_path)


async def _render_once(out_path: Path) -> Path:
    scale = _render_scale()
    data = await gather()
    html = build_html(data)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    workdir = tempfile.mkdtemp(prefix="mcard-")
    html_path = os.path.join(workdir, "card.html")
    raw = os.path.join(workdir, "raw.png")
    Path(html_path).write_text(html, encoding="utf-8")
    try:
        cmd = [
            _chrome_bin(), "--headless=new", "--no-sandbox", "--disable-gpu",
            "--disable-software-rasterizer", "--disable-dev-shm-usage", "--no-zygote",
            "--disable-extensions", "--disable-background-networking",
            "--hide-scrollbars", "--allow-file-access-from-files",
            f"--user-data-dir={os.path.join(workdir, 'prof')}",
            f"--crash-dumps-dir={workdir}",
            f"--force-device-scale-factor={scale}",
            f"--window-size={_W},{_H + _MARGIN}",
            f"--screenshot={raw}", "--virtual-time-budget=4000",
            f"file://{html_path}",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=_RENDER_TIMEOUT)
        except asyncio.TimeoutError:
            for _kill in (proc.kill,):
                try:
                    _kill()
                except Exception:  # noqa: BLE001
                    pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except Exception:  # noqa: BLE001
                pass
            raise RuntimeError("Chromium render timed out")
        if not os.path.exists(raw) or os.path.getsize(raw) == 0:
            raise RuntimeError(f"Chromium screenshot failed: {(stderr or b'').decode(errors='ignore')[-400:]}")

        def _crop() -> None:
            from PIL import Image
            with Image.open(raw) as im:
                im.convert("RGB").crop((0, 0, _W * scale, _H * scale)).save(out_path, "PNG")
        await asyncio.to_thread(_crop)
        return out_path
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
