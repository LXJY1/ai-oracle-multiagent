const hre = require("hardhat");

async function main() {
  const Oracle = await hre.ethers.getContractFactory("Oracle");
  const oracle = await Oracle.attach("0x5FbDB2315678afecb367f032d93F642f64180aa3");

  // 用Account #0（默认管理员）给Account #1添加Agent角色
  const [admin, agent] = await hre.ethers.getSigners();

  console.log("管理员地址:", admin.address);
  console.log("Agent地址:", agent.address);

  // 添加Agent
  const tx = await oracle.connect(admin).addAgent(agent.address);
  await tx.wait();
  console.log("✅ 已添加Agent角色");

  // Agent模拟AI返回结果
  const result = hre.ethers.utils.formatBytes32String('{"price": 2500, "unit": "USD"}');
  console.log("\nAgent准备返回结果:", '{"price": 2500, "unit": "USD"}');

  const tx2 = await oracle.connect(agent).fulfillRequest(0, result, "0x00");
  await tx2.wait();
  console.log("✅ Agent已回调合约，结果已写入");

  // 查询结果
  const finalResult = await oracle.getResult(0);
  console.log("\n最终查询结果(bytes):", finalResult);

  // 解析成字符串
  const decoded = hre.ethers.utils.toUtf8String(finalResult);
  console.log("解析后(JSON):", decoded);
}

main().catch(console.error);