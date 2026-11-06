// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

// Deploys the badge oracle and the vault, and links them together.
// Order matters: the vault needs the oracle's address, and the oracle needs the vault's (setVault).
// Env: PRICE_FEED, OPERATOR, MAX_PRICE_AGE (seconds). USE_DEV_ORACLE=1 skips ENS (fallback, accepts any badge).
import {Script, console} from "forge-std/Script.sol";
import {ParableVault} from "../src/ParableVault.sol";
import {EnsV2BadgeOracle} from "../src/adapters/EnsV2BadgeOracle.sol";
import {AlwaysValidBadgeOracle} from "../src/dev/AlwaysValidBadgeOracle.sol";

contract Deploy is Script {
    function run() external returns (ParableVault vault) {
        address priceFeed = vm.envAddress("PRICE_FEED");
        address operator = vm.envAddress("OPERATOR");
        uint256 maxPriceAge = vm.envUint("MAX_PRICE_AGE");
        bool useDevOracle = vm.envOr("USE_DEV_ORACLE", uint256(0)) == 1;

        vm.startBroadcast();
        address oracle;
        if (useDevOracle) {
            oracle = address(new AlwaysValidBadgeOracle());
            console.log("WARNING: DEV-ONLY oracle, every badge counts as valid");
        } else {
            oracle = address(new EnsV2BadgeOracle(operator));
        }
        vault = new ParableVault(priceFeed, oracle, operator, maxPriceAge);
        if (!useDevOracle) {
            // setVault is operator-only and one-shot, so the broadcaster must be the operator.
            EnsV2BadgeOracle(oracle).setVault(address(vault));
        }
        vm.stopBroadcast();

        console.log("badgeOracle", oracle);
        console.log("ParableVault", address(vault));
    }
}
