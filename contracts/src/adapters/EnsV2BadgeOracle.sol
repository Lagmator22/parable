// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IBadgeOracle} from "../interfaces/IBadgeOracle.sol";

/// Minimal slice of the ENSv2 PermissionedRegistry (ensdomains/contracts-v2). `getState` returns a
/// struct of static fields, which ABI-encodes exactly like these five flat values.
/// Status enum: 0 AVAILABLE, 1 RESERVED, 2 REGISTERED.
interface IEnsV2Registry {
    struct State {
        uint8 status;
        uint64 expiry;
        address latestOwner;
        uint256 tokenId;
        uint256 resource;
    }

    function getState(uint256 anyId) external view returns (State memory);
    function getResolver(string calldata label) external view returns (address);
    function unregister(uint256 anyId) external;
}

/// ENSv2 resolvers answer reads through the ENSIP-10 style `resolve(name, data)` entrypoint.
interface IEnsExtendedResolver {
    function resolve(bytes calldata dnsName, bytes calldata data) external view returns (bytes memory);
}

/// @title EnsV2BadgeOracle
/// @notice IBadgeOracle backed by ENSv2 subnames on Sepolia. A bot badge is valid while its subname is
///         REGISTERED and unexpired in the ENSv2 registry, and its `addr` record equals the bot.
/// @dev The vault only passes a namehash, which cannot be walked back to a registry, so the operator
///      `bind`s each badge once (node -> registry, label, bot). Everything that decides validity is then
///      read live from ENS on every call. Revocation by the vault burns the ENS name itself: this
///      contract holds ROLE_UNREGISTER on the subname registry (granted by the operator at setup).
///      Soulbound-ness is a property of the registry (ROLE_CAN_TRANSFER_ADMIN is never granted).
contract EnsV2BadgeOracle is IBadgeOracle {
    struct Binding {
        IEnsV2Registry registry;
        uint256 labelId; // keccak256(label); the registry strips its own version bits
        address bot;
        string label;
        bytes dnsName; // DNS-wire-encoded full name, used to read records off the resolver
    }

    // addr(bytes32) selector, the profile read for the bot binding.
    bytes4 private constant ADDR_SELECTOR = 0x3b3b57de;
    uint8 private constant STATUS_REGISTERED = 2;

    address public immutable operator;
    address public vault; // set once, after the vault is deployed
    mapping(bytes32 node => Binding) private _bindings;
    mapping(bytes32 node => bool) public revoked;

    event VaultSet(address vault);
    event Bound(bytes32 indexed node, address indexed bot, address registry, string label);
    event Revoked(bytes32 indexed node, bool ensUnregistered);

    error NotOperator();
    error NotVault();
    error VaultAlreadySet();
    error AlreadyBound();
    error BadName();
    error ZeroAddress();

    constructor(address operator_) {
        if (operator_ == address(0)) revert ZeroAddress();
        operator = operator_;
    }

    /// One-shot: deploy order is oracle -> vault(oracle) -> oracle.setVault(vault).
    function setVault(address vault_) external {
        if (msg.sender != operator) revert NotOperator();
        if (vault != address(0)) revert VaultAlreadySet();
        if (vault_ == address(0)) revert ZeroAddress();
        vault = vault_;
        emit VaultSet(vault_);
    }

    /// Register the binding for a freshly issued badge. `dnsName` must hash to `node` and start
    /// with `label`, so the stored data cannot point at a different name than the vault tracks.
    function bind(bytes32 node, IEnsV2Registry registry, string calldata label, bytes calldata dnsName, address bot)
        external
    {
        if (msg.sender != operator) revert NotOperator();
        if (address(registry) == address(0) || bot == address(0)) revert ZeroAddress();
        if (address(_bindings[node].registry) != address(0)) revert AlreadyBound();
        if (_namehash(dnsName, bytes(label)) != node) revert BadName();
        _bindings[node] = Binding(registry, uint256(keccak256(bytes(label))), bot, label, dnsName);
        emit Bound(node, bot, address(registry), label);
    }

    function bindingOf(bytes32 node) external view returns (Binding memory) {
        return _bindings[node];
    }

    /// Valid iff: bound to `bot`, not revoked, REGISTERED + unexpired in ENS, and ENS `addr` == bot.
    /// Any failure to read ENS returns false: no answer from ENS means no trade.
    function isValid(bytes32 node, address bot) external view returns (bool) {
        Binding storage b = _bindings[node];
        if (address(b.registry) == address(0) || bot == address(0) || b.bot != bot || revoked[node]) {
            return false;
        }

        try b.registry.getState(b.labelId) returns (IEnsV2Registry.State memory s) {
            // latestOwner is cleared by unregister and kept by a plain lapse; require both signals.
            if (s.status != STATUS_REGISTERED || s.latestOwner == address(0) || s.expiry <= block.timestamp) {
                return false;
            }
        } catch {
            return false;
        }

        address resolver;
        try b.registry.getResolver(b.label) returns (address r) {
            resolver = r;
        } catch {
            return false;
        }
        if (resolver == address(0)) return false;

        try IEnsExtendedResolver(resolver).resolve(b.dnsName, abi.encodeWithSelector(ADDR_SELECTOR, node)) returns (
            bytes memory ret
        ) {
            if (ret.length != 32) return false;
            return abi.decode(ret, (address)) == bot;
        } catch {
            return false;
        }
    }

    /// Vault-only. Marks the badge dead locally (so isValid is false even if ENS misbehaves) and tries
    /// to burn the ENS name. Never reverts on an ENS failure: the vault's death must not be blockable.
    function revoke(bytes32 node) external {
        if (msg.sender != vault) revert NotVault();
        Binding storage b = _bindings[node];
        revoked[node] = true;
        bool burned;
        if (address(b.registry) != address(0)) {
            try b.registry.unregister(b.labelId) {
                burned = true;
            } catch {}
        }
        emit Revoked(node, burned);
    }

    /// namehash of a DNS-wire name, requiring its first label to equal `firstLabel`.
    function _namehash(bytes calldata dns, bytes memory firstLabel) private pure returns (bytes32) {
        bytes32[16] memory hashes;
        uint256 count;
        uint256 i;
        while (true) {
            if (i >= dns.length) revert BadName();
            uint256 len = uint8(dns[i]);
            if (len == 0) break;
            if (count == 16 || i + 1 + len > dns.length) revert BadName();
            bytes32 h = keccak256(dns[i + 1:i + 1 + len]);
            if (count == 0 && h != keccak256(firstLabel)) revert BadName();
            hashes[count++] = h;
            i += 1 + len;
        }
        if (count == 0 || i + 1 != dns.length) revert BadName();
        bytes32 node;
        while (count > 0) {
            node = keccak256(abi.encodePacked(node, hashes[--count]));
        }
        return node;
    }
}
