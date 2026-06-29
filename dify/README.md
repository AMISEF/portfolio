# ورک‌فلوهای Dify — کریپتو اسمارت

این پوشه سه ورک‌فلو برای پلتفرم Dify دارد:

| فایل | اپ | متغیر `.env` | کاربرد |
|------|-----|-------------|--------|
| `asset_registration.yml` | کریپتو اسمارت \| ثبت سبد دارایی | `DIFY_API_KEY` | چت‌بات ثبت دارایی — کاربر دارایی‌هایش را به فارسی می‌نویسد، ربات JSON استخراج می‌کند |
| `portfolio_advisor.yml` | CryptoSmart Portfolio Advisor | `DIFY_ADVISOR_KEY` | سه سبد هفتگی/ماهانه/سالانه با نواحی خرید و فروش (endpoint: `/api/portfolio/advisor`) |
| `algo_allocation.yml` | CryptoSmart ALGO Allocation | `DIFY_ALLOCATION_KEY` | **سبدچینی با هوش مصنوعی** — دکمهٔ صفحهٔ مدیریت سرمایه (ویژهٔ مشترکین) |

## ترتیب ایمپورت و راه‌اندازی

هر سه فایل را جداگانه در Dify → **Studio → Import DSL → Local File** ایمپورت کن.
پس از Publish هر اپ، کلید API آن را از **API Access** بردار و در `.env` سرور بگذار.

برای استفاده از دکمهٔ «سبدچینی با هوش مصنوعی» در سایت، **`algo_allocation.yml`** را
ایمپورت کن (بخش پایین همین فایل). بخش زیر مربوط به ورک‌فلوِ مشاور سبد است.

---

## ورک‌فلو ۱: Portfolio Advisor

ورک‌فلو **CryptoSmart Portfolio Advisor** بر اساس دارایی‌های فعلی کاربر، درصد و
توضیح ریسک‌پذیری، و تحلیل تکنیکال زندهٔ صرافی Toobit، سه **سبد پیشنهادی هفتگی،
ماهانه و سالانه** با **نواحی دقیق خرید و فروش** می‌سازد.

```
کاربر (چت قبلی → دارایی‌ها) ─┐
ریسک‌پذیری (٪ + توضیح) ───────┼─► Dify Start
                              │
        ┌─────────────────────▼─────────────────────┐
        │ HTTP: POST /api/advisor/context            │  ← بک‌اند CryptoSmart
        │   • دارایی‌های ارزش‌گذاری‌شده                │     (FastAPI)
        │   • پروفایل ریسک                            │
        │   • رژیم بازار (روند BTC، RSI، ترس‌وطمع)     │
        │   • تحلیل تکنیکال هر نماد:                   │
        │       buy_zones / sell_zones (۳ افق)        │  ← کندل‌های Toobit
        └─────────────────────┬─────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │ LLM: Gemini 2.5    │  ← OpenRouter
                    │ Flash              │
                    └─────────┬─────────┘
                              │
                         سبد پیشنهادی
                  (هفتگی / ماهانه / سالانه)
```

## معماری: چرا تحلیل در بک‌اند است نه در مدل؟

نواحی خرید/فروش از **داده‌های واقعی کندل** محاسبه می‌شوند (سوینگ‌های فرکتال،
خوشه‌بندی حمایت/مقاومت، RSI، ATR، میانگین‌های متحرک) — نه از حدسِ مدل روی تصویر.
این کارِ بک‌اند `app/services/ta.py` است و دقت را تضمین می‌کند. مدل Gemini روی
این اعداد **استدلال** می‌کند و سبد می‌سازد. نمودار شمعی هم به‌صورت SVG رندر
می‌شود (`/api/advisor/chart/{symbol}.svg`) برای نمایش در سایت و تحلیل دیداری.

## اندپوینت‌های بک‌اند (ابزار ورک‌فلو)

| متد | مسیر | توضیح |
|-----|------|-------|
| POST | `/api/advisor/context` | بستهٔ کامل: دارایی + ریسک + رژیم بازار + تحلیل نمادها |
| GET | `/api/advisor/chart/{symbol}.svg?interval=1d` | نمودار شمعی + نواحی خرید/فروش |

### بدنهٔ ورودی `/api/advisor/context` (همه اختیاری)

```json
{
  "uid": "cs_uid کاربر برای واکشی دارایی/ریسک ذخیره‌شده",
  "assets": [{"kind":"crypto","symbol":"BTC","amount":0.1,"buy_price":null}],
  "risk_percent": 72,
  "risk_label": "ریسک‌پذیر",
  "risk_desc": "توضیح متنی ریسک‌پذیری کاربر",
  "extra_symbols": ["SOL","ADA"]
}
```

- اگر `assets`/`risk_*` داده شود همان استفاده می‌شود؛ وگرنه با `uid` از دیتابیس
  خوانده می‌شود (همان دارایی‌هایی که کاربر در چت قبلی با هوش مصنوعی ثبت کرده).
- خروجی شامل `crypto_analysis[]` است که برای هر نماد، در سه افق
  `weekly(4h) / monthly(1d) / yearly(1w)`، کلیدهای `buy_zones` و `sell_zones`
  را دارد (هر ناحیه: `low/mid/high`, `dist_pct`, `touches`).

## نصب و راه‌اندازی

### ۱) سمت سرور (.env)

یک کلید تصادفی بلند بساز و در `.env` سرور قرار بده، سپس سرویس را ری‌استارت کن:

```bash
# تولید کلید
python -c "import secrets; print(secrets.token_urlsafe(32))"

# در فایل .env
ADVISOR_API_KEY=<کلید تولیدشده>

pm2 restart cryptosmart-portfolio
```

> اگر `ADVISOR_API_KEY` تنظیم نشود، اندپوینت بدون احراز کار می‌کند (فقط برای
> تست محلی توصیه می‌شود). برای محیط واقعی حتماً تنظیمش کن تا دادهٔ مالی کاربران
> بی‌اجازه خوانده نشود.

> پیش‌نیاز شبکه: میزبان `api.toobit.com` باید در allowlist خروجیِ سرور باشد تا
> کندل‌ها واکشی شوند.

### ۲) ایمپورت ورک‌فلو در Dify

1. وارد Dify شو → **Studio → Import DSL → Local File** → فایل
   `dify/portfolio_advisor.yml` را انتخاب کن.
2. پس از ایمپورت، در تنظیمات اپ → **Environment Variables**:
   - `ADVISOR_BASE_URL` = آدرس بک‌اند (پیش‌فرض `https://portfolio.cryptosmart.site`)
   - `ADVISOR_API_KEY` = همان کلیدی که در `.env` سرور گذاشتی.

### ۳) مدل OpenRouter (Gemini 2.5 Flash)

1. در Dify → **Settings → Model Provider → OpenRouter** را نصب/فعال کن و
   `OPENROUTER_API_KEY` خودت را وارد کن.
2. در نود `ساخت سبد پیشنهادی` مطمئن شو مدل روی `google/gemini-2.5-flash`
   (Provider: OpenRouter) تنظیم است. اگر provider متفاوتی نصب داری، همان‌جا
   انتخابش کن.

### ۴) اجرا و تست

در Dify → **Run** و ورودی‌ها را بده. ساده‌ترین حالت: فقط `uid` کاربر را بده
(تا دارایی و ریسکِ ذخیره‌شده‌اش خوانده شود). یا برای تست مستقل،
`risk_percent` و `extra_symbols` را دستی وارد کن.

تست مستقیم بک‌اند (بدون Dify):

```bash
curl -s -X POST https://portfolio.cryptosmart.site/api/advisor/context \
  -H "Content-Type: application/json" \
  -H "X-Advisor-Key: $ADVISOR_API_KEY" \
  -d '{"risk_percent":72,"extra_symbols":["SOL","ADA"]}' | jq .
```

## خروجی ورک‌فلو

- `advice` — متن Markdown فارسی: خلاصهٔ وضعیت + سه جدول سبد (هفتگی/ماهانه/سالانه)
  با ستون‌های «دارایی، درصد، ناحیهٔ خرید، هدف فروش، حد ضرر، اقدام» + مدیریت ریسک.
- `context` — همان JSON خام تحلیل (برای لاگ/دیباگ یا نمایش نمودار).

## نکات

- نواحی خرید/فروش فقط از داده‌های واقعی می‌آیند؛ پرامپت به مدل صریحاً می‌گوید
  هیچ ناحیه‌ای از خودش نسازد. اگر دادهٔ کافی نباشد، مدل «صبر تا تثبیت» پیشنهاد
  می‌دهد.
- تخصیص دارایی خودکار با سطح ریسک هماهنگ می‌شود (محافظه‌کار → تتر/طلا/BTC بیشتر؛
  ریسک‌پذیر → آلت بیشتر).
- طلا با نماد `PAXG` (طلای توکنایزشده) روی Toobit برای نواحی کندلی تحلیل می‌شود؛
  قیمت طلای ۱۸ عیار و انس از SourceArena، و تتر تومانی از Tabdeal می‌آید.

---

## ورک‌فلو ۲: ALGO Allocation (سبدچینی با هوش مصنوعی)

این ورک‌فلو پشتِ دکمهٔ **«سبدچینی با هوش مصنوعی»** در صفحهٔ مدیریت سرمایه است
(`algo_allocation.yml`). اپ، ریسک‌پذیری و موجودی کاربر را به آن می‌دهد و متن سبد
پیشنهادی را می‌گیرد. این قابلیت فقط برای کاربران **دارای اشتراک فعال** باز می‌شود.

```
اپ CryptoSmart ─► POST /v1/workflows/run (با DIFY_ALLOCATION_KEY)
        │  inputs: risk_percent, risk_level, allowed_assets, tether_usd, holdings, …
        ▼
   Start ─► HTTP: /api/advisor/context ─► HTTP: /api/advisor/signals ─► Gemini ─► End(result)
```

- **قاعدهٔ دارایی مجاز:** کم‌ریسک = طلا/دلار/تتر | متوسط = +BTC/ETH | پرریسک = +آلت‌کوین.
- **ابزار context:** نواحی خرید/فروش و رژیم بازار (همان اندپوینت ورک‌فلو ۱).
- **ابزار signals:** تحلیل‌های کانال پورتفولیو (`/api/advisor/signals`) که ربات
  `portfolio_Cryptosmart_bot` از طریق وب‌هوک تلگرام دریافت کرده و تا ۷ روز نگه
  می‌دارد. این تحلیل‌ها وین‌ریت بالایی دارند و در پرامپت بر تحلیل تکنیکال خودکار
  ارجحیت داده شده‌اند. هر پست `text` (نقاط خرید/فروش)، `hashtags`، `image_url`
  (تصویر چارت) و `expires_at` دارد.
- **چنل پیشنهادی** را خودِ اپ بر اساس موجودی تتر می‌سازد (برنزی/نقره‌ای/طلایی) و
  زیر متن نمایش می‌دهد؛ مدل لازم نیست آن را بسازد.

### ایمپورت و راه‌اندازی

1. در Dify → **Studio → Import DSL → Local File** → `dify/algo_allocation.yml`.
2. در **Environment Variables** اپ:
   - `ADVISOR_BASE_URL` = آدرس بک‌اند (پیش‌فرض `https://portfolio.cryptosmart.site`)
   - `ADVISOR_API_KEY` = همان کلید `.env` سرور.
3. مدل OpenRouter (Gemini 2.5 Flash) را مثل ورک‌فلو ۱ تنظیم کن.
4. اپ را **Publish** کن، سپس از **API Access** کلید را بردار و در `.env` سرور بگذار:
   ```bash
   DIFY_ALLOCATION_KEY=<کلید API ورک‌فلو>
   # برای خواندن تحلیل‌های کانال پورتفولیو (ربات باید «ادمین» کانال باشد):
   SIGNALS_BOT_TOKEN=<توکن ربات portfolio_Cryptosmart_bot از BotFather>
   SIGNALS_CHANNEL_ID=-1004451073096
   PUBLIC_BASE_URL=https://portfolio.cryptosmart.site
   pm2 restart cryptosmart-portfolio
   ```

   > پس از ری‌استارت، برنامه خودکار وب‌هوک تلگرام را روی
   > `PUBLIC_BASE_URL/api/advisor/telegram/webhook` ثبت می‌کند. از آن پس هر پست
   > جدید کانال (متن تحلیل + تصویر چارت) ذخیره و تا ۷ روز در پیشنهادها لحاظ می‌شود.
   > ربات حتماً باید **ادمین کانال** باشد؛ عضو ساده نمی‌تواند `channel_post` بدهد.

> نام فیلد خروجی End node باید `result` باشد (یا اگر تغییرش دادی، همان را در
> `DIFY_ALLOCATION_OUTPUT` بگذار). اپ متنِ همین فیلد را به کاربر نشان می‌دهد.

> راهنمای کامل اسکیمای ورودی/خروجی: `docs/algo_allocation_workflow.md`.
