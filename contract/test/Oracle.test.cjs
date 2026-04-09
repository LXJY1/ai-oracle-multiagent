const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Oracle", function () {
  let oracle;
  let owner;
  let agent;
  let user;

  beforeEach(async function () {
    const Oracle = await ethers.getContractFactory("Oracle");
    oracle = await Oracle.deploy();
    await oracle.deployed();

    [owner, agent, user] = await ethers.getSigners();
  });

  describe("requestData", function () {
    it("Should emit OracleRequest event", async function () {
      const query = "price of ETH";

      await expect(oracle.connect(user).requestData(query))
        .to.emit(oracle, "OracleRequest")
        .withArgs(0, query, user.address);
    });

    it("Should increment requestCounter", async function () {
      expect(await oracle.requestCounter()).to.equal(0);

      await oracle.connect(user).requestData("query 1");
      expect(await oracle.requestCounter()).to.equal(1);

      await oracle.connect(user).requestData("query 2");
      expect(await oracle.requestCounter()).to.equal(2);
    });

    it("Should store request correctly", async function () {
      await oracle.connect(user).requestData("test query");

      const request = await oracle.requests(0);
      expect(request.requester).to.equal(user.address);
      expect(request.query).to.equal("test query");
      expect(request.fulfilled).to.equal(false);
    });
  });

  describe("fulfillRequest", function () {
    beforeEach(async function () {
      await oracle.connect(owner).addAgent(agent.address);
    });

    it("Should reject if caller is not agent", async function () {
      await oracle.connect(user).requestData("query");
      const result = ethers.utils.formatBytes32String("test result");

      await expect(
        oracle.connect(user).fulfillRequest(0, result, "0x00")
      ).to.be.reverted;
    });

    it("Should revert if already fulfilled", async function () {
      await oracle.connect(user).requestData("query");
      const result = ethers.utils.formatBytes32String("test result");

      await oracle.connect(agent).fulfillRequest(0, result, "0x00");
      await expect(
        oracle.connect(agent).fulfillRequest(0, result, "0x00")
      ).to.be.revertedWith("Already fulfilled");
    });

    it("Should fulfill request and emit OracleResponse", async function () {
      await oracle.connect(user).requestData("query");
      const result = ethers.utils.formatBytes32String('{"price": 2500}');

      await expect(oracle.connect(agent).fulfillRequest(0, result, "0x00"))
        .to.emit(oracle, "OracleResponse")
        .withArgs(0, result, agent.address);
    });

    it("Should update request.fulfilled to true", async function () {
      await oracle.connect(user).requestData("query");
      const result = ethers.utils.formatBytes32String("test result");

      let request = await oracle.requests(0);
      expect(request.fulfilled).to.equal(false);

      await oracle.connect(agent).fulfillRequest(0, result, "0x00");

      request = await oracle.requests(0);
      expect(request.fulfilled).to.equal(true);
      expect(request.result).to.equal(result);
    });
  });

  describe("getResult", function () {
    beforeEach(async function () {
      await oracle.connect(owner).addAgent(agent.address);
      await oracle.connect(user).requestData("query");
    });

    it("Should revert if request not fulfilled", async function () {
      await expect(oracle.getResult(0)).to.be.revertedWith(
        "Request not fulfilled yet"
      );
    });

    it("Should return result after fulfillment", async function () {
      const expectedResult = ethers.utils.formatBytes32String('{"price": 3000}');
      await oracle.connect(agent).fulfillRequest(0, expectedResult, "0x00");

      const result = await oracle.getResult(0);
      expect(result).to.equal(expectedResult);
    });
  });

  describe("addAgent / removeAgent", function () {
    it("Should allow admin to add agent", async function () {
      await oracle.connect(owner).addAgent(agent.address);
      await oracle.connect(user).requestData("query");
      const result = ethers.utils.formatBytes32String("result");
      await expect(
        oracle.connect(agent).fulfillRequest(0, result, "0x00")
      ).to.not.be.reverted;
    });

    it("Should allow admin to remove agent", async function () {
      await oracle.connect(owner).addAgent(agent.address);
      await oracle.connect(owner).removeAgent(agent.address);

      await oracle.connect(user).requestData("query");
      const result = ethers.utils.formatBytes32String("result");
      await expect(
        oracle.connect(agent).fulfillRequest(0, result, "0x00")
      ).to.be.reverted;
    });

    it("Should revert if non-admin tries to add agent", async function () {
      await expect(
        oracle.connect(user).addAgent(agent.address)
      ).to.be.reverted;
    });
  });
});