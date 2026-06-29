"""
پیکربندی مرکزی CryptoSmart Hub.

تمام کلیدهای API و تنظیمات از متغیرهای محیطی (فایل .env روی سرور) خوانده می‌شوند.
هیچ کلید واقعی در کد قرار نمی‌گیرد؛ مقادیر پیش‌فرض فقط برای اجرای محلی‌اند.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ---- برند ----
    app_name: str = "CryptoSmart Hub"
    app_brand_fa: str = "کریپتو اسمارت"
    app_title_fa: str = "پنل مدیریت سرمایه"
    app_subtitle_fa: str = "مدیریت هوشمند پورتفولیو"
    debug: bool = False

    # ---- CryptoRank (شاخص کلان + هیت‌مپ + کالاها XAU/XAG/OIL) ----
    cryptorank_api_key: str = ""
    cryptorank_base_url: str = "https://api.cryptorank.io/v2"
    # سقف مصرف کردیت پلن رایگان
    cryptorank_monthly_credits: int = 10_000
    cryptorank_daily_credits: int = 400
    cryptorank_per_min_credits: int = 100
    cryptorank_cost_global: int = 1
    cryptorank_cost_currencies: int = 1
    # کش ۱۰ دقیقه ⇒ حدود ۸٬۶۴۰ کردیت در ماه (< ۱۰٬۰۰۰)
    cryptorank_ttl: int = 600
    # نقشهٔ حرارتی: ساختار (دسته/مارکت‌کپ/حجم/تغییر چنددوره‌ای) هر ۵ دقیقه از
    # CryptoRank (۱ کردیت، ۲۸۸/روز < ۴۰۰). قیمت زندهٔ ۲۴ساعته هر ۵ ثانیه از توبیت.
    cryptorank_heatmap_ttl: int = 300
    cryptorank_heatmap_limit: int = 500

    # ---- Toobit (ارزهای برتر + هیت‌مپ + نفت + تصاویر ارز) ----
    toobit_access_key: str = ""
    toobit_secret_key: str = ""
    toobit_base_url: str = "https://api.toobit.com"
    toobit_ttl: int = 12               # سازگاری عقب‌رو
    toobit_coins_ttl: int = 5          # ۵ ارز برتر — هر ۵ ثانیه (زنده)
    toobit_heatmap_ttl: int = 5        # قیمت زندهٔ نقشهٔ حرارتی (هر ۵ ثانیه)
    toobit_oil_ttl: int = 120          # نفت کم‌نوسان‌تر
    toobit_sparkline_ttl: int = 60     # شِماتیک قیمت ۵ ارز برتر (هر ۶۰ ثانیه)
    toobit_rsi_ttl: int = 300          # میانگین RSI بازار (هر ۵ دقیقه)
    toobit_gainers_count: int = 5

    # ---- CoinMarketCap (شاخص‌های کلان + فصل آلت‌کوین) ----
    # کلید از متغیر محیطی CMC_API_KEY خوانده می‌شود.
    cmc_api_key: str = ""
    cmc_base_url: str = "https://pro-api.coinmarketcap.com"
    cmc_macro_ttl: int = 300           # global-metrics هر ۵ دقیقه
    cmc_altseason_ttl: int = 900       # فصل آلت‌کوین (۹۰روزه، کم‌تغییر) هر ۱۵ دقیقه
    cmc_fng_ttl: int = 300             # ترس و طمع از CMC هر ۵ دقیقه (v3/fear-and-greed)
    # سقف مصرف کردیت پلن Basic (هارد‌کپ ماهانه ۲۰٬۰۰۰ و ۵۰ درخواست/دقیقه)
    cmc_monthly_credits: int = 19_000  # حاشیهٔ ایمنی زیر ۲۰٬۰۰۰
    cmc_daily_credits: int = 600
    cmc_per_min_credits: int = 40      # زیر ۵۰/دقیقه
    cmc_state_file: str = "data/cmc_credit_state.json"
    # نقشهٔ حرارتی از listings/latest کوین‌مارکت‌کپ (قیمت/مارکت‌کپ/حجم + تغییر
    # چنددوره‌ای ۲۴ساعته/۷روزه/۳۰روزه/۹۰روزه + برچسب دسته). کش ۱۰ دقیقه.
    cmc_heatmap_ttl: int = 600
    cmc_heatmap_limit: int = 200

    # ---- Tabdeal (تتر تومانی — بدون هیچ تبدیلی) ----
    tabdeal_api_key: str = ""
    tabdeal_api_secret: str = ""
    tabdeal_base_url: str = "https://api.tabdeal.org"
    tabdeal_ttl: int = 15

    # ---- SourceArena (طلای ۱۸ عیار + دلار آزاد — هر ۱۵ دقیقه) ----
    sourcearena_token: str = ""
    # برای دسترسی از سرور خارج از ایران
    sourcearena_base_url: str = "https://sa.resicard.ir/api"
    sourcearena_ttl: int = 900

    # ---- CoinGecko (شاخص‌های کلان دقیق — بدون کلید) ----
    coingecko_base_url: str = "https://api.coingecko.com/api/v3"
    coingecko_ttl: int = 60

    # ---- شاخص ترس و طمع (پشتیبان: alternative.me؛ منبع اصلی CMC v3) ----
    fng_base_url: str = "https://api.alternative.me/fng/"
    fng_ttl: int = 600

    # ---- کالاهای جهانی: طلا/نقره/نفت (Yahoo Finance، رایگان و بدون کلید) ----
    # GC=F طلا، SI=F نقره، CL=F نفت خام WTI — قیمت + تغییر ۲۴ساعته.
    # میزبان query1.finance.yahoo.com باید در allowlist شبکهٔ سرور باشد.
    yahoo_base_url: str = "https://query1.finance.yahoo.com"
    commodities_ttl: int = 15

    # مسیر فایل پایدار شمارندهٔ کردیت
    credit_state_file: str = "data/credit_state.json"

    # ---- پورتفولیو / مدیریت سرمایه ----
    # دیتابیس SQLite پروفایل ریسک و دارایی‌ها (طبق .gitignore کامیت نمی‌شود).
    portfolio_db_file: str = "data/portfolio.db"
    # چت‌بات ثبت دارایی (asset_registration.yml) — کلید در .env با نام DIFY_API_KEY.
    # وب‌اپ روی /app است؛ API سرویس روی /v1. قابل بازنویسی با DIFY_API_BASE در .env.
    dify_api_base: str = "http://38.252.8.181/v1"
    dify_api_key: str = ""
    # مشاور سبد (portfolio_advisor.yml) — ورک‌فلوِ سه سبد هفتگی/ماهانه/سالانه.
    # کلید جداگانه در .env با نام DIFY_ADVISOR_KEY.
    dify_advisor_key: str = ""

    # ---- مشاور سبد (ابزار تحلیل بازار برای ورک‌فلو Dify) ----
    # اگر تنظیم شود، اندپوینت /api/advisor/context هدر «X-Advisor-Key» را الزامی
    # می‌کند تا فقط ورک‌فلو Dify (با همین کلید) بتواند دادهٔ مالی کاربران را بخواند.
    advisor_api_key: str = ""

    # ---- سبدچینی با هوش مصنوعی (ALGO SMART) ----
    # ورک‌فلوِ Dify که با توجه به ریسک‌پذیری و موجودی کاربر، سبد پیشنهادی می‌سازد.
    # کلید API این ورک‌فلو در .env سرور قرار می‌گیرد (DIFY_ALLOCATION_KEY).
    # وب‌اپ Dify روی /app است؛ API سرویس روی /v1.
    dify_allocation_base: str = "http://38.252.8.181/v1"
    dify_allocation_key: str = ""
    # نام فیلد خروجی ورک‌فلو که متن سبد پیشنهادی را برمی‌گرداند (در صورت نیاز قابل تغییر).
    dify_allocation_output: str = "result"
    # ربات «الگو آنالایزر» که عضو کانال است؛ با توکن آن می‌توان پیام‌های کانال
    # (تحلیل‌های #طلا #تتر #btc #eth و …) را خواند و به ورک‌فلو داد.
    algo_analyzer_bot_token: str = ""
    # شناسهٔ کانال سیگنال‌ها و نشانی‌های عضویت/ثبت‌نام.
    algo_channel_id: str = "-1002341340633"
    algo_channel_url: str = "https://t.me/CRYPTOSMART_ORG"
    algo_signup_bot_url: str = "https://t.me/cryptosmart_futures_bot"

    # ---- سیگنال‌های کانال پورتفولیو (ربات portfolio_Cryptosmart_bot) ----
    # ربات تحلیل که ادمین کانال «Portfolio CryptoSmart» است. از طریق وب‌هوک تلگرام
    # پست‌های کانال (تحلیل ارز + نقاط خرید/فروش + تصویر چارت) دریافت و در دیتابیس
    # نگه داشته می‌شوند. هر تحلیل به مدت signals_ttl_days روز معتبر است و سپس
    # خودکار حذف می‌شود. این تحلیل‌ها به ورک‌فلوِ سبدچینی هوش مصنوعی خورانده می‌شوند.
    # ⚠️ توکن فقط در .env سرور (SIGNALS_BOT_TOKEN) قرار می‌گیرد، هرگز در کد.
    signals_bot_token: str = ""
    signals_channel_id: str = "-1004451073096"
    signals_channel_url: str = "https://t.me/Portfolio_CryptoSmart"
    signals_ttl_days: int = 7
    # نشانیِ عمومیِ این برنامه (برای ثبت وب‌هوک تلگرام و ساخت URL تصاویر).
    public_base_url: str = "https://portfolio.cryptosmart.site"
    # توکن مخفیِ تأیید وب‌هوک؛ اگر خالی باشد از admin_secret_key مشتق می‌شود.
    signals_webhook_secret: str = ""

    # ---- ایمیل (ارسال کد تأیید و بازیابی رمز از طریق Resend) ----
    # ارسال از طریق REST API سرویس Resend انجام می‌شود (با httpx، بدون وابستگی
    # اضافه). کلید فقط در .env سرور قرار می‌گیرد و هرگز در کد/مخزن نیست.
    # برای ارسال از آدرس دامنه، باید دامنه در Resend تأیید (DNS) شده باشد.
    resend_api_key: str = ""
    resend_api_url: str = "https://api.resend.com/emails"
    mail_from_email: str = "cryptosmart@cryptosmart.site"
    mail_from_name: str = "کریپتو اسمارت"
    # اعتبار و محدودیت کد یک‌بارمصرف
    auth_code_ttl: int = 600           # اعتبار کد: ۱۰ دقیقه
    auth_code_cooldown: int = 60       # حداقل فاصلهٔ ارسال مجدد کد (ثانیه)
    auth_code_max_attempts: int = 5    # حداکثر تلاش اشتباه برای هر کد
    session_ttl_days: int = 30         # طول عمر نشست ورود

    # ---- ادمین و اشتراک ----
    # ایمیل‌هایی که به‌صورت خودکار نقش «ادمین» می‌گیرند (با کاما جدا شوند).
    # اولین ادمین سیستم از همین فهرست بوت‌استرپ می‌شود.
    admin_emails: str = "cryptosmart@cryptosmart.site"
    # کلید رمزنگاریِ برگشت‌پذیرِ گذرواژه (فقط برای نمایش به ادمین). حتماً در
    # .env سرور با مقدار تصادفیِ بلند بازنویسی شود؛ مقدار پیش‌فرض ناامن است.
    admin_secret_key: str = "cs-change-this-in-env-please"
    # روزهای پیش‌فرض تمدید اشتراک
    subscription_renew_days: int = 30

    http_timeout: float = 10.0

    @property
    def admin_email_list(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    @property
    def signals_webhook_secret_effective(self) -> str:
        """توکن مخفیِ مؤثرِ وب‌هوک سیگنال‌ها (تنظیم‌شده یا مشتق از admin_secret_key)."""
        if self.signals_webhook_secret:
            return self.signals_webhook_secret
        import hashlib
        return hashlib.sha256(f"sig:{self.admin_secret_key}".encode()).hexdigest()[:40]


settings = Settings()
