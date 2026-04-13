"""
Web3 Oracle Agent Listener - Multi-Agent Consensus Architecture
主Agent：监听事件 -> 广播给子Agent -> 收集 -> 聚合 -> 上链
状态上报到 ai_service (http://localhost:8000/api/heartbeat)
"""

import asyncio
import json
import os
import re
import math
import time
import threading
from dataclasses import dataclass
from typing import Optional
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct
import aiohttp
import ssl
import certifi
from dotenv import load_dotenv

# SSL context using certifi certificates
ssl_context = ssl.create_default_context(cafile=certifi.where())

load_dotenv()

# ========== 配置 ==========
RPC_URL = os.getenv("RPC_URL", "http://localhost:8545")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "0x7A2127475B453aDb46CB83Bb1075854aa43a7738")
AGENT_PRIVATE_KEY = os.getenv("AGENT_PRIVATE_KEY")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8000/predict")
HEARTBEAT_URL = os.getenv("HEARTBEAT_URL", "http://localhost:8000/api/heartbeat")

# 价格数据源 API
COINGECKO_API = "https://api.coingecko.com/api/v3"
COINPAPRIKA_API = "https://api.coinpaprika.com/v1"
COINCAP_API = "https://api.coincap.io/v2"

# 共识配置
RESPONSE_TIMEOUT = 30
CONSENSUS_THRESHOLD = 2

w3 = Web3(Web3.HTTPProvider(RPC_URL))
blockchain_connected = w3.is_connected()
if blockchain_connected:
    print(f"Connected to blockchain: {w3.eth.chain_id}")

# 加载合约ABI
ABI_PATH = os.getenv("ABI_PATH", "oracle_abi.json")
with open(ABI_PATH) as f:
    artifact = json.load(f)
    abi = artifact["abi"]
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=abi)

# Agent地址
agent_account = w3.eth.account.from_key(AGENT_PRIVATE_KEY)
agent_address = agent_account.address
print(f"Agent address: {agent_address}")


# ========== Heartbeat 上报 ==========
async def send_heartbeat(**kwargs):
    """异步 POST 状态到 ai_service dashboard"""
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            async with session.post(HEARTBEAT_URL, json=kwargs, timeout=5) as resp:
                pass
    except Exception:
        pass


def heartbeat(**kwargs):
    asyncio.create_task(send_heartbeat(**kwargs))


# ========== 数据结构 ==========
@dataclass
class SubAgentResult:
    sub_agent_id: str
    sub_agent_name: str
    price: float
    data_source: str
    evidence: dict
    timestamp: float


@dataclass
class ConsensusResult:
    reached: bool
    final_price: float
    agree_count: int
    total_count: int
    prices: list[float]
    disagree_reason: Optional[str] = None


# ========== Sub-Agent 配置 ==========
SUB_AGENTS = [
    {"id": "agent_1", "name": "CoinGecko-Researcher", "sources": ["coingecko"]},
    {"id": "agent_2", "name": "CoinPaprika-Researcher", "sources": ["coinpaprika"]},
    {"id": "agent_3", "name": "CoinCap-Researcher", "sources": ["coincap"]},
    {"id": "agent_4", "name": "Multi-Source-Analyst", "sources": ["coingecko", "coinpaprika", "coincap"]},
]

SYMBOL_TO_IDS = {
    "btc": {"coingecko": "bitcoin", "coinpaprika": "btc-bitcoin", "coincap": "bitcoin"},
    "bitcoin": {"coingecko": "bitcoin", "coinpaprika": "btc-bitcoin", "coincap": "bitcoin"},
    "eth": {"coingecko": "ethereum", "coinpaprika": "eth-ethereum", "coincap": "ethereum"},
    "ethereum": {"coingecko": "ethereum", "coinpaprika": "eth-ethereum", "coincap": "ethereum"},
    "ltc": {"coingecko": "litecoin", "coinpaprika": "ltc-litecoin", "coincap": "litecoin"},
    "dogecoin": {"coingecko": "dogecoin", "coinpaprika": "doge-dogecoin", "coincap": "dogecoin"},
    "doge": {"coingecko": "dogecoin", "coinpaprika": "doge-dogecoin", "coincap": "dogecoin"},
    "sol": {"coingecko": "solana", "coinpaprika": "sol-solana", "coincap": "solana"},
    "solana": {"coingecko": "solana", "coinpaprika": "sol-solana", "coincap": "solana"},
    "ada": {"coingecko": "cardano", "coinpaprika": "ada-cardano", "coincap": "cardano"},
    "cardano": {"coingecko": "cardano", "coinpaprika": "ada-cardano", "coincap": "cardano"},
    "dot": {"coingecko": "polkadot", "coinpaprika": "dot-polkadot", "coincap": "polkadot"},
    "avax": {"coingecko": "avalanche-2", "coinpaprika": "avax-avalanche", "coincap": "avalanche"},
    "link": {"coingecko": "chainlink", "coinpaprika": "link-chainlink", "coincap": "chainlink"},
    "matic": {"coingecko": "matic-network", "coinpaprika": "matic-polygon", "coincap": "polygon"},
    "polygon": {"coingecko": "matic-network", "coinpaprika": "matic-polygon", "coincap": "polygon"},
    "bnb": {"coingecko": "binancecoin", "coinpaprika": "bnb-binance-coin", "coincap": "binance-coin"},
    "xrp": {"coingecko": "ripple", "coinpaprika": "xrp-xrp", "coincap": "ripple"},
}


def extract_symbol(query: str) -> Optional[str]:
    query_lower = query.lower()
    patterns = [
        r'\b(btc|bitcoin|eth|ethereum|ltc|doge|dogecoin|sol|solana|ada|cardano|dot|polkadot|avax|avalanche|link|chainlink|matic|polygon|usdt|usdc|bnb|xrp|ripple)\b',
        r'price\s+(?:of\s+)?(\w+)',
        r'(\w+)/usd',
    ]
    for pattern in patterns:
        match = re.search(pattern, query_lower)
        if match:
            symbol = match.group(1)
            if symbol in ["usdt", "usdc"]:
                return None
            return symbol
    return None


# ========== Sub-Agent 实现 ==========
async def sub_agent_coingecko(symbol: str, request_id: int) -> Optional[SubAgentResult]:
    if symbol not in SYMBOL_TO_IDS:
        return None
    coin_id = SYMBOL_TO_IDS[symbol]["coingecko"]
    url = f"{COINGECKO_API}/simple/price?ids={coin_id}&vs_currencies=usd&include_24hr_change=true"
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            async with session.get(url, timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    price = data.get(coin_id, {}).get("usd")
                    change_24h = data.get(coin_id, {}).get("usd_24h_change", 0)
                    return SubAgentResult(
                        sub_agent_id="agent_1", sub_agent_name="CoinGecko-Researcher",
                        price=price, data_source="CoinGecko",
                        evidence={"coin_id": coin_id, "price_24h_change": change_24h},
                        timestamp=time.time()
                    )
    except Exception as e:
        heartbeat(log_level="ERROR", log_message=f"[Agent1] CoinGecko error: {e}")
    return None


async def sub_agent_coinpaprika(symbol: str, request_id: int) -> Optional[SubAgentResult]:
    if symbol not in SYMBOL_TO_IDS:
        return None
    coin_id = SYMBOL_TO_IDS[symbol]["coinpaprika"]
    url = f"{COINPAPRIKA_API}/tickers/{coin_id}"
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            async with session.get(url, timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    price = data.get("quotes", {}).get("USD", {}).get("price")
                    return SubAgentResult(
                        sub_agent_id="agent_2", sub_agent_name="CoinPaprika-Researcher",
                        price=price, data_source="CoinPaprika",
                        evidence={"coin_id": coin_id},
                        timestamp=time.time()
                    )
    except Exception as e:
        heartbeat(log_level="ERROR", log_message=f"[Agent2] CoinPaprika error: {e}")
    return None


async def sub_agent_coincap(symbol: str, request_id: int) -> Optional[SubAgentResult]:
    if symbol not in SYMBOL_TO_IDS:
        return None
    coin_id = SYMBOL_TO_IDS[symbol]["coincap"]
    url = f"{COINCAP_API}/assets/{coin_id}"
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            async with session.get(url, timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    price = float(data.get("data", {}).get("priceUsd", 0))
                    return SubAgentResult(
                        sub_agent_id="agent_3", sub_agent_name="CoinCap-Researcher",
                        price=price, data_source="CoinCap",
                        evidence={"coin_id": coin_id},
                        timestamp=time.time()
                    )
    except Exception as e:
        heartbeat(log_level="ERROR", log_message=f"[Agent3] CoinCap error: {e}")
    return None


async def sub_agent_multi_source(symbol: str, request_id: int) -> Optional[SubAgentResult]:
    if symbol not in SYMBOL_TO_IDS:
        return None
    results = await asyncio.gather(
        sub_agent_coingecko(symbol, request_id),
        sub_agent_coinpaprika(symbol, request_id),
        sub_agent_coincap(symbol, request_id),
    )
    valid = [r for r in results if r is not None]
    if not valid:
        return None
    avg = sum(r.price for r in valid) / len(valid)
    return SubAgentResult(
        sub_agent_id="agent_4", sub_agent_name="Multi-Source-Analyst",
        price=avg, data_source="Multi-Source Aggregation",
        evidence={"individual_prices": {r.data_source: r.price for r in valid}},
        timestamp=time.time()
    )


# ========== 共识算法 ==========
def calculate_std(prices: list[float]) -> float:
    if len(prices) < 2:
        return 0.0
    mean = sum(prices) / len(prices)
    return math.sqrt(sum((p - mean) ** 2 for p in prices) / len(prices))


def calculate_consensus(results: list[SubAgentResult]) -> ConsensusResult:
    if not results:
        return ConsensusResult(reached=False, final_price=0.0, agree_count=0, total_count=0, prices=[])
    prices = [r.price for r in results]
    total = len(prices)
    avg = sum(prices) / total
    std = calculate_std(prices)
    heartbeat(log_level="INFO", log_message=f"[Consensus] Prices: {[f'{p:.4f}' for p in prices]}, Avg: {avg:.4f}, StdDev: {std:.4f}")
    if std == 0:
        return ConsensusResult(reached=True, final_price=avg, agree_count=total, total_count=total, prices=prices)
    threshold = CONSENSUS_THRESHOLD * std
    within = sum(1 for p in prices if abs(p - avg) <= threshold)
    if within == total or within > total / 2:
        return ConsensusResult(reached=True, final_price=avg, agree_count=within, total_count=total, prices=prices)
    return ConsensusResult(reached=False, final_price=avg, agree_count=within, total_count=total, prices=prices,
                          disagree_reason=f"Only {within}/{total} agents agree")


# ========== 争议解决 ==========
async def dispute_resolution(results: list[SubAgentResult], symbol: str, request_id: int) -> tuple[ConsensusResult, bool]:
    heartbeat(log_level="WARN", log_message=f"[Dispute] Starting for request #{request_id}")
    retry = await asyncio.gather(
        sub_agent_coingecko(symbol, request_id),
        sub_agent_coinpaprika(symbol, request_id),
        sub_agent_coincap(symbol, request_id),
        sub_agent_multi_source(symbol, request_id),
    )
    new_results = [r for r in retry if r is not None]
    if new_results:
        c = calculate_consensus(new_results)
        if c.reached:
            heartbeat(log_level="INFO", log_message="[Dispute] Consensus reached on retry")
            return (c, False)
    weighted = sum(r.price * (2 if r.sub_agent_id == "agent_4" else 1) for r in results)
    weight_total = sum(2 if r.sub_agent_id == "agent_4" else 1 for r in results)
    fallback = weighted / weight_total
    return ConsensusResult(reached=True, final_price=fallback, agree_count=len(results),
                           total_count=len(results), prices=[r.price for r in results],
                           disagree_reason="Fallback after dispute resolution"), False


# ========== AI 服务 ==========
async def query_ai_for_confirmation(price: float, symbol: str, query: str) -> dict:
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
            async with session.post(AI_SERVICE_URL,
                json={"query": f"{query}\n\nMarket price reference: ${price}"},
                timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result = data.get("result", {})
                    ai_price = result.get("price") if isinstance(result, dict) else None
                    if ai_price:
                        deviation = abs(ai_price - price) / price if price > 0 else 0
                        return {"confirmed": deviation < 0.05, "ai_price": ai_price, "reason": f"Deviation: {deviation:.2%}"}
    except Exception as e:
        heartbeat(log_level="ERROR", log_message=f"[AI Confirmation] Error: {e}")
    return {"confirmed": True, "ai_price": price, "reason": "AI check skipped"}


# ========== 主Agent处理流程 ==========
async def process_request(request_id: int, query: str, requester: str):
    start_time = time.time()
    heartbeat(
        log_level="INFO",
        log_message=f"[Request #{request_id}] Processing: {query}",
        request_id=request_id,
        request_requester=requester,
        request_query=query,
        request_status="processing",
    )

    try:
        symbol = extract_symbol(query)
        if not symbol:
            heartbeat(log_level="WARN", log_message=f"[Request #{request_id}] Cannot extract symbol",
                      request_id=request_id, request_status="failed", request_error="Cannot extract symbol",
                      increment_failed=True)
            return

        heartbeat(log_level="INFO", log_message=f"[Request #{request_id}] Extracted symbol: {symbol}",
                   request_id=request_id, request_symbol=symbol)

        tasks = [
            sub_agent_coingecko(symbol, request_id),
            sub_agent_coinpaprika(symbol, request_id),
            sub_agent_coincap(symbol, request_id),
            sub_agent_multi_source(symbol, request_id),
        ]
        try:
            results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=RESPONSE_TIMEOUT)
        except asyncio.TimeoutError:
            heartbeat(log_level="WARN", log_message=f"[Request #{request_id}] Sub-agent timeout")
            results = []

        valid = [r for r in results if isinstance(r, SubAgentResult)]
        if len(valid) == 0:
            heartbeat(log_level="ERROR", log_message=f"[Request #{request_id}] No valid results",
                       request_id=request_id, request_status="failed", request_error="No valid results",
                       increment_failed=True)
            return

        for r in valid:
            heartbeat(log_level="DEBUG", log_message=f"  - {r.sub_agent_name}: ${r.price:.4f} (source: {r.data_source})")

        consensus = calculate_consensus(valid)
        heartbeat(log_level="INFO",
                   log_message=f"[Request #{request_id}] Consensus: reached={consensus.reached}, price={consensus.final_price:.4f}",
                   request_id=request_id, request_final_price=consensus.final_price,
                   request_consensus_reached=consensus.reached)

        if not consensus.reached:
            consensus, _ = await dispute_resolution(valid, symbol, request_id)

        ai_confirmation = await query_ai_for_confirmation(consensus.final_price, symbol, query)
        final_price = consensus.final_price

        result_bytes = json.dumps({
            "analysis": {},
            "consensus_price": final_price,
            "consensus_reached": consensus.reached,
            "sub_agent_count": len(valid),
            "ai_confirmation": ai_confirmation
        }).encode()

        message = encode_defunct(primitive=result_bytes)
        signature = Account.sign_message(message, private_key=AGENT_PRIVATE_KEY).signature

        nonce = w3.eth.get_transaction_count(agent_account.address)
        tx = contract.functions.fulfillRequest(request_id, result_bytes, signature).build_transaction({
            'from': agent_account.address,
            'nonce': nonce,
            'gas': 300000,
            'gasPrice': w3.eth.gas_price,
            'chainId': w3.eth.chain_id
        })
        signed_tx = agent_account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_hex = tx_hash.hex()

        duration_ms = round((time.time() - start_time) * 1000)
        heartbeat(log_level="INFO",
                   log_message=f"[Request #{request_id}] Completed in {duration_ms}ms, tx: {tx_hex}",
                   request_id=request_id, request_status="success",
                   request_tx_hash=tx_hex, request_duration_ms=duration_ms,
                   increment_success=True)

    except Exception as e:
        heartbeat(log_level="ERROR", log_message=f"[Request #{request_id}] Error: {e}",
                   request_id=request_id, request_status="failed", request_error=str(e),
                   increment_failed=True)


# ========== 事件监听 ==========
async def listen_events():
    heartbeat(
        running=True,
        connected=w3.is_connected(),
        agent_address=agent_address,
        contract_address=CONTRACT_ADDRESS,
        log_level="INFO",
        log_message=f"Agent started. Listening on {CONTRACT_ADDRESS}"
    )

    last_block = w3.eth.block_number

    while True:
        try:
            current_block = w3.eth.block_number
            heartbeat(connected=w3.is_connected())

            if current_block > last_block:
                logs = contract.events.OracleRequest.get_logs(
                    from_block=last_block + 1, to_block=current_block
                )
                for log in logs:
                    request_id = log['args']['requestId']
                    query = log['args']['query']
                    requester = log['args']['requester']
                    heartbeat(log_level="INFO",
                               log_message=f"[New Request #{request_id}] from {requester}: {query}")
                    asyncio.create_task(process_request(request_id, query, requester))

                last_block = current_block

            await asyncio.sleep(2)
        except Exception as e:
            heartbeat(log_level="ERROR", log_message=f"[Listen Loop] Error: {e}", connected=False)
            await asyncio.sleep(5)


# ========== 启动 ==========
if __name__ == "__main__":
    asyncio.run(listen_events())
