const hre = require("hardhat");
const fs = require("fs");
async function main() {
  const MinimalOracle = await hre.ethers.getContractFactory("MinimalOracle");
  const oracle = await MinimalOracle.deploy();
  await oracle.deployed();
  console.log("MinimalOracle deployed to:", oracle.address);
  fs.writeFileSync("deployment.json", JSON.stringify({ network: hre.network.name, contractAddress: oracle.address }, null, 2));
}
main().catch(console.error);
