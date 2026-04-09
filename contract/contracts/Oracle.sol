// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/access/AccessControl.sol";

contract Oracle is AccessControl {
    bytes32 public constant AGENT_ROLE = keccak256("AGENT_ROLE");

    struct Request {
        address requester;
        string query;
        bool fulfilled;
        bytes result;
        uint256 timestamp;
    }

    mapping(uint256 => Request) public requests;
    uint256 public requestCounter;

    event OracleRequest(uint256 indexed requestId, string query, address indexed requester);
    event OracleResponse(uint256 indexed requestId, bytes result, address indexed agent);

    constructor() {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
    }

    function requestData(string memory query) external returns (uint256) {
        uint256 requestId = requestCounter++;
        requests[requestId] = Request({
            requester: msg.sender,
            query: query,
            fulfilled: false,
            result: "",
            timestamp: block.timestamp
        });
        emit OracleRequest(requestId, query, msg.sender);
        return requestId;
    }

    function fulfillRequest(
        uint256 requestId,
        bytes memory result,
        bytes memory /* signature */
    ) external onlyRole(AGENT_ROLE) {
        require(!requests[requestId].fulfilled, "Already fulfilled");
        // In production, should verify signature is from trusted agent
        requests[requestId].result = result;
        requests[requestId].fulfilled = true;
        emit OracleResponse(requestId, result, msg.sender);
    }

    function getResult(uint256 requestId) external view returns (bytes memory) {
        require(requests[requestId].fulfilled, "Request not fulfilled yet");
        return requests[requestId].result;
    }

    function addAgent(address agent) external onlyRole(DEFAULT_ADMIN_ROLE) {
        grantRole(AGENT_ROLE, agent);
    }

    function removeAgent(address agent) external onlyRole(DEFAULT_ADMIN_ROLE) {
        revokeRole(AGENT_ROLE, agent);
    }
}