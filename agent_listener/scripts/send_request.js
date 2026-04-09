// Script to send a test oracle request
const hre = require("hardhat");

async function main() {
  const contractAddress = process.env.CONTRACT_ADDRESS || "0xB7f8BC63BbcaD18155201308C8f3540b07f84F5e";
  const Oracle = await hre.ethers.getContractFactory("Oracle");
  const oracle = Oracle.attach(contractAddress);

  console.log("Sending test oracle request...");

  const tx = await oracle.requestData("What is the price of ETH?");
  const receipt = await tx.wait();

  console.log("Request sent! Transaction:", receipt.hash);
  console.log("Request ID:", receipt.logs[0].args.requestId.toString());
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
