const hre = require("hardhat");

async function main() {
  console.log("Deploying Oracle contract...");

  const Oracle = await hre.ethers.getContractFactory("Oracle");
  const oracle = await Oracle.deploy();

  await oracle.waitForDeployment();
  const address = await oracle.getAddress();

  console.log("Oracle deployed to:", address);
  console.log("Update your .env with:");
  console.log(`CONTRACT_ADDRESS=${address}`);

  // Add default agent (Hardhat account #0)
  const [deployer] = await hre.ethers.getSigners();
  await oracle.addAgent(deployer.address);
  console.log("Added agent:", deployer.address);

  // Export ABI
  const artifact = await hre.artifacts.readArtifact("Oracle");
  const fs = require("fs");
  fs.writeFileSync("Oracle_abi.json", JSON.stringify(artifact.abi, null, 2));
  console.log("ABI exported to Oracle_abi.json");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
