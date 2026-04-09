const hre = require("hardhat");
const fs = require("fs");

async function main() {
  const Oracle = await hre.ethers.getContractFactory("Oracle");
  const oracle = await Oracle.deploy();
  await oracle.deployed();
  const address = oracle.address;
  console.log("Oracle deployed to:", address);

  const deploymentInfo = {
    network: hre.network.name,
    contractAddress: address,
    timestamp: new Date().toISOString()
  };
  fs.writeFileSync(
    "deployment.json",
    JSON.stringify(deploymentInfo, null, 2)
  );
  console.log("Deployment info saved to deployment.json");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});