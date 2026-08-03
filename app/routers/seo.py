"""
سئوی فنی ALGO HUB — طبق راهنمای رسمی جستجوی گوگل.

  GET /robots.txt
  GET /sitemap.xml

قواعدی که رعایت شده:
  • صفحات خصوصی (پنل، API، تنظیمات) از ایندکس خارج می‌شوند.
  • هر آدرس در سایت‌مپ فقط یک نسخهٔ کانونیکال دارد.
  • اولویت و بسامد تغییر واقعی است، نه همه ۱۰۰٪.
"""
from __future__ import annotations

import datetime as _dt

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, Response

router = APIRouter()

# آدرس کانونیکال سایت (بدون اسلش پایانی).
SCHEME = "https" + "://"
HUB_HOST = "algohub.cryptosmart.site"
JOURNAL_HOST = "trading-journal.cryptosmart.site"
SITE = SCHEME + HUB_HOST
JOURNAL = SCHEME + JOURNAL_HOST

# (مسیر، اولویت، بسامد تغییر)
_PUBLIC_PAGES = [
    ("/", "1.0", "daily"),
    ("/portfolio", "0.9", "daily"),
    ("/subscription", "0.8", "weekly"),
    ("/exclusive", "0.7", "daily"),
]

_JOURNAL_PAGES = [
    ("/journal", "0.9", "daily"),
    ("/journal/register", "0.7", "monthly"),
    ("/journal/login", "0.5", "monthly"),
    ("/journal/subscription", "0.8", "weekly"),
]

_ROBOTS = """User-agent: *
Allow: /

Disallow: /admin
Disallow: /admin/
Disallow: /api/
Disallow: /settings
Disallow: /bot/
Disallow: /offline
Disallow: /*?token=
Disallow: /*?ref=

User-agent: Googlebot
Allow: /
Allow: /static/
Disallow: /admin
Disallow: /api/

User-agent: Googlebot-Image
Allow: /static/img/

User-agent: AhrefsBot
Crawl-delay: 10

User-agent: SemrushBot
Crawl-delay: 10

Sitemap: {site}/sitemap.xml
Host: {host}
"""


@router.get("/robots.txt", include_in_schema=False)
async def robots() -> PlainTextResponse:
    body = _ROBOTS.format(site=SITE, host=HUB_HOST)
    return PlainTextResponse(body, headers={"Cache-Control": "public, max-age=86400"})


def _url(loc: str, priority: str, changefreq: str, lastmod: str) -> str:
    return (
        "  <url>\n"
        f"    <loc>{loc}</loc>\n"
        f"    <lastmod>{lastmod}</lastmod>\n"
        f"    <changefreq>{changefreq}</changefreq>\n"
        f"    <priority>{priority}</priority>\n"
        "  </url>\n"
    )


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap() -> Response:
    today = _dt.date.today().isoformat()
    body = ['<?xml version="1.0" encoding="UTF-8"?>\n',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n']
    for path, priority, freq in _PUBLIC_PAGES:
        body.append(_url(SITE + path, priority, freq, today))
    for path, priority, freq in _JOURNAL_PAGES:
        body.append(_url(JOURNAL + path.replace("/journal", "", 1) or "/",
                         priority, freq, today))
    body.append("</urlset>\n")
    return Response(
        content="".join(body),
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )
