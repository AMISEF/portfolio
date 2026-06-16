"""
دادهٔ نمونهٔ واقع‌گرایانه برای زمانی که منبع بیرونی در دسترس نیست
(مثلاً در محیط توسعه بدون دسترسی شبکه، یا خطای موقت API).

شکل این داده‌ها دقیقاً همان چیزی است که سرویس‌ها پس از نرمال‌سازی برمی‌گردانند،
بنابراین فرانت‌اند تفاوتی بین دادهٔ زنده و نمونه نمی‌بیند. هر پاسخ دارای فیلد
"source": "live" | "sample" است تا در UI شفاف باشد.
"""
from __future__ import annotations


def macro() -> dict:
    """شاخص‌های کلان بازار + نوار تیکر + هیت‌مپ + ترس و طمع."""
    return {
        "source": "sample",
        "stats": {
            "total_market_cap": {"value": 2_320_000_000_000, "change_24h": 2.32},
            "total_volume_24h": {"value": 30_140_000_000, "change_24h": 4.08},
            "btc_dominance": {"value": 56.7, "change_24h": 0.11},
            "eth_dominance": {"value": 8.93, "change_24h": 0.30},
            "eth_market_cap": {"value": 207_000_000_000, "change_24h": 2.63},
            "alt_market_cap": {"value": 1_004_560_000_000, "change_24h": 1.87},
            "usdt_dominance": {"value": 4.62, "change_24h": -0.04},
        },
        "fear_greed": {"value": 20, "label_en": "Extreme Fear", "label_fa": "ترس شدید"},
        "heatmap": _heatmap(),
    }


def _heatmap() -> list[dict]:
    rows = [
        ("BTC", "Bitcoin", "Currency", 65803, 2.43, 1_300_000_000_000),
        ("ETH", "Ethereum", "Blockchain", 1719, 2.63, 207_000_000_000),
        ("BNB", "BNB", "Blockchain", 617.1, 1.05, 88_000_000_000),
        ("SOL", "Solana", "Blockchain", 171.0, 4.65, 78_000_000_000),
        ("XRP", "XRP", "Currency", 2.11, 0.71, 120_000_000_000),
        ("USDT", "Tether", "Stablecoin", 0.999, -0.01, 110_000_000_000),
        ("USDC", "USD Coin", "Stablecoin", 1.00, 0.0, 40_000_000_000),
        ("TRX", "TRON", "Blockchain", 0.27, 1.30, 24_000_000_000),
        ("ADA", "Cardano", "Blockchain", 0.62, 1.10, 22_000_000_000),
        ("DOGE", "Dogecoin", "Meme", 0.16, 3.20, 23_000_000_000),
        ("HYPE", "Hyperliquid", "DeFi", 32.5, 5.10, 14_440_000_000),
        ("LINK", "Chainlink", "DeFi", 17.8, 2.40, 11_000_000_000),
        ("AVAX", "Avalanche", "Blockchain", 28.4, -1.20, 11_500_000_000),
        ("XLM", "Stellar", "Currency", 0.31, 0.90, 9_000_000_000),
        ("ZEC", "Zcash", "Currency", 497.57, 17.5, 8_110_000_000),
    ]
    return [
        {"symbol": s, "name": n, "category": c, "price": p, "change_24h": ch, "market_cap": mc}
        for (s, n, c, p, ch, mc) in rows
    ]


def toobit_gainers() -> dict:
    """تاپ گینرهای صرافی توبیت (۵ ارز)."""
    rows = [
        ("PUFFER", "PUFFERUSDT", 0.0261, 76.6, 12_300_000),
        ("ASTEROID", "ASTEROIDUSDT", 0.000107, 75.1, 44_600_000),
        ("DN", "DNUSDT", 0.901, 64.6, 21_900_000),
        ("JELLYJELLY", "JELLYJELLYUSDT", 0.0915, 45.3, 89_800_000),
        ("CLO", "CLOUSDT", 0.259, 43.9, 33_700_000),
    ]
    return {
        "source": "sample",
        "gainers": [
            {"symbol": s, "pair": p, "price": pr, "change_24h": ch, "volume_24h": v}
            for (s, p, pr, ch, v) in rows
        ],
    }


def toobit_futures() -> dict:
    """قیمت فیوچرز فلزات و نفت از توبیت."""
    return {
        "source": "sample",
        "futures": {
            "XAUUSDT": {"name": "طلای جهانی (اونس)", "price": 2_648.30, "change_24h": 0.42},
            "XAGUSDT": {"name": "نقره (اونس)", "price": 31.18, "change_24h": -0.65},
            "OILBRENTUSDT": {"name": "نفت برنت", "price": 72.94, "change_24h": 1.21},
        },
    }


def tabdeal_usdt() -> dict:
    """قیمت تتر تومانی از صرافی تبدیل (تومان)."""
    return {
        "source": "sample",
        "usdt_irt": {"name": "تتر / تومان", "price": 102_450, "change_24h": 0.35},
    }


def sourcearena_gold() -> dict:
    """قیمت طلای ۱۸ عیار (تومان به ازای هر گرم)."""
    return {
        "source": "sample",
        "gold_18k": {"name": "طلای ۱۸ عیار (گرم)", "price": 6_540_000, "change_24h": 0.58, "unit": "تومان"},
    }
