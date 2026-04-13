const hre = require("hardhat");

async function main() {
  const contractAddress = "0x8464135c8F25Da09e49BC8782676a84730C318bC";
  const artifact = await hre.artifacts.readArtifact("Oracle");
  const contract = new hre.ethers.Contract(contractAddress, artifact.abi, new hre.ethers.Wallet("0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d", hre.ethers.provider));
  
  // Add Account #0 as agent
  const tx = await contract.addAgent("0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266");
  await tx.wait();
  console.log("Account #0 added as agent");
}

main().catch(console.error);
