// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IBadgeOracle {
    function isValid(bytes32 node, address bot) external view returns (bool);
    function revoke(bytes32 node) external; // only callable by the vault
}
