// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract MinimalOracle {
    uint256 public counter;
    
    function requestData(string calldata query) external returns (uint256) {
        counter++;
        return counter;
    }
    
    function fulfillRequest(uint256 requestId, bytes calldata result) external {
        // do nothing for now
    }
}
