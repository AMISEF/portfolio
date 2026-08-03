"""
نقطهٔ ورود CryptoSmart Hub (FastAPI).
اجرا:  uvicorn app.main:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import asyncio

from app import db
from app.config import settings
from app.routers import (admin, advisor, auth, bot, market, pages, portfolio,
                         settings_api)
from app.services import (algohub_bot, broadcast_job, market_card_job,
                          price_alerts_job, signals_retention, telegram_signals)

app = FastAPI(title=settings.app_name, debug=settings.debug)

# پشتیبانِ فشرده‌سازی برای زمانی که uvicorn مستقیم (بدونِ gzipِ nginx) پاسخ می‌دهد.
app.add_middleware(GZipMiddleware, minimum_size=512)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


# ── اپلیکیشن نصب‌شدنی ALGO HUB (PWA) ──────────────────
# منیفست و سرویس‌وورکر باید روی ریشهٔ دامنه سرو شوند تا دامنهٔ پوشش «/»
# باشد و ژورنال (زیرِ /journal) هم بخشی از همان اپ ALGO HUB دیده شود.

# آیکن رسمی اپ: نسخهٔ دارای پس‌زمینهٔ آبی (برای صفحهٔ اصلی iOS و اندروید).
_ICON_CANDIDATES = [
    os.getenv("ALGOHUB_ICON_PATH", ""),
    "ALGOHUB-icon.png",
    "/var/www/portfolio/ALGOHUB-icon.png",
    "app/static/img/algohub-icon.png",
]

# لوگوی شفافِ ALGO HUB: برای صفحهٔ شروع (اسپلش) و نمایش درونِ اپ.
_SPLASH_CANDIDATES = [
    os.getenv("ALGOHUB_LOGO_PATH", ""),
    "ALGOHUB-LOGO.png",
    "app/static/img/algohub-logo.png",
    "/var/www/trading-journal/ALGOHUB-LOGO.png",
    "../trading-journal/ALGOHUB-LOGO.png",
    "app/static/img/logo.png",
]

# اندازه‌های مجاز (تا ورودیِ دلخواه باعثِ ساختِ بی‌پایانِ تصویر نشود).
_ICON_SIZES = (48, 72, 96, 128, 144, 152, 167, 180, 192, 256, 384, 512, 640, 768, 1024)

# کلیدِ کش شاملِ «نسخهٔ فایل» است؛ بنابراین به محض اینکه تصویرِ روی دیسک
# عوض شود، کلید هم عوض می‌شود و تصویرِ جدید بدون ریستارت سرو می‌شود.
_ICON_CACHE: dict[tuple[str, int, str], bytes] = {}


def _first_existing(candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def _version_of(kind: str) -> str:
    """امضای کوتاهِ فایل (اندازه + زمان تغییر).

    هر بار که تصویرِ تازه‌ای آپلود شود، این رشته عوض می‌شود و چون داخلِ
    آدرسِ آیکن می‌آید، مرورگر و سیستم‌عامل مجبور می‌شوند دوباره دانلود کنند.
    """
    source = _first_existing(_ICON_CANDIDATES if kind == "icon" else _SPLASH_CANDIDATES)
    if not source:
        return "0"
    try:
        stat = Path(source).stat()
        return f"{stat.st_size}-{int(stat.st_mtime)}"
    except OSError:
        return "0"


def _render(kind: str, size: int) -> bytes | None:
    """تغییر اندازهٔ تصویر به یک PNG مربعی (با کش در حافظه).

    اگر Pillow در دسترس نباشد یا خطایی رخ دهد، None برمی‌گردد و فایلِ خام سرو می‌شود.
    """
    version = _version_of(kind)
    cached = _ICON_CACHE.get((kind, size, version))
    if cached is not None:
        return cached

    source = _first_existing(_ICON_CANDIDATES if kind == "icon" else _SPLASH_CANDIDATES)
    if not source:
        return None

    try:
        from PIL import Image  # type: ignore

        with Image.open(source) as img:
            img = img.convert("RGBA")
            side = max(img.width, img.height)
            if img.width != img.height:
                canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
                canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
                img = canvas
            img = img.resize((size, size), Image.LANCZOS)

            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            data = buf.getvalue()
    except Exception:  # noqa: BLE001
        return None

    # فقط نسخهٔ جاری را نگه می‌داریم؛ نسخه‌های قدیمی دور ریخته می‌شوند.
    for key in [k for k in _ICON_CACHE if k[0] == kind and k[2] != version]:
        _ICON_CACHE.pop(key, None)
    _ICON_CACHE[(kind, size, version)] = data
    return data


def _png_response(kind: str, size: int, candidates: list[str], versioned: bool):
    if size not in _ICON_SIZES:
        size = 512

    # آدرسِ نسخه‌دار (شامل ?v=) را می‌توان مدت‌ها کش کرد؛ آدرسِ بدونِ نسخه
    # هرگز نباید کش شود، وگرنه آپلودِ تصویر جدید دیده نمی‌شود.
    cache_control = (
        "public, max-age=31536000, immutable" if versioned else "no-cache, must-revalidate"
    )

    data = _render(kind, size)
    if data is not None:
        return Response(
            content=data,
            media_type="image/png",
            headers={"Cache-Control": cache_control},
        )

    source = _first_existing(candidates)
    if source:
        return FileResponse(
            source,
            media_type="image/png",
            headers={"Cache-Control": cache_control},
        )
    raise HTTPException(status_code=404, detail="image not found")


@app.get("/manifest.webmanifest", include_in_schema=False)
async def pwa_manifest() -> JSONResponse:
    """منیفست پویا: آدرسِ آیکن‌ها همیشه برچسبِ نسخهٔ فایلِ فعلی را دارد."""
    with open("app/static/manifest.webmanifest", encoding="utf-8") as fh:
        manifest = json.load(fh)

    version = _version_of("icon")
    manifest["icons"] = [
        {
            "src": f"/app-icon?size=192&v={version}",
            "sizes": "192x192",
            "type": "image/png",
            "purpose": "any",
        },
        {
            "src": f"/app-icon?size=512&v={version}",
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "any",
        },
        {
            "src": f"/app-icon?size=192&v={version}",
            "sizes": "192x192",
            "type": "image/png",
            "purpose": "maskable",
        },
        {
            "src": f"/app-icon?size=512&v={version}",
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "maskable",
        },
    ]

    return JSONResponse(
        manifest,
        media_type="application/manifest+json",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


@app.get("/sw.js", include_in_schema=False)
async def pwa_service_worker() -> FileResponse:
    return FileResponse(
        "app/static/sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
    )


@app.get("/app-icon", include_in_schema=False)
async def pwa_app_icon(size: int = 512, v: str | None = None):
    """آیکن اپ (پس‌زمینهٔ آبی) — روی صفحهٔ اصلی گوشی و اعلان‌ها."""
    return _png_response("icon", size, _ICON_CANDIDATES, versioned=bool(v))


@app.get("/app-splash", include_in_schema=False)
async def pwa_app_splash(size: int = 512, v: str | None = None):
    """لوگوی شفاف — صفحهٔ شروعِ اپ و نمایشِ درون‌برنامه‌ای."""
    return _png_response("splash", size, _SPLASH_CANDIDATES, versioned=bool(v))


@app.get("/app-icon/debug", include_in_schema=False)
async def pwa_app_icon_debug():
    """عیب‌یابی: دقیقاً چه فایلی به‌عنوان آیکن/اسپلش سرو می‌شود؟"""

    def describe(kind: str, candidates: list[str]) -> dict:
        found = _first_existing(candidates)
        return {
            "using": found,
            "bytes": Path(found).stat().st_size if found else None,
            "version": _version_of(kind),
            "candidates": [
                {"path": c, "exists": bool(c) and Path(c).is_file()}
                for c in candidates
                if c
            ],
        }

    try:
        from PIL import Image  # type: ignore

        pillow = getattr(Image, "__version__", "installed")
    except Exception:  # noqa: BLE001
        pillow = None

    return {
        "cwd": os.getcwd(),
        "pillow": pillow,
        "icon": describe("icon", _ICON_CANDIDATES),
        "splash": describe("splash", _SPLASH_CANDIDATES),
        "cached": sorted(f"{k[0]}:{k[1]}:{k[2]}" for k in _ICON_CACHE),
    }


@app.get("/offline", include_in_schema=False)
async def pwa_offline() -> FileResponse:
    return FileResponse("app/static/offline.html", media_type="text/html")


app.include_router(pages.router)
app.include_router(market.router)
app.include_router(portfolio.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(advisor.router)
app.include_router(bot.router)
app.include_router(settings_api.router)


@app.on_event("startup")
async def _startup() -> None:
    db.init_db()
    # پاک‌سازیِ تحلیل‌های منقضی: یک‌بار در استارت‌آپ و سپس هر ساعت.
    asyncio.create_task(signals_retention.loop())

    # پیش‌ساختِ آیکن‌های اپ تا اولین درخواست کند نشود.
    async def _warm_icons() -> None:
        for size in (180, 192, 512):
            await asyncio.to_thread(_render, "icon", size)
        await asyncio.to_thread(_render, "splash", 512)

    asyncio.create_task(_warm_icons())

    # ثبت وب‌هوکِ ربات سیگنال‌ها (بدون بلوکه‌کردن استارت‌آپ).
    if settings.signals_bot_token:
        async def _init_signals() -> None:
            try:
                await telegram_signals.register_webhook()
            except Exception:  # noqa: BLE001
                pass
        asyncio.create_task(_init_signals())
        # زمان‌بندِ روزانهٔ تصویر «نمای کلی بازار» (هر روز ۱۱:۰۰ تهران).
        asyncio.create_task(market_card_job.daily_loop())

    # ربات «الگو هاب»: ثبتِ وب‌هوک + حلقهٔ پایشِ قیمت برای هشدارهای خرید.
    if settings.algohub_bot_token:
        async def _init_algohub() -> None:
            try:
                await algohub_bot.register_webhook()
            except Exception:  # noqa: BLE001
                pass
        asyncio.create_task(_init_algohub())
        asyncio.create_task(price_alerts_job.loop())
        # کارگرِ صفِ پیام همگانی: ارسالِ تدریجی با سقفِ ساعتی.
        asyncio.create_task(broadcast_job.loop())


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "build": "p2-portfolio-1"}
