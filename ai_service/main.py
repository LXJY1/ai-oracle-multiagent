"""
AI Oracle Service + Agent Dashboard
统一服务端口: http://localhost:8000

├── GET  /              → Agent 控制面板 (HTML)
├── GET  /api/status    → Agent 实时状态
├── GET  /api/logs      → Agent 日志
├── POST /api/heartbeat → Agent 心跳/状态上报
├── POST /predict       → AI 价格查询
├── POST /chat          → AI 聊天
└── GET  /health        → 健康检查
"""

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import threading
import time
import json
import httpx
import uvicorn

from models import QueryRequest, QueryResponse, PriceResult, ErrorResult
from nlp import parse_query, chat_with_llm
from price_fetcher import get_price

app = FastAPI(title="AI Oracle Service + Agent Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# Agent 共享状态（线程安全）
# ============================================================
class SharedAgentState:
    def __init__(self):
        self._lock = threading.RLock()
        self._logs: list[dict] = []
        self._requests: list[dict] = []
        self._sub_agents = [
            {"id": "agent_1", "name": "CoinGecko-Researcher", "sources": ["coingecko"], "status": "active"},
            {"id": "agent_2", "name": "CoinPaprika-Researcher", "sources": ["coinpaprika"], "status": "active"},
            {"id": "agent_3", "name": "CoinCap-Researcher", "sources": ["coincap"], "status": "active"},
            {"id": "agent_4", "name": "Multi-Source-Analyst", "sources": ["coingecko", "coinpaprika", "coincap"], "status": "active"},
        ]
        self._stats = {
            "total_requests": 0,
            "successful": 0,
            "failed": 0,
            "start_time": time.time(),
        }
        self._running = False
        self._connected = False
        self._agent_address = ""
        self._contract_address = ""

    def update(self, data: dict):
        with self._lock:
            if "running" in data:
                self._running = data["running"]
            if "connected" in data:
                self._connected = data["connected"]
            if "agent_address" in data:
                self._agent_address = data["agent_address"]
            if "contract_address" in data:
                self._contract_address = data["contract_address"]

    def add_log(self, level: str, message: str):
        from datetime import datetime
        with self._lock:
            self._logs.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "level": level,
                "message": message,
            })
            if len(self._logs) > 500:
                self._logs = self._logs[-500:]

    def add_request(self, req: dict):
        with self._lock:
            self._requests.insert(0, req)
            if len(self._requests) > 100:
                self._requests = self._requests[:100]
            self._stats["total_requests"] += 1

    def update_request(self, request_id: int, **kwargs):
        with self._lock:
            for req in self._requests:
                if req.get("request_id") == request_id:
                    req.update(kwargs)
                    break

    def inc_success(self):
        with self._lock:
            self._stats["successful"] += 1

    def inc_failed(self):
        with self._lock:
            self._stats["failed"] += 1

    def get_status(self) -> dict:
        with self._lock:
            return {
                "running": self._running,
                "connected": self._connected,
                "logs": list(self._logs[-50:]),
                "requests": list(self._requests[:20]),
                "sub_agents": list(self._sub_agents),
                "stats": dict(self._stats),
                "uptime": round(time.time() - self._stats["start_time"]),
                "agent_address": self._agent_address,
                "contract_address": self._contract_address,
            }


agent_state = SharedAgentState()


# ============================================================
# Pydantic 模型
# ============================================================
class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


class HeartbeatRequest(BaseModel):
    running: Optional[bool] = None
    connected: Optional[bool] = None
    agent_address: Optional[str] = None
    contract_address: Optional[str] = None
    log_level: Optional[str] = None
    log_message: Optional[str] = None
    request_id: Optional[int] = None
    request_requester: Optional[str] = None
    request_query: Optional[str] = None
    request_status: Optional[str] = None
    request_symbol: Optional[str] = None
    request_tx_hash: Optional[str] = None
    request_duration_ms: Optional[int] = None
    request_error: Optional[str] = None
    request_final_price: Optional[float] = None
    request_consensus_reached: Optional[bool] = None
    increment_success: Optional[bool] = None
    increment_failed: Optional[bool] = None


# ============================================================
# AI Service 端点
# ============================================================
@app.post("/predict", response_model=QueryResponse)
async def predict(request: QueryRequest) -> QueryResponse:
    try:
        symbol = parse_query(request.query)
    except ValueError as e:
        return QueryResponse(result=ErrorResult(error=str(e), symbol=None), confidence=0.0)
    try:
        price_data = get_price(symbol)
    except ValueError as e:
        return QueryResponse(result=ErrorResult(error=str(e), symbol=symbol), confidence=0.0)
    except RuntimeError as e:
        return QueryResponse(result=ErrorResult(error=str(e), symbol=symbol), confidence=0.0)
    return QueryResponse(
        result=PriceResult(
            symbol=price_data["symbol"],
            price=price_data["price"],
            currency=price_data["currency"],
            sources=price_data["sources"],
            timestamp=price_data["timestamp"],
        ),
        confidence=price_data["confidence"],
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    reply = chat_with_llm(request.message)
    return ChatResponse(reply=reply or "Sorry, I couldn't generate a response.")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "agent_running": agent_state._running}


# ============================================================
# Agent Dashboard 端点
# ============================================================
@app.get("/api/status")
async def api_status():
    return agent_state.get_status()


@app.get("/api/logs")
async def api_logs():
    return {"logs": list(agent_state._logs)}


@app.post("/api/heartbeat")
async def api_heartbeat(data: HeartbeatRequest):
    """Listener 通过此端点上报状态到共享 state"""
    if data.running is not None or data.connected is not None:
        agent_state.update({
            "running": data.running,
            "connected": data.connected,
            "agent_address": data.agent_address or "",
            "contract_address": data.contract_address or "",
        })
    if data.log_level and data.log_message:
        agent_state.add_log(data.log_level, data.log_message)
    if data.request_id is not None:
        req_entry = {
            "request_id": data.request_id,
            "query": data.request_query or "",
            "requester": data.request_requester or "",
            "status": data.request_status or "processing",
            "symbol": data.request_symbol,
            "final_price": data.request_final_price,
            "tx_hash": data.request_tx_hash,
            "duration_ms": data.request_duration_ms,
            "error": data.request_error,
            "consensus_reached": data.request_consensus_reached,
            "timestamp": time.strftime("%H:%M:%S"),
        }
        # 检查是否已存在
        existing = [r for r in agent_state._requests if r.get("request_id") == data.request_id]
        if existing:
            existing[0].update(req_entry)
        else:
            agent_state.add_request(req_entry)
    if data.increment_success:
        agent_state.inc_success()
    if data.increment_failed:
        agent_state.inc_failed()
    return {"ok": True}


# ============================================================
# Agent Dashboard HTML
# ============================================================
@app.get("/")
async def dashboard():
    return Response(content=DASHBOARD_HTML, media_type="text/html")


# ============================================================
# Dashboard HTML (内联，避免单独文件)
# ============================================================
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Oracle Agent Dashboard</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Inter:wght@400;500;600&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Inter', sans-serif; background: #0a0a0f; color: #e8e6f0; min-height: 100vh; }
  .container { max-width: 1200px; margin: 0 auto; padding: 24px; }

  .header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 16px 24px; background: #13131a; border-bottom: 1px solid #1e1e2e;
    margin-bottom: 24px;
  }
  .header-left { display: flex; align-items: center; gap: 12px; }
  .logo-icon {
    width: 40px; height: 40px; background: linear-gradient(135deg, #7F77DD, #5DCAA5);
    border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px;
  }
  .logo-text { font-family: 'Space Mono', monospace; font-size: 18px; font-weight: 700; }
  .logo-sub { font-size: 11px; color: #5F5E5A; margin-top: 2px; }

  .status-pill {
    display: flex; align-items: center; gap: 8px;
    padding: 8px 16px; border-radius: 20px; font-size: 13px; font-weight: 500;
  }
  .status-pill.connected { background: #04342C; border: 1px solid #085041; color: #5DCAA5; }
  .status-pill.disconnected { background: #2a1a1a; border: 1px solid #5a2020; color: #e05a5a; }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }

  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .card {
    background: #13131a; border: 1px solid #1e1e2e; border-radius: 16px;
    padding: 20px;
  }
  .card-label {
    font-size: 11px; font-weight: 500; letter-spacing: 1.5px; text-transform: uppercase;
    color: #5F5E5A; margin-bottom: 12px;
  }
  .stat-value { font-family: 'Space Mono', monospace; font-size: 28px; font-weight: 700; }
  .stat-accent.green { color: #5DCAA5; }
  .stat-accent.purple { color: #7F77DD; }
  .stat-accent.yellow { color: #BA7517; }
  .stat-accent.red { color: #e05a5a; }
  .stat-sub { font-size: 11px; color: #5F5E5A; margin-top: 4px; }

  .uptime-bar { height: 3px; background: #1e1e2e; border-radius: 2px; margin-top: 12px; overflow: hidden; }
  .uptime-bar-fill { height: 100%; background: linear-gradient(90deg, #7F77DD, #5DCAA5); border-radius: 2px; transition: width 0.5s; }

  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  @media (max-width: 900px) { .two-col { grid-template-columns: 1fr; } }

  .section-title { font-size: 14px; font-weight: 600; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; }
  .card-label-inline { font-size: 11px; font-weight: 500; letter-spacing: 1.5px; text-transform: uppercase; color: #5F5E5A; margin: 0; }

  .agent-item { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid #1e1e2e; }
  .agent-item:last-child { border-bottom: none; }
  .agent-avatar {
    width: 34px; height: 34px; border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 11px; font-weight: 700; font-family: 'Space Mono', monospace;
  }
  .agent-name { font-size: 12px; font-weight: 500; }
  .agent-sources { font-size: 10px; color: #5F5E5A; margin-top: 1px; }
  .agent-status {
    margin-left: auto; font-size: 10px; padding: 3px 8px;
    border-radius: 6px; font-weight: 500;
  }
  .agent-status.active { background: #04342C; color: #5DCAA5; border: 1px solid #085041; }
  .agent-status.inactive { background: #2a1a1a; color: #e05a5a; border: 1px solid #5a2020; }

  .requests-list { max-height: 400px; overflow-y: auto; }
  .request-item { padding: 12px 0; border-bottom: 1px solid #1e1e2e; }
  .request-item:last-child { border-bottom: none; }
  .request-top { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
  .request-id {
    font-family: 'Space Mono', monospace; font-size: 10px;
    background: #26215C; color: #7F77DD; padding: 2px 7px; border-radius: 5px;
  }
  .request-status {
    font-size: 10px; padding: 3px 8px; border-radius: 6px; font-weight: 500; margin-left: auto;
  }
  .request-status.success { background: #04342C; color: #5DCAA5; border: 1px solid #085041; }
  .request-status.failed { background: #2a1a1a; color: #e05a5a; border: 1px solid #5a2020; }
  .request-status.processing { background: #412402; color: #BA7517; border: 1px solid #633806; }
  .request-query { font-size: 12px; color: #B4B2A9; }
  .request-meta { display: flex; gap: 12px; margin-top: 3px; font-size: 10px; color: #5F5E5A; flex-wrap: wrap; }
  .request-price { color: #5DCAA5; font-family: 'Space Mono', monospace; }
  .request-tx { color: #7F77DD; font-family: 'Space Mono', monospace; }

  .logs-container { max-height: 400px; overflow-y: auto; font-family: 'Space Mono', monospace; font-size: 10px; }
  .log-line { padding: 3px 6px; border-radius: 3px; margin-bottom: 1px; }
  .log-line.INFO { color: #B4B2A9; }
  .log-line.WARN { color: #BA7517; background: #2a1f0a; }
  .log-line.ERROR { color: #e05a5a; background: #2a1a1a; }
  .log-line.DEBUG { color: #5F5E5A; }
  .log-time { color: #5F5E5A; margin-right: 6px; }
  .log-badge { padding: 1px 5px; border-radius: 3px; margin-right: 6px; font-size: 9px; }
  .log-badge.INFO { background: #26215C; color: #7F77DD; }
  .log-badge.WARN { background: #412402; color: #BA7517; }
  .log-badge.ERROR { background: #2a1a1a; color: #e05a5a; }
  .log-badge.DEBUG { background: #1e1e2e; color: #5F5E5A; }

  .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 12px; }
  .info-field { background: #0a0a0f; border-radius: 8px; padding: 10px; }
  .info-label { font-size: 9px; color: #5F5E5A; text-transform: uppercase; letter-spacing: 1px; }
  .info-value { font-family: 'Space Mono', monospace; font-size: 11px; color: #AFA9EC; margin-top: 3px; overflow: hidden; text-overflow: ellipsis; }

  .spinner { width: 8px; height: 8px; border: 1.5px solid #BA7517; border-top-color: transparent; border-radius: 50%; animation: spin 0.8s linear infinite; display: inline-block; }
  @keyframes spin { to { transform: rotate(360deg); } }

  .refresh-hint { text-align: center; font-size: 10px; color: #3a3a3a; margin-top: 12px; }
  .empty-state { text-align: center; padding: 40px 20px; color: #3a3a3a; font-size: 12px; }
  .badge { font-family: 'Space Mono', monospace; font-size: 10px; padding: 2px 8px; border-radius: 10px; background: #1e1e2e; color: #5F5E5A; }
</style>
</head>
<body>
  <div class="header">
    <div class="header-left">
      <div class="logo-icon">🔮</div>
      <div>
        <div class="logo-text">OracleX Agent</div>
        <div class="logo-sub">Multi-Agent Consensus Oracle</div>
      </div>
    </div>
    <div id="connectionStatus" class="status-pill disconnected">
      <div class="status-dot"></div>
      <span id="statusText">Connecting...</span>
    </div>
  </div>

  <div class="container">
    <!-- Stats Row -->
    <div class="grid">
      <div class="card">
        <div class="card-label">Total Requests</div>
        <div class="stat-value" id="totalRequests">-</div>
        <div class="stat-sub">since agent started</div>
        <div class="uptime-bar"><div class="uptime-bar-fill" id="uptimeBar" style="width:0%"></div></div>
      </div>
      <div class="card">
        <div class="card-label">Successful</div>
        <div class="stat-value stat-accent green" id="successCount">-</div>
        <div class="stat-sub" id="successRate">-</div>
      </div>
      <div class="card">
        <div class="card-label">Failed</div>
        <div class="stat-value stat-accent red" id="failedCount">-</div>
        <div class="stat-sub">consensus / network errors</div>
      </div>
      <div class="card">
        <div class="card-label">Processing</div>
        <div class="stat-value stat-accent yellow" id="pendingCount">-</div>
        <div class="stat-sub">active requests</div>
      </div>
    </div>

    <!-- Sub-Agents -->
    <div class="card" style="margin-bottom:16px;">
      <div class="section-title">
        <span class="card-label-inline">Sub-Agents</span>
        <span style="font-size:10px;color:#5F5E5A;">4 active</span>
      </div>
      <div id="agentsList"></div>
      <div class="info-grid">
        <div class="info-field">
          <div class="info-label">Contract</div>
          <div class="info-value" id="contractAddr">-</div>
        </div>
        <div class="info-field">
          <div class="info-label">Agent Wallet</div>
          <div class="info-value" id="agentAddr">-</div>
        </div>
      </div>
    </div>

    <!-- Requests + Logs -->
    <div class="two-col">
      <div class="card">
        <div class="section-title">
          <span class="card-label-inline">Recent Requests</span>
          <span class="badge" id="reqCount">0</span>
        </div>
        <div class="requests-list" id="requestsList">
          <div class="empty-state">No requests yet. Waiting for on-chain events...</div>
        </div>
      </div>
      <div class="card">
        <div class="section-title">
          <span class="card-label-inline">Live Logs</span>
          <span class="badge" id="logCount">-</span>
        </div>
        <div class="logs-container" id="logsContainer"></div>
      </div>
    </div>
    <div class="refresh-hint">Auto-refreshes every 3 seconds</div>
  </div>

<script>
function shortAddr(addr) {
  if (!addr || addr.length < 10) return addr || '-';
  return addr.slice(0,6) + '...' + addr.slice(-4);
}

function formatUptime(s) {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  if (h > 0) return h + 'h ' + m + 'm';
  if (m > 0) return m + 'm ' + sec + 's';
  return sec + 's';
}

function render(data) {
  const statusEl = document.getElementById('connectionStatus');
  if (data.connected) {
    statusEl.className = 'status-pill connected';
    document.getElementById('statusText').textContent = 'Connected';
  } else {
    statusEl.className = 'status-pill disconnected';
    document.getElementById('statusText').textContent = data.running ? 'Disconnected' : 'Agent Offline';
  }

  const s = data.stats || {};
  document.getElementById('totalRequests').textContent = s.total_requests || 0;
  document.getElementById('successCount').textContent = s.successful || 0;
  document.getElementById('failedCount').textContent = s.failed || 0;
  const rate = s.total_requests > 0 ? ((s.successful / s.total_requests) * 100).toFixed(0) + '%' : '-';
  document.getElementById('successRate').textContent = rate;
  const uptime = data.uptime || 0;
  document.getElementById('uptimeBar').style.width = Math.min((uptime / 3600) * 100, 100) + '%';
  const pending = (data.requests || []).filter(r => r.status === 'processing').length;
  document.getElementById('pendingCount').textContent = pending;

  document.getElementById('contractAddr').textContent = shortAddr(data.contract_address || '0x7A2127475B453aDb46CB83Bb1075854aa43a7738');
  document.getElementById('agentAddr').textContent = shortAddr(data.agent_address || '-');

  // Sub-agents
  const agents = data.sub_agents || [];
  document.getElementById('agentsList').innerHTML = agents.map(a => `
    <div class="agent-item">
      <div class="agent-avatar" style="background:${a.id === 'agent_4' ? '#085041' : '#26215C'}">
        ${a.id === 'agent_1' ? 'CG' : a.id === 'agent_2' ? 'CP' : a.id === 'agent_3' ? 'CC' : 'MS'}
      </div>
      <div>
        <div class="agent-name">${a.name}</div>
        <div class="agent-sources">${(a.sources || []).join(', ')}</div>
      </div>
      <div class="agent-status ${a.status === 'active' ? 'active' : 'inactive'}">${a.status}</div>
    </div>
  `).join('');

  // Requests
  const requests = data.requests || [];
  document.getElementById('reqCount').textContent = requests.length;
  if (requests.length === 0) {
    document.getElementById('requestsList').innerHTML = '<div class="empty-state">No requests yet. Waiting for on-chain events...</div>';
  } else {
    document.getElementById('requestsList').innerHTML = requests.slice(0, 20).map(r => `
      <div class="request-item">
        <div class="request-top">
          <span class="request-id">#${r.request_id}</span>
          <span style="font-size:10px;color:#5F5E5A;">${r.symbol || '-'} · ${r.timestamp || ''}</span>
          <span class="request-status ${r.status}">${r.status === 'processing' ? '<span class="spinner"></span> ' : ''}${r.status}</span>
        </div>
        <div class="request-query">${r.query}</div>
        <div class="request-meta">
          ${r.final_price ? '<span class="request-price">$' + Number(r.final_price).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 4}) + '</span>' : ''}
          ${r.tx_hash ? '<span class="request-tx">' + shortAddr(r.tx_hash) + '</span>' : ''}
          ${r.duration_ms ? '<span>' + r.duration_ms + 'ms</span>' : ''}
          ${r.error ? '<span style="color:#e05a5a;">' + r.error + '</span>' : ''}
        </div>
      </div>
    `).join('');
  }

  // Logs
  const logs = data.logs || [];
  document.getElementById('logCount').textContent = logs.length;
  const container = document.getElementById('logsContainer');
  container.innerHTML = logs.slice(-100).map(l => `
    <div class="log-line ${l.level}">
      <span class="log-time">${l.time}</span>
      <span class="log-badge ${l.level}">${l.level}</span>
      ${l.message}
    </div>
  `).join('');
  container.scrollTop = container.scrollHeight;
}

async function fetchStatus() {
  try {
    const resp = await fetch('/api/status');
    const data = await resp.json();
    render(data);
  } catch (e) { console.error('fetch error:', e); }
}

fetchStatus();
setInterval(fetchStatus, 3000);
</script>
</body>
</html>"""


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
