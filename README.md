# AI Oracle Agent

## 贡献者

- [@Miracold](https://github.com/Miracold) - Contract 开发
- [@jmczhc](https://github.com/jmczhc) - AI Service 开发
- [@Mingyue13](https://github.com/Mingyue13) - Frontend 开发
- [@LXJY1](https://github.com/LXJY1) - Agent Listener 开发

---

An AI-powered oracle system that aggregates multi-source crypto data and derives robust reference prices with explainable reasoning. Users interact via a Telegram bot; queries flow through an on-chain Oracle contract, a Python agent listener, and an AI price service.

## System Architecture

```
Telegram Bot (D)
      │  natural language query
      ▼
AI Service - POST /predict (B)        ← OKX + CoinGecko price feeds
      │  {result, confidence}
      ▼
Agent Listener (C)                    ← listens for on-chain OracleRequest events
      │  fulfillRequest()
      ▼
Oracle Smart Contract (A)             ← deployed on Sepolia testnet
```

## Modules

| Folder | Role |
|--------|------|
| `contract/` | Solidity Oracle contract (OpenZeppelin AccessControl) |
| `agent_listener/` | Python agent — listens for events, calls AI service, writes results on-chain |
| `ai_service/` | FastAPI service — NLP parsing + dual-source price aggregation |
| `telegram_bot/` | Telegram bot — user-facing interface |

---

## Prerequisites

- Python 3.10+
- Node.js 18+ and npm (for contract)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- **One** of the following LLM providers:
  - **OpenAI** — get API key at https://platform.openai.com
  - **Claude (Anthropic)** — get API key at https://console.anthropic.com
  - **Google Gemini** — get API key at https://aistudio.google.com
  - **Minimax** — get API key at https://www.minimaxi.com
  - **Kimi (Moonshot AI)** — get API key at https://platform.moonshot.cn
  - **Zhipu AI (智谱AI)** — get API key at https://open.bigmodel.cn
  - **Ollama** — free, runs locally. Install at https://ollama.com, then `ollama pull llama3.2:3b`
- A local HTTP proxy on port `7890` if Telegram is blocked in your region

---

## Setup

### 1. Clone and install Python dependencies

```bash
git clone <repo-url>
cd ai-oracle-agent
pip install -r requirements.txt
```

### 2. Configure AI Service (Interactive Setup)

```bash
cd ai_service
python setup_ai.py
```

The setup script will guide you to select your AI provider and enter your API key. Supported providers:

| # | Provider | API Key URL |
|---|----------|-------------|
| 1 | OpenAI | https://platform.openai.com/api-keys |
| 2 | Claude (Anthropic) | https://console.anthropic.com/settings/keys |
| 3 | Google Gemini | https://aistudio.google.com/app/apikey |
| 4 | Minimax | https://www.minimaxi.com |
| 5 | Kimi (Moonshot AI) | https://platform.moonshot.cn |
| 6 | Zhipu AI (智谱AI) | https://open.bigmodel.cn |
| 7 | Ollama (local, free) | https://ollama.com |

Alternatively, create `ai_service/.env` manually:

```env
LLM_PROVIDER=openai          # openai | claude | google | minimax | kimi | zhipu | ollama
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

Other settings (same for all providers):
```env
PRICE_CACHE_TTL=5
SYMBOL_CACHE_TTL=1800
CONFIDENCE_THRESHOLD=0.80
```

### 3. Configure Agent Listener

Edit `agent_listener/.env`:

```env
RPC_URL=https://sepolia.infura.io/v3/YOUR_INFURA_KEY
CONTRACT_ADDRESS=0x7A2127475B453aDb46CB83Bb1075854aa43a7738
AGENT_PRIVATE_KEY=0x...           # agent wallet private key (must have AGENT_ROLE + Sepolia ETH)
ABI_PATH=Oracle_abi.json
AI_SERVICE_URL=http://localhost:8000/predict
```

**Getting a free Sepolia RPC URL:** Sign up at [Infura](https://infura.io) or [Alchemy](https://alchemy.com), create a project, and copy the Sepolia HTTPS endpoint.

### 4. Grant AGENT_ROLE to your agent wallet

Generate a new agent wallet (run once):

```bash
python -c "
from eth_account import Account
import secrets
key = '0x' + secrets.token_hex(32)
acct = Account.from_key(key)
print('Private key:', key)
print('Address:    ', acct.address)
"
```

Put the private key in `agent_listener/.env` under `AGENT_PRIVATE_KEY`, then grant it the role:

```bash
python add_agent.py
```

> `add_agent.py` uses the contract deployer key to call `addAgent()` on the Oracle contract. Make sure the deployer key in `contract/.env` is correct.

### 5. Fund the agent wallet with Sepolia ETH

The agent needs ETH to pay gas for `fulfillRequest()` transactions. Get test ETH from:
- [Chainlink Faucet](https://faucet.chain.link/sepolia)
- [Alchemy Faucet](https://sepoliafaucet.com)

Minimum recommended: **0.02 ETH**

### 6. Configure Telegram Bot

```bash
cp telegram_bot/.env.example telegram_bot/.env
```

Edit `telegram_bot/.env`:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdef...   # from @BotFather
AI_SERVICE_URL=http://localhost:8000/predict
```

> If you are in a region where Telegram is blocked, the bot automatically uses a local HTTP proxy at `http://127.0.0.1:7890`. Make sure your proxy (e.g. Clash) is running.

### 7. Configure the Contract (for redeployment only)

```bash
cp contract/.env.example contract/.env
```

Edit `contract/.env`:

```env
SEPOLIA_RPC_URL=https://sepolia.infura.io/v3/YOUR_INFURA_KEY
DEPLOYER_PRIVATE_KEY=your-deployer-private-key-without-0x-prefix
```

---

## Running the System

Open **3 terminals**:

```bash
# Terminal 1 — AI Service (port 8000)
cd ai_service && python main.py

# Terminal 2 — Agent Listener
cd agent_listener && python listener.py

# Terminal 3 — Telegram Bot
cd telegram_bot && pip install -r requirements.txt && python bot.py
```

Verify the AI service is up:
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"query": "ETH price"}'
```

Expected response:
```json
{
  "result": {
    "symbol": "ETH",
    "price": 2231.45,
    "currency": "USD",
    "sources": ["okx", "coingecko"],
    "timestamp": "2026-04-09T12:00:00Z"
  },
  "confidence": 0.95
}
```

---

## Using the Telegram Bot

Find your bot on Telegram and send:

| Input | Description |
|-------|-------------|
| `ETH price` | Natural language query |
| `What is Bitcoin worth?` | Full sentence |
| `/price SOL` | Command-style query |
| `/start` | Welcome message |
| `/help` | Help message |

---

## Contract Details

- **Network:** Sepolia testnet
- **Address:** `0x7A2127475B453aDb46CB83Bb1075854aa43a7738`
- **ABI:** `agent_listener/Oracle_abi.json`

Key functions:
- `requestData(string query)` — submit an oracle request (emits `OracleRequest`)
- `fulfillRequest(uint256 requestId, bytes result, bytes signature)` — agent-only, write result on-chain (emits `OracleResponse`)
- `getResult(uint256 requestId)` — read fulfilled result
- `addAgent(address)` — admin-only, grant AGENT_ROLE

---

## Supported Tokens

BTC · ETH · SOL · BNB · MATIC · AVAX · DOGE · ADA · LINK · DOT · XRP

Price data aggregated from **OKX** and **CoinGecko**. Confidence score reflects agreement between sources:

| Source agreement | Confidence |
|-----------------|-----------|
| Both sources, deviation < 0.5% | 0.95 |
| Both sources, deviation < 2% | 0.85 |
| Both sources, deviation < 5% | 0.70 |
| Single source only | 0.80 |

---

## Security Notes

- **Never commit `.env` files** — all `.env` files are in `.gitignore`
- Use `.env.example` files as templates for teammates
- The agent wallet private key should only hold small amounts of testnet ETH
- Rotate the deployer private key if it was ever committed to git history
