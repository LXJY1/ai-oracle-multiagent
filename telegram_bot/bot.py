from __future__ import annotations

import asyncio
import os
import re

import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.request import HTTPXRequest
from web3 import Web3

import oracle_client

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
HTTPS_PROXY: str = os.getenv("HTTPS_PROXY", "http://127.0.0.1:7890")
AI_SERVICE_URL: str = os.getenv("AI_SERVICE_URL", "http://localhost:8000/predict")

# Detect price intent in plain text
_PRICE_INTENT = re.compile(
    r"\b(price|worth|cost|value|rate|how much|convert)\b.*\b(btc|eth|sol|bnb|doge|ada|xrp|matic|avax|link|dot|bitcoin|ethereum|solana|dogecoin|cardano|ripple|polkadot|chainlink|polygon|avalanche)\b"
    r"|\b(btc|eth|sol|bnb|doge|ada|xrp|matic|avax|link|dot|bitcoin|ethereum|solana|dogecoin|cardano|ripple|polkadot|chainlink|polygon|avalanche)\b.*(price|worth|cost|value|rate)",
    re.IGNORECASE,
)

WELCOME_TEXT = (
    "🔮 OracleX — AI Crypto Oracle Bot\n\n"
    "I have two modes:\n\n"
    "💬 Chat mode (instant, free):\n"
    "  Just type anything — prices, questions, whatever\n"
    "  e.g.  ETH price?   what is Bitcoin?   hi\n\n"
    "⛓️ On-chain Oracle mode (verified on Sepolia):\n"
    "  /oracle <query>  — submits to smart contract, result written on-chain\n"
    "  e.g.  /oracle ETH price\n"
    "        /oracle how much is SOL?\n\n"
    "Other commands:\n"
    "  /price <symbol>  — quick price check (no chain)\n"
    "  /status          — bot wallet & contract info\n"
    "  /help            — show this message"
)


def _chat_with_llm(message: str) -> str:
    try:
        resp = requests.post(
            AI_SERVICE_URL.replace("/predict", "/chat"),
            json={"message": message},
            timeout=30,
        )
        if resp.ok:
            return resp.json().get("reply", "")
    except Exception:
        pass
    return ""


def _quick_price(symbol: str) -> str:
    try:
        resp = requests.post(
            AI_SERVICE_URL,
            json={"query": f"{symbol} price"},
            timeout=15,
        )
        if not resp.ok:
            return f"❌ Service error: {resp.status_code}"
        data = resp.json()
        r = data["result"]
        if "error" in r:
            return f"❌ {r['error']}"
        confidence = data.get("confidence", 0)
        return (
            f"💰 {r['symbol']} Price\n\n"
            f"Price:      ${r['price']:,.2f} {r.get('currency', 'USD')}\n"
            f"Confidence: {confidence * 100:.0f}%\n"
            f"Sources:    {', '.join(r.get('sources', []))}\n"
            f"Updated:    {r.get('timestamp', '?')}\n"
            f"(off-chain · use /oracle for on-chain verification)"
        )
    except Exception as e:
        return f"❌ Error: {e}"


def _format_result(result: dict, request_id: int) -> str:
    symbol: str = result.get("symbol", "?")
    price: float = result.get("price", 0.0)
    currency: str = result.get("currency", "USD")
    sources_raw = result.get("sources", [])
    sources: str = ", ".join(sources_raw) if isinstance(sources_raw, list) else str(sources_raw)
    timestamp: str = result.get("timestamp", "?")

    confidence_raw = result.get("confidence")
    if confidence_raw is None:
        confidence_str = "N/A"
    elif isinstance(confidence_raw, float) and confidence_raw <= 1.0:
        confidence_str = f"{confidence_raw * 100:.0f}%"
    else:
        confidence_str = f"{confidence_raw}%"

    return (
        f"🔮 Oracle Result  #{request_id}\n\n"
        f"Token:      {symbol}\n"
        f"Price:      ${price:,.2f} {currency}\n"
        f"Confidence: {confidence_str}\n"
        f"Sources:    {sources}\n"
        f"Updated:    {timestamp}\n"
        "⛓️ Verified on Sepolia"
    )


async def _handle_oracle_query(update: Update, query: str) -> None:
    assert update.message is not None
    interim = await update.message.reply_text("⏳ Submitting to Oracle contract...")

    try:
        request_id: int = await asyncio.to_thread(oracle_client.submit_request, query)
        await interim.edit_text(
            f"⛓️ Request #{request_id} submitted.\n"
            f"⏳ Waiting for Agent to process and write result on-chain..."
        )
        result: dict = await asyncio.to_thread(oracle_client.wait_for_result, request_id)
        await interim.delete()
        await update.message.reply_text(_format_result(result, request_id))

    except TimeoutError:
        await interim.edit_text(
            "⏰ Timeout — the Agent did not respond in time.\n"
            "Make sure agent_listener is running."
        )
    except Exception as e:
        await interim.edit_text(f"❌ Error: {e}")


async def _handle_chat(update: Update, message: str) -> None:
    assert update.message is not None
    interim = await update.message.reply_text("💬 Thinking...")
    try:
        reply = await asyncio.to_thread(_chat_with_llm, message)
        if reply:
            await interim.edit_text(reply)
        else:
            await interim.edit_text(
                "🤖 I couldn't get a response from the AI right now.\n"
                "For crypto prices, try: ETH price"
            )
    except Exception as e:
        await interim.edit_text(f"❌ Error: {e}")


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    await update.message.reply_text(WELCOME_TEXT)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    await update.message.reply_text(WELCOME_TEXT)


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    try:
        address: str = oracle_client.get_bot_address()
        w3 = Web3(Web3.HTTPProvider(oracle_client._RPC_URL))
        balance_wei = await asyncio.to_thread(w3.eth.get_balance, address)
        balance_eth = float(w3.from_wei(balance_wei, "ether"))
        await update.message.reply_text(
            f"🤖 Bot wallet: {address}\n"
            f"💰 Balance: {balance_eth:.4f} ETH\n"
            f"⛓️ Contract: 0x7A2127475B453aDb46CB83Bb1075854aa43a7738\n"
            f"🌐 Network: Sepolia"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error fetching status: {e}")


async def price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Quick off-chain price check."""
    assert update.message is not None
    if not context.args:
        await update.message.reply_text("Usage: /price <symbol>  — e.g. /price BTC")
        return
    symbol = context.args[0].upper()
    interim = await update.message.reply_text(f"💰 Fetching {symbol} price...")
    result = await asyncio.to_thread(_quick_price, symbol)
    await interim.edit_text(result)


async def oracle_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Full on-chain Oracle flow."""
    assert update.message is not None
    if not context.args:
        await update.message.reply_text(
            "Usage: /oracle <query>\n"
            "e.g.  /oracle ETH price\n"
            "      /oracle how much is Bitcoin?"
        )
        return
    query = " ".join(context.args)
    await _handle_oracle_query(update, query)


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message is not None
    query = (update.message.text or "").strip()
    if not query:
        return

    lower = query.lower()

    # "oracle ..." without slash → on-chain flow
    if lower.startswith("oracle "):
        await _handle_oracle_query(update, query[7:].strip())
        return

    # Price intent detected → quick off-chain price (same as /price)
    if _PRICE_INTENT.search(query):
        # Extract symbol from query via AI service
        interim = await update.message.reply_text("💰 Fetching price...")
        try:
            import requests as _req
            resp = _req.post(AI_SERVICE_URL, json={"query": query}, timeout=15)
            data = resp.json()
            r = data["result"]
            if "error" in r:
                await interim.edit_text(f"❌ {r['error']}\nTip: use /oracle {query} for on-chain result")
            else:
                confidence = data.get("confidence", 0)
                await interim.edit_text(
                    f"💰 {r['symbol']} Price\n\n"
                    f"Price:      ${r['price']:,.2f} {r.get('currency', 'USD')}\n"
                    f"Confidence: {confidence * 100:.0f}%\n"
                    f"Sources:    {', '.join(r.get('sources', []))}\n"
                    f"Updated:    {r.get('timestamp', '?')}\n"
                    f"(off-chain · use /oracle for on-chain verification)"
                )
        except Exception as e:
            await interim.edit_text(f"❌ Error: {e}")
        return

    # Everything else → LLM chat
    await _handle_chat(update, query)


def main() -> None:
    request = HTTPXRequest(proxy=HTTPS_PROXY)
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).request(request).build()
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("price", price_handler))
    app.add_handler(CommandHandler("oracle", oracle_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.run_polling()


if __name__ == "__main__":
    main()
