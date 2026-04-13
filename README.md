# AI Oracle Multi-Agent

## contributors

- [@Miracold](https://github.com/Miracold) - Contract developer
- [@jmczhc](https://github.com/jmczhc) - AI Service developer
- [@Mingyue13](https://github.com/Mingyue13) - Frontend developer
- [@LXJY1](https://github.com/LXJY1) - Agent Listener developer

---

An AI-powered oracle system that aggregates multi-source crypto data and derives robust reference prices with consensus reasoning. Queries flow through an on-chain Oracle contract, a Python agent listener, and an AI price service.

## System Architecture

```
┌─────────────┐
│   Frontend  │  ← React dApp (MetaMask wallet)
└──────┬──────┘
       │  requestData()
       ▼
┌─────────────────────────────────────┐
│     Oracle Smart Contract           │  ← Sepolia testnet
│  (OpenZeppelin AccessControl)       │
└──────┬──────────────────────────────┘
       │  OracleRequest event
       ▼
┌─────────────────────────────────────┐
│      Agent Listener                 │  ← Python (listening)
│  - Multi-source price fetch         │
│  - Consensus calculation            │
│  - fulfillRequest()                 │
└──────┬──────────────────────────────┘
       │  AI Service
       ▼
┌─────────────────────────────────────┐
│      AI Service                    │  ← FastAPI (port 8000)
│  - Symbol extraction (LLM)         │
│  - Price aggregation               │
│  - Dashboard + Heartbeat API      │
└─────────────────────────────────────┘
```

## Modules

| Folder | Role |
|--------|------|
| `contract/` | Solidity Oracle contract |
| `agent_listener/` | Python agent — listens events, consensus, writes on-chain |
| `ai_service/` | FastAPI — NLP parsing, price fetch, dashboard |
| `frontend/` | React dApp — MetaMask wallet connection |

---

## Prerequisites

- Python 3.13+
- Node.js 18+ and npm
- MetaMask browser extension
- **One** LLM provider (optional for symbol extraction):
  - **OpenAI** — https://platform.openai.com
  - **Claude (Anthropic)** — https://console.anthropic.com
  - **Google Gemini** — https://aistudio.google.com
  - **Minimax** — https://www.minimaxi.com
  - **Kimi (Moonshot AI)** — https://platform.moonshot.cn
  - **Zhipu AI** — https://open.bigmodel.cn
  - **Ollama** (local, free) — https://ollama.com

---

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/LXJY1/ai-oracle-multiagent.git
cd ai-oracle-multiagent
```

### 2. Configure AI Service

```bash
cd ai_service
cp .env.example .env
```

Edit `ai_service/.env`:
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

Or run interactive setup:
```bash
python setup_ai.py
```

### 3. Configure Agent Listener

```bash
cd agent_listener
cp .env.example .env
```

Edit `agent_listener/.env`:
```env
RPC_URL=https://ethereum-sepolia.publicnode.com
CONTRACT_ADDRESS=0xB3AffBbe601a3D41a1fc8e7ec817e5EdC34d4f48
AGENT_PRIVATE_KEY=0x...           # Must have AGENT_ROLE + Sepolia ETH
AI_SERVICE_URL=http://localhost:8000/predict
HEARTBEAT_URL=http://localhost:8000/api/heartbeat
```

### 4. Configure Frontend

```bash
cd frontend
cp .env.example .env  # if needed
npm install
```

The contract address and chain ID are configured in `src/App.js`:
```javascript
const CONTRACT_ADDRESS = '0xB3AffBbe601a3D41a1fc8e7ec817e5EdC34d4f48';
const TARGET_CHAIN_ID = 11155111;  // Sepolia
```

### 5. Grant Agent Permissions

If deploying a new agent wallet:

```bash
cd contract
cp .env.example .env
# Edit .env with your deployer private key

# Grant AGENT_ROLE
node scripts/add_agent.cjs <agent_address>
```

### 6. Fund Agent Wallet

The agent needs Sepolia ETH for gas. Get testnet ETH from:
- https://faucet.sepolia.dev/
- https://www.alchemy.com/faucets/ethereum-sepolia

Minimum recommended: **0.01 ETH**

---

## Running the System

Open **2 terminals**:

```bash
# Terminal 1 — AI Service (port 8000)
cd ai_service && python3 main.py

# Terminal 2 — Agent Listener
cd agent_listener && python3 listener.py
```

Then start frontend:
```bash
# Terminal 3
cd frontend && npm start
```

Access:
- Frontend: http://localhost:3000
- Agent Dashboard: http://localhost:8000/

---

## Test AI Service

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"query": "BTC price"}'
```

---

## Contract Details

- **Network:** Sepolia testnet
- **Address:** `0xB3AffBbe601a3D41a1fc8e7ec817e5EdC34d4f48`
- **ABI:** `agent_listener/Oracle_abi.json`

Key functions:
- `requestData(string query)` — submit request (emits `OracleRequest`)
- `fulfillRequest(uint256 requestId, bytes result, bytes signature)` — agent-only
- `getResult(uint256 requestId)` — read fulfilled result
- `addAgent(address)` — admin-only, grant AGENT_ROLE

---

## Supported Tokens

BTC · ETH · SOL · BNB · MATIC · AVAX · DOGE · ADA · LINK · DOT · XRP

Price data from **OKX**, **CoinGecko**, **CoinPaprika**, **CoinCap**. Confidence based on cross-source deviation.

| Deviation | Confidence |
|-----------|------------|
| < 0.5% | 0.95 |
| < 2% | 0.85 |
| < 5% | 0.70 |
| Single source | 0.80 |

---

## Security Notes

- **Never commit `.env` files** — all are in `.gitignore`
- Agent wallet should only hold testnet ETH
- Use `.env.example` as templates for teammates
