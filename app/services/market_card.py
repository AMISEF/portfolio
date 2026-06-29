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
    for name, w in weights.items():
        uri = _data_uri(_FONTS / f"Vazirmatn-{name}.woff2", "font/woff2")
        if uri:
            out.append(f"@font-face{{font-family:Vaz;src:url({uri}) format('woff2');"
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


async def gather() -> dict[str, Any]:
    from app.routers import market as mkt
    from app.services import coinmarketcap

    coins_d, prices_d, gl_d, macro_d = await asyncio.gather(
        _safe(toobit.top_coins()),
        _safe(mkt.prices()),
        _safe(toobit.gainers_losers()),
        _safe(coinmarketcap.macro()),
    )

    coins = (coins_d.get("coins") if isinstance(coins_d, dict) else None) \
        or mock_data.toobit_top_coins()["coins"]
    coins = coins[:5]
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


# ───────────────────────── ساخت HTML ─────────────────────────
def _chip(ch: float) -> str:
    cls = "up" if ch > 0 else ("down" if ch < 0 else "flat")
    return f'<span class="chip chip--{cls}">{pct_fa(ch)}</span>'


def _coin_row(g: dict, icons: dict) -> str:
    sym = g.get("symbol", "")
    return (
        '<div class="row">'
        '<div class="row__r">' + _icon_html(sym, "row__ic", icons) +
        f'<span class="row__nm">{sym}</span></div>'
        '<div class="row__l">'
        f'<span class="row__price">{usd_fa(g.get("price"))}</span>'
        + _chip(g.get("change_24h", 0)) + '</div></div>'
    )


def _key_row(key: str, name: str, sub: str, price_html: str, ch: float) -> str:
    return (
        '<div class="row">'
        '<div class="row__r">' + _metal_icon(key, "row__ic") +
        f'<span class="row__nm">{name}<small>{sub}</small></span></div>'
        '<div class="row__l">'
        f'<span class="row__price">{price_html}</span>' + _chip(ch) + '</div></div>'
    )


def _gl_row(it: dict, icons: dict) -> str:
    ch = float(it.get("change_24h", 0))
    cls = "up" if ch >= 0 else "down"
    return (
        '<div class="gl__row">'
        '<span class="gl__l">' + _icon_html(it.get("symbol", ""), "gl__ic", icons) +
        f'<b>{it.get("symbol","")}</b><span class="gl__q">/USDT</span></span>'
        '<span class="gl__rr">'
        f'<span class="gl__p">{_usd_num(it.get("price"))}</span>'
        f'<span class="gl__c {cls}">{ch:+.2f}%</span></span>'
        '</div>'
    )


def _gl_box(title: str, icon: str, rows: list[dict], kind: str, icons: dict) -> str:
    body = "".join(_gl_row(r, icons) for r in rows[:settings.toobit_gl_count])
    return (
        f'<div class="gl gl--{kind}">'
        f'<div class="gl__hd"><span class="gl__hi">{icon}</span>'
        f'<span class="gl__t">{title}</span></div>{body}</div>'
    )


def build_html(data: dict[str, Any]) -> str:
    coins, pr, gl, mac = data["coins"], data["prices"], data["gl"], data["macro"]
    icons = data.get("icons", {})

    coin_rows = "".join(_coin_row(g, icons) for g in coins)

    usdt = pr.get("usdt_irt") or {}
    g18 = pr.get("gold_18k") or {}
    comm = pr.get("commodities") or {}
    xau, xag, oil = comm.get("XAU") or {}, comm.get("XAG") or {}, comm.get("OIL") or {}
    key_rows = (
        _key_row("usdt", "تتر / تومان", "تومان", toman_fa(usdt.get("price")), usdt.get("change_24h", 0))
        + _key_row("g18", "طلای ۱۸ عیار", "هر گرم", toman_fa(g18.get("price")), g18.get("change_24h", 0))
        + _key_row("XAU", "طلای جهانی", "اونس", usd_fa(xau.get("price")), xau.get("change_24h", 0))
        + _key_row("XAG", "نقره", "اونس", usd_fa(xag.get("price")), xag.get("change_24h", 0))
        + _key_row("OIL", "نفت خام", "بشکه", usd_fa(oil.get("price")), oil.get("change_24h", 0))
    )

    gl_html = (_gl_box("Gainers", "▲", gl.get("gainers", []), "up", icons)
               + _gl_box("Top losers", "▼", gl.get("losers", []), "down", icons))

    mc, vol, dom = mac.get("market_cap") or {}, mac.get("volume_24h") or {}, mac.get("dominance") or {}

    def stat(label, val, ch=None):
        c = ""
        if ch is not None and ch != 0:
            c = f'<span class="st__c {"up" if ch > 0 else "down"}">{pct_fa(ch)}</span>'
        return (f'<span class="st"><span class="st__l">{label}</span>'
                f'<span class="st__v">{val}</span>{c}</span>')

    stats = (
        stat("ارزش بازار", big_fa(mc.get("value")), mc.get("change_24h"))
        + stat("حجم ۲۴ساعته", big_fa(vol.get("value")), vol.get("change_24h"))
        + stat("دامیننس BTC", _fa(f"{dom.get('btc', 0):.1f}") + "٪", dom.get("btc_change_24h"))
        + stat("دامیننس ETH", _fa(f"{dom.get('eth', 0):.1f}") + "٪")
    )

    logo = _file_url(_IMG / "logo-lockup.png")
    B = BRAND

    return f"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<style>
{_font_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:720px;height:1280px;font-family:Vaz,sans-serif;
  background:{B['bg0']};color:{B['ink']};-webkit-font-smoothing:antialiased}}
.card{{width:720px;height:1280px;overflow:hidden;position:relative;
  background:
    radial-gradient(700px 420px at 92% -6%, rgba(25,195,179,.12), transparent 60%),
    radial-gradient(640px 460px at 0% 104%, rgba(45,99,176,.20), transparent 55%),
    linear-gradient(160deg, {B['bg0']} 0%, {B['bg1']} 55%, {B['bg2']} 100%)}}
/* هدر: عنوان راست، تاریخ چپ */
.hd{{position:absolute;top:20px;left:24px;right:24px;
  display:flex;justify-content:space-between;align-items:flex-start;direction:rtl}}
.title{{font-size:31px;font-weight:900;color:#fff;letter-spacing:-.4px;line-height:1.05;text-align:right}}
.title .ac{{color:{B['teal']}}}
.title small{{display:block;font-size:12.5px;font-weight:600;color:{B['dim']};margin-top:7px}}
.datepill{{background:linear-gradient(135deg,{B['navy']},{B['blue']});color:#fff;
  font-weight:800;font-size:14.5px;padding:9px 15px;border-radius:12px;white-space:nowrap;
  border:1px solid rgba(166,240,232,.25);box-shadow:0 6px 18px -8px rgba(0,0,0,.6)}}
/* شاخص‌ها */
.stats{{position:absolute;top:90px;left:24px;right:24px;
  display:flex;flex-wrap:wrap;gap:8px 18px;padding:10px 14px;border-radius:12px;
  background:rgba(255,255,255,.045);border:1px solid {B['line']};direction:rtl}}
.st{{display:inline-flex;align-items:center;gap:6px;font-size:12.5px}}
.st__l{{color:{B['dim']};font-weight:600}}
.st__v{{color:#fff;font-weight:800}}
.up{{color:{B['up']}}} .down{{color:{B['down']}}} .flat{{color:{B['dim']}}}
/* بدنه */
.body{{position:absolute;top:150px;left:24px;right:24px;bottom:104px;
  overflow:hidden;display:flex;flex-direction:column;gap:11px}}
.sec{{display:flex;flex-direction:column;min-height:0}}
.sec--coins{{flex:5}} .sec--keys{{flex:5}} .sec--gl{{flex:4}}
.sec h3{{font-size:16px;font-weight:800;color:{B['glow']};margin:0 2px 7px;display:flex;
  align-items:center;gap:8px}}
.sec h3::before{{content:"";width:4px;height:17px;border-radius:3px;
  background:linear-gradient(180deg,{B['teal']},{B['blue']})}}
.list{{flex:1;min-height:0;display:flex;flex-direction:column;gap:8px}}
/* ردیف ارز/قیمت */
.row{{flex:1;min-height:0;overflow:hidden;background:linear-gradient(160deg,{B['card']},{B['card2']});
  border:1px solid {B['line']};border-radius:15px;padding:8px 15px;
  display:flex;align-items:center;justify-content:space-between;
  box-shadow:0 8px 20px -15px rgba(0,0,0,.75)}}
.row__r{{display:flex;align-items:center;gap:12px;min-width:0}}
.row__ic{{width:34px;height:34px;border-radius:50%;overflow:hidden;flex:none;display:grid;place-items:center;background:#fff1}}
.row__ic img{{width:100%;height:100%;object-fit:cover}}
.row__nm{{font-weight:800;font-size:17px;color:#fff;line-height:1.2}}
.row__nm small{{display:block;font-weight:600;font-size:11.5px;color:{B['dim']}}}
.row__l{{display:flex;flex-direction:column;align-items:flex-start;gap:5px;direction:ltr}}
.row__price{{font-weight:900;font-size:19px;color:#fff;letter-spacing:-.2px}}
.chip{{font-weight:800;font-size:12.5px;padding:3px 9px;border-radius:8px}}
.chip--up{{color:{B['up']};background:rgba(22,199,132,.15)}}
.chip--down{{color:{B['down']};background:rgba(234,57,67,.15)}}
.chip--flat{{color:{B['dim']};background:rgba(124,154,200,.15)}}
/* Gainers / Top losers — کنار هم، سبک توبیت (LTR) */
.glwrap{{flex:1;min-height:0;display:flex;gap:13px;direction:ltr}}
.gl{{flex:1;min-height:0;border-radius:15px;overflow:hidden;border:1px solid {B['line']};
  background:{B['card2']};display:flex;flex-direction:column;box-shadow:0 8px 20px -15px rgba(0,0,0,.75)}}
.gl__hd{{display:flex;align-items:center;gap:8px;padding:9px 14px;font-weight:800;font-size:15px;color:#fff}}
.gl--up .gl__hd{{background:linear-gradient(90deg,rgba(22,199,132,.32),rgba(22,199,132,.02))}}
.gl--down .gl__hd{{background:linear-gradient(90deg,rgba(234,57,67,.32),rgba(234,57,67,.02))}}
.gl__hi{{font-size:11px}} .gl--up .gl__hi{{color:{B['up']}}} .gl--down .gl__hi{{color:{B['down']}}}
.gl__row{{flex:1;min-height:0;display:flex;align-items:center;justify-content:space-between;
  padding:6px 13px;border-top:1px solid rgba(255,255,255,.05)}}
.gl__l{{display:flex;align-items:center;gap:8px;min-width:0}}
.gl__ic{{width:26px;height:26px;border-radius:50%;overflow:hidden;flex:none;display:grid;place-items:center;background:#fff1}}
.gl__ic img{{width:100%;height:100%;object-fit:cover}}
.gl__l b{{font-size:14px;font-weight:800;color:#fff}}
.gl__q{{font-size:11px;color:{B['dim']};font-weight:600}}
.gl__rr{{display:flex;flex-direction:column;align-items:flex-end;gap:1px}}
.gl__p{{font-weight:800;font-size:13.5px;color:#fff}}
.gl__c{{font-weight:800;font-size:12px}}
.ic-badge{{color:#fff;font-weight:900;font-size:11px;background:linear-gradient(135deg,{B['blue']},{B['navy']})}}
/* فوتر */
.ft{{position:absolute;left:24px;right:24px;bottom:18px;height:74px;
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;
  padding-top:11px;border-top:1px solid {B['line']}}}
.brand{{background:{B['light']};border-radius:12px;padding:7px 16px;display:flex;align-items:center;
  box-shadow:0 6px 18px -8px rgba(0,0,0,.6)}}
.brand img{{height:26px;display:block}}
.ft__meta{{color:{B['teal2']};font-weight:700;font-size:13px;direction:ltr}}
.ft__meta span{{color:{B['dim']};font-weight:600;margin:0 6px}}
</style></head>
<body><div class="card">
  <div class="hd">
    <div class="title">نمای کلی <span class="ac">بازار</span>
      <small>گزارش روزانهٔ بازار کریپتو · کریپتو‌اسمارت</small></div>
    <div class="datepill">{data['shamsi']}</div>
  </div>
  <div class="stats">{stats}</div>
  <div class="body">
    <section class="sec sec--coins"><h3>ارزهای برتر بازار</h3><div class="list">{coin_rows}</div></section>
    <section class="sec sec--keys"><h3>قیمت‌های کلیدی</h3><div class="list">{key_rows}</div></section>
    <section class="sec sec--gl"><h3>بیشترین رشد و افت بازار</h3><div class="glwrap">{gl_html}</div></section>
  </div>
  <div class="ft">
    <div class="brand"><img src="{logo}" alt="CryptoSmart"></div>
    <div class="ft__meta">@Portfolio_CryptoSmart<span>•</span>portfolio.cryptosmart.site</div>
  </div>
</div></body></html>"""


# ───────────────────────── رِندر با Chromium ─────────────────────────
def _chrome_bin() -> str:
    env = os.environ.get("CHROMIUM_BIN") or os.environ.get("CHROME_BIN")
    if env and Path(env).exists():
        return env
    for g in sorted(glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"), reverse=True):
        return g
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        p = shutil.which(name)
        if p:
            return p
    raise RuntimeError("Chromium binary not found (set CHROMIUM_BIN in .env)")


# ابعاد طراحی (CSS px) و ضریب مقیاس برای خروجی 4K عمودی (۹:۱۶ ⇒ ۲۱۶۰×۳۸۴۰)
_W, _H, _SCALE = 720, 1280, 3
# هِدلسِ کرومیوم ارتفاع viewport را حدود ۷۵px کمتر از window می‌گیرد؛ پنجره را
# بلندتر می‌سازیم تا کلِ کارت (با فوتر) داخل viewport بیفتد و بعد دقیق برش می‌زنیم.
_MARGIN = 120


async def render_png(out_path: Path) -> Path:
    """HTML را می‌سازد و با Chromium بدون‌هد در ۴K عمودی (۲۱۶۰×۳۸۴۰، ۹:۱۶) اسکرین‌شات می‌گیرد."""
    data = await gather()
    html = build_html(data)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html)
        html_path = f.name
    raw = out_path.with_suffix(".raw.png")
    try:
        cmd = [
            _chrome_bin(), "--headless=new", "--no-sandbox", "--disable-gpu",
            "--hide-scrollbars", "--disable-dev-shm-usage", "--allow-file-access-from-files",
            f"--force-device-scale-factor={_SCALE}",
            f"--window-size={_W},{_H + _MARGIN}",
            f"--screenshot={raw}", "--virtual-time-budget=3000",
            f"file://{html_path}",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        _, stderr = await proc.communicate()
        if not raw.exists() or raw.stat().st_size == 0:
            raise RuntimeError(f"Chromium screenshot failed: {stderr.decode()[-500:]}")
        # برش دقیق به ۲۱۶۰×۳۸۴۰ (حذفِ حاشیهٔ اضافیِ پایین)
        from PIL import Image
        img = Image.open(raw).convert("RGB")
        img = img.crop((0, 0, _W * _SCALE, _H * _SCALE))
        img.save(out_path, "PNG")
        return out_path
    finally:
        for p in (html_path, raw):
            try:
                os.unlink(p)
            except Exception:
                pass
