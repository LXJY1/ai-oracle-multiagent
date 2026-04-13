const hre = require("hardhat");

async function main() {
  const Simple = await hre.ethers.getContractFactory("Simple");
  const simple = await Simple.deploy();
  await simple.deployed();
  console.log("Simple deployed to:", simple.address);
}

main().catch(console.error);
