// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {ParableVault} from "../src/ParableVault.sol";
import {AlwaysValidBadgeOracle} from "../src/dev/AlwaysValidBadgeOracle.sol";

/// Env: PRICE_FEED, OPERATOR, MAX_PRICE_AGE (seconds), optional BADGE_ORACLE.
/// If BADGE_ORACLE is unset, deploys the DEV-ONLY AlwaysValidBadgeOracle placeholder.
contract Deploy is Script {
    function run() external returns (ParableVault vault) {
        address priceFeed = vm.envAddress("PRICE_FEED");
        address operator = vm.envAddress("OPERATOR");
        uint256 maxPriceAge = vm.envUint("MAX_PRICE_AGE");
        address badgeOracle = vm.envOr("BADGE_ORACLE", address(0));

        vm.startBroadcast();
        if (badgeOracle == address(0)) {
            badgeOracle = address(new AlwaysValidBadgeOracle());
            console.log("WARNING: deployed DEV-ONLY AlwaysValidBadgeOracle", badgeOracle);
        }
        vault = new ParableVault(priceFeed, badgeOracle, operator, maxPriceAge);
        vm.stopBroadcast();

        console.log("ParableVault", address(vault));
        console.log("badgeOracle", badgeOracle);
    }
}
