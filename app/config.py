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
    # چت‌بات مدیریت سرمایه از پلتفرم Dify (سلف‌هاست؛ کلید در .env سرور).
    # وب‌اپ روی /app است؛ API سرویس روی /v1. قابل بازنویسی با DIFY_API_BASE در .env.
    dify_api_base: str = "http://38.252.8.181/v1"
    dify_api_key: str = ""

    http_timeout: float = 10.0


settings = Settings()
