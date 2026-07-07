# CryptoSmart Hub — پنل مدیریت سرمایه (پورتفولیو)

پلتفرم فارسی، راست‌چین و موبایل‌محور مدیریت سرمایه و تحلیل بازار کریپتو — وب‌سایت + مینی‌اپ تلگرام.
ساخته‌شده طبق **CryptoSmart Design System**.

> این فایل مرجعِ کامل پروژه است: معماری، پشتهٔ فناوری، اجرای محلی، تست، دیپلوی، و
> راهنمای دیباگِ سرور. اگر با پروژه آشنا نیستید، همین یک فایل کافی است تا بتوانید
> سایت را از صفر بالا بیاورید یا مشکلی را روی سرور پیدا و رفع کنید.

---

## فهرست

1. [این پروژه چیست و کجا زندگی می‌کند](#۱-این-پروژه-چیست-و-کجا-زندگی-میکند)
2. [معماری کلی (این پروژه + پروژهٔ خواهر Trading Journal)](#۲-معماری-کلی)
3. [نقشهٔ پورت‌ها و سرویس‌های سرور](#۳-نقشهٔ-پورتها-و-سرویسهای-سرور)
4. [پشتهٔ فناوری و معماری کد](#۴-پشتهٔ-فناوری-و-معماری-کد)
5. [ساختار پوشه‌ها](#۵-ساختار-پوشهها)
6. [اجرای محلی (توسعه)](#۶-اجرای-محلی-توسعه)
7. [تست و آزمون نرم‌افزار](#۷-تست-و-آزمون-نرمافزار)
8. [متغیرهای محیطی (`.env`)](#۸-متغیرهای-محیطی-env)
9. [دیتابیس](#۹-دیتابیس)
10. [راه‌اندازی کامل سرور از صفر](#۱۰-راهاندازی-کامل-سرور-از-صفر)
11. [Nginx و مسیرهای هر دو اپ زیرِ یک ساب‌دامنه](#۱۱-nginx-و-مسیرهای-هر-دو-اپ-زیرِ-یک-ساب‌دامنه)
12. [CI/CD (استقرار خودکار)](#۱۲-cicd-استقرار-خودکار)
13. [دیباگ روی سرور — چک‌لیست قدم‌به‌قدم](#۱۳-دیباگ-روی-سرور--چکلیست-قدمبهقدم)
14. [اشتباهات رایج و درس‌های آموخته‌شده](#۱۴-اشتباهات-رایج-و-درسهای-آموختهشده)
15. [امنیت](#۱۵-امنیت)

---

## ۱. این پروژه چیست و کجا زندگی می‌کند

**CryptoSmart Hub** یک اپ **FastAPI** است که نمای کلی بازار کریپتو، مدیریت سبد
دارایی (پورتفولیو)، تحلیل‌های اختصاصی کانال تلگرام، سبدچینی با هوش مصنوعی، و
پنل ادمین را ارائه می‌دهد. رندر عمدتاً سمت سرور است (Jinja2) به‌همراه جاوااسکریپت
سبک برای تعامل‌های زنده.

- **دامنهٔ یکپارچهٔ فعلی (توصیه‌شده):** `https://algohub.cryptosmart.site/` — این پروژه
  روی **روتِ همین دامنه** سرو می‌شود.
- **دامنهٔ مستقل (قدیمی، هنوز فعال):** `https://portfolio.cryptosmart.site/`
- **سرور:** یک VPS با IP ثابت `38.252.8.195`، که میزبان **سه** پروژهٔ مستقل است:
  1. `cryptosmart.site` — سایت دیگری که **کاملاً مستقل** است و این مستندات به آن کاری ندارند.
  2. **CryptoSmart Hub** (همین پروژه — پورتفولیو).
  3. **Trading Journal** (پروژهٔ خواهر — ریپوی جدا `AMISEF/trading-journal`؛ به بخش
     [معماری کلی](#۲-معماری-کلی) نگاه کنید).

هر سه پروژه روی یک سرور اما با **دیتابیس‌ها، پوشه‌ها، پروسه‌های pm2 و پورت‌های
کاملاً جدا از هم** اجرا می‌شوند — هیچ‌کدام دادهٔ دیگری را نمی‌بینند یا تغییر
نمی‌دهند.

## ۲. معماری کلی

از تاریخ یکپارچه‌سازی، هر دو اپ (پورتفولیو + ژورنال تریدینگ) زیرِ **یک ساب‌دامنهٔ
مشترک** `algohub.cryptosmart.site` سرو می‌شوند، اما به‌عنوان **دو پروسهٔ کاملاً
مجزا** با **دو دیتابیس مجزا** باقی می‌مانند. Nginx فقط بر اساس مسیر URL بین آن‌ها
مسیریابی (reverse proxy) می‌کند:

```
                         algohub.cryptosmart.site
                                    │
                                 Nginx (80/443)
                    ┌───────────────┴────────────────┐
                    │                                 │
              مسیر  "/"  و "/static/"          مسیر  "/journal/*"
                    │                                 │
                    ▼                                 ▼
     ┌─────────────────────────────┐   ┌──────────────────────────────────┐
     │  CryptoSmart Hub (این ریپو) │   │  Trading Journal (ریپوی جدا)      │
     │  FastAPI + Jinja2           │   │  Next.js (فرانت) + FastAPI (بک‌اند)│
     │  pm2: cryptosmart-portfolio │   │  pm2: tj-frontend / tj-backend    │
     │  پورت: 127.0.0.1:8000       │   │  پورت: 3001 (فرانت) / 8001 (بک‌اند)│
     │  دیتابیس: SQLite            │   │  دیتابیس: PostgreSQL              │
     │  (data/portfolio.db)        │   │  (trading_journal)                │
     └─────────────────────────────┘   └────────────────────────────────────┘
```

- کاربر از منوی سایت پورتفولیو می‌تواند به لینک «تریدینگ ژورنال» برود که به
  `/journal/` هدایت می‌شود؛ برعکس، در ژورنال یک نوار «هاب کریپتو اسمارت» به
  صفحات این پروژه لینک می‌دهد.
- **دیتابیس‌ها هرگز قاطی نمی‌شوند**: پورتفولیو از SQLite محلی خودش
  (`data/portfolio.db`) و ژورنال از PostgreSQL خودش (`trading_journal`)
  استفاده می‌کند؛ هیچ کد مشترکی بین این دو دیتابیس رد‌وبدل نمی‌شود.
- برای جزئیات کامل سمت ژورنال (basePath، env، nginx و…) به README ریپوی
  `trading-journal` مراجعه کنید.

## ۳. نقشهٔ پورت‌ها و سرویس‌های سرور

| سایت / اپ | پوشه روی سرور | نام پروسهٔ pm2 | پورت داخلی (فقط 127.0.0.1) | دیتابیس |
|---|---|---|---|---|
| `cryptosmart.site` (مستقل، دست‌نخورده) | `/var/www/cryptosmart` | `cryptosmart` | `3000` | مستقل از این دو پروژه |
| **CryptoSmart Hub** (پورتفولیو — همین ریپو) | `/var/www/portfolio` | `cryptosmart-portfolio` | `8000` | SQLite: `data/portfolio.db` |
| **Trading Journal — فرانت** (Next.js) | `/var/www/trading-journal/frontend` | `tj-frontend` | `3001` | ندارد (فقط UI) |
| **Trading Journal — بک‌اند** (FastAPI) | `/var/www/trading-journal/backend` | `tj-backend` | `8001` | PostgreSQL: `trading_journal` |

هیچ‌کدام از این پورت‌ها مستقیماً به اینترنت باز نیستند — همه فقط روی
`127.0.0.1` گوش می‌دهند و **Nginx** تنها درِ ورودی از پورت‌های عمومی `80`/`443`
است که بر اساس `server_name` (دامنه) و مسیر URL بین این پروسه‌ها مسیریابی
می‌کند.

بررسی سریع وضعیت همهٔ پروسه‌ها روی سرور:
```bash
pm2 list
# باید 4 پروسه سبز (online) ببینید: cryptosmart, cryptosmart-portfolio, tj-frontend, tj-backend
ss -tlnp | grep -E ':3000|:3001|:8000|:8001'
```

## ۴. پشتهٔ فناوری و معماری کد

- **زبان و فریم‌ورک بک‌اند:** Python 3.11 + **FastAPI** (async) — معماری لایه‌ای:
  - `app/routers/` — لایهٔ HTTP (مسیرها، اعتبارسنجی ورودی، پاسخ‌ها). هر روتر
    مسئول یک حوزه است: `pages.py` (صفحات HTML)، `auth.py` (ثبت‌نام/ورود)،
    `portfolio.py` (سبد دارایی + سبدچینی هوش مصنوعی + ریسک)، `market.py`
    (داده‌های زنده‌ی بازار)، `advisor.py` (چت‌بات مشاور Dify)، `admin.py` (پنل
    مدیریت — سیگنال‌ها، کاربران، اشتراک‌ها).
  - `app/services/` — لایهٔ منطق تجاری و اتصال به سرویس‌های خارجی (هر فایل یک
    مسئولیت واحد: `coinmarketcap.py`، `toobit.py`، `tabdeal.py`،
    `sourcearena.py`، `telegram_signals.py`، `algo_allocation.py`،
    `portfolio_valuation.py`، `mailer.py`، `xlsx.py`، `chart_svg.py`، …).
    این لایه از FastAPI/HTTP بی‌خبر است و می‌توان آن را جدا تست کرد.
  - `app/db.py` — دسترسی به SQLite (بدون ORM سنگین؛ کوئری‌های ساده و صریح).
  - `app/cache.py` — کش حافظه‌ای برای داده‌های بازار (جلوگیری از فراخوانی
    بیش‌ازحد API های خارجی و رعایت سقف کردیت).
  - `app/config.py` — تنظیمات از طریق `pydantic-settings` (خواندن `.env`).
  - `app/main.py` — نقطهٔ ورود اپ؛ ثبت روترها، میدل‌ورها، mount کردن استاتیک.
- **رندر:** Jinja2 (سمت سرور، راست‌چین، فارسی) — `app/templates/`.
- **فرانت‌اند:** HTML/CSS/JS ساده (بدون فریم‌ورک سنگین)، طبق توکن‌های
  CryptoSmart Design System؛ فایل‌های استاتیک در `app/static/`.
- **سرویس‌دهی (process manager):** pm2 — یک پروسهٔ uvicorn تک‌رشته‌ای
  (بدون `--workers`، تا pm2 دقیقاً یک PID را مدیریت کند و هنگام ری‌استارت
  پروسهٔ یتیم روی پورت باقی نماند).
- **وب‌سرور جلویی:** Nginx (reverse proxy + TLS با Certbot/Let's Encrypt).
- **CI/CD:** GitHub Actions → SSH + rsync → اسکریپت `deploy/remote_update.sh`.
- **ادغام‌های خارجی:** CoinMarketCap، Toobit، Tabdeal، SourceArena، Yahoo
  Finance، Dify (چت‌بات/سبدچینی هوش مصنوعی)، Telegram Bot API (وب‌هوک کانال
  سیگنال‌ها + مینی‌اپ تلگرام)، Resend (ایمیل).

### چرا این معماری؟
- **جداسازی لایه‌ها** (routers ↔ services ↔ db) باعث می‌شود منطق تجاری
  (مثلاً محاسبهٔ ارزش سبد یا سبدچینی هوش مصنوعی) بدون وابستگی به FastAPI قابل
  فراخوانی و تست باشد.
- **SQLite** برای این پروژه کافی است چون حجم داده کم و بار همزمانی پایین است؛
  از سربار راه‌اندازی/نگهداریِ یک سرور دیتابیس جدا صرف‌نظر شده.
- **کش حافظه‌ای** برای API های خارجیِ محدودیت‌دار (مثل CoinMarketCap) استفاده
  می‌شود تا سقف کردیت رعایت شود و صفحه سریع بارگذاری شود.
- **تک‌پروسه بدون Reload خودکار در پروداکشن** برای پیش‌بینی‌پذیریِ رفتار pm2 و
  جلوگیری از پروسه‌های یتیم انتخاب شده (نکته‌ای که مستقیماً منجر به یکی از
  حل‌شده‌ترین باگ‌های این پروژه شد — به [بخش ۱۴](#۱۴-اشتباهات-رایج-و-درسهای-آموختهشده) نگاه کنید).

## ۵. ساختار پوشه‌ها

```
portfolio/
├─ app/
│  ├─ main.py              # نقطهٔ ورود FastAPI
│  ├─ config.py            # تنظیمات (.env)
│  ├─ db.py                 # لایهٔ دیتابیس SQLite
│  ├─ cache.py               # کش حافظه‌ای
│  ├─ routers/              # مسیرهای HTTP (pages, auth, portfolio, market, advisor, admin)
│  ├─ services/              # منطق تجاری + اتصال به سرویس‌های خارجی
│  ├─ static/                # CSS/JS/تصاویر
│  └─ templates/             # قالب‌های Jinja2 (HTML)
├─ data/
│  ├─ portfolio.db           # دیتابیس SQLite (در گیت نیست)
│  └─ signals/                # تصاویر ذخیره‌شدهٔ کانال سیگنال‌ها
├─ deploy/
│  ├─ remote_update.sh       # اسکریپت دیپلوی روی سرور (CI/CD صدا می‌زند)
│  └─ nginx/                 # قالب‌های تنظیمات Nginx
│     ├─ portfolio.cryptosmart.site.conf   # دامنهٔ مستقل قدیمی
│     └─ algohub.cryptosmart.site.conf     # دامنهٔ یکپارچهٔ فعلی (هر دو اپ)
├─ dify/                      # تعریف ورک‌فلوهای Dify (چت‌بات/سبدچینی)
├─ docs/                      # مستندات تکمیلی (مثلاً ساخت ورک‌فلوی سبدچینی)
├─ ecosystem.config.js        # پیکربندی pm2
├─ requirements.txt           # وابستگی‌های پایتون
├─ run.py                     # اجرای محلی (uvicorn با reload)
└─ .env.example                # نمونهٔ متغیرهای محیطی
```

## ۶. اجرای محلی (توسعه)

پیش‌نیاز: Python 3.11+.

```bash
git clone <URL-ریپو> portfolio
cd portfolio
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # حداقل کلیدهای موردنیاز بخش خودتان را پر کنید
python run.py              # http://127.0.0.1:8000 (با auto-reload)
```

بدون هیچ کلید API هم اپ بالا می‌آید (بخش‌هایی از داده‌های بازار خالی/خطا نشان
داده می‌شوند، ولی صفحات لود می‌شوند). برای تست کامل، حداقل `CMC_API_KEY` را
پر کنید.

## ۷. تست و آزمون نرم‌افزار

این پروژه در حال حاضر فایل تست خودکار (`pytest`) ندارد؛ آزمون کیفیت به شکل
زیر انجام می‌شود و **پیش از هر push/PR باید انجام شود**:

1. **بررسی نحو/ایمپورت (Smoke test):**
   ```bash
   source .venv/bin/activate
   python -c "from app.main import app; print('OK, routes:', len(app.routes))"
   ```
2. **اجرای محلی و تست دستی مسیرهای اصلی** (پیشنهاد می‌شود قبل از هر تغییر بزرگ):
   ```bash
   python run.py
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/exclusive
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/portfolio
   ```
   هر سه باید `200` برگردانند (یا `303`/ریدایرکت به صفحهٔ ورود اگر لاگین لازم است).
3. **تست بصری (UI) در مرورگر واقعی**: چون بخش زیادی از منطق در جاوااسکریپت
   سمت کلاینت (لایت‌باکس گالری، فرم‌های ادمین، تب‌های داشبورد) است، هر تغییر
   UI باید حداقل یک‌بار در مرورگر (دسکتاپ + موبایل، تم روشن + تاریک) دیده شود.
   مسیر پیشنهادی: باز کردن مرورگر headless با Playwright (از‌پیش نصب‌شده در
   محیط) و گرفتن اسکرین‌شات از صفحات تغییریافته.
4. **بررسی لاگ سرور پس از دیپلوی** (به [بخش ۱۳](#۱۳-دیباگ-روی-سرور--چکلیست-قدمبهقدم) نگاه کنید).

> پیشنهاد برای آینده: افزودن `pytest` + `httpx.AsyncClient` برای تست‌های واحد
> روی `app/services/` (که از HTTP مستقل‌اند) و تست‌های یکپارچگی روی
> `app/routers/` با یک دیتابیس SQLite موقت (`:memory:` یا فایل تستی جدا).

## ۸. متغیرهای محیطی (`.env`)

فایل کامل نمونه در `.env.example` است؛ مهم‌ترین گروه‌ها:

| گروه | متغیرها | کاربرد |
|---|---|---|
| دادهٔ بازار | `CMC_API_KEY`, `TOOBIT_*`, `TABDEAL_API_*`, `SOURCEARENA_TOKEN` | نمای کلی بازار، تاپ گینرها، قیمت‌ها |
| هوش مصنوعی (Dify) | `DIFY_API_BASE`, `DIFY_API_KEY`, `DIFY_ADVISOR_KEY`, `DIFY_ALLOCATION_*`, `ADVISOR_API_KEY` | چت‌بات ثبت دارایی، مشاور سبد، سبدچینی هوش مصنوعی |
| تلگرام | `ALGO_ANALYZER_BOT_TOKEN`, `ALGO_CHANNEL_ID`, `SIGNALS_BOT_TOKEN`, `SIGNALS_CHANNEL_ID`, `TELEGRAM_ADMIN_IDS` | خواندن سیگنال‌های کانال، وب‌هوک، مینی‌اپ |
| ایمیل | `RESEND_API_KEY`, `MAIL_FROM_EMAIL`, `MAIL_FROM_NAME` | کد تأیید/بازیابی رمز |
| ادمین/امنیت | `ADMIN_EMAILS`, `ADMIN_SECRET_KEY` | نقش ادمین، رمزنگاری رمزهای قابل‌نمایش |
| عمومی | `PUBLIC_BASE_URL`, `DEBUG` | ساخت URL وب‌هوک/تصاویر، حالت دیباگ |

⚠️ `.env` هرگز کامیت نمی‌شود (در `.gitignore`). روی سرور، فایل واقعی مستقیماً
در `/var/www/portfolio/.env` نگه‌داری می‌شود و CI/CD به آن دست نمی‌زند.

## ۹. دیتابیس

- **نوع:** SQLite، فایل تکی در `data/portfolio.db`.
- در اولین اجرا خودکار ساخته/migrate می‌شود (نیازی به دستور جداگانه نیست).
- پوشهٔ `data/` (شامل دیتابیس و تصاویر سیگنال‌ها) در `.gitignore` است و هرگز
  کامیت نمی‌شود — یعنی هر بار دیپلوی، **همان فایل دیتابیس روی سرور** دست‌نخورده
  باقی می‌ماند (کد جدید rsync می‌شود، `data/` نه).
- بکاپ‌گیری دستی:
  ```bash
  cp /var/www/portfolio/data/portfolio.db ~/portfolio-backup-$(date +%F).db
  ```

## ۱۰. راه‌اندازی کامل سرور از صفر

```bash
# پیش‌نیازها
apt-get update && apt-get install -y python3-venv nodejs npm
npm install -g pm2

# کد را بگیرید (یا با CI/CD خودکار rsync می‌شود، یا دستی clone کنید)
mkdir -p /var/www/portfolio && cd /var/www/portfolio
git clone <URL-ریپو> .
cp .env.example .env
nano .env                       # کلیدهای واقعی را وارد کنید

python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

pm2 start ecosystem.config.js
pm2 save                        # تا بعد از ری‌استارت سرور هم بالا بیاید
```

سپس Nginx (به [بخش ۱۱](#۱۱-nginx-و-مسیرهای-هر-دو-اپ-زیرِ-یک-ساب‌دامنه) نگاه کنید) و در نهایت SSL:
```bash
certbot --nginx -d algohub.cryptosmart.site --non-interactive --redirect
```

## ۱۱. Nginx و مسیرهای هر دو اپ زیرِ یک ساب‌دامنه

فایل الگو: `deploy/nginx/algohub.cryptosmart.site.conf` (کاملاً کامنت‌گذاری
شده). خلاصهٔ مسیرها:

| مسیر URL | مقصد | توضیح |
|---|---|---|
| `algohub.cryptosmart.site/` | `127.0.0.1:8000` (پورتفولیو) | صفحهٔ اصلی و بقیهٔ مسیرهای پورتفولیو |
| `algohub.cryptosmart.site/static/` | دیسک (`app/static/` — `alias`، نه proxy) | فایل‌های استاتیک پورتفولیو |
| `algohub.cryptosmart.site/journal` (دقیقاً، بدون اسلش) | `127.0.0.1:3001/journal` | صفحهٔ اصلی ژورنال (Next.js با basePath) |
| `algohub.cryptosmart.site/journal/` | `127.0.0.1:3001` | بقیهٔ صفحات ژورنال |
| `algohub.cryptosmart.site/journal/api/` | `127.0.0.1:8001/api/` | بک‌اند FastAPI ژورنال |
| `algohub.cryptosmart.site/journal/uploads/` | `127.0.0.1:8001/uploads/` | تصاویر آپلودی ژورنال |

نصب/به‌روزرسانی روی سرور:
```bash
cp deploy/nginx/algohub.cryptosmart.site.conf /etc/nginx/sites-available/algohub.cryptosmart.site.conf
ln -s /etc/nginx/sites-available/algohub.cryptosmart.site.conf /etc/nginx/sites-enabled/ 2>/dev/null
nginx -t && systemctl reload nginx
certbot --nginx -d algohub.cryptosmart.site --non-interactive --redirect
```

> ⚠️⚠️ **بسیار مهم — قبل از هر `cp` روی فایل زندهٔ `/etc/nginx/sites-available/algohub.cryptosmart.site.conf`
> حتماً بخش [۱۴](#۱۴-اشتباهات-رایج-و-درسهای-آموختهشده) را بخوانید.** این قالب گیت
> بلوکِ SSL که Certbot خودش اضافه می‌کند را **ندارد**؛ اگر بی‌احتیاط این فایل را
> روی فایل زندهٔ سرور کپی کنید، بلوک SSL از بین می‌رود و کل سایت (هر دو اپ) از کار
> می‌افتد تا دوباره `certbot --nginx -d algohub.cryptosmart.site` را اجرا کنید.

فایل الگوی مستقل قدیمی (`portfolio.cryptosmart.site`) هم در همان پوشه موجود
است، اگر خواستید فقط پورتفولیو را مستقل سرو کنید.

## ۱۲. CI/CD (استقرار خودکار)

هر push به شاخهٔ `main` توسط GitHub Actions:
1. با SSH به سرور وصل می‌شود.
2. کد جدید را با `rsync` منتقل می‌کند (پوشه‌های `data/` و `.env` دست‌نخورده
   می‌مانند چون در exclude list هستند).
3. `deploy/remote_update.sh` را اجرا می‌کند: نصب/به‌روزرسانی وابستگی‌ها +
   `pm2 restart cryptosmart-portfolio`.

سکرت‌های لازم در تنظیمات ریپو (**Settings → Secrets and variables → Actions**):
`VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`.

## ۱۳. دیباگ روی سرور — چک‌لیست قدم‌به‌قدم

اگر سایت بالا نمی‌آید یا خطای غیرمنتظره می‌دهد، این ترتیب را دنبال کنید (از
ساده به پیچیده):

1. **وضعیت پروسه‌ها:**
   ```bash
   pm2 list
   pm2 logs cryptosmart-portfolio --lines 100
   ```
   اگر `errored` یا مدام ری‌استارت می‌شود، لاگ خطا معمولاً علت را نشان می‌دهد
   (مثلاً `.env` ناقص، خطای import، پورت اشغال).

2. **آیا پروسه واقعاً روی پورت درست گوش می‌دهد؟**
   ```bash
   ss -tlnp | grep :8000
   ```

3. **تست مستقیم بدون Nginx (رد کردن هر مشکل احتمالی وب‌سرور/Cloudflare):**
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/
   ```

4. **تست از پشتِ Nginx، بدون Cloudflare** (با ست‌کردن SNI و Host درست):
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" \
        --resolve algohub.cryptosmart.site:443:127.0.0.1 \
        https://algohub.cryptosmart.site/
   ```
   ⚠️ حتماً از `--resolve` استفاده کنید، نه فقط هدر `Host` دستی — چون بدون
   SNI درست، Nginx ممکن است سرتیفیکیت/بلوکِ سرور اشتباهی انتخاب کند (دقیقاً
   همان چیزی که علت اصلی بزرگ‌ترین قطعیِ این پروژه بود؛ به بخش ۱۴ نگاه کنید).

5. **بررسی خودِ تنظیمات Nginx:**
   ```bash
   nginx -t                     # خطای نحوی؟
   nginx -T | grep -A 30 "server_name algohub"   # آیا بلوکِ 443 ssl برای این دامنه واقعاً وجود دارد؟
   ```
   اگر در خروجیِ `nginx -T` برای `algohub.cryptosmart.site` فقط بلوکِ `listen 80`
   دیدید و بلوکِ `listen 443 ssl` را **ندیدید**، مشکل پیدا شد — به بخش ۱۴ بروید.

6. **لاگ‌های Nginx:**
   ```bash
   tail -n 100 /var/log/nginx/error.log
   tail -n 100 /var/log/nginx/access.log
   ```

7. **از راه عمومی (با Cloudflare)، برای رد کردن مشکلات مربوط به کش/DNS Cloudflare:**
   ```bash
   curl -sI https://algohub.cryptosmart.site/
   ```

8. **بررسی اینکه دو اپ دیگر (`cryptosmart.site` و ژورنال) دست‌نخورده مانده‌اند:**
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" https://cryptosmart.site/
   curl -s -o /dev/null -w "%{http_code}\n" https://algohub.cryptosmart.site/journal
   ```

## ۱۴. اشتباهات رایج و درس‌های آموخته‌شده

این بخش تجربهٔ واقعی رفعِ یک قطعیِ چندساعته است — خواندنش قبل از هر تغییرِ
Nginx روی سرور **الزامی** است:

- **علت اصلیِ بزرگ‌ترین باگ این پروژه:** Certbot هنگام گرفتنِ گواهیِ SSL، مستقیماً
  به فایلِ زندهٔ `/etc/nginx/sites-available/algohub.cryptosmart.site.conf` خط‌های
  `listen 443 ssl;`، `ssl_certificate ...` و غیره را **اضافه می‌کند** — این خط‌ها
  در قالبِ گیت (`deploy/nginx/algohub.cryptosmart.site.conf`) وجود ندارند و
  هرگز به‌صورت خودکار به گیت برنمی‌گردند. اگر بعداً همین قالبِ گیت را دوباره روی
  فایل زندهٔ سرور `cp` کنید، این خط‌های SSL **پاک می‌شوند** — بدون خطای نصب یا
  ری‌لود؛ فقط رفتار HTTPS دامنه به‌طرز مبهمی خراب می‌شود (گاهی محتوای سایتِ
  دیگری نشان داده می‌شود، گاهی 404 عجیب). **راه‌حل:** بعد از هر `cp` روی این
  فایل خاص، همیشه بلافاصله دوباره اجرا کنید:
  ```bash
  certbot --nginx -d algohub.cryptosmart.site --non-interactive --redirect
  ```
  این دستور برای گواهیِ معتبرِ موجود بی‌ضرر (idempotent) است و فقط بلوکِ SSL را
  دوباره اضافه می‌کند.
- **تستِ `curl` بدونِ `--resolve` گمراه‌کننده است:** ست‌کردنِ فقط هدرِ `Host` روی
  `curl https://127.0.0.1` باعث می‌شود SNI درستی فرستاده نشود؛ Nginx ممکن است
  بلوکِ سرورِ دیگری را انتخاب کند و شما نتیجهٔ غلط ببینید. همیشه از
  `--resolve <domain>:443:127.0.0.1` استفاده کنید.
  ```
- **basePath ساختِ Next.js (پروژهٔ ژورنال) یک ثابتِ زمانِ build است** — یک
  خروجیِ ساخته‌شده نمی‌تواند هم با `/journal` prefix و هم بدونِ آن سرو شود.
  وقتی ژورنال با `basePath=/journal` برای algohub بازسازی شد، دامنهٔ مستقلِ
  قدیمیِ `trading-journal.cryptosmart.site` (که prefix نمی‌خواست) شکست — به
  همین دلیل آن دامنه الان صرفاً یک **ریدایرکتِ ۳۰۱** به
  `algohub.cryptosmart.site/journal` است (جزئیات در README ریپوی
  trading-journal).
- **حلقهٔ ریدایرکتِ بی‌نهایت روی `/journal` (بدون اسلش):** اگر Nginx برای
  `location = /journal` یک ریدایرکتِ ۳۰۸ به `/journal/` بزند، و Next.js خودش
  به‌صورت پیش‌فرض `/journal/` را با ۳۰۸ به `/journal` ریدایرکت کند، بینِ این
  دو یک **حلقهٔ بی‌نهایت** ساخته می‌شود. راه‌حل: `location = /journal` باید
  **مستقیماً proxy_pass** کند، نه ریدایرکت.
- **دیوَرجنسِ گیتِ سرور:** اگر روی سرور `git pull` خطای «divergent branches»
  داد (معمولاً چون CI/CD با rsync کد را جابه‌جا می‌کند یا PRها squash-merge
  شده‌اند)، و مطمئن بودید تغییرِ محلیِ مهمی روی سرور نیست (چون `.env` و
  `data/` در gitignore هستند)، این‌طور ریست کنید:
  ```bash
  git fetch origin main && git reset --hard origin/main
  ```
  ⚠️ این دستور مخرب است — قبلش حتماً `git status` بزنید تا از نبودِ تغییرِ
  مهمِ ذخیره‌نشده مطمئن شوید.

## ۱۵. امنیت

- فایل `.env` و پوشهٔ `data/` هرگز کامیت نمی‌شوند (در `.gitignore`).
- کلیدهای API فقط در `.env` روی سرور قرار می‌گیرند، هرگز در کد.
- دسترسی API صرافی‌ها در فازهای بعد فقط **خواندنی (Read-Only)** خواهد بود.
- مصرف کردیت CryptoRank/CoinMarketCap با بودجهٔ پایدار کنترل می‌شود (سقف
  ۱۰٬۰۰۰ در ماه).
- `ADMIN_SECRET_KEY` باید یک رشتهٔ تصادفیِ بلند و یکتا باشد (برای رمزنگاریِ
  برگشت‌پذیرِ رمزهای نمایش‌داده‌شده به ادمین).
