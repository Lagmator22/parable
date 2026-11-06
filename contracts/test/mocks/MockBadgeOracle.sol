// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IBadgeOracle} from "../../src/interfaces/IBadgeOracle.sol";

contract MockBadgeOracle is IBadgeOracle {
    mapping(bytes32 => bool) public valid;
    mapping(bytes32 => bool) public revoked;
    bool public revertOnRevoke;

    function setValid(bytes32 node, bool v) external {
        valid[node] = v;
    }

    function setRevertOnRevoke(bool v) external {
        revertOnRevoke = v;
    }

    function isValid(bytes32 node, address) external view returns (bool) {
        return valid[node];
    }

    function revoke(bytes32 node) external {
        require(!revertOnRevoke, "revoke failed");
        valid[node] = false;
        revoked[node] = true;
    }
}
