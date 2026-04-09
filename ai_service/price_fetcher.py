import requests
from datetime import datetime

SYMBOL_MAP = {
    "btc": {"coingecko": "bitcoin", "okx": "BTC-USDT"},
    "bitcoin": {"coingecko": "bitcoin", "okx": "BTC-USDT"},
    "eth": {"coingecko": "ethereum", "okx": "ETH-USDT"},
    "ethereum": {"coingecko": "ethereum", "okx": "ETH-USDT"},
    "sol": {"coingecko": "solana", "okx": "SOL-USDT"},
    "solana": {"coingecko": "solana", "okx": "SOL-USDT"},
    "bnb": {"coingecko": "binancecoin", "okx": "BNB-USDT"},
    "matic": {"coingecko": "matic-network", "okx": "MATIC-USDT"},
    "polygon": {"coingecko": "matic-network", "okx": "MATIC-USDT"},
    "avax": {"coingecko": "avalanche-2", "okx": "AVAX-USDT"},
    "doge": {"coingecko": "dogecoin", "okx": "DOGE-USDT"},
    "dogecoin": {"coingecko": "dogecoin", "okx": "DOGE-USDT"},
    "ada": {"coingecko": "cardano", "okx": "ADA-USDT"},
    "cardano": {"coingecko": "cardano", "okx": "ADA-USDT"},
    "link": {"coingecko": "chainlink", "okx": "LINK-USDT"},
    "chainlink": {"coingecko": "chainlink", "okx": "LINK-USDT"},
    "dot": {"coingecko": "polkadot", "okx": "DOT-USDT"},
    "xrp": {"coingecko": "ripple", "okx": "XRP-USDT"},
}


def resolve_symbol(user_input: str) -> dict | None:
    key = user_input.lower().strip()
    return SYMBOL_MAP.get(key)


def fetch_okx_price(okx_symbol: str) -> float | None:
    try:
        response = requests.get(
            "https://www.okx.com/api/v5/market/ticker",
            params={"instId": okx_symbol},
            timeout=5,
        )
        response.raise_for_status()
        data = response.json().get("data", [])
        if not data:
            return None
        return float(data[0]["last"])
    except Exception:
        return None


def fetch_coingecko_price(coingecko_id: str) -> float | None:
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": coingecko_id, "vs_currencies": "usd"},
            timeout=5,
        )
        response.raise_for_status()
        return float(response.json()[coingecko_id]["usd"])
    except Exception:
        return None


def calculate_confidence(prices: dict[str, float]) -> float:
    if len(prices) == 1:
        return 0.80
    values = list(prices.values())
    p1, p2 = values[0], values[1]
    avg = (p1 + p2) / 2
    deviation = abs(p1 - p2) / avg
    if deviation < 0.005:
        return 0.95
    if deviation < 0.02:
        return 0.85
    if deviation < 0.05:
        return 0.70
    return 0.50


def get_price(symbol_input: str) -> dict:
    mapping = resolve_symbol(symbol_input)
    if mapping is None:
        raise ValueError(f"Unknown symbol: '{symbol_input}'")

    okx_price = fetch_okx_price(mapping["okx"])
    coingecko_price = fetch_coingecko_price(mapping["coingecko"])

    prices: dict[str, float] = {}
    if okx_price is not None:
        prices["okx"] = okx_price
    if coingecko_price is not None:
        prices["coingecko"] = coingecko_price

    if not prices:
        raise RuntimeError("All price sources unavailable")

    if len(prices) == 2:
        total_weight = 1.0 + 0.95
        aggregated_price = (prices["okx"] * 1.0 + prices["coingecko"] * 0.95) / total_weight
    else:
        aggregated_price = next(iter(prices.values()))

    confidence = calculate_confidence(prices)

    return {
        "symbol": symbol_input.upper(),
        "price": round(aggregated_price, 4),
        "currency": "USD",
        "sources": list(prices.keys()),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "confidence": confidence,
    }
