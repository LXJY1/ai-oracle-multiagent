import React, { useState, useEffect } from 'react';
import { ethers } from 'ethers';
import OracleABI from './OracleABI.json';

const CONTRACT_ADDRESS = '0xB3AffBbe601a3D41a1fc8e7ec817e5EdC34d4f48';
const TARGET_CHAIN_ID = 11155111;

const CHAIN_NAMES = {
  1: 'Ethereum Mainnet',
  5: 'Goerli',
  11155111: 'Sepolia',
  31337: 'Hardhat Local',
  137: 'Polygon',
  56: 'BSC',
  42161: 'Arbitrum',
  10: 'Optimism',
};

const SEPOLIA_NETWORK_CONFIG = {
  chainId: '0xaa36a7',
  chainName: 'Sepolia',
  nativeCurrency: { name: 'Sepolia ETH', symbol: 'ETH', decimals: 18 },
  rpcUrls: ['https://ethereum-sepolia.publicnode.com'],
  blockExplorerUrls: ['https://sepolia.etherscan.io'],
};

function App() {
  const [account, setAccount] = useState('');
  const [contract, setContract] = useState(null);
  const [query, setQuery] = useState('');
  const [requests, setRequests] = useState([]);
  const [networkName, setNetworkName] = useState('');
  const [isConnecting, setIsConnecting] = useState(false);

  // Helper to create provider (ethers v5)
  const createProvider = () => {
    return new ethers.providers.Web3Provider(window.ethereum);
  };

  // Sync MetaMask account and network changes
  useEffect(() => {
    if (!window.ethereum) return;

    const handleAccountsChanged = (accounts) => {
      if (accounts.length === 0) {
        setAccount('');
        setContract(null);
      } else if (accounts[0] !== account) {
        setAccount(accounts[0]);
        initContractWithSigner();
      }
    };

    const handleChainChanged = () => {
      window.location.reload();
    };

    window.ethereum.on('accountsChanged', handleAccountsChanged);
    window.ethereum.on('chainChanged', handleChainChanged);

    // Check if already connected
    const checkConnection = async () => {
      try {
        await switchToTargetNetwork();
        const provider = createProvider();
        const accounts = await provider.listAccounts();
        if (accounts.length > 0) {
          setAccount(accounts[0]);
          await initContractWithSigner();
        }
        const network = await provider.getNetwork();
        setNetworkName(CHAIN_NAMES[Number(network.chainId)] || `Chain ${network.chainId}`);
      } catch (err) {
        console.error('Check connection error:', err);
      }
    };
    checkConnection();

    return () => {
      window.ethereum.removeListener('accountsChanged', handleAccountsChanged);
      window.ethereum.removeListener('chainChanged', handleChainChanged);
    };
  }, [account]);

  const initContractWithSigner = async () => {
    try {
      const provider = createProvider();
      const signer = provider.getSigner();
      const contractInstance = new ethers.Contract(CONTRACT_ADDRESS, OracleABI, signer);
      setContract(contractInstance);
      listenEvents(contractInstance);
      const network = await provider.getNetwork();
      setNetworkName(CHAIN_NAMES[Number(network.chainId)] || `Chain ${network.chainId}`);
    } catch (err) {
      console.error('Init contract error:', err);
    }
  };

  const switchToTargetNetwork = async () => {
    if (!window.ethereum) return;
    const currentChainId = await window.ethereum.request({ method: 'eth_chainId' });
    const targetHex = '0x' + TARGET_CHAIN_ID.toString(16);
    if (currentChainId === targetHex) return;

    try {
      await window.ethereum.request({
        method: 'wallet_switchEthereumChain',
        params: [{ chainId: targetHex }],
      });
    } catch (switchError) {
      if (switchError.code === 4902) {
        try {
          await window.ethereum.request({
            method: 'wallet_addEthereumChain',
            params: [SEPOLIA_NETWORK_CONFIG],
          });
        } catch (addError) {
          throw new Error('Cannot add Sepolia network');
        }
      }
    }
  };

  const connectWallet = async () => {
    if (!window.ethereum) {
      alert('Please install MetaMask');
      return;
    }
    try {
      setIsConnecting(true);
      await switchToTargetNetwork();
      const provider = createProvider();
      await provider.send("eth_requestAccounts", []);
      const signer = provider.getSigner();
      const address = await signer.getAddress();
      const contractInstance = new ethers.Contract(CONTRACT_ADDRESS, OracleABI, signer);
      setAccount(address);
      setContract(contractInstance);
      const network = await provider.getNetwork();
      setNetworkName(CHAIN_NAMES[Number(network.chainId)] || `Chain ${network.chainId}`);
      listenEvents(contractInstance);
    } catch (err) {
      alert('Failed to connect: ' + err.message);
    } finally {
      setIsConnecting(false);
    }
  };

  const listenEvents = (contractInstance) => {
    contractInstance.on('OracleResponse', (requestId, result) => {
      setRequests(prev => prev.map(req =>
        req.id === requestId.toNumber()
          ? { ...req, result: ethers.utils.toUtf8String(result), fulfilled: true }
          : req
      ));
    });
  };

  const requestData = async () => {
    if (!contract) return alert('Connect wallet first!');
    if (!query) return alert('Please enter a query!');
    try {
      const tx = await contract.requestData(query);
      console.log('Transaction sent:', tx.hash);
      const receipt = await tx.wait();
      console.log('Receipt logs:', receipt.logs);
      // The OracleRequest event signature hash
      const ORACLE_REQUEST_SIG = '0x04fae5251e21f33e0fa2ef6acc2b553e65fd9f87f14e23e09d0de905ea06f86f';
      for (const log of receipt.logs) {
        if (log.topics[0] === ORACLE_REQUEST_SIG) {
          console.log('Found OracleRequest log!');
          // requestId is in topics[1] as uint256
          const requestId = ethers.BigNumber.from(log.topics[1]).toNumber();
          console.log('Request ID:', requestId);
          setRequests(prev => [...prev, { id: requestId, query, fulfilled: false, result: null }]);
          setQuery('');
          return;
        }
      }
      console.log('OracleRequest event not found in logs');
      alert('Request sent but event not found. Check console.');
    } catch (err) {
      console.error('Transaction error:', err);
      alert('Transaction failed: ' + err.message);
    }
  };

  const shortAddress = (addr) => `${addr.slice(0, 6)}...${addr.slice(-4)}`;

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@400;500;600&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0a0a0f; margin: 0; }
        .app { font-family: 'DM Sans', sans-serif; min-height: 100vh; background: #0a0a0f; color: #e8e6f0; padding: 2rem; max-width: 700px; margin: 0 auto; }
        .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 2.5rem; }
        .logo { display: flex; align-items: center; gap: 10px; }
        .logo-icon { width: 36px; height: 36px; background: linear-gradient(135deg, #7F77DD, #5DCAA5); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 18px; }
        .logo-text { font-family: 'Space Mono', monospace; font-size: 18px; font-weight: 700; color: #e8e6f0; letter-spacing: -0.5px; }
        .connect-btn { font-family: 'DM Sans', sans-serif; font-size: 14px; font-weight: 500; padding: 10px 20px; border-radius: 10px; border: 1px solid #3C3489; background: #26215C; color: #AFA9EC; cursor: pointer; display: flex; align-items: center; gap: 8px; transition: all 0.2s; }
        .connect-btn:hover { background: #3C3489; color: #EEEDFE; }
        .connect-btn.connected { background: #085041; border-color: #0F6E56; color: #9FE1CB; }
        .dot { width: 8px; height: 8px; border-radius: 50%; background: #5DCAA5; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        .network-bar { display: flex; align-items: center; gap: 8px; padding: 10px 14px; background: #0a0a0f; border: 1px solid #1e1e2e; border-radius: 10px; font-size: 12px; color: #888780; margin-bottom: 1.5rem; }
        .network-dot { width: 6px; height: 6px; border-radius: 50%; background: #5DCAA5; }
        .mono { font-family: 'Space Mono', monospace; font-size: 11px; color: #5F5E5A; margin-left: auto; }
        .card { background: #13131a; border: 1px solid #1e1e2e; border-radius: 16px; padding: 1.5rem; margin-bottom: 1.5rem; }
        .card-label { font-size: 11px; font-weight: 500; letter-spacing: 1.5px; text-transform: uppercase; color: #5F5E5A; margin-bottom: 1rem; }
        .input-row { display: flex; gap: 10px; }
        .query-input { flex: 1; font-family: 'DM Sans', sans-serif; font-size: 15px; padding: 12px 16px; background: #0a0a0f; border: 1px solid #1e1e2e; border-radius: 10px; color: #e8e6f0; outline: none; transition: border-color 0.2s; }
        .query-input::placeholder { color: #444441; }
        .query-input:focus { border-color: #534AB7; }
        .send-btn { font-family: 'DM Sans', sans-serif; font-size: 14px; font-weight: 500; padding: 12px 24px; background: #534AB7; border: none; border-radius: 10px; color: #EEEDFE; cursor: pointer; transition: background 0.2s; white-space: nowrap; }
        .send-btn:hover { background: #7F77DD; }
        .send-btn:disabled { background: #1e1e2e; color: #444441; cursor: not-allowed; }
        .requests-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; }
        .badge { font-family: 'Space Mono', monospace; font-size: 11px; padding: 3px 10px; border-radius: 20px; background: #1e1e2e; color: #888780; }
        .empty-state { text-align: center; padding: 3rem 1rem; color: #444441; font-size: 14px; }
        .request-item { display: flex; align-items: center; gap: 12px; padding: 14px 0; border-bottom: 1px solid #1e1e2e; }
        .request-item:last-child { border-bottom: none; }
        .request-id { font-family: 'Space Mono', monospace; font-size: 11px; color: #534AB7; background: #26215C; padding: 4px 8px; border-radius: 6px; white-space: nowrap; min-width: 44px; text-align: center; }
        .request-info { flex: 1; min-width: 0; }
        .request-query { font-size: 14px; color: #B4B2A9; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .request-result { font-size: 13px; margin-top: 3px; color: #5DCAA5; }
        .status-pending { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #BA7517; background: #412402; border: 1px solid #633806; padding: 5px 10px; border-radius: 8px; white-space: nowrap; }
        .status-done { font-size: 12px; color: #1D9E75; background: #04342C; border: 1px solid #085041; padding: 5px 10px; border-radius: 8px; white-space: nowrap; }
        .spinner { width: 8px; height: 8px; border: 1.5px solid #BA7517; border-top-color: transparent; border-radius: 50%; animation: spin 0.8s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>

      <div className="app">
        <div className="header">
          <div className="logo">
            <div className="logo-icon">🔮</div>
            <span className="logo-text">Oracle DApp</span>
          </div>
          <button
            className={`connect-btn ${account ? 'connected' : ''}`}
            onClick={connectWallet}
            disabled={isConnecting}
          >
            {account && <div className="dot" />}
            {isConnecting ? 'Connecting...' : account ? shortAddress(account) : 'Connect Wallet'}
          </button>
        </div>

        <div className="network-bar">
          <div className="network-dot" />
          <span>{networkName || 'Unknown Network'}</span>
          <span className="mono">Contract: {shortAddress(CONTRACT_ADDRESS)}</span>
        </div>

        <div className="card">
          <div className="card-label">New Request</div>
          <div className="input-row">
            <input
              className="query-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && requestData()}
              placeholder="Ask something, e.g. SOL price or BTC price"
            />
            <button className="send-btn" onClick={requestData} disabled={!contract || !query}>
              Send Request
            </button>
          </div>
        </div>

        <div className="card">
          <div className="requests-header">
            <div className="card-label" style={{ marginBottom: 0 }}>Requests</div>
            <span className="badge">{requests.length} total</span>
          </div>
          {requests.length === 0 ? (
            <div className="empty-state">No requests yet. Connect your wallet and send one!</div>
          ) : (
            requests.map((req) => (
              <div className="request-item" key={req.id}>
                <span className="request-id">#{req.id}</span>
                <div className="request-info">
                  <div className="request-query">{req.query}</div>
                  {req.fulfilled && <div className="request-result">{req.result}</div>}
                </div>
                {req.fulfilled ? (
                  <span className="status-done">Fulfilled</span>
                ) : (
                  <span className="status-pending"><div className="spinner" />Pending</span>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}

export default App;
