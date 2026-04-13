// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title Oracle
 * @dev Multi-agent oracle with consensus mechanism for price aggregation.
 */
contract Oracle {
    uint256 private _requestIdCounter;

    // Maximum number of sub-agents
    uint256 public constant MAX_SUB_AGENTS = 10;
    uint256 public constant CONSENSUS_THRESHOLD = 2; // Standard deviation threshold for consensus

    // Event emitted when a new oracle request is made
    event OracleRequest(
        uint256 indexed requestId,
        address indexed requester,
        string query
    );

    // Event emitted when a sub-agent submits a price response
    event SubAgentResponse(
        uint256 indexed requestId,
        address indexed subAgent,
        uint256 price,
        uint256 timestamp
    );

    // Event emitted when consensus is reached
    event ConsensusReached(
        uint256 indexed requestId,
        uint256 finalPrice,
        uint256 agreeCount,
        uint256 totalResponses
    );

    // Event emitted when consensus fails and human intervention needed
    event ConsensusFailed(
        uint256 indexed requestId,
        uint256 disagreeCount,
        string reason
    );

    // Event emitted when final result is submitted
    event FinalResultSubmitted(
        uint256 indexed requestId,
        uint256 price,
        bytes result,
        bytes signature
    );

    // Consensus status
    enum ConsensusStatus {
        Pending,
        Reached,
        Failed,
        Finalized
    }

    // Sub-agent info
    struct SubAgent {
        address addr;
        string name;
        bool active;
    }

    // Individual sub-agent response
    struct SubAgentResponse {
        address subAgent;
        uint256 price;
        string dataSource;      // e.g., "CoinGecko", "CoinPaprika", "CoinCap"
        uint256 timestamp;
        bool submitted;
    }

    // Request details
    struct Request {
        address requester;
        string query;
        bytes result;
        bytes signature;
        bool fulfilled;
        ConsensusStatus consensusStatus;
        uint256 finalPrice;
        uint256 agreeCount;
        uint256 disagreeCount;
        // Sub-agent responses
        mapping(address => SubAgentResponse) responses;
        address[] respondingSubAgents;
    }

    // Mapping of request ID to request details
    mapping(uint256 => Request) public requests;

    // Mapping of authorized agents (main agents)
    mapping(address => bool) public agents;

    // Registered sub-agents
    mapping(uint256 => SubAgent) public subAgents;
    uint256 public subAgentCount;

    // Timeout for collecting sub-agent responses (in seconds)
    uint256 public responseTimeout;

    modifier onlyAgent() {
        require(agents[msg.sender], "Not an authorized agent");
        _;
    }

    /**
     * @dev Set the response timeout for sub-agent responses
     * @param _timeout Timeout in seconds
     */
    constructor(uint256 _timeout) {
        responseTimeout = _timeout > 0 ? _timeout : 30 seconds;
    }

    /**
     * @dev Add an authorized main agent
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
     * @dev Register a sub-agent
     * @param addr The sub-agent address
     * @param name The sub-agent name
     */
    function registerSubAgent(address addr, string calldata name) external onlyAgent {
        require(subAgentCount < MAX_SUB_AGENTS, "Max sub-agents reached");
        subAgentCount++;
        subAgents[subAgentCount] = SubAgent({
            addr: addr,
            name: name,
            active: true
        });
    }

    /**
     * @dev Deactivate a sub-agent
     * @param index The sub-agent index to deactivate
     */
    function deactivateSubAgent(uint256 index) external onlyAgent {
        require(index <= subAgentCount, "Invalid sub-agent index");
        subAgents[index].active = false;
    }

    /**
     * @dev Request data from the oracle.
     * @param query The natural language query.
     */
    function requestData(string calldata query) external returns (uint256) {
        _requestIdCounter++;
        uint256 requestId = _requestIdCounter;

        Request storage req = requests[requestId];
        req.requester = msg.sender;
        req.query = query;
        req.consensusStatus = ConsensusStatus.Pending;
        req.fulfilled = false;

        emit OracleRequest(requestId, msg.sender, query);

        return requestId;
    }

    /**
     * @dev Submit price response from a sub-agent
     * @param requestId The ID of the request
     * @param price The price reported by the sub-agent (in smallest unit)
     * @param dataSource The data source used (e.g., "CoinGecko")
     */
    function submitSubAgentResponse(
        uint256 requestId,
        uint256 price,
        string calldata dataSource
    ) external {
        Request storage req = requests[requestId];
        require(req.consensusStatus == ConsensusStatus.Pending, "Request not pending");

        // Check if caller is an active sub-agent
        bool isValidSubAgent = false;
        for (uint256 i = 1; i <= subAgentCount; i++) {
            if (subAgents[i].addr == msg.sender && subAgents[i].active) {
                isValidSubAgent = true;
                break;
            }
        }
        require(isValidSubAgent, "Not an authorized sub-agent");

        // Record response
        SubAgentResponse storage response = req.responses[msg.sender];
        response.subAgent = msg.sender;
        response.price = price;
        response.dataSource = dataSource;
        response.timestamp = block.timestamp;
        response.submitted = true;

        // Track responding sub-agents
        req.respondingSubAgents.push(msg.sender);

        emit SubAgentResponse(requestId, msg.sender, price, block.timestamp);
    }

    /**
     * @dev Calculate consensus from collected sub-agent responses
     * Called by main agent after timeout
     * @param requestId The ID of the request
     * @return finalPrice The consensus price
     * @return agreeCount Number of agents agreeing with consensus
     */
    function calculateConsensus(uint256 requestId) external onlyAgent returns (uint256 finalPrice, uint256 agreeCount) {
        Request storage req = requests[requestId];
        require(req.consensusStatus == ConsensusStatus.Pending, "Request not pending");
        require(req.respondingSubAgents.length > 0, "No responses collected");

        uint256 totalResponses = req.respondingSubAgents.length;

        // Calculate average and standard deviation
        uint256 sum = 0;
        uint256[] memory prices = new uint256[](totalResponses);

        for (uint256 i = 0; i < totalResponses; i++) {
            address subAgent = req.respondingSubAgents[i];
            uint256 price = req.responses[subAgent].price;
            prices[i] = price;
            sum += price;
        }

        uint256 avg = sum / totalResponses;

        // Calculate standard deviation
        uint256 varianceSum = 0;
        for (uint256 i = 0; i < totalResponses; i++) {
            uint256 diff = prices[i] > avg ? prices[i] - avg : avg - prices[i];
            varianceSum += diff * diff;
        }
        uint256 variance = varianceSum / totalResponses;
        uint256 stdDev = uint256(sqrt(uint256(variance)));

        // Count agents within threshold
        uint256 withinThreshold = 0;
        uint256 threshold = CONSENSUS_THRESHOLD * stdDev;

        // If stdDev is 0 (all same), all agree
        if (stdDev == 0) {
            withinThreshold = totalResponses;
        } else {
            for (uint256 i = 0; i < totalResponses; i++) {
                address subAgent = req.respondingSubAgents[i];
                uint256 price = req.responses[subAgent].price;
                uint256 diff = price > avg ? price - avg : avg - price;
                if (diff <= threshold) {
                    withinThreshold++;
                }
            }
        }

        agreeCount = withinThreshold;
        uint256 disagreeCount = totalResponses - withinThreshold;

        req.agreeCount = agreeCount;
        req.disagreeCount = disagreeCount;

        // Determine consensus
        if (agreeCount == totalResponses) {
            // Full consensus
            req.consensusStatus = ConsensusStatus.Reached;
            req.finalPrice = avg;
            emit ConsensusReached(requestId, avg, agreeCount, totalResponses);
        } else if (agreeCount > totalResponses / 2) {
            // Majority consensus
            req.consensusStatus = ConsensusStatus.Reached;
            req.finalPrice = avg;
            emit ConsensusReached(requestId, avg, agreeCount, totalResponses);
        } else {
            // No consensus - needs human intervention
            req.consensusStatus = ConsensusStatus.Failed;
            emit ConsensusFailed(requestId, disagreeCount, "No majority agreement");
        }

        return (req.finalPrice, agreeCount);
    }

    /**
     * @dev Force finalize with human decision (fallback)
     * @param requestId The ID of the request
     * @param price The human-decided price
     */
    function forceFinalize(uint256 requestId, uint256 price) external onlyAgent {
        Request storage req = requests[requestId];
        require(req.consensusStatus == ConsensusStatus.Failed, "Not in failed state");
        req.finalPrice = price;
        req.consensusStatus = ConsensusStatus.Finalized;
    }

    /**
     * @dev Submit final result with AI analysis (only callable by authorized agents).
     * @param requestId The ID of the request
     * @param result The AI result data as bytes
     * @param signature The signature of the result
     */
    function fulfillRequest(
        uint256 requestId,
        bytes calldata result,
        bytes calldata signature
    ) external onlyAgent {
        Request storage req = requests[requestId];
        require(
            req.consensusStatus == ConsensusStatus.Reached ||
            req.consensusStatus == ConsensusStatus.Finalized,
            "Consensus not reached or finalized"
        );
        require(!req.fulfilled, "Request already fulfilled");

        req.result = result;
        req.signature = signature;
        req.fulfilled = true;

        emit FinalResultSubmitted(requestId, req.finalPrice, result, signature);
    }

    /**
     * @dev Get the details of a request
     * @param requestId The ID of the request
     */
    function getRequest(uint256 requestId) external view returns (Request memory) {
        return requests[requestId];
    }

    /**
     * @dev Get sub-agent response for a specific request
     * @param requestId The ID of the request
     * @param subAgent The sub-agent address
     */
    function getSubAgentResponse(uint256 requestId, address subAgent)
        external
        view
        returns (SubAgentResponse memory)
    {
        return requests[requestId].responses[subAgent];
    }

    /**
     * @dev Get responding sub-agents for a request
     * @param requestId The ID of the request
     */
    function getRespondingSubAgents(uint256 requestId) external view returns (address[] memory) {
        return requests[requestId].respondingSubAgents;
    }

    /**
     * @dev Get the latest request ID
     */
    function getLatestRequestId() external view returns (uint256) {
        return _requestIdCounter;
    }

    // Math library for sqrt
    function sqrt(uint256 x) internal pure returns (uint256) {
        if (x == 0) return 0;
        uint256 z = (x + 1) / 2;
        uint256 y = x;
        while (z < y) {
            y = z;
            z = (x / z + z) / 2;
        }
        return y;
    }
}
