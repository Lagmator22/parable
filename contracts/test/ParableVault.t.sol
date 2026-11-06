// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {ParableVault} from "../src/ParableVault.sol";
import {MockPriceFeed} from "./mocks/MockPriceFeed.sol";
import {MockBadgeOracle} from "./mocks/MockBadgeOracle.sol";

contract ParableVaultTest is Test {
    ParableVault vault;
    MockPriceFeed feed;
    MockBadgeOracle oracle;

    address operator = makeAddr("operator");
    address bot = makeAddr("bot");
    address bot2 = makeAddr("bot2");
    address creatorWallet = makeAddr("creatorWallet");
    address stranger = makeAddr("stranger");

    bytes32 creatorId = keccak256("creator-1");
    bytes32 node = keccak256("bot-01.parable.eth");
    bytes32 node2 = keccak256("bot-02.parable.eth");

    uint256 constant PRICE = 2000e8;
    uint256 constant CASH = 1000e6;
    uint256 constant MAX_TRADE = 500e6;
    uint16 constant MAX_LOSS = 1000; // 10%
    uint256 constant MAX_AGE = 1 hours;

    function setUp() public {
        vm.warp(1_000_000);
        feed = new MockPriceFeed(int256(PRICE));
        oracle = new MockBadgeOracle();
        vault = new ParableVault(address(feed), address(oracle), operator, MAX_AGE);
        oracle.setValid(node, true);
        oracle.setValid(node2, true);
    }

    function _register() internal returns (uint256) {
        return _registerFull(bot, creatorId, creatorWallet, node, uint64(block.timestamp + 1 days), MAX_TRADE);
    }

    function _registerFull(
        address b,
        bytes32 cid,
        address wallet,
        bytes32 n,
        uint64 expiresAt,
        uint256 maxTrade
    ) internal returns (uint256) {
        vm.prank(operator);
        return vault.registerBot(b, cid, wallet, n, expiresAt, CASH, maxTrade, MAX_LOSS, keccak256("momentum"));
    }

    function _status(uint256 id) internal view returns (ParableVault.Status) {
        return vault.getBot(id).status;
    }

    // ---------------------------------------------------------------- happy path

    function test_happyPathTrade() public {
        uint256 id = _register();
        assertEq(id, 1);
        assertEq(vault.botIdOf(bot), 1);
        assertEq(vault.equityUsd(id), CASH);

        vm.prank(bot);
        vault.trade(id, true, 500e6);
        ParableVault.Bot memory b = vault.getBot(id);
        assertEq(b.cashUsd, 500e6);
        assertEq(b.ethWei, 0.25 ether); // 500 USD at 2000
        assertEq(vault.equityUsd(id), CASH);

        // price up 10%: equity 1050, sell 100 USD worth
        feed.setPrice(int256(2200e8));
        vm.prank(bot);
        vault.trade(id, false, 100e6);
        b = vault.getBot(id);
        assertEq(b.cashUsd, 600e6);
        // hwm follows equity (~1050, a hair below because the sell rounds against the bot)
        assertEq(b.hwmUsd, vault.equityUsd(id));
        assertTrue(b.hwmUsd > 1049e6 && b.hwmUsd <= 1050e6);
        assertEq(uint8(b.status), uint8(ParableVault.Status.Alive));
        // 100 USD at 2200 = 0.04545... ETH rounded up
        uint256 numerator = 100e6 * 1e20;
        uint256 sold = (numerator - 1) / 2200e8 + 1;
        assertEq(b.ethWei, 0.25 ether - sold);
    }

    function test_roundingNeverCreatesValue() public {
        uint256 id = _register();
        vm.startPrank(bot);
        feed.setPrice(int256(3333_33333333)); // awkward price
        vault.trade(id, true, 7e6);
        vault.trade(id, false, 7e6);
        vm.stopPrank();
        assertLe(vault.equityUsd(id), CASH);
    }

    // ---------------------------------------------------------------- blocked trades

    function test_unregisteredBotBlocked() public {
        vm.prank(bot);
        vm.expectRevert(ParableVault.NotRegistered.selector);
        vault.trade(1, true, 1e6);
    }

    function test_nonBotCallerBlocked() public {
        uint256 id = _register();
        vm.prank(stranger);
        vm.expectRevert(ParableVault.NotBot.selector);
        vault.trade(id, true, 1e6);
    }

    function test_expiredBlocked() public {
        uint256 id = _register();
        vm.warp(block.timestamp + 1 days);
        feed.setPrice(int256(PRICE));
        vm.prank(bot);
        vm.expectRevert(ParableVault.Expired.selector);
        vault.trade(id, true, 1e6);
    }

    function test_badgeInvalidBlocked() public {
        uint256 id = _register();
        oracle.setValid(node, false);
        vm.prank(bot);
        vm.expectRevert(ParableVault.BadgeInvalid.selector);
        vault.trade(id, true, 1e6);
    }

    function test_overLimitBlocked() public {
        uint256 id = _register();
        vm.prank(bot);
        vm.expectRevert(ParableVault.OverTradeLimit.selector);
        vault.trade(id, true, MAX_TRADE + 1);
    }

    function test_zeroAmountBlocked() public {
        uint256 id = _register();
        vm.prank(bot);
        vm.expectRevert(ParableVault.ZeroAmount.selector);
        vault.trade(id, true, 0);
    }

    function test_insufficientBalance() public {
        uint256 id = _registerFull(bot, creatorId, creatorWallet, node, uint64(block.timestamp + 1 days), 5000e6);
        vm.startPrank(bot);
        vm.expectRevert(ParableVault.InsufficientBalance.selector);
        vault.trade(id, true, CASH + 1); // more cash than it has
        vm.expectRevert(ParableVault.InsufficientBalance.selector);
        vault.trade(id, false, 1e6); // no ETH to sell
        vm.stopPrank();
    }

    function test_stalePriceBlocked() public {
        uint256 id = _register();
        vm.warp(block.timestamp + MAX_AGE + 1);
        vm.prank(bot);
        vm.expectRevert(ParableVault.StalePrice.selector);
        vault.trade(id, true, 1e6);
    }

    function test_nonPositivePriceBlocked() public {
        uint256 id = _register();
        feed.setPrice(0);
        vm.prank(bot);
        vm.expectRevert(ParableVault.StalePrice.selector);
        vault.trade(id, true, 1e6);
    }

    function test_deadBotCannotTrade() public {
        uint256 id = _register();
        vm.prank(creatorWallet);
        vault.kill(id);
        vm.prank(bot);
        vm.expectRevert(ParableVault.NotAlive.selector);
        vault.trade(id, true, 1e6);
    }

    // ---------------------------------------------------------------- death

    function test_autoKillOnLossAfterTrade() public {
        uint256 id = _register();
        vm.prank(bot);
        vault.trade(id, true, 500e6); // 0.25 ETH, equity 1000
        feed.setPrice(int256(1500e8)); // equity 875 -> 12.5% drawdown, still alive until someone acts
        assertEq(uint8(_status(id)), uint8(ParableVault.Status.Alive));

        vm.prank(bot);
        vault.trade(id, false, 1e6);
        ParableVault.Bot memory b = vault.getBot(id);
        assertEq(uint8(b.status), uint8(ParableVault.Status.Dead));
        assertEq(uint8(b.cause), uint8(ParableVault.DeathCause.LossLimit));
        assertTrue(oracle.revoked(node));
        assertEq(vault.totalDead(), 1);
        assertEq(vault.equityUsd(id), b.finalEquityUsd);
    }

    function test_checkAndRevokeByAnyone() public {
        uint256 id = _register();
        vm.prank(bot);
        vault.trade(id, true, 500e6);

        vm.prank(stranger);
        vm.expectRevert(ParableVault.NotOverLimit.selector);
        vault.checkAndRevoke(id);

        feed.setPrice(int256(1500e8));
        vm.prank(stranger);
        vault.checkAndRevoke(id);
        ParableVault.Bot memory b = vault.getBot(id);
        assertEq(uint8(b.status), uint8(ParableVault.Status.Dead));
        assertEq(uint8(b.cause), uint8(ParableVault.DeathCause.LossLimit));
        assertEq(b.finalEquityUsd, 875e6);
        assertTrue(oracle.revoked(node));

        vm.prank(stranger);
        vm.expectRevert(ParableVault.NotAlive.selector);
        vault.checkAndRevoke(id);
    }

    function test_checkAndRevokeBoundaryExactlyAtLimit() public {
        uint256 id = _register();
        vm.prank(bot);
        vault.trade(id, true, 500e6);
        feed.setPrice(int256(1800e8)); // equity 950 -> 5%: safe
        vm.expectRevert(ParableVault.NotOverLimit.selector);
        vault.checkAndRevoke(id);
        feed.setPrice(int256(1600e8)); // equity 900 -> exactly 10%: dies (>=)
        vault.checkAndRevoke(id);
        assertEq(uint8(_status(id)), uint8(ParableVault.Status.Dead));
    }

    function test_killByCreatorAndOperatorOnly() public {
        uint256 id = _register();
        vm.prank(stranger);
        vm.expectRevert(ParableVault.Unauthorized.selector);
        vault.kill(id);

        vm.prank(creatorWallet);
        vault.kill(id);
        ParableVault.Bot memory b = vault.getBot(id);
        assertEq(uint8(b.cause), uint8(ParableVault.DeathCause.Killed));
        assertEq(b.finalEquityUsd, CASH);
        assertTrue(oracle.revoked(node));

        uint256 id2 = _registerFull(bot2, creatorId, creatorWallet, node2, uint64(block.timestamp + 1 days), MAX_TRADE);
        vm.prank(operator);
        vault.kill(id2);
        assertEq(uint8(_status(id2)), uint8(ParableVault.Status.Dead));
    }

    function test_expireByAnyoneAfterExpiry() public {
        uint256 id = _register();
        vm.prank(stranger);
        vm.expectRevert(ParableVault.NotExpired.selector);
        vault.expire(id);

        vm.warp(block.timestamp + 1 days);
        vm.prank(stranger);
        vault.expire(id);
        ParableVault.Bot memory b = vault.getBot(id);
        assertEq(uint8(b.cause), uint8(ParableVault.DeathCause.Expired));
        assertTrue(oracle.revoked(node));
    }

    function test_deathNotBlockedByStaleFeed() public {
        uint256 id = _register();
        vm.warp(block.timestamp + 1 days); // feed now stale too
        vault.expire(id);
        assertEq(uint8(_status(id)), uint8(ParableVault.Status.Dead));
    }

    function test_revokeFailureDoesNotBlockDeath() public {
        uint256 id = _register();
        oracle.setRevertOnRevoke(true);
        vm.prank(creatorWallet);
        vault.kill(id);
        assertEq(uint8(_status(id)), uint8(ParableVault.Status.Dead));
        assertFalse(oracle.revoked(node));
        assertEq(vault.totalDead(), 1);
    }

    // ---------------------------------------------------------------- registration

    function test_registerOnlyOperator() public {
        vm.prank(stranger);
        vm.expectRevert(ParableVault.NotOperator.selector);
        vault.registerBot(bot, creatorId, creatorWallet, node, uint64(block.timestamp + 1 days), CASH, MAX_TRADE, MAX_LOSS, 0);
    }

    function test_creatorWalletMismatchReverts() public {
        _register();
        // same creatorId, different wallet
        vm.prank(operator);
        vm.expectRevert(ParableVault.CreatorIdentityMismatch.selector);
        vault.registerBot(bot2, creatorId, stranger, node2, uint64(block.timestamp + 1 days), CASH, MAX_TRADE, MAX_LOSS, 0);
        // same wallet, different creatorId
        vm.prank(operator);
        vm.expectRevert(ParableVault.CreatorIdentityMismatch.selector);
        vault.registerBot(bot2, keccak256("other"), creatorWallet, node2, uint64(block.timestamp + 1 days), CASH, MAX_TRADE, MAX_LOSS, 0);
    }

    function test_duplicateBotAddressReverts() public {
        _register();
        vm.prank(operator);
        vm.expectRevert(ParableVault.BotAlreadyRegistered.selector);
        vault.registerBot(bot, creatorId, creatorWallet, node2, uint64(block.timestamp + 1 days), CASH, MAX_TRADE, MAX_LOSS, 0);
    }

    function test_invalidParamsRevert() public {
        vm.startPrank(operator);
        vm.expectRevert(ParableVault.InvalidParams.selector);
        vault.registerBot(bot, creatorId, creatorWallet, node, uint64(block.timestamp), CASH, MAX_TRADE, MAX_LOSS, 0); // already expired
        vm.expectRevert(ParableVault.InvalidParams.selector);
        vault.registerBot(bot, creatorId, creatorWallet, node, uint64(block.timestamp + 1 days), CASH, MAX_TRADE, 0, 0); // zero loss limit
        vm.stopPrank();
    }

    // ---------------------------------------------------------------- counters

    function test_countersIncludingDeadBots() public {
        bytes32 otherCreator = keccak256("creator-2");
        address otherWallet = makeAddr("otherWallet");
        address bot3 = makeAddr("bot3");

        uint256 a = _register();
        _registerFull(bot2, creatorId, creatorWallet, node2, uint64(block.timestamp + 1 days), MAX_TRADE);
        _registerFull(bot3, otherCreator, otherWallet, keccak256("n3"), uint64(block.timestamp + 1 days), MAX_TRADE);

        assertEq(vault.totalBorn(), 3);
        assertEq(vault.creatorBorn(creatorId), 2);
        assertEq(vault.creatorBorn(otherCreator), 1);
        assertEq(vault.totalDead(), 0);

        vm.prank(creatorWallet);
        vault.kill(a);

        assertEq(vault.totalBorn(), 3); // dead bots still counted as born
        assertEq(vault.totalDead(), 1);
        assertEq(vault.creatorDead(creatorId), 1);
        assertEq(vault.creatorDead(otherCreator), 0);
    }
}
