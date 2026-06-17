"""
دادهٔ نمونهٔ واقع‌گرایانه برای زمانی که منبع بیرونی در دسترس نیست.
شکل این داده‌ها دقیقاً همان چیزی است که سرویس‌ها پس از نرمال‌سازی برمی‌گردانند،
پس فرانت‌اند تفاوتی بین «زنده» و «نمونه» در ساختار نمی‌بیند. هر پاسخ فیلد
"source": "live" | "sample" دارد تا در UI شفاف باشد.
"""
from __future__ import annotations


def macro() -> dict:
    return {
        "source": "sample",
        "stats": {
            "total_market_cap": {"value": 2_340_000_000_000, "change_24h": -1.57},
            "total_volume_24h": {"value": 33_950_000_000, "change_24h": -3.20},
            "btc_dominance": {"value": 56.3, "change_24h": 0.22},
            "eth_dominance": {"value": 9.24, "change_24h": 2.50},
            "eth_market_cap": {"value": 216_000_000_000, "change_24h": 0.89},
            "alt_market_cap": {"value": 1_021_000_000_000, "change_24h": -1.10},
            "usdt_dominance": {"value": 4.62, "change_24h": -0.04},
        },
        "heatmap": _heatmap(),
    }


def _heatmap() -> list[dict]:
    rows = [
        ("BTC", "Bitcoin", "Currency", 65541, -1.39, 1_300_000_000_000),
        ("ETH", "Ethereum", "Blockchain", 1788, 0.89, 216_000_000_000),
        ("BNB", "BNB", "Blockchain", 606.25, -1.51, 88_000_000_000),
        ("SOL", "Solana", "Blockchain", 138.0, -1.18, 66_000_000_000),
        ("XRP", "XRP", "Currency", 2.11, -1.99, 120_000_000_000),
        ("USDT", "Tether", "Stablecoin", 0.999, -0.04, 140_000_000_000),
        ("USDC", "USD Coin", "Stablecoin", 1.00, -0.01, 43_000_000_000),
        ("TRX", "TRON", "Blockchain", 0.27, 0.0, 24_000_000_000),
        ("ADA", "Cardano", "Blockchain", 0.62, 1.10, 22_000_000_000),
        ("DOGE", "Dogecoin", "Meme", 0.16, 1.20, 23_000_000_000),
        ("LINK", "Chainlink", "DeFi", 17.8, 2.40, 11_000_000_000),
        ("AVAX", "Avalanche", "Blockchain", 28.4, -1.20, 11_500_000_000),
        ("XLM", "Stellar", "Currency", 0.31, 0.90, 9_000_000_000),
        ("WBT", "WhiteBIT", "CeFi", 30.5, 0.20, 4_400_000_000),
        ("ZEC", "Zcash", "Currency", 49.5, 1.5, 8_110_000_000),
    ]
    return [
        {"symbol": s, "name": n, "category": c, "price": p, "change_24h": ch, "market_cap": mc}
        for (s, n, c, p, ch, mc) in rows
    ]


def cmc_macro() -> dict:
    """شاخص‌های کلان نمونه (هم‌شکل خروجی CoinMarketCap)."""
    return {
        "source": "sample",
        "market_cap": {"value": 2_260_000_000_000, "change_24h": -1.20},
        "volume_24h": {"value": 71_000_000_000, "change_24h": -3.40},
        "dominance": {"btc": 58.5, "eth": 9.5, "others": 32.0, "btc_change_24h": 0.18},
    }


def cmc_altseason() -> dict:
    """شاخص فصل آلت‌کوین نمونه."""
    return {"source": "sample", "altcoin_season": {
        "value": 47, "label_en": "Mixed", "label_fa": "بازار متعادل"}}


def toobit_heatmap() -> dict:
    """نقشهٔ حرارتی نمونه (بدون استیبل‌کوین، با چند میم‌کوین، اندازه بر اساس حجم)."""
    rows = [
        ("BTC", "Currency", 65541, -1.39, 9_000_000_000),
        ("ETH", "Smart Contract", 1788, 0.89, 4_000_000_000),
        ("SOL", "Smart Contract", 138.0, -1.18, 1_200_000_000),
        ("BNB", "Smart Contract", 606.25, -1.51, 900_000_000),
        ("XRP", "Currency", 2.11, -1.99, 1_500_000_000),
        ("DOGE", "Meme", 0.16, 1.20, 600_000_000),
        ("SHIB", "Meme", 0.000012, 2.30, 420_000_000),
        ("PEPE", "Meme", 0.0000089, -3.10, 380_000_000),
        ("WIF", "Meme", 1.42, 4.50, 190_000_000),
        ("BONK", "Meme", 0.000021, -2.10, 160_000_000),
        ("FLOKI", "Meme", 0.00014, 1.80, 120_000_000),
        ("TRX", "Smart Contract", 0.27, 0.0, 400_000_000),
        ("ADA", "Smart Contract", 0.62, 1.10, 350_000_000),
        ("LINK", "DeFi", 17.8, 2.40, 300_000_000),
        ("AVAX", "Smart Contract", 28.4, -1.20, 280_000_000),
        ("XLM", "Currency", 0.31, 0.90, 200_000_000),
        ("HYPE", "DeFi", 32.5, 5.10, 250_000_000),
        ("UNI", "DeFi", 7.4, -0.80, 140_000_000),
        ("DOT", "Smart Contract", 4.2, 0.40, 130_000_000),
        ("ZEC", "Currency", 49.5, 1.5, 150_000_000),
    ]
    return {"source": "sample", "heatmap": [
        {"symbol": s, "name": s, "category": c, "price": p, "change_24h": ch, "market_cap": v}
        for (s, c, p, ch, v) in rows
    ]}


def toobit_oil() -> dict:
    """نفت خام (دلار، هر بشکه) — از توبیت."""
    return {"source": "sample", "oil": {"name": "نفت خام", "sub": "بشکه", "price": 72.94, "change_24h": 1.21}}


def toobit_top_coins() -> dict:
    """ارزهای اصلی بازار (مارکت‌کپ بالا) — قیمت، تغییر ۲۴ساعته، حجم دلاری."""
    rows = [
        ("BTC", "BTCUSDT", 65541.0, 2.43, 1_300_000_000),
        ("ETH", "ETHUSDT", 1788.0, 0.89, 640_000_000),
        ("BNB", "BNBUSDT", 606.25, -1.51, 90_000_000),
        ("SOL", "SOLUSDT", 138.0, -1.18, 180_000_000),
        ("XRP", "XRPUSDT", 2.11, -1.99, 210_000_000),
    ]
    return {
        "source": "sample",
        "coins": [
            {"symbol": s, "pair": p, "price": pr, "change_24h": ch, "volume_24h": v}
            for (s, p, pr, ch, v) in rows
        ],
    }


def tabdeal_usdt() -> dict:
    """قیمت تتر — مستقیماً به تومان، بدون هیچ تبدیلی."""
    return {
        "source": "sample",
        "usdt_irt": {"name": "تتر / تومان", "price": 102_450, "change_24h": 0.35},
    }


def sourcearena_metals() -> dict:
    """طلای ۱۸ع (تومان/گرم) + انس طلا و نقره (دلار)."""
    return {
        "source": "sample",
        "usd_change_24h": 0.42,
        "gold_18k": {"name": "طلای ۱۸ عیار", "sub": "هر گرم", "price": 16_470_000, "change_24h": 0.65},
        "commodities": {
            "XAU": {"name": "طلای جهانی", "sub": "اونس", "price": 4326.2, "change_24h": 0.31},
            "XAG": {"name": "نقره", "sub": "اونس", "price": 69.9, "change_24h": -0.58},
        },
    }


def fear_greed() -> dict:
    return {"value": 22, "label_en": "Extreme Fear", "label_fa": "ترس شدید"}
