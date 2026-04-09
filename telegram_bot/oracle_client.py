import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from web3 import Web3

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

_RPC_URL = os.environ["RPC_URL"]
_CONTRACT_ADDRESS = os.environ.get("CONTRACT_ADDRESS", "0x7A2127475B453aDb46CB83Bb1075854aa43a7738")
_BOT_PRIVATE_KEY = os.environ["BOT_PRIVATE_KEY"]
_POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", 3))
_REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", 120))

w3 = Web3(Web3.HTTPProvider(_RPC_URL))

_abi_path = Path(__file__).parent / "../agent_listener/Oracle_abi.json"
with open(_abi_path) as _f:
    _CONTRACT_ABI = json.load(_f)["abi"]

contract = w3.eth.contract(
    address=Web3.to_checksum_address(_CONTRACT_ADDRESS),
    abi=_CONTRACT_ABI,
)

_raw_key = _BOT_PRIVATE_KEY if _BOT_PRIVATE_KEY.startswith("0x") else "0x" + _BOT_PRIVATE_KEY
bot_account = w3.eth.account.from_key(_raw_key)

_balance_wei = w3.eth.get_balance(bot_account.address)
_balance_eth = w3.from_wei(_balance_wei, "ether")
print(f"Bot wallet: {bot_account.address}, Balance: {_balance_eth} ETH")


def submit_request(query: str) -> int:
    nonce = w3.eth.get_transaction_count(bot_account.address)
    gas_price = int(w3.eth.gas_price * 1.5)  # 1.5x to avoid mempool drops
    tx = contract.functions.requestData(query).build_transaction(
        {
            "gas": 200000,
            "gasPrice": gas_price,
            "nonce": nonce,
            "chainId": w3.eth.chain_id,
        }
    )
    signed = bot_account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"[oracle] requestData tx: {tx_hash.hex()}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

    logs = contract.events.OracleRequest().process_receipt(receipt)
    request_id = int(logs[0]["args"]["requestId"])
    return request_id


def wait_for_result(request_id: int, timeout: int = None) -> dict:
    deadline = time.time() + (timeout if timeout is not None else _REQUEST_TIMEOUT)
    while time.time() < deadline:
        try:
            result_bytes = contract.functions.getResult(request_id).call()
            return json.loads(result_bytes.decode("utf-8"))
        except Exception:
            time.sleep(_POLL_INTERVAL)
    raise TimeoutError("Oracle did not respond in time")


def get_bot_address() -> str:
    return bot_account.address
