import React, { useState } from 'react';
import { ethers } from 'ethers';
import OracleABI from './OracleABI.json';

const CONTRACT_ADDRESS = '0x7A2127475B453aDb46CB83Bb1075854aa43a7738'; // Replace with the actual address from Person A

function App() {
  const [account, setAccount] = useState('');
  const [contract, setContract] = useState(null);
  const [query, setQuery] = useState('');
  const [requests, setRequests] = useState([]);

  const connectWallet = async () => {
    if (window.ethereum) {
      const provider = new ethers.providers.Web3Provider(window.ethereum);
      await provider.send("eth_requestAccounts", []);
      const signer = provider.getSigner();
      const address = await signer.getAddress();
      const contractInstance = new ethers.Contract(CONTRACT_ADDRESS, OracleABI, signer);
      setAccount(address);
      setContract(contractInstance);
      listenEvents(contractInstance);
    } else {
      alert('Please install MetaMask');
    }
  };

  const listenEvents = (contractInstance) => {
    contractInstance.on('OracleResponse', (requestId, result, signature) => {
      setRequests(prev => prev.map(req =>
        req.id === requestId.toNumber()
          ? { ...req, result: ethers.utils.toUtf8String(result), fulfilled: true }
          : req
      ));
    });
  };

  const requestData = async () => {
    if (!contract) return alert('Connect wallet first!');
    try {
      const tx = await contract.requestData(query);
      const receipt = await tx.wait();
      const event = receipt.events.find(e => e.event === 'OracleRequest');
      const requestId = event.args.requestId.toNumber();
      setRequests(prev => [...prev, { id: requestId, query, fulfilled: false, result: null }]);
      setQuery('');
    } catch (err) {
      console.error(err);
      alert('Transaction failed: ' + err.message);
    }
  };

  return (
    <div style={{ padding: 30 }}>
      <h1>🔮 Oracle DApp</h1>

      <button onClick={connectWallet}>
        {account
          ? `✅ Connected: ${account.slice(0, 6)}...${account.slice(-4)}`
          : 'Connect Wallet'}
      </button>

      <hr />

      <div>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask something, e.g. ETH price"
          style={{ width: 300, marginRight: 10 }}
        />
        <button onClick={requestData} disabled={!contract || !query}>
          Send Request
        </button>
      </div>

      <h3>Requests</h3>
      {requests.length === 0
        ? <p style={{ color: 'gray' }}>No requests yet.</p>
        : <ul>
            {requests.map(req => (
              <li key={req.id} style={{ marginBottom: 8 }}>
                <strong>#{req.id}</strong>: {req.query} →{' '}
                {req.fulfilled
                  ? <span style={{ color: 'green' }}>{req.result}</span>
                  : <span style={{ color: 'orange' }}>pending...</span>}
              </li>
            ))}
          </ul>
      }
    </div>
  );
}

export default App;