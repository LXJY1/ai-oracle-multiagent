const hre = require("hardhat");
const fs = require("fs");
async function main() {
  const Oracle = await hre.ethers.getContractFactory("Oracle");
  const signer = new hre.ethers.Wallet("0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d", hre.ethers.provider);
  console.log("Deploying from:", signer.address);
  const oracle = await Oracle.connect(signer).deploy();
  await oracle.deployed();
  const address = oracle.address;
  console.log("Oracle deployed to:", address);
  await oracle.addAgent(signer.address);
  console.log("Agent added:", signer.address);
  fs.writeFileSync("deployment.json", JSON.stringify({ network: hre.network.name, contractAddress: address, timestamp: new Date().toISOString() }, null, 2));
}
main().catch(console.error);
