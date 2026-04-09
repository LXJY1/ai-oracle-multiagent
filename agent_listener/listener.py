"""
Web3 Oracle Agent Listener
实现Agent监听服务，连接区块链和AI服务。
"""

import asyncio
import json
import os
from pathlib import Path
from eth_account.messages import encode_defunct
from web3 import Web3
import aiohttp
from dotenv import load_dotenv

# Load .env relative to this file so it works from any working directory
_DIR = Path(__file__).parent
load_dotenv(_DIR / ".env")

# 配置
RPC_URL = os.getenv("RPC_URL", "http://localhost:8545")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "0x...")
AGENT_PRIVATE_KEY = os.getenv("AGENT_PRIVATE_KEY")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8000/predict")
ABI_PATH = str(_DIR / os.getenv("ABI_PATH", "Oracle_abi.json"))

w3 = Web3(Web3.HTTPProvider(RPC_URL))
if w3.is_connected():
    print(f"Connected to blockchain: {w3.eth.chain_id}")

# 加载合约ABI（从 Hardhat artifacts 读取）
with open(ABI_PATH) as f:
    artifact = json.load(f)
    abi = artifact["abi"]
contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=abi)

# Agent地址
agent_account = w3.eth.account.from_key(AGENT_PRIVATE_KEY)
print(f"Agent address: {agent_account.address}")


async def process_request(request_id: int, query: str):
    """处理单个请求：调用AI服务，然后回链"""
    print(f"Processing request {request_id}: {query}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(AI_SERVICE_URL, json={"query": query}) as resp:
                data = await resp.json()
                result = data["result"]
                confidence = data.get("confidence", 0.0)
                result["confidence"] = confidence  # include in on-chain payload
                print(f"AI response for {request_id}: confidence={confidence}")

        # 将结果打包为bytes
        result_bytes = json.dumps(result).encode()

        # 签名
        signable = encode_defunct(result_bytes)
        signature = w3.eth.account.sign_message(signable, private_key=AGENT_PRIVATE_KEY).signature

        # 构建回调交易
        nonce = w3.eth.get_transaction_count(agent_account.address)
        tx = contract.functions.fulfillRequest(
            request_id,
            result_bytes,
            signature
        ).build_transaction({
            'from': agent_account.address,
            'nonce': nonce,
            'gas': 200000,
            'gasPrice': w3.eth.gas_price,
            'chainId': w3.eth.chain_id
        })

        signed_tx = agent_account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Fulfilled request {request_id}, tx: {tx_hash.hex()}")

    except aiohttp.ClientError as e:
        print(f"AI service error for request {request_id}: {e}")
    except Exception as e:
        print(f"Error processing request {request_id}: {e}")


async def listen_events():
    """监听区块链事件（轮询日志方式）"""
    print(f"Listening for OracleRequest events on {CONTRACT_ADDRESS}")

    last_block = w3.eth.block_number

    while True:
        try:
            current_block = w3.eth.block_number

            if current_block > last_block:
                logs = contract.events.OracleRequest.get_logs(
                    from_block=last_block + 1,
                    to_block=current_block
                )

                for log in logs:
                    request_id = log['args']['requestId']
                    query = log['args']['query']
                    requester = log['args']['requester']
                    print(f"New request {request_id} from {requester}: {query}")
                    asyncio.create_task(process_request(request_id, query))

                last_block = current_block

            await asyncio.sleep(2)

        except Exception as e:
            print(f"Error in listen loop: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(listen_events())
