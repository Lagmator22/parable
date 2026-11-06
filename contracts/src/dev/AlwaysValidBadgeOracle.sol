// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IBadgeOracle} from "../interfaces/IBadgeOracle.sol";

/// DEV ONLY. Accepts every badge. Never use outside local/first-deploy testing:
/// it makes the vault's badge check meaningless.
contract AlwaysValidBadgeOracle is IBadgeOracle {
    function isValid(bytes32, address) external pure returns (bool) {
        return true;
    }

    function revoke(bytes32) external {}
}
