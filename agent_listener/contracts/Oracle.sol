// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title Oracle
 * @dev A simple oracle contract that records requests and accepts responses.
 */
contract Oracle {
    uint256 private _requestIdCounter;

    // Event emitted when a new oracle request is made
    event OracleRequest(
        uint256 indexed requestId,
        address indexed requester,
        string query
    );

    // Event emitted when an oracle response is provided
    event OracleResponse(
        uint256 indexed requestId,
        bytes result,
        bytes signature
    );

    // Struct to store request details
    struct Request {
        address requester;
        string query;
        bytes result;
        bytes signature;
        bool fulfilled;
    }

    // Mapping of request ID to request details
    mapping(uint256 => Request) public requests;

    // Mapping of authorized agents
    mapping(address => bool) public agents;

    modifier onlyAgent() {
        require(agents[msg.sender], "Not an authorized agent");
        _;
    }

    /**
     * @dev Add an authorized agent
     * @param agent The address to add
     */
    function addAgent(address agent) external {
        agents[agent] = true;
    }

    /**
     * @dev Remove an agent
     * @param agent The address to remove
     */
    function removeAgent(address agent) external {
        agents[agent] = false;
    }

    /**
     * @dev Request data from the oracle.
     * @param query The natural language query.
     */
    function requestData(string calldata query) external returns (uint256) {
        _requestIdCounter++;
        uint256 requestId = _requestIdCounter;

        requests[requestId] = Request({
            requester: msg.sender,
            query: query,
            result: "",
            signature: "",
            fulfilled: false
        });

        emit OracleRequest(requestId, msg.sender, query);

        return requestId;
    }

    /**
     * @dev Fulfill an oracle request (only callable by authorized agents).
     * @param requestId The ID of the request to fulfill.
     * @param result The result data as bytes.
     * @param signature The signature of the result.
     */
    function fulfillRequest(
        uint256 requestId,
        bytes calldata result,
        bytes calldata signature
    ) external onlyAgent {
        require(!requests[requestId].fulfilled, "Request already fulfilled");

        requests[requestId].result = result;
        requests[requestId].signature = signature;
        requests[requestId].fulfilled = true;

        emit OracleResponse(requestId, result, signature);
    }

    /**
     * @dev Get the details of a request.
     * @param requestId The ID of the request.
     */
    function getRequest(uint256 requestId) external view returns (Request memory) {
        return requests[requestId];
    }

    /**
     * @dev Get the latest request ID.
     */
    function getLatestRequestId() external view returns (uint256) {
        return _requestIdCounter;
    }
}
