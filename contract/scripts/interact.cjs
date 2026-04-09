const hre = require("hardhat");

async function main() {
  // 获取合约
  const Oracle = await hre.ethers.getContractFactory("Oracle");
  const oracle = await Oracle.attach("0x5FbDB2315678afecb367f032d93F642f64180aa3");

  // 1. 查询当前请求数量
  const counter = await oracle.requestCounter();
  console.log("当前请求数量:", counter.toString());

  // 2. 发起一个请求
  console.log("\n发起请求: 查询ETH价格");
  const tx = await oracle.requestData("ETH价格是多少？");
  const receipt = await tx.wait();
  console.log("交易hash:", receipt.hash);

  // 3. 再次查询请求数量
  const newCounter = await oracle.requestCounter();
  console.log("请求后数量:", newCounter.toString());

  // 4. 查询请求#0的内容
  const request = await oracle.requests(0);
  console.log("\n请求#0内容:");
  console.log("  - 请求者:", request[0]);
  console.log("  - 查询内容:", request[1]);
  console.log("  - 是否完成:", request[2]);
}

main().catch(console.error);