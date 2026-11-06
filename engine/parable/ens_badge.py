"""ENSv2 badge for each bot: an expiring, revocable, soulbound subname on Ethereum Sepolia.

Model (details in docs/ENS_NOTES.md):
  - The operator owns a parent name (ENS_PARENT_NAME, e.g. parable.eth). `setup_parent()` gives it a
    UserRegistry as subregistry (operator holds the root roles) and a PermissionedResolver.
  - `issue_badge` registers `<label>.<parent>` with owner = operator and an EMPTY role bitmap, so no one
    (not even the operator) holds ROLE_CAN_TRANSFER_ADMIN on the token: the badge is soulbound. The
    operator keeps ROLE_UNREGISTER at the registry root, so it (or the vault oracle) can burn the badge.
  - The resolver's `addr` record is the bot address; text records carry rules / creator / born / status.
  - Expiry is the registry's own `expiry`; there is nothing to remember to check.

Approach adapted from Batas (MIT, ETHGlobal prior art: agent/ens.mjs `classifyName` / `mandateNameStatus`),
re-implemented in web3.py against the current ensdomains/contracts-v2 interfaces.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from eth_abi import decode as abi_decode
from eth_abi import encode as abi_encode
from eth_account import Account
from eth_utils import keccak
from web3 import Web3

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
STATUS_REGISTERED = 2  # IPermissionedRegistry.Status: 0 AVAILABLE, 1 RESERVED, 2 REGISTERED
ETH_COIN_TYPE = 60

# Defaults: ENSv2 Sepolia deployment, https://docs.ens.domains/learn/deployments (checked on-chain
# 2026-11-06). Sepolia ENSv2 has been reset before: every one is overridable by env.
DEFAULT_ROOT_REGISTRY = "0xb458d6a3a77919449d03e7a6903c26827c1ec43f"
DEFAULT_FACTORY = "0xda70306c98e97ece36f997a21368e53298572991"
DEFAULT_USER_REGISTRY_IMPL = "0x9bd8a88719068d09ecee662f36c0e3856708366a"
DEFAULT_RESOLVER_IMPL = "0x115eb53f0c60696633855f90b138178fb40b2b2c"
DEFAULT_RPC = "https://ethereum-sepolia-rpc.publicnode.com"

# Role bits, ensdomains/contracts-v2 RegistryRolesLib / PermissionedResolverLib. A role's admin is the
# role shifted left by 128.
ROLE_REGISTRAR = 1 << 0
ROLE_UNREGISTER = 1 << 12
ROLE_RENEW = 1 << 16
ROLE_SET_SUBREGISTRY = 1 << 20
ROLE_SET_RESOLVER = 1 << 24
ROLE_CAN_TRANSFER_ADMIN = (1 << 28) << 128  # checked on the token owner; never granted => soulbound
RESOLVER_ROLE_SET_ADDRESS = 1 << 0
RESOLVER_ROLE_SET_TEXT = 1 << 4


def admin_of(role: int) -> int:
    return role << 128


# What the operator holds at the subname registry root: register, burn, renew, and re-delegate those.
REGISTRY_OPERATOR_ROLES = 0
for _r in (ROLE_REGISTRAR, ROLE_UNREGISTER, ROLE_RENEW, ROLE_SET_RESOLVER):
    REGISTRY_OPERATOR_ROLES |= _r | admin_of(_r)
# What the operator holds on the resolver: write addr + text records.
RESOLVER_OPERATOR_ROLES = 0
for _r in (RESOLVER_ROLE_SET_ADDRESS, RESOLVER_ROLE_SET_TEXT):
    RESOLVER_OPERATOR_ROLES |= _r | admin_of(_r)

_STATE = "(uint8,uint64,address,uint256,uint256)"
_GRANTS = "(address,uint256)[]"


def _abi(sig_list: list[str]) -> list[dict]:
    """Tiny ABI builder from 'name(type,..):out' strings, to keep this file readable."""
    out = []
    for sig in sig_list:
        mutability = "view" if sig.startswith("view ") else "nonpayable"
        sig = sig.removeprefix("view ")
        head, _, ret = sig.partition(":")
        name, args = head.split("(", 1)
        out.append(
            {
                "type": "function",
                "name": name,
                "stateMutability": mutability,
                "inputs": _types(args.rstrip(")"), "i"),
                "outputs": _types(ret, "o") if ret else [],
            }
        )
    return out


def _types(s: str, prefix: str) -> list[dict]:
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        if ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        parts.append(cur)
    return [_param(p, f"{prefix}{i}") for i, p in enumerate(parts)]


def _param(t: str, name: str) -> dict:
    if t.endswith("[]"):
        inner = _param(t[:-2], name)
        inner["type"] += "[]"
        return inner
    if t.startswith("("):
        comps = _types(t[1:-1], name + "_")
        return {"name": name, "type": "tuple", "components": comps}
    return {"name": name, "type": t}


REGISTRY_ABI = _abi(
    [
        "view getSubregistry(string):address",
        "view getResolver(string):address",
        f"view getState(uint256):{_STATE}",
        "view hasRoles(uint256,uint256,address):bool",
        "register(string,address,address,address,uint256,uint64):uint256",
        "unregister(uint256)",
        "setSubregistry(uint256,address)",
        "grantRootRoles(uint256,address):bool",
    ]
)
RESOLVER_ABI = _abi(
    [
        "view resolve(bytes,bytes):bytes",
        "setText(bytes,string,string)",
        "setAddress(bytes,uint256,bytes)",
        "multicall(bytes[]):bytes[]",
        f"initialize({_GRANTS},bytes[])",
    ]
)
FACTORY_ABI = _abi(
    [
        "deployProxy(address,uint256,bytes):address",
        "view predictProxyAddress(address,uint256):address",
    ]
)
ORACLE_ABI = _abi(
    [
        "bind(bytes32,address,string,bytes,address)",
        "view isValid(bytes32,address):bool",
        "view revoked(bytes32):bool",
    ]
)
REGISTRY_INIT_SIG = f"initialize({_GRANTS})"


class BadgeError(Exception):
    pass


# ---------------------------------------------------------------- pure helpers


def namehash(name: str) -> bytes:
    node = b"\x00" * 32
    if name:
        for label in reversed(name.split(".")):
            node = keccak(node + keccak(label.encode()))
    return node


def dns_encode(name: str) -> bytes:
    out = b""
    for label in name.split("."):
        raw = label.encode()
        if not 0 < len(raw) < 64:
            raise BadgeError(f"bad label length in {name!r}")
        out += bytes([len(raw)]) + raw
    return out + b"\x00"


def label_id(label: str) -> int:
    """Registry any-id for a label: the labelhash (the registry strips its own version bits)."""
    return int.from_bytes(keccak(label.encode()), "big")


_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def check_label(label: str) -> str:
    if not _LABEL_RE.match(label):
        raise BadgeError(f"label must be lowercase a-z, 0-9, '-': {label!r}")
    return label


def split_name(ens_name: str) -> tuple[str, str]:
    label, _, parent = ens_name.partition(".")
    if not label or not parent:
        raise BadgeError(f"expected <label>.<parent>, got {ens_name!r}")
    return label, parent


def classify(state: tuple, now: int) -> tuple[bool, str]:
    """Judge an ENSv2 registry `getState` answer. Mirrors EnsV2BadgeOracle.isValid's registry half.

    `unregister` clears latestOwner and sets expiry to the revoke moment, while a plain lapse keeps the
    owner, so the two are told apart by the owner field (the trick Batas found).
    """
    status, expiry, owner, _token_id, _resource = state
    if status != STATUS_REGISTERED and expiry == 0:
        return False, "not registered"
    if status == 1:
        return False, "reserved (held by nobody)"
    if owner == ZERO_ADDRESS:
        return False, "revoked (burned)"
    if status != STATUS_REGISTERED or expiry <= now:
        return False, "expired"
    return True, "registered and unexpired"


# ---------------------------------------------------------------- config


@dataclass
class Settings:
    rpc_url: str = field(default_factory=lambda: os.environ.get("SEPOLIA_RPC_URL") or DEFAULT_RPC)
    private_key: str = field(default_factory=lambda: os.environ.get("OPERATOR_PRIVATE_KEY", ""))
    parent_name: str = field(default_factory=lambda: os.environ.get("ENS_PARENT_NAME", ""))
    resolver: str = field(default_factory=lambda: os.environ.get("ENS_RESOLVER", ""))
    oracle: str = field(default_factory=lambda: os.environ.get("ENS_BADGE_ORACLE", ""))
    root_registry: str = field(default_factory=lambda: os.environ.get("ENS_ROOT_REGISTRY") or DEFAULT_ROOT_REGISTRY)
    factory: str = field(default_factory=lambda: os.environ.get("ENS_FACTORY") or DEFAULT_FACTORY)
    registry_impl: str = field(
        default_factory=lambda: os.environ.get("ENS_USER_REGISTRY_IMPL") or DEFAULT_USER_REGISTRY_IMPL
    )
    resolver_impl: str = field(default_factory=lambda: os.environ.get("ENS_RESOLVER_IMPL") or DEFAULT_RESOLVER_IMPL)


def missing_setup(s: Settings) -> list[str]:
    """Human-readable list of what is missing for signing calls (read-only calls need none)."""
    out = []
    if not s.private_key:
        out.append("OPERATOR_PRIVATE_KEY (funded with Sepolia ETH)")
    if not s.parent_name:
        out.append("ENS_PARENT_NAME (an ENSv2 .eth name the operator owns on Sepolia)")
    return out


# ---------------------------------------------------------------- client


class EnsBadge:
    def __init__(self, settings: Settings | None = None, w3: Web3 | None = None):
        self.s = settings or Settings()
        self.w3 = w3 or Web3(Web3.HTTPProvider(self.s.rpc_url, request_kwargs={"timeout": 30}))
        self._account = Account.from_key(self.s.private_key) if self.s.private_key else None

    # -- contract handles (tests replace these with mocks)
    def _registry(self, address: str):
        return self.w3.eth.contract(address=Web3.to_checksum_address(address), abi=REGISTRY_ABI)

    def _resolver(self, address: str):
        return self.w3.eth.contract(address=Web3.to_checksum_address(address), abi=RESOLVER_ABI)

    def _factory(self):
        return self.w3.eth.contract(address=Web3.to_checksum_address(self.s.factory), abi=FACTORY_ABI)

    def _oracle(self):
        return self.w3.eth.contract(address=Web3.to_checksum_address(self.s.oracle), abi=ORACLE_ABI)

    @property
    def operator(self) -> str:
        if self._account is None:
            raise BadgeError("OPERATOR_PRIVATE_KEY is not set")
        return self._account.address

    def _now(self) -> int:
        return int(self.w3.eth.get_block("latest")["timestamp"])

    def _send(self, fn) -> str:
        """Sign and send one contract call as the operator; returns the tx hash, raises on revert."""
        acct = self._account
        if acct is None:
            raise BadgeError("OPERATOR_PRIVATE_KEY is not set")
        base = self.w3.eth.get_block("latest")["baseFeePerGas"]
        tip = self.w3.to_wei(2, "gwei")
        tx = fn.build_transaction(
            {
                "from": acct.address,
                "nonce": self.w3.eth.get_transaction_count(acct.address, "pending"),
                "maxFeePerGas": base * 2 + tip,
                "maxPriorityFeePerGas": tip,
                "chainId": self.w3.eth.chain_id,
            }
        )
        signed = acct.sign_transaction(tx)
        h = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        rcpt = self.w3.eth.wait_for_transaction_receipt(h, timeout=180)
        if rcpt["status"] != 1:
            raise BadgeError(f"tx reverted: {h.hex()}")
        return "0x" + h.hex().removeprefix("0x")

    # -- name -> registry
    def registry_for(self, name: str) -> str:
        """Address of the registry that holds the leftmost label of `name` (walk from the root)."""
        labels = name.split(".")
        cur = Web3.to_checksum_address(self.s.root_registry)
        for label in reversed(labels[1:]):
            nxt = self._registry(cur).functions.getSubregistry(label).call()
            if nxt == ZERO_ADDRESS:
                raise BadgeError(f"{label!r} has no subregistry under the registry at {cur}; run setup_parent()")
            cur = nxt
        return cur

    # -- record reads (ENSv2 resolvers answer through resolve(name, calldata))
    def _resolve(self, resolver: str, ens_name: str, selector_sig: str, types: list[str], args: list, out: str) -> Any:
        data = keccak(selector_sig.encode())[:4] + abi_encode(types, args)
        raw = self._resolver(resolver).functions.resolve(dns_encode(ens_name), data).call()
        return abi_decode([out], raw)[0]

    def _addr_record(self, resolver: str, ens_name: str) -> str:
        raw = self._resolve(resolver, ens_name, "addr(bytes32)", ["bytes32"], [namehash(ens_name)], "address")
        return Web3.to_checksum_address(raw)

    def _text_record(self, resolver: str, ens_name: str, key: str) -> str:
        return self._resolve(
            resolver, ens_name, "text(bytes32,string)", ["bytes32", "string"], [namehash(ens_name), key], "string"
        )

    # -- public API (INTERFACES.md)
    def issue_badge(self, label: str, bot_address: str, expires_at: int, records: dict[str, str]) -> tuple[str, str]:
        """Create `<label>.<parent>`: soulbound, expiring, operator-revocable. Returns (name, node_hex)."""
        check_label(label)
        bot = Web3.to_checksum_address(bot_address)
        parent = self.s.parent_name
        if not parent or not self.s.resolver:
            raise BadgeError("ENS_PARENT_NAME and ENS_RESOLVER must be set (run setup_parent() once)")
        if expires_at <= self._now():
            raise BadgeError("expires_at is in the past")
        name = f"{label}.{parent}"
        registry = self.registry_for(name)

        # Owner = operator, roleBitmap = 0: nobody holds ROLE_CAN_TRANSFER_ADMIN, so the token cannot
        # move. The operator's root roles on the registry still let it unregister (revoke) the name.
        self._send(
            self._registry(registry).functions.register(
                label, self.operator, ZERO_ADDRESS, Web3.to_checksum_address(self.s.resolver), 0, int(expires_at)
            )
        )

        dns = dns_encode(name)
        resolver = self._resolver(self.s.resolver)
        full = {"status": "alive", **records}
        calls = [resolver.encode_abi("setAddress", [dns, ETH_COIN_TYPE, bytes.fromhex(bot[2:])])]
        calls += [resolver.encode_abi("setText", [dns, k, str(v)]) for k, v in full.items()]
        self._send(resolver.functions.multicall([bytes.fromhex(c[2:]) for c in calls]))

        node = namehash(name)
        if self.s.oracle:
            self._send(self._oracle().functions.bind(node, registry, label, dns, bot))
        return name, "0x" + node.hex()

    def read_badge(self, ens_name: str) -> dict:
        label, _ = split_name(ens_name)
        registry = self.registry_for(ens_name)
        reg = self._registry(registry)
        state = reg.functions.getState(label_id(label)).call()
        now = self._now()
        valid_registry, reason = classify(state, now)
        status, expiry, owner, token_id, _resource = state
        resolver = reg.functions.getResolver(label).call()
        info: dict[str, Any] = {
            "name": ens_name,
            "node": "0x" + namehash(ens_name).hex(),
            "registry": registry,
            "status": status,
            "registered": valid_registry,
            "reason": reason,
            "expiry": expiry,
            "seconds_left": max(0, expiry - now) if valid_registry else 0,
            "owner": owner,
            "token_id": token_id,
            "resolver": resolver,
            "addr": None,
            "texts": {},
            "soulbound": None,
        }
        if owner != ZERO_ADDRESS:
            # ROLE_CAN_TRANSFER_ADMIN on the token owner is what would permit a transfer.
            can_transfer = reg.functions.hasRoles(token_id, ROLE_CAN_TRANSFER_ADMIN, owner).call()
            info["soulbound"] = not can_transfer
        if resolver != ZERO_ADDRESS:
            info["addr"] = self._addr_record(resolver, ens_name)
            for key in ("rules", "creator", "born", "status"):
                info["texts"][key] = self._text_record(resolver, ens_name, key)
        return info

    def revoke_badge(self, ens_name: str) -> str:
        """Unregister the subname (burns the token, expires it now). Returns the tx hash."""
        label, _ = split_name(ens_name)
        reg = self._registry(self.registry_for(ens_name))
        return self._send(reg.functions.unregister(label_id(label)))

    def is_valid(self, ens_name: str, bot_address: str) -> bool:
        """Same rule as EnsV2BadgeOracle.isValid: registered, unexpired, and addr record == bot."""
        label, _ = split_name(ens_name)
        try:
            reg = self._registry(self.registry_for(ens_name))
            ok, _ = classify(reg.functions.getState(label_id(label)).call(), self._now())
            if not ok:
                return False
            resolver = reg.functions.getResolver(label).call()
            if resolver == ZERO_ADDRESS:
                return False
            return self._addr_record(resolver, ens_name).lower() == bot_address.lower()
        except BadgeError:
            return False

    # -- one-time setup
    def setup_parent(self) -> dict[str, str]:
        """Give the operator's parent name a UserRegistry subregistry and a PermissionedResolver.

        Idempotent: re-running reuses what already exists. Returns addresses to put in .env.
        Needs the operator to own the parent name (it then holds ROLE_SET_SUBREGISTRY on it).
        """
        parent = self.s.parent_name
        label, grandparent = split_name(parent)
        parent_registry = self._registry(self.registry_for(parent))
        factory = self._factory()
        op = self.operator
        out: dict[str, str] = {}

        sub = parent_registry.functions.getSubregistry(label).call()
        if sub == ZERO_ADDRESS:
            if not parent_registry.functions.hasRoles(label_id(label), ROLE_SET_SUBREGISTRY, op).call():
                raise BadgeError(f"operator {op} does not hold ROLE_SET_SUBREGISTRY on {parent}: is it the owner?")
            init = keccak(REGISTRY_INIT_SIG.encode())[:4] + abi_encode(
                [_GRANTS], [[(op, REGISTRY_OPERATOR_ROLES)]]
            )
            sub = self._deploy_proxy(factory, self.s.registry_impl, f"parable.registry.{parent}", init)
            self._send(parent_registry.functions.setSubregistry(label_id(label), sub))
        out["ENS_SUBREGISTRY"] = sub  # informational: discovered on-chain, not read from env

        if self.s.resolver:
            out["ENS_RESOLVER"] = self.s.resolver
        else:
            res = self._resolver(self.s.resolver_impl)  # only for encoding
            init = bytes.fromhex(
                res.encode_abi("initialize", [[(op, RESOLVER_OPERATOR_ROLES)], []])[2:]
            )
            out["ENS_RESOLVER"] = self._deploy_proxy(factory, self.s.resolver_impl, f"parable.resolver.{parent}", init)

        if self.s.oracle:
            self.grant_oracle_unregister(sub)
        return out

    def grant_oracle_unregister(self, registry: str | None = None) -> str | None:
        """Let the oracle burn badges when the vault revokes: grant it ROLE_UNREGISTER at the registry root."""
        registry = registry or self.registry_for(f"x.{self.s.parent_name}")
        reg = self._registry(registry)
        oracle = Web3.to_checksum_address(self.s.oracle)
        if reg.functions.hasRoles(0, ROLE_UNREGISTER, oracle).call():
            return None
        return self._send(reg.functions.grantRootRoles(ROLE_UNREGISTER, oracle))

    def _deploy_proxy(self, factory, impl: str, salt_seed: str, init: bytes) -> str:
        salt = int.from_bytes(keccak(salt_seed.encode()), "big")
        predicted = factory.functions.predictProxyAddress(self.operator, salt).call()
        if self.w3.eth.get_code(predicted):
            return predicted
        self._send(factory.functions.deployProxy(Web3.to_checksum_address(impl), salt, init))
        return predicted


# ---------------------------------------------------------------- module-level API


_client: EnsBadge | None = None


def _default() -> EnsBadge:
    global _client
    if _client is None:
        _client = EnsBadge()
    return _client


def issue_badge(label: str, bot_address: str, expires_at: int, records: dict[str, str]) -> tuple[str, str]:
    return _default().issue_badge(label, bot_address, expires_at, records)


def read_badge(ens_name: str) -> dict:
    return _default().read_badge(ens_name)


def revoke_badge(ens_name: str) -> str:
    return _default().revoke_badge(ens_name)


def is_valid(ens_name: str, bot_address: str) -> bool:
    return _default().is_valid(ens_name, bot_address)


def now() -> int:
    return int(time.time())
