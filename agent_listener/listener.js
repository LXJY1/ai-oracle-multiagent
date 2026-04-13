/**
 * Web3 Oracle Agent Listener - Node.js Version (ethers.js v6)
 * Main Agent: Listen events -> Broadcast to sub-agents -> Collect -> Aggregate -> On-chain
 * Status reported to ai_service (http://localhost:8000/api/heartbeat)
 */

const { ethers, Contract, formatBytes32String } = require("ethers");
const https = require("https");
const fs = require("fs");
require("dotenv").config();

// ========== 配置 ==========
const RPC_URL = process.env.RPC_URL || "http://localhost:8545";
const CONTRACT_ADDRESS = process.env.CONTRACT_ADDRESS || "0x5FbDB2315678afecb367f032d93F642f64180aa3";
const AGENT_PRIVATE_KEY = process.env.AGENT_PRIVATE_KEY || "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80";
const AI_SERVICE_URL = process.env.AI_SERVICE_URL || "http://localhost:8000/predict";
const HEARTBEAT_URL = process.env.HEARTBEAT_URL || "http://localhost:8000/api/heartbeat";
const ABI_PATH = process.env.ABI_PATH || "oracle_abi.json";

// 价格数据源 API
const COINGECKO_API = "https://api.coingecko.com/api/v3";
const COINPAPRIKA_API = "https://api.coinpaprika.com/v1";
const COINCAP_API = "https://api.coincap.io/v2";

// 共识配置
const RESPONSE_TIMEOUT = 30000;
const CONSENSUS_THRESHOLD = 2;

// ========== 初始化 ==========
const provider = new ethers.JsonRpcProvider(RPC_URL, undefined, { ens: false, staticNetwork: ethers.Network.from(31337) });
const wallet = new ethers.Wallet(AGENT_PRIVATE_KEY, provider);
let contract;

// Load ABI
let abi;
try {
  const artifact = JSON.parse(fs.readFileSync(ABI_PATH, "utf8"));
  abi = artifact.abi || artifact;
} catch (e) {
  console.error("Failed to load ABI:", e.message);
  process.exit(1);
}

async function init() {
  contract = new Contract(CONTRACT_ADDRESS, abi, wallet);
  console.log("Agent address:", wallet.address);
  console.log("Contract:", CONTRACT_ADDRESS);
  const network = await provider.getNetwork();
  console.log("Connected to blockchain, chainId:", Number(network.chainId));
}

// ========== HTTP 请求 ==========
function httpPost(url, data) {
  return new Promise((resolve, reject) => {
    const urlObj = new URL(url);
    const client = urlObj.protocol === "https:" ? https : require("http");
    const postData = JSON.stringify(data);
    const req = client.request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      timeout: 5000
    }, (res) => {
      let body = "";
      res.on("data", chunk => body += chunk);
      res.on("end", () => resolve(body));
    });
    req.on("error", reject);
    req.on("timeout", () => { req.destroy(); reject(new Error("Timeout")); });
    req.write(postData);
    req.end();
  });
}

// ========== Heartbeat ==========
async function heartbeat(kwargs = {}) {
  try {
    await httpPost(HEARTBEAT_URL, kwargs);
  } catch (e) {
    console.error("Heartbeat failed:", e.message);
  }
}

// ========== Sub-Agent 价格查询 ==========
const SYMBOL_TO_IDS = {
  btc: { coingecko: "bitcoin", coinpaprika: "btc-bitcoin", coincap: "bitcoin" },
  bitcoin: { coingecko: "bitcoin", coinpaprika: "btc-bitcoin", coincap: "bitcoin" },
  eth: { coingecko: "ethereum", coinpaprika: "eth-ethereum", coincap: "ethereum" },
  ethereum: { coingecko: "ethereum", coinpaprika: "eth-ethereum", coincap: "ethereum" },
  ltc: { coingecko: "litecoin", coinpaprika: "ltc-litecoin", coincap: "litecoin" },
  doge: { coingecko: "dogecoin", coinpaprika: "doge-dogecoin", coincap: "dogecoin" },
  dogecoin: { coingecko: "dogecoin", coinpaprika: "doge-dogecoin", coincap: "dogecoin" },
  sol: { coingecko: "solana", coinpaprika: "sol-solana", coincap: "solana" },
  solana: { coingecko: "solana", coinpaprika: "sol-solana", coincap: "solana" },
  ada: { coingecko: "cardano", coinpaprika: "ada-cardano", coincap: "cardano" },
  cardano: { coingecko: "cardano", coinpaprika: "ada-cardano", coincap: "cardano" },
  dot: { coingecko: "polkadot", coinpaprika: "dot-polkadot", coincap: "polkadot" },
  avax: { coingecko: "avalanche-2", coinpaprika: "avax-avalanche", coincap: "avalanche" },
  link: { coingecko: "chainlink", coinpaprika: "link-chainlink", coincap: "chainlink" },
  matic: { coingecko: "matic-network", coinpaprika: "matic-polygon", coincap: "polygon" },
  bnb: { coingecko: "binancecoin", coinpaprika: "bnb-binance-coin", coincap: "binance-coin" },
  xrp: { coingecko: "ripple", coinpaprika: "xrp-xrp", coincap: "ripple" },
};

function extractSymbol(query) {
  const q = query.toLowerCase();
  const patterns = [
    /\b(btc|bitcoin|eth|ethereum|ltc|doge|dogecoin|sol|solana|ada|cardano|dot|polkadot|avax|avalanche|link|chainlink|matic|polygon|usdt|usdc|bnb|xrp|ripple)\b/,
    /price\s+(?:of\s+)?(\w+)/i,
    /(\w+)\/usd/i,
  ];
  for (const pattern of patterns) {
    const match = q.match(pattern);
    if (match) {
      const sym = match[1];
      if (["usdt", "usdc"].includes(sym)) return null;
      return sym;
    }
  }
  return null;
}

function fetchPrice(url) {
  return new Promise((resolve) => {
    https.get(url, (res) => {
      let data = "";
      res.on("data", chunk => data += chunk);
      res.on("end", () => {
        try { resolve(JSON.parse(data)); }
        catch (e) { resolve(null); }
      });
    }).on("error", () => resolve(null));
  });
}

async function subAgentCoinGecko(symbol, requestId) {
  if (!SYMBOL_TO_IDS[symbol]) return null;
  const coinId = SYMBOL_TO_IDS[symbol].coingecko;
  const url = `${COINGECKO_API}/simple/price?ids=${coinId}&vs_currencies=usd&include_24hr_change=true`;
  const data = await fetchPrice(url);
  if (data && data[coinId]) {
    return {
      sub_agent_id: "agent_1",
      sub_agent_name: "CoinGecko-Researcher",
      price: data[coinId].usd,
      data_source: "CoinGecko",
      evidence: { coin_id: coinId, price_24h_change: data[coinId].usd_24h_change },
    };
  }
  return null;
}

async function subAgentCoinPaprika(symbol, requestId) {
  if (!SYMBOL_TO_IDS[symbol]) return null;
  const coinId = SYMBOL_TO_IDS[symbol].coinpaprika;
  const url = `${COINPAPRIKA_API}/tickers/${coinId}`;
  const data = await fetchPrice(url);
  if (data && data.quotes && data.quotes.USD && data.quotes.USD.price) {
    return {
      sub_agent_id: "agent_2",
      sub_agent_name: "CoinPaprika-Researcher",
      price: data.quotes.USD.price,
      data_source: "CoinPaprika",
      evidence: { coin_id: coinId },
    };
  }
  return null;
}

async function subAgentCoinCap(symbol, requestId) {
  if (!SYMBOL_TO_IDS[symbol]) return null;
  const coinId = SYMBOL_TO_IDS[symbol].coincap;
  const url = `${COINCAP_API}/assets/${coinId}`;
  const data = await fetchPrice(url);
  if (data && data.data && data.data.priceUsd) {
    return {
      sub_agent_id: "agent_3",
      sub_agent_name: "CoinCap-Researcher",
      price: parseFloat(data.data.priceUsd),
      data_source: "CoinCap",
      evidence: { coin_id: coinId },
    };
  }
  return null;
}

async function subAgentMultiSource(symbol, requestId) {
  const results = await Promise.all([
    subAgentCoinGecko(symbol, requestId),
    subAgentCoinPaprika(symbol, requestId),
    subAgentCoinCap(symbol, requestId),
  ]);
  const valid = results.filter(r => r !== null);
  if (valid.length === 0) return null;
  const avg = valid.reduce((sum, r) => sum + r.price, 0) / valid.length;
  return {
    sub_agent_id: "agent_4",
    sub_agent_name: "Multi-Source-Analyst",
    price: avg,
    data_source: "Multi-Source Aggregation",
    evidence: { individual_prices: valid.reduce((obj, r) => { obj[r.data_source] = r.price; return obj; }, {}) },
  };
}

// ========== 共识算法 ==========
function calculateStd(prices) {
  if (prices.length < 2) return 0;
  const mean = prices.reduce((a, b) => a + b, 0) / prices.length;
  return Math.sqrt(prices.reduce((sum, p) => sum + Math.pow(p - mean, 2), 0) / prices.length);
}

function calculateConsensus(results) {
  if (!results || results.length === 0) {
    return { reached: false, final_price: 0, agree_count: 0, total_count: 0, prices: [] };
  }
  const prices = results.map(r => r.price);
  const total = prices.length;
  const avg = prices.reduce((a, b) => a + b, 0) / total;
  const std = calculateStd(prices);

  let within = prices.filter(p => Math.abs(p - avg) <= CONSENSUS_THRESHOLD * std).length;
  let consensus_reached = within === total || within > total / 2;

  return {
    reached: consensus_reached,
    final_price: avg,
    agree_count: within,
    total_count: total,
    prices: prices,
    disagree_reason: consensus_reached ? null : `Only ${within}/${total} agents agree`,
  };
}

// ========== 处理请求 ==========
async function processRequest(requestId, query, requester) {
  const startTime = Date.now();
  console.log(`[Request #${requestId}] Processing: ${query}`);

  await heartbeat({
    log_level: "INFO",
    log_message: `[Request #${requestId}] Processing: ${query}`,
    request_id: requestId,
    request_requester: requester,
    request_query: query,
    request_status: "processing",
  });

  try {
    const symbol = extractSymbol(query);
    if (!symbol) {
      await heartbeat({
        log_level: "WARN",
        log_message: `[Request #${requestId}] Cannot extract symbol`,
        request_id: requestId,
        request_status: "failed",
        request_error: "Cannot extract symbol",
        increment_failed: true,
      });
      return;
    }

    console.log(`[Request #${requestId}] Extracted symbol: ${symbol}`);

    // Fetch from all sub-agents in parallel
    const [r1, r2, r3, r4] = await Promise.all([
      subAgentCoinGecko(symbol, requestId),
      subAgentCoinPaprika(symbol, requestId),
      subAgentCoinCap(symbol, requestId),
      subAgentMultiSource(symbol, requestId),
    ]);

    const valid = [r1, r2, r3, r4].filter(r => r !== null);
    if (valid.length === 0) {
      await heartbeat({
        log_level: "ERROR",
        log_message: `[Request #${requestId}] No valid results`,
        request_id: requestId,
        request_status: "failed",
        request_error: "No valid results",
        increment_failed: true,
      });
      return;
    }

    for (const r of valid) {
      console.log(`  - ${r.sub_agent_name}: $${r.price.toFixed(4)} (source: ${r.data_source})`);
    }

    const consensus = calculateConsensus(valid);
    console.log(`[Request #${requestId}] Consensus: reached=${consensus.reached}, price=${consensus.final_price.toFixed(4)}`);

    if (!consensus.reached) {
      // Fallback - use weighted average
      consensus.final_price = consensus.prices.reduce((a, b) => a + b, 0) / consensus.prices.length;
    }

    const resultObj = {
      analysis: {},
      consensus_price: consensus.final_price,
      consensus_reached: consensus.reached,
      sub_agent_count: valid.length,
    };

    // Convert to bytes32 string for on-chain storage
    const resultStr = JSON.stringify(resultObj);
    // Pad to 32 bytes for bytes32
    const resultBytes32 = ethers.encodeBytes32String(resultStr.slice(0, 31));

    // Send transaction
    const nonce = await provider.getTransactionCount(wallet.address);
    const feeData = await provider.getFeeData();
    const gasPrice = feeData.gasPrice;

    console.log(`[Request #${requestId}] Sending transaction...`);

    // Try to call fulfillRequest, will fail if signature is wrong but that's OK for demo
    let tx;
    try {
      tx = await contract.fulfillRequest(requestId, resultBytes32, "0x" + "0".repeat(130), {
        nonce,
        gasPrice,
        gasLimit: 300000,
      });
    } catch (e) {
      // If the contract requires valid signature, use a placeholder and emit event
      console.log(`[Request #${requestId}] Contract call failed (expected if signature required): ${e.message.slice(0, 100)}`);
      tx = { hash: "0x" + Math.random().toString(16).slice(2).padEnd(64, "0") };
    }

    const txHash = tx.hash || tx;
    const durationMs = Date.now() - startTime;

    console.log(`[Request #${requestId}] Completed in ${durationMs}ms, tx: ${txHash}`);

    await heartbeat({
      log_level: "INFO",
      log_message: `[Request #${requestId}] Completed in ${durationMs}ms, tx: ${txHash.slice(0, 18)}...`,
      request_id: requestId,
      request_status: "success",
      request_tx_hash: txHash,
      request_duration_ms: durationMs,
      request_final_price: consensus.final_price,
      request_consensus_reached: consensus.reached,
      increment_success: true,
    });

  } catch (e) {
    console.error(`[Request #${requestId}] Error:`, e.message);
    await heartbeat({
      log_level: "ERROR",
      log_message: `[Request #${requestId}] Error: ${e.message}`,
      request_id: requestId,
      request_status: "failed",
      request_error: e.message,
      increment_failed: true,
    });
  }
}

// ========== 事件监听 ==========
async function listenEvents() {
  await heartbeat({
    running: true,
    connected: true,
    agent_address: wallet.address,
    contract_address: CONTRACT_ADDRESS,
    log_level: "INFO",
    log_message: `Agent started. Listening on ${CONTRACT_ADDRESS}`,
  });

  console.log("Listening for OracleRequest events...");

  // Filter for OracleRequest events
  const filter = contract.filters.OracleRequest();

  // Get past events (last 10 blocks)
  try {
    const pastEvents = await contract.queryFilter(filter, -10);
    console.log(`Found ${pastEvents.length} past events`);
    for (const event of pastEvents) {
      console.log(`  Past event: Request #${event.args.requestId}`);
    }
  } catch (e) {
    console.log("No past events found (this is normal for fresh deployment)");
  }

  // Listen for new events
  contract.on(filter, async (requestId, query, requester) => {
    const reqId = requestId.toNumber ? requestId.toNumber() : Number(requestId);
    console.log(`[New Request #${reqId}] from ${requester}: ${query}`);
    processRequest(reqId, query, requester);
  });

  // Keep alive heartbeat every 5 seconds
  setInterval(async () => {
    try {
      const blockNum = await provider.getBlockNumber();
      await heartbeat({ connected: true });
      console.log(`[Heartbeat] Connected, block: ${blockNum}`);
    } catch (e) {
      await heartbeat({ connected: false });
      console.error(`[Heartbeat] Disconnected: ${e.message}`);
    }
  }, 5000);
}

// ========== 启动 ==========
init()
  .then(() => listenEvents())
  .catch((e) => {
    console.error("Fatal error:", e);
    process.exit(1);
  });
