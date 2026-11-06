// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

// Tests for EnsV2BadgeOracle using fake ENS contracts (no network): a fake registry that we can set to
// registered / expired / burned, and a fake resolver that returns whatever `addr` we tell it to.
import {Test} from "forge-std/Test.sol";
import {EnsV2BadgeOracle, IEnsV2Registry} from "../src/adapters/EnsV2BadgeOracle.sol";

contract FakeRegistry {
    IEnsV2Registry.State public state;
    address public resolver;
    bool public broken; // simulates ENS being down: every call reverts
    bool public unregistered;

    function set(uint8 status, uint64 expiry, address owner, address resolver_) external {
        state = IEnsV2Registry.State(status, expiry, owner, 1, 2);
        resolver = resolver_;
    }

    function setBroken(bool b) external {
        broken = b;
    }

    function getState(uint256) external view returns (IEnsV2Registry.State memory) {
        require(!broken, "down");
        return state;
    }

    function getResolver(string calldata) external view returns (address) {
        require(!broken, "down");
        return resolver;
    }

    function unregister(uint256) external {
        require(!broken, "down");
        unregistered = true;
    }
}

contract FakeResolver {
    address public addr;
    bool public broken;

    function setAddr(address a) external {
        addr = a;
    }

    function setBroken(bool b) external {
        broken = b;
    }

    function resolve(bytes calldata, bytes calldata) external view returns (bytes memory) {
        require(!broken, "down");
        return abi.encode(addr);
    }
}

contract EnsV2BadgeOracleTest is Test {
    EnsV2BadgeOracle oracle;
    FakeRegistry registry;
    FakeResolver resolver;

    address operator = makeAddr("operator");
    address vault = makeAddr("vault");
    address bot = makeAddr("bot");
    address stranger = makeAddr("stranger");

    string label = "bot-01";
    // DNS wire format of bot-01.parable.eth: each label prefixed by its length, ending with a zero byte.
    bytes dnsName = abi.encodePacked(uint8(6), "bot-01", uint8(7), "parable", uint8(3), "eth", uint8(0));
    bytes32 node;

    function setUp() public {
        vm.warp(1_000_000);
        // namehash("bot-01.parable.eth"): fold the label hashes from the right.
        node = keccak256(abi.encodePacked(
            keccak256(abi.encodePacked(keccak256(abi.encodePacked(bytes32(0), keccak256("eth"))), keccak256("parable"))),
            keccak256("bot-01")
        ));
        oracle = new EnsV2BadgeOracle(operator);
        registry = new FakeRegistry();
        resolver = new FakeResolver();
        resolver.setAddr(bot);
        registry.set(2, uint64(block.timestamp + 1 days), operator, address(resolver));
        vm.startPrank(operator);
        oracle.setVault(vault);
        oracle.bind(node, IEnsV2Registry(address(registry)), label, dnsName, bot);
        vm.stopPrank();
    }

    // ---------------------------------------------------------------- isValid

    function test_validWhenRegisteredUnexpiredAndAddrMatches() public view {
        assertTrue(oracle.isValid(node, bot));
    }

    function test_invalidForWrongBotOrUnboundNode() public view {
        assertFalse(oracle.isValid(node, stranger));
        assertFalse(oracle.isValid(keccak256("other"), bot));
    }

    function test_invalidAfterExpiry() public {
        vm.warp(block.timestamp + 1 days);
        assertFalse(oracle.isValid(node, bot));
    }

    function test_invalidWhenBurnedInEns() public {
        registry.set(0, uint64(block.timestamp), address(0), address(resolver)); // what unregister leaves behind
        assertFalse(oracle.isValid(node, bot));
    }

    function test_invalidWhenAddrRecordPointsElsewhere() public {
        resolver.setAddr(stranger);
        assertFalse(oracle.isValid(node, bot));
    }

    function test_invalidWhenResolverMissing() public {
        registry.set(2, uint64(block.timestamp + 1 days), operator, address(0));
        assertFalse(oracle.isValid(node, bot));
    }

    function test_invalidWhenEnsIsDown() public {
        registry.setBroken(true);
        assertFalse(oracle.isValid(node, bot));
        registry.setBroken(false);
        resolver.setBroken(true);
        assertFalse(oracle.isValid(node, bot));
    }

    // ---------------------------------------------------------------- revoke

    function test_onlyVaultCanRevoke() public {
        vm.prank(stranger);
        vm.expectRevert(EnsV2BadgeOracle.NotVault.selector);
        oracle.revoke(node);
    }

    function test_revokeBurnsEnsNameAndKillsBadge() public {
        vm.prank(vault);
        oracle.revoke(node);
        assertTrue(registry.unregistered());
        assertTrue(oracle.revoked(node));
        assertFalse(oracle.isValid(node, bot));
    }

    function test_revokeStillWorksWhenEnsIsDown() public {
        registry.setBroken(true);
        vm.prank(vault);
        oracle.revoke(node); // must not revert: a bot's death can never be blocked
        assertTrue(oracle.revoked(node));
    }

    // ---------------------------------------------------------------- bind / setVault guards

    function test_bindIsOperatorOnly() public {
        vm.prank(stranger);
        vm.expectRevert(EnsV2BadgeOracle.NotOperator.selector);
        oracle.bind(keccak256("x"), IEnsV2Registry(address(registry)), label, dnsName, bot);
    }

    function test_bindRejectsNameThatDoesNotHashToNode() public {
        vm.prank(operator);
        vm.expectRevert(EnsV2BadgeOracle.BadName.selector);
        oracle.bind(keccak256("wrong-node"), IEnsV2Registry(address(registry)), label, dnsName, bot);
    }

    function test_bindRejectsLabelThatIsNotTheFirstLabel() public {
        bytes32 freshNode = keccak256("some-unbound-node"); // not bound in setUp, so the name check is reached
        vm.prank(operator);
        vm.expectRevert(EnsV2BadgeOracle.BadName.selector);
        oracle.bind(freshNode, IEnsV2Registry(address(registry)), "bot-02", dnsName, bot);
    }

    function test_cannotBindTwice() public {
        vm.prank(operator);
        vm.expectRevert(EnsV2BadgeOracle.AlreadyBound.selector);
        oracle.bind(node, IEnsV2Registry(address(registry)), label, dnsName, bot);
    }

    function test_setVaultIsOneShotAndOperatorOnly() public {
        vm.prank(operator);
        vm.expectRevert(EnsV2BadgeOracle.VaultAlreadySet.selector);
        oracle.setVault(stranger);

        EnsV2BadgeOracle fresh = new EnsV2BadgeOracle(operator);
        vm.prank(stranger);
        vm.expectRevert(EnsV2BadgeOracle.NotOperator.selector);
        fresh.setVault(vault);
    }
}
