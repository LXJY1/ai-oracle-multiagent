const hre = require("hardhat");

async function main() {
  const Oracle = await hre.ethers.getContractFactory("Oracle");
  const oracle = await Oracle.attach("0x5FbDB2315678afecb367f032d93F642f64180aa3");
  const agent = (await hre.ethers.getSigners())[1];
  const result = hre.ethers.utils.formatBytes32String("new data");

  console.log("尝试对已完成的请求再次回调...\n");
  try {
    await oracle.connect(agent).fulfillRequest(0, result, "0x00");
    console.log("❌ 应该失败但没有");
  } catch (err) {
    console.log("✅ 被正确拒绝了！错误信息:");
    console.log("   ", err.message.includes("Already fulfilled") ? "Already fulfilled" : err.message);
  }
}

main();