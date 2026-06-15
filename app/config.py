"""
پیکربندی مرکزی پروژه CryptoSmart Hub.

تمام کلیدهای API و تنظیمات کش/بودجه از متغیرهای محیطی (.env) خوانده می‌شوند.
هیچ کلید واقعی در این فایل hard-code نمی‌شود؛ مقادیر پیش‌فرض فقط برای اجرای
محلی و توسعه هستند. روی سرور، فایل .env را با کلیدهای واقعی قرار دهید.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ---- اطلاعات کلی برنامه ----
    app_name: str = "CryptoSmart Hub"
    app_brand_fa: str = "کریپتو اسمارت"
    app_title_fa: str = "پنل مدیریت سرمایه"
    debug: bool = True

    # ---- CryptoRank (داده‌های کلان بازار + هیت‌مپ) ----
    cryptorank_api_key: str = ""
    cryptorank_base_url: str = "https://api.cryptorank.io/v2"
    # بودجهٔ کردیت طبق پلن رایگان: ۱۰هزار در ماه، ۴۰۰ در روز، ۱۰۰ در دقیقه
    cryptorank_monthly_credits: int = 10_000
    cryptorank_daily_credits: int = 400
    cryptorank_per_min_credits: int = 100
    # هزینهٔ تخمینی هر فراخوانی (credit). محافظه‌کارانه؛ روی سرور قابل تنظیم.
    cryptorank_cost_global: int = 1
    cryptorank_cost_currencies: int = 1
    # TTL کش به ثانیه — ۱۰ دقیقه تا مصرف ماهانه زیر سقف بماند
    # ۲ فراخوانی هر ۱۰ دقیقه ⇒ ~۸٬۶۴۰ کردیت در ماه (< ۱۰٬۰۰۰)
    cryptorank_ttl: int = 600

    # ---- Toobit (تاپ گینرها + فیوچرز فلزات/نفت) ----
    toobit_access_key: str = ""
    toobit_secret_key: str = ""
    toobit_base_url: str = "https://api.toobit.com"
    # دامنهٔ فیوچرز توبیت (قراردادهای XAU/XAG/OIL)
    toobit_futures_base_url: str = "https://api.toobit.com"
    toobit_ttl: int = 12          # قیمت‌های لحظه‌ای — هر ~۱۲ ثانیه
    toobit_gainers_count: int = 5
    # نمادهای فیوچرز موردنظر
    toobit_futures_symbols: str = "XAUUSDT,XAGUSDT,OILBRENTUSDT"

    # ---- Tabdeal (قیمت تتر تومانی) ----
    tabdeal_api_key: str = ""
    tabdeal_api_secret: str = ""
    tabdeal_base_url: str = "https://api.tabdeal.org"
    tabdeal_ttl: int = 15

    # ---- SourceArena (طلای ۱۸ عیار — سرور خارج) ----
    sourcearena_token: str = ""
    sourcearena_base_url: str = "https://sa.resicard.ir/api"
    sourcearena_ttl: int = 1800   # طبق درخواست: هر نیم ساعت یک‌بار

    # ---- Fear & Greed (alternative.me به‌عنوان منبع جایگزین) ----
    fng_base_url: str = "https://api.alternative.me/fng"
    fng_ttl: int = 600

    # مسیر فایل پایدار شمارندهٔ کردیت
    credit_state_file: str = "data/credit_state.json"

    # مهلت زمانی درخواست‌های HTTP خروجی (ثانیه)
    http_timeout: float = 10.0

    # ---- احراز هویت و دیتابیس ----
    # کلید امضای کوکی نشست — حتماً روی سرور در .env مقدار تصادفی بدهید
    secret_key: str = "change-me-in-production-please-set-a-long-random-value"
    database_url: str = "sqlite:///data/cryptosmart.db"
    session_max_age: int = 60 * 60 * 24 * 30  # ۳۰ روز
    # توکن ربات تلگرام (برای احراز هویت مینی‌اپ — اختیاری در فاز فعلی)
    telegram_bot_token: str = ""


settings = Settings()
