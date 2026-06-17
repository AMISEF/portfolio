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

    # ---- Toobit (تاپ گینرها + تصاویر ارز) ----
    toobit_access_key: str = ""
    toobit_secret_key: str = ""
    toobit_base_url: str = "https://api.toobit.com"
    toobit_ttl: int = 12
    toobit_gainers_count: int = 5

    # ---- Tabdeal (تتر تومانی — بدون هیچ تبدیلی) ----
    tabdeal_api_key: str = ""
    tabdeal_api_secret: str = ""
    tabdeal_base_url: str = "https://api.tabdeal.org"
    tabdeal_ttl: int = 15

    # ---- SourceArena (طلای ۱۸ عیار — هر نیم ساعت) ----
    sourcearena_token: str = ""
    # برای دسترسی از سرور خارج از ایران
    sourcearena_base_url: str = "https://sa.resicard.ir/api"
    sourcearena_ttl: int = 1800

    # ---- شاخص ترس و طمع ----
    fng_base_url: str = "https://api.alternative.me/fng/"
    fng_ttl: int = 600

    # مسیر فایل پایدار شمارندهٔ کردیت
    credit_state_file: str = "data/credit_state.json"

    http_timeout: float = 10.0


settings = Settings()
