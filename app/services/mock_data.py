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
        "dominance": {"btc": 58.5, "eth": 9.5, "others": 32.0, "usdt": 5.12, "btc_change_24h": 0.18},
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


def toobit_gainers_losers() -> dict:
    """بیشترین رشد/افت نمونه (هم‌شکل خروجی توبیت)."""
    gainers = [
        ("TAC", "TACUSDT", 0.05915, 166.20),
        ("SYN", "SYNUSDT", 0.50383, 43.59),
        ("UB", "UBUSDT", 0.11861, 42.01),
    ]
    losers = [
        ("ESPORTS", "ESPORTSUSDT", 0.03692, -27.12),
        ("GUA", "GUAUSDT", 0.34428, -20.65),
        ("MANTA", "MANTAUSDT", 0.07584, -18.57),
    ]
    mk = lambda r: [{"symbol": s, "pair": p, "price": pr, "change_24h": ch} for (s, p, pr, ch) in r]
    return {"source": "sample", "gainers": mk(gainers), "losers": mk(losers)}


def toobit_swap_commodities() -> dict:
    """کالاهای جهانی (SWAP) — طلا/نقره/نفت از توبیت."""
    return {"source": "sample", "commodities": {
        "XAU": {"name": "انس طلا", "sub": "اونس", "price": 3326.5, "change_24h": 0.31},
        "XAG": {"name": "نقره جهانی", "sub": "اونس", "price": 36.4, "change_24h": -0.58},
        "OIL": {"name": "نفت برنت", "sub": "بشکه", "price": 72.94, "change_24h": 1.21},
    }}


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


def toobit_sparklines() -> dict:
    """شِماتیک قیمت نمونه (۲۴ نقطه) برای ۵ ارز برتر."""
    base = {
        "BTC": [62000, 62150, 61900, 62400, 62300, 62600, 62450, 62800, 62700, 63000,
                62850, 63200, 63050, 62900, 63100, 62950, 63300, 63150, 62800, 63126,
                63000, 63200, 63050, 63126],
        "ETH": [1690, 1695, 1688, 1700, 1698, 1705, 1702, 1710, 1708, 1715, 1712, 1709,
                1706, 1700, 1704, 1701, 1707, 1703, 1699, 1704, 1702, 1705, 1703, 1704],
        "BNB": [575, 576, 574, 578, 577, 580, 579, 582, 581, 584, 583, 580, 578, 576,
                579, 577, 581, 579, 576, 578, 577, 579, 578, 578],
        "SOL": [68.5, 68.8, 68.2, 69.1, 68.9, 69.4, 69.2, 69.8, 69.6, 70.0, 69.8, 69.5,
                69.2, 68.8, 69.1, 68.9, 69.3, 69.0, 68.6, 69.09, 68.9, 69.2, 69.0, 69.09],
        "XRP": [1.12, 1.125, 1.118, 1.13, 1.128, 1.135, 1.132, 1.14, 1.138, 1.13, 1.125,
                1.12, 1.115, 1.11, 1.118, 1.112, 1.122, 1.116, 1.11, 1.1356, 1.12, 1.13, 1.125, 1.1356],
    }
    return {"source": "sample", "sparklines": base}


def avg_rsi() -> dict:
    return {"source": "sample", "value": 46.43}


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
            "OIL": {"name": "نفت خام", "sub": "بشکه", "price": 72.94, "change_24h": 1.21},
        },
    }



def cr_heatmap() -> dict:
    """نقشهٔ حرارتی غنی نمونه (هم‌شکل خروجی CryptoRank): دسته + مارکت‌کپ + حجم +
    تغییر چنددوره‌ای. برای زمانی که CryptoRank در دسترس نیست."""
    # (symbol, name, category, price, market_cap, volume, h24, d7, d30, m3, y1, ytd)
    rows = [
        ("BTC", "Bitcoin", "Currency", 62392, 1_240_000_000_000, 38_000_000_000, -2.37, -5.1, 3.2, 12.4, 48.0, 22.1),
        ("ETH", "Ethereum", "Blockchain", 1688, 203_000_000_000, 18_000_000_000, -2.96, -7.3, -4.1, 6.2, 21.0, 9.4),
        ("XRP", "XRP", "Currency", 1.12, 64_000_000_000, 3_500_000_000, -3.86, -6.2, -8.0, 18.0, 220.0, 30.0),
        ("BNB", "BNB", "Blockchain", 571.61, 83_000_000_000, 1_800_000_000, -2.90, -3.1, 2.0, 9.0, 35.0, 14.0),
        ("SOL", "Solana", "Blockchain", 68.18, 31_000_000_000, 2_900_000_000, -4.19, -9.0, -12.0, -2.0, 60.0, -8.0),
        ("TRX", "TRON", "Blockchain", 0.322, 28_000_000_000, 900_000_000, 0.36, 1.2, 5.0, 14.0, 70.0, 25.0),
        ("DOGE", "Dogecoin", "Meme", 0.0822, 12_000_000_000, 800_000_000, -2.88, -6.0, -10.0, 4.0, 30.0, -5.0),
        ("ADA", "Cardano", "Blockchain", 0.62, 22_000_000_000, 600_000_000, -4.8, -8.0, -6.0, 2.0, 40.0, 3.0),
        ("HYPE", "Hyperliquid", "DeFi", 66.78, 22_000_000_000, 400_000_000, -6.71, -10.0, 5.0, 25.0, 120.0, 60.0),
        ("LINK", "Chainlink", "Infrastructure", 11.78, 7_000_000_000, 400_000_000, -2.16, -5.0, -3.0, 8.0, 25.0, 6.0),
        ("XLM", "Stellar", "Blockchain", 0.29, 9_000_000_000, 200_000_000, -8.84, -12.0, -9.0, -4.0, 90.0, -10.0),
        ("AVAX", "Avalanche", "Blockchain", 18.2, 7_500_000_000, 300_000_000, -6.0, -9.0, -7.0, 1.0, 20.0, -2.0),
        ("WBT", "WhiteBIT", "CeFi", 51.51, 7_400_000_000, 50_000_000, -2.49, -1.0, 4.0, 10.0, 45.0, 18.0),
        ("LEO", "UNUS SED LEO", "CeFi", 9.55, 8_800_000_000, 5_000_000, -1.17, 0.5, 2.0, 6.0, 15.0, 7.0),
        ("ZEC", "Zcash", "Currency", 466.0, 7_400_000_000, 400_000_000, -4.57, 12.0, 40.0, 120.0, 300.0, 250.0),
        ("XMR", "Monero", "Currency", 320.0, 5_900_000_000, 90_000_000, -2.02, -1.0, 5.0, 10.0, 30.0, 12.0),
        ("NEAR", "NEAR", "Blockchain", 1.8, 2_300_000_000, 150_000_000, -4.0, -6.0, -8.0, 0.0, 10.0, -5.0),
        ("UNI", "Uniswap", "DeFi", 6.0, 3_800_000_000, 200_000_000, -3.0, -5.0, -2.0, 5.0, 18.0, 4.0),
        ("AAVE", "Aave", "DeFi", 240.0, 3_600_000_000, 250_000_000, -2.0, -4.0, 6.0, 20.0, 80.0, 40.0),
        ("SHIB", "Shiba Inu", "Meme", 0.0000089, 5_200_000_000, 150_000_000, -3.1, -7.0, -11.0, 2.0, 12.0, -8.0),
        ("PEPE", "Pepe", "Meme", 0.0000089, 3_700_000_000, 300_000_000, -5.0, -9.0, -14.0, 3.0, 60.0, -12.0),
        ("LTC", "Litecoin", "Currency", 88.0, 6_600_000_000, 350_000_000, -3.0, -4.0, -1.0, 5.0, 20.0, 8.0),
        ("BCH", "Bitcoin Cash", "Currency", 480.0, 9_500_000_000, 400_000_000, -3.5, -5.0, 2.0, 12.0, 55.0, 20.0),
        ("ONDO", "Ondo", "DeFi", 0.7, 2_200_000_000, 120_000_000, -2.0, -3.0, 4.0, 15.0, 35.0, 10.0),
        ("LAB", "LayerAI", "Exchange", 15.0, 1_100_000_000, 60_000_000, -3.31, -6.0, -9.0, -2.0, 8.0, -4.0),
    ]
    return {"source": "sample", "items": [
        {"symbol": s, "name": n, "category": cat, "type": ("token" if s in ("HYPE", "ONDO", "LINK", "UNI", "AAVE", "SHIB", "PEPE", "DOGE", "LAB") else "coin"),
         "price": p, "market_cap": mc, "volume": vol,
         "changes": {"h24": h24, "d7": d7, "d30": d30, "m3": m3, "m6": y1}}
        for (s, n, cat, p, mc, vol, h24, d7, d30, m3, y1, ytd) in rows
    ]}


def commodities() -> dict:
    """کالاهای جهانی نمونه (طلا/نقره/نفت) — هم‌شکل خروجی Yahoo Finance."""
    _xau = [4290, 4310, 4302, 4330, 4325, 4348, 4360, 4351, 4375, 4368, 4380, 4374.94]
    _xag = [71.2, 71.5, 70.9, 71.8, 71.4, 70.8, 70.5, 70.9, 70.4, 70.6, 70.3, 70.31]
    _oil = [70.5, 71.2, 70.8, 72.1, 71.6, 72.8, 73.2, 72.5, 73.0, 72.6, 72.9, 72.94]
    return {"source": "sample", "commodities": {
        "XAU": {"name": "طلای جهانی", "sub": "اونس", "price": 4374.94, "change_24h": 0.31, "spark": _xau},
        "XAG": {"name": "نقره", "sub": "اونس", "price": 70.31, "change_24h": -0.58, "spark": _xag},
        "OIL": {"name": "نفت خام", "sub": "بشکه", "price": 72.94, "change_24h": 1.21, "spark": _oil},
    }}


def fear_greed() -> dict:
    return {"value": 22, "label_en": "Extreme Fear", "label_fa": "ترس شدید"}
