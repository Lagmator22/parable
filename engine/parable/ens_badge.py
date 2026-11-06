"""ENSv2 badge for each bot: an expiring, revocable, soulbound subname on Ethereum Sepolia.

The operator owns a parent name (ENS_PARENT_NAME, e.g. parable.eth). Each bot gets `<label>.<parent>`.
Role table and what is verified live: docs/ENS.md. Adapted from Batas (MIT) for ENSv2 in web3.py.
"""

import re

from eth_abi import decode as abi_decode
from eth_abi import encode as abi_encode
from eth_account import Account
from eth_utils import keccak
from web3 import Web3

from parable import tx_sender
from parable.config import Settings, get_settings

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
STATUS_REGISTERED = 2  # registry status: 0 AVAILABLE, 1 RESERVED, 2 REGISTERED
ETH_COIN_TYPE = 60  # ENS coin type for plain Ethereum addresses

# ENSv2 permissions are bit flags. A role's "admin" (who may hand it out) is the role shifted left 128.
ROLE_REGISTRAR = 1 << 0
ROLE_UNREGISTER = 1 << 12
ROLE_SET_SUBREGISTRY = 1 << 20
ROLE_CAN_TRANSFER_ADMIN = (1 << 28) << 128  # needed to move a token; never granted, so badges are soulbound
RESOLVER_ROLE_SET_ADDRESS = 1 << 0
RESOLVER_ROLE_SET_TEXT = 1 << 4

# role | (role << 128) == role * (1 + 2**128): each role plus its admin bit (the right to hand it out).
WITH_ADMIN = 1 + (1 << 128)
REGISTRY_OPERATOR_ROLES = (ROLE_REGISTRAR | ROLE_UNREGISTER) * WITH_ADMIN
RESOLVER_OPERATOR_ROLES = (RESOLVER_ROLE_SET_ADDRESS | RESOLVER_ROLE_SET_TEXT) * WITH_ADMIN

# Minimal ABIs: only the functions we call. Types are written as plain space-separated words.
STATE_TYPES = ["uint8", "uint64", "address", "uint256", "uint256"]  # status, expiry, owner, id, resource
STATE = {"name": "", "type": "tuple", "components": [{"name": f"f{i}", "type": t} for i, t in enumerate(STATE_TYPES)]}


def _fn(name: str, inputs: str = "", outputs: str = "", view: bool = False) -> dict:
    def args(words: str) -> list[dict]:
        return [STATE if w == "state" else {"name": "", "type": w} for w in words.split()]

    state = "view" if view else "nonpayable"
    return {"type": "function", "name": name, "stateMutability": state, "inputs": args(inputs), "outputs": args(outputs)}


REGISTRY_ABI = [
    _fn("getSubregistry", "string", "address", view=True),
    _fn("getResolver", "string", "address", view=True),
    _fn("getState", "uint256", "state", view=True),
    _fn("hasRoles", "uint256 uint256 address", "bool", view=True),
    _fn("register", "string address address address uint256 uint64", "uint256"),
    _fn("unregister", "uint256"),
    _fn("setSubregistry", "uint256 address"),
    _fn("grantRootRoles", "uint256 address", "bool"),
]
RESOLVER_ABI = [
    _fn("resolve", "bytes bytes", "bytes", view=True),
    _fn("setText", "bytes string string"),
    _fn("setAddress", "bytes uint256 bytes"),
    _fn("multicall", "bytes[]", "bytes[]"),
]
FACTORY_ABI = [
    _fn("deployProxy", "address uint256 bytes", "address"),
    _fn("predictProxyAddress", "address uint256", "address", view=True),
]
ORACLE_ABI = [_fn("bind", "bytes32 address string bytes address")]
GRANT = "(address,uint256)[]"  # (account, roleBitmap) pairs handed to a new registry / resolver at creation


class BadgeError(Exception):
    """Anything that stops a badge action."""

def namehash(name: str) -> bytes:
    """ENS name -> 32-byte id. Hash each label from the right, folding into the previous result."""
    node = b"\x00" * 32
    for label in reversed(name.split(".")):
        node = keccak(node + keccak(label.encode()))
    return node


def dns_encode(name: str) -> bytes:
    """'a.eth' -> length-prefixed labels, the format ENSv2 resolvers take."""
    return b"".join(bytes([len(x)]) + x.encode() for x in name.split(".")) + b"\x00"


def label_id(label: str) -> int:
    """A label's registry id is just its hash."""
    return int.from_bytes(keccak(label.encode()), "big")


def _init_call(signature: str, types: list[str], args: list) -> bytes:
    """Calldata for a new proxy's `initialize(...)`: 4-byte function id + encoded arguments."""
    return keccak(signature.encode())[:4] + abi_encode(types, args)


def split_name(ens_name: str) -> tuple[str, str]:
    label, _, parent = ens_name.partition(".")
    if not label or not parent:
        raise BadgeError(f"expected <label>.<parent>, got {ens_name!r}")
    return label, parent


def classify(state: tuple, now: int) -> tuple[bool, str]:
    """Judge a registry `getState` answer. Same rule as EnsV2BadgeOracle.isValid.

    `unregister` clears the owner while a plain expiry keeps it, so the owner field tells them apart.
    """
    status, expiry, owner = state[:3]
    if status != STATUS_REGISTERED and expiry == 0:
        return False, "not registered"
    if owner == ZERO_ADDRESS:
        return False, "revoked (burned)"
    if status != STATUS_REGISTERED or expiry <= now:
        return False, "expired"
    return True, "registered and unexpired"


# The client
class EnsBadge:
    def __init__(self, settings: Settings | None = None, w3: Web3 | None = None):
        self.s = settings or get_settings()
        from parable.vault import make_w3  # same retrying Sepolia connection as the vault client

        self.w3 = w3 or make_w3(self.s.sepolia_rpc_url)
        key = self.s.operator_private_key
        self._account = Account.from_key(key) if key else None

    def _registry(self, address: str):
        return self.w3.eth.contract(address=Web3.to_checksum_address(address), abi=REGISTRY_ABI)

    def _resolver(self, address: str):
        return self.w3.eth.contract(address=Web3.to_checksum_address(address), abi=RESOLVER_ABI)

    @property
    def operator(self) -> str:
        if self._account is None:
            raise BadgeError("OPERATOR_PRIVATE_KEY is not set")
        return self._account.address

    def _now(self) -> int:  # chain time, not laptop time
        return int(self.w3.eth.get_block("latest")["timestamp"])

    def _send(self, fn) -> str:
        """Sign one contract call with the operator key and send it through the shared post office
        (the vault client uses the same one, so the two never pick the same transaction number)."""
        receipt = tx_sender.send(self.w3, self._account.key, fn.build_transaction)
        tx_hash = "0x" + receipt["transactionHash"].hex().removeprefix("0x")
        if receipt["status"] != 1:
            raise BadgeError(f"tx reverted: {tx_hash}")
        return tx_hash

    def registry_for(self, name: str) -> str:
        """Address of the registry that holds the first label of `name`. Walk down from the root."""
        current = Web3.to_checksum_address(self.s.ens_root_registry)
        for label in reversed(name.split(".")[1:]):
            current = self._registry(current).functions.getSubregistry(label).call()
            if current == ZERO_ADDRESS:
                raise BadgeError(f"{label!r} has no subregistry: run setup_parent() first")
        return current

    def _record(self, resolver: str, ens_name: str, signature: str, types: list[str], args: list, out: str):
        """Read one ENS record. ENSv2 resolvers answer through resolve(name, encodedQuestion)."""
        question = keccak(signature.encode())[:4] + abi_encode(types, args)
        answer = self._resolver(resolver).functions.resolve(dns_encode(ens_name), question).call()
        return abi_decode([out], answer)[0]

    def _addr_record(self, resolver: str, ens_name: str) -> str:
        answer = self._record(resolver, ens_name, "addr(bytes32)", ["bytes32"], [namehash(ens_name)], "address")
        return Web3.to_checksum_address(answer)

    def _text_record(self, resolver: str, ens_name: str, key: str) -> str:
        args = [namehash(ens_name), key]
        return self._record(resolver, ens_name, "text(bytes32,string)", ["bytes32", "string"], args, "string")

    # Public API (INTERFACES.md)
    def issue_badge(self, label: str, bot_address: str, expires_at: int, records: dict[str, str]) -> tuple[str, str]:
        """Create `<label>.<parent>`: soulbound, expiring, revocable. Returns (name, node_hex)."""
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label):
            raise BadgeError(f"label must be lowercase a-z, 0-9, '-': {label!r}")
        bot = Web3.to_checksum_address(bot_address)
        if not (self.s.ens_parent_name and self.s.ens_resolver):
            raise BadgeError("ENS_PARENT_NAME and ENS_RESOLVER must be set (run setup_parent() once)")
        if expires_at <= self._now():
            raise BadgeError("expires_at is in the past")
        name = f"{label}.{self.s.ens_parent_name}"
        registry = self.registry_for(name)

        # Owner = operator but role bitmap = 0: nobody holds CAN_TRANSFER, so the badge cannot move.
        # The operator still holds UNREGISTER at the registry root, so it can burn the badge later.
        resolver_address = Web3.to_checksum_address(self.s.ens_resolver)
        register = self._registry(registry).functions.register
        self._send(register(label, self.operator, ZERO_ADDRESS, resolver_address, 0, int(expires_at)))

        # One transaction sets the addr record (the bot) and every text record.
        resolver = self._resolver(resolver_address)
        dns = dns_encode(name)
        calls = [resolver.encode_abi("setAddress", [dns, ETH_COIN_TYPE, bytes.fromhex(bot[2:])])]
        calls += [resolver.encode_abi("setText", [dns, k, str(v)]) for k, v in {"status": "alive", **records}.items()]
        self._send(resolver.functions.multicall([bytes.fromhex(c[2:]) for c in calls]))

        node = namehash(name)
        if self.s.ens_badge_oracle:
            # The vault only knows the node hash, so tell the oracle where to look this badge up.
            oracle = self.w3.eth.contract(address=Web3.to_checksum_address(self.s.ens_badge_oracle), abi=ORACLE_ABI)
            self._send(oracle.functions.bind(node, registry, label, dns, bot))
        return name, "0x" + node.hex()

    def read_badge(self, ens_name: str) -> dict:
        label, _ = split_name(ens_name)
        reg = self._registry(self.registry_for(ens_name))
        state = reg.functions.getState(label_id(label)).call()
        registered, reason = classify(state, self._now())
        _status, expiry, owner, token_id, _resource = state
        resolver = reg.functions.getResolver(label).call()
        left = max(0, expiry - self._now()) if registered else 0
        info = {"registered": registered, "reason": reason, "expiry": expiry, "seconds_left": left, "owner": owner}
        info.update(resolver=resolver, addr=None, texts={}, soulbound=None)
        if owner != ZERO_ADDRESS:
            info["soulbound"] = not reg.functions.hasRoles(token_id, ROLE_CAN_TRANSFER_ADMIN, owner).call()
        if resolver != ZERO_ADDRESS:
            info["addr"] = self._addr_record(resolver, ens_name)
            for key in ("rules", "creator", "born", "status"):
                info["texts"][key] = self._text_record(resolver, ens_name, key)
        return info

    def revoke_badge(self, ens_name: str) -> str:
        """Unregister the subname: burns the token and expires it now. Returns the tx hash."""
        label, _ = split_name(ens_name)
        return self._send(self._registry(self.registry_for(ens_name)).functions.unregister(label_id(label)))

    def is_valid(self, ens_name: str, bot_address: str) -> bool:
        """Registered, not expired, and the `addr` record equals the bot (same as the oracle)."""
        label, _ = split_name(ens_name)
        try:
            reg = self._registry(self.registry_for(ens_name))
            ok, _ = classify(reg.functions.getState(label_id(label)).call(), self._now())
            resolver = reg.functions.getResolver(label).call()
            if not ok or resolver == ZERO_ADDRESS:
                return False
            return self._addr_record(resolver, ens_name).lower() == bot_address.lower()
        except BadgeError:
            return False

    # One-time setup
    def setup_parent(self) -> dict[str, str]:
        """Give the parent name its own subname registry and resolver. Safe to re-run; the operator
        must own the parent name. Returns addresses to put in .env."""
        s, op = self.s, self.operator
        label, _ = split_name(s.ens_parent_name)
        parent_registry = self._registry(self.registry_for(s.ens_parent_name))

        subregistry = parent_registry.functions.getSubregistry(label).call()
        if subregistry == ZERO_ADDRESS:
            if not parent_registry.functions.hasRoles(label_id(label), ROLE_SET_SUBREGISTRY, op).call():
                raise BadgeError(f"{op} does not hold ROLE_SET_SUBREGISTRY on {s.ens_parent_name}: not the owner?")
            init = _init_call(f"initialize({GRANT})", [GRANT], [[(op, REGISTRY_OPERATOR_ROLES)]])
            subregistry = self._deploy_proxy(s.ens_user_registry_impl, f"parable.registry.{s.ens_parent_name}", init)
            self._send(parent_registry.functions.setSubregistry(label_id(label), subregistry))

        resolver = s.ens_resolver
        if not resolver:
            init = _init_call(f"initialize({GRANT},bytes[])", [GRANT, "bytes[]"], [[(op, RESOLVER_OPERATOR_ROLES)], []])
            resolver = self._deploy_proxy(s.ens_resolver_impl, f"parable.resolver.{s.ens_parent_name}", init)

        if s.ens_badge_oracle:
            # Let the oracle burn badges (the vault's revoke path): ROLE_UNREGISTER at the registry root.
            reg, oracle = self._registry(subregistry), Web3.to_checksum_address(s.ens_badge_oracle)
            if not reg.functions.hasRoles(0, ROLE_UNREGISTER, oracle).call():
                self._send(reg.functions.grantRootRoles(ROLE_UNREGISTER, oracle))
        return {"ENS_SUBREGISTRY": subregistry, "ENS_RESOLVER": resolver}

    def _deploy_proxy(self, impl: str, salt_text: str, init: bytes) -> str:
        """Clone `impl` through the ENS factory. Same salt = same address, so re-runs reuse it."""
        factory = self.w3.eth.contract(address=Web3.to_checksum_address(self.s.ens_factory), abi=FACTORY_ABI)
        salt = int.from_bytes(keccak(salt_text.encode()), "big")
        predicted = factory.functions.predictProxyAddress(self.operator, salt).call()
        if not self.w3.eth.get_code(predicted):
            self._send(factory.functions.deployProxy(Web3.to_checksum_address(impl), salt, init))
        return predicted


# Module-level API (INTERFACES.md). Building a client makes no network call, so one per call is fine.
def issue_badge(label: str, bot_address: str, expires_at: int, records: dict[str, str]) -> tuple[str, str]:
    return EnsBadge().issue_badge(label, bot_address, expires_at, records)


def read_badge(ens_name: str) -> dict:
    return EnsBadge().read_badge(ens_name)


def revoke_badge(ens_name: str) -> str:
    return EnsBadge().revoke_badge(ens_name)


def is_valid(ens_name: str, bot_address: str) -> bool:
    return EnsBadge().is_valid(ens_name, bot_address)
