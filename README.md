# CryptoSmart Hub — پنل مدیریت سرمایه

پلتفرم فارسی، راست‌چین و موبایل‌محور مدیریت سرمایه و تحلیل بازار کریپتو —
وب‌سایت + مینی‌اپ تلگرام. ساخته‌شده طبق **CryptoSmart Design System**.

- **آدرس:** https://portfolio.cryptosmart.site
- **سرور:** `38.252.8.195` (در کنار `cryptosmart.site` و `trading-journal.cryptosmart.site`)

## فاز ۱ — نمای کلی بازار (Market Overview)
- تیکر متحرک شاخص‌های کلان (CryptoRank)
- نقشهٔ حرارتی دسته‌بندی‌شدهٔ بازار (CryptoRank)
- شاخص ترس و طمع به‌صورت گیج گرافیکی (alternative.me)
- شاخص‌های کلان: ارزش کل بازار، حجم، دامیننس BTC/ETH (CryptoRank)
- بیشترین رشد ۲۴ساعته — ۵ ارز برتر با آیکون (Toobit)
- قیمت‌های کلیدی: تتر تومانی (Tabdeal، **بدون تبدیل**)، طلای ۱۸ عیار
  (SourceArena، هر ۳۰ دقیقه)، طلای جهانی/نقره/نفت = XAU/XAG/OIL (CryptoRank)
- تاریخ شمسی + میلادی + ساعت زنده، نقاط چشمک‌زن، به‌روزرسانی خودکار بدون رفرش
- تم روشن/تاریک با نماد خورشید/ماه

## پشتهٔ فناوری
- **بک‌اند:** Python · FastAPI · Jinja2 (رندر سمت سرور)
- **فرانت‌اند:** HTML/CSS/JS ساده (بدون فریم‌ورک سنگین) با توکن‌های دیزاین سیستم
- **سرویس:** pm2 (uvicorn تک‌پروسه روی `127.0.0.1:8000`؛ پورت‌های دیگرِ سرور: cryptosmart=3000، tj-frontend=3001، tj-backend=8001)
- **وب‌سرور:** Nginx (reverse proxy)
- **CI/CD:** GitHub Actions → SSH + rsync → `deploy/remote_update.sh`

## اجرای محلی
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # کلیدها را قرار دهید
python run.py          # http://127.0.0.1:8000
```

## راه‌اندازی اولیهٔ سرور (یک‌بار)
```bash
# پیش‌نیازها
apt-get update && apt-get install -y python3-venv nodejs npm
npm install -g pm2

# کد (CI/CD خودش rsync می‌کند، یا دستی clone کنید) در /var/www/portfolio
cd /var/www/portfolio
cp .env.example .env   # کلیدهای واقعی را وارد کنید

# Nginx
cp deploy/nginx/portfolio.cryptosmart.site.conf /etc/nginx/sites-available/
ln -s /etc/nginx/sites-available/portfolio.cryptosmart.site.conf /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d portfolio.cryptosmart.site   # گواهی TLS
```
پس از آن، هر push به شاخهٔ `main` به‌صورت خودکار دیپلوی می‌شود.

## امنیت
- فایل `.env` و پوشهٔ `data/` هرگز کامیت نمی‌شوند (در `.gitignore`).
- کلیدهای API فقط در `.env` روی سرور قرار می‌گیرند، هرگز در کد.
- دسترسی API صرافی‌ها در فازهای بعد فقط **خواندنی (Read-Only)** خواهد بود.
- مصرف کردیت CryptoRank با بودجهٔ پایدار کنترل می‌شود (سقف ۱۰٬۰۰۰ در ماه).
