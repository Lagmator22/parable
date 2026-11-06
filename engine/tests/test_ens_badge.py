"""Unit tests for ens_badge.py with web3 contract calls mocked (no network, no keys)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from eth_abi import decode as abi_decode
from eth_abi import encode as abi_encode
from eth_utils import keccak
from web3 import Web3

from parable import ens_badge as eb

OPERATOR_KEY = "0x" + "11" * 32
BOT = "0x00000000000000000000000000000000000000B0"
REGISTRY = "0x00000000000000000000000000000000000000A1"
RESOLVER = "0x00000000000000000000000000000000000000A2"
ORACLE = "0x00000000000000000000000000000000000000A3"
ZERO = eb.ZERO_ADDRESS
NOW = 1_800_000_000
NAME = "bot-07.parable.eth"


class Call:
    def __init__(self, name, args, ret=None):
        self.name, self.args, self._ret = name, args, ret

    def call(self):
        return self._ret


class FakeContract:
    """Stands in for a web3 contract: `functions.X(*args)` returns a Call that `.call()`s a canned
    answer; encode_abi is the real one so multicall payloads can be decoded."""

    def __init__(self, abi, answers=None):
        self._real = Web3().eth.contract(address=Web3.to_checksum_address(RESOLVER), abi=abi)
        self.answers = answers or {}
        self.functions = SimpleNamespace()
        for item in abi:
            setattr(self.functions, item["name"], self._make(item["name"]))

    def _make(self, name):
        return lambda *args: Call(name, args, self.answers.get(name, lambda *_: None)(*args))

    def encode_abi(self, name, args):
        return self._real.encode_abi(name, args)


def make_client(registry_answers=None, resolver_answers=None, oracle=False):
    s = eb.Settings(
        rpc_url="http://unused",
        private_key=OPERATOR_KEY,
        parent_name="parable.eth",
        resolver=RESOLVER,
        oracle=ORACLE if oracle else "",
    )
    c = eb.EnsBadge(s, w3=SimpleNamespace())
    reg = FakeContract(eb.REGISTRY_ABI, registry_answers)
    res = FakeContract(eb.RESOLVER_ABI, resolver_answers)
    orc = FakeContract(eb.ORACLE_ABI)
    sent: list[Call] = []
    c._registry = lambda _addr: reg
    c._resolver = lambda _addr: res
    c._oracle = lambda: orc
    c.registry_for = lambda _name: REGISTRY
    c._now = lambda: NOW
    c._send = lambda fn: (sent.append(fn), f"0x{len(sent):064x}")[1]
    return c, sent


def resolve_answers(addr=BOT, texts=None):
    texts = texts if texts is not None else {}

    def resolve(_dns, data):
        sel, body = data[:4], data[4:]
        if sel == keccak(b"addr(bytes32)")[:4]:
            return abi_encode(["address"], [Web3.to_checksum_address(addr)])
        if sel == keccak(b"text(bytes32,string)")[:4]:
            _node, key = abi_decode(["bytes32", "string"], body)
            return abi_encode(["string"], [texts.get(key, "")])
        raise AssertionError("unexpected profile")

    return {"resolve": resolve}


# ------------------------------------------------------------------ pure helpers


def test_namehash_vectors():
    assert eb.namehash("") == b"\x00" * 32
    assert eb.namehash("eth").hex() == "93cdeb708b7545dc668eb9280176169d1c33cfd8ed6f04690a0bcc88a93fc4ae"


def test_dns_encode():
    assert eb.dns_encode("a.eth") == b"\x01a\x03eth\x00"


def test_label_validation():
    assert eb.check_label("bot-07") == "bot-07"
    for bad in ("Bot", "a.b", "", "-x", "x_y"):
        with pytest.raises(eb.BadgeError):
            eb.check_label(bad)


def test_soulbound_roles_withheld():
    assert eb.ROLE_CAN_TRANSFER_ADMIN == (1 << 28) << 128
    assert eb.REGISTRY_OPERATOR_ROLES & eb.ROLE_UNREGISTER
    assert eb.REGISTRY_OPERATOR_ROLES & eb.ROLE_CAN_TRANSFER_ADMIN == 0


@pytest.mark.parametrize(
    "state,ok,reason",
    [
        ((2, NOW + 100, BOT, 1, 2), True, "registered and unexpired"),
        ((2, NOW - 1, BOT, 1, 2), False, "expired"),
        ((0, NOW - 5, ZERO, 1, 2), False, "revoked (burned)"),
        ((0, 0, ZERO, 1, 2), False, "not registered"),
        ((1, NOW + 100, ZERO, 1, 2), False, "reserved (held by nobody)"),
    ],
)
def test_classify(state, ok, reason):
    assert eb.classify(state, NOW) == (ok, reason)


# ------------------------------------------------------------------ issue / revoke


def test_issue_badge_registers_soulbound_and_writes_records():
    c, sent = make_client(oracle=True)
    name, node = c.issue_badge("bot-07", BOT, NOW + 3600, {"rules": "r", "creator": "c", "born": "1"})
    assert name == NAME
    assert node == "0x" + eb.namehash(NAME).hex()

    register, multicall, bind = sent
    assert register.name == "register"
    label, owner, subregistry, resolver, roles, expiry = register.args
    assert (label, owner, subregistry) == ("bot-07", c.operator, ZERO)
    assert resolver == Web3.to_checksum_address(RESOLVER)
    assert roles == 0  # no CAN_TRANSFER_ADMIN for anyone => soulbound
    assert expiry == NOW + 3600

    assert multicall.name == "multicall"
    selectors = [call[:4] for call in multicall.args[0]]
    real = Web3().eth.contract(abi=eb.RESOLVER_ABI)
    text_sel = bytes.fromhex(real.encode_abi("setText", [b"", "", ""])[2:10])
    addr_sel = bytes.fromhex(real.encode_abi("setAddress", [b"", 60, b""])[2:10])
    assert selectors.count(addr_sel) == 1
    keys = [
        abi_decode(["bytes", "string", "string"], call[4:])[1:] for call in multicall.args[0] if call[:4] == text_sel
    ]
    assert dict(keys) == {"status": "alive", "rules": "r", "creator": "c", "born": "1"}
    addr_call = next(call for call in multicall.args[0] if call[:4] == addr_sel)
    assert abi_decode(["bytes", "uint256", "bytes"], addr_call[4:])[2] == bytes.fromhex(BOT[2:])

    assert bind.name == "bind"
    assert bind.args[0] == eb.namehash(NAME)
    assert bind.args[3] == eb.dns_encode(NAME)


def test_issue_badge_skips_bind_without_oracle():
    c, sent = make_client(oracle=False)
    c.issue_badge("bot-07", BOT, NOW + 10, {})
    assert [s.name for s in sent] == ["register", "multicall"]


def test_issue_badge_rejects_past_expiry_and_bad_label():
    c, sent = make_client()
    with pytest.raises(eb.BadgeError):
        c.issue_badge("bot-07", BOT, NOW - 1, {})
    with pytest.raises(eb.BadgeError):
        c.issue_badge("Bad Label", BOT, NOW + 10, {})
    assert sent == []


def test_revoke_badge_unregisters_label():
    c, sent = make_client()
    tx = c.revoke_badge(NAME)
    assert tx.startswith("0x")
    assert sent[0].name == "unregister"
    assert sent[0].args == (eb.label_id("bot-07"),)


# ------------------------------------------------------------------ read / is_valid


def registry_answers(state, resolver=RESOLVER, can_transfer=False):
    return {
        "getState": lambda _id: state,
        "getResolver": lambda _label: resolver,
        "hasRoles": lambda *_: can_transfer,
    }


def test_is_valid_true_then_false_cases():
    live = (2, NOW + 100, Web3.to_checksum_address(BOT), 7, 8)
    c, _ = make_client(registry_answers(live), resolve_answers())
    assert c.is_valid(NAME, BOT) is True

    c, _ = make_client(registry_answers(live), resolve_answers(addr="0x" + "22" * 20))
    assert c.is_valid(NAME, BOT) is False  # addr record points elsewhere

    expired = (2, NOW - 1, Web3.to_checksum_address(BOT), 7, 8)
    c, _ = make_client(registry_answers(expired), resolve_answers())
    assert c.is_valid(NAME, BOT) is False

    burned = (0, NOW - 5, ZERO, 7, 8)
    c, _ = make_client(registry_answers(burned), resolve_answers())
    assert c.is_valid(NAME, BOT) is False

    c, _ = make_client(registry_answers(live, resolver=ZERO), resolve_answers())
    assert c.is_valid(NAME, BOT) is False


def test_read_badge_reports_records_and_soulbound():
    live = (2, NOW + 100, Web3.to_checksum_address(BOT), 7, 8)
    texts = {"rules": "buy dips", "creator": "0xabc", "born": "123", "status": "alive"}
    c, _ = make_client(registry_answers(live), resolve_answers(texts=texts))
    info = c.read_badge(NAME)
    assert info["registered"] is True and info["seconds_left"] == 100
    assert info["soulbound"] is True
    assert info["addr"] == Web3.to_checksum_address(BOT)
    assert info["texts"] == texts
    assert info["node"] == "0x" + eb.namehash(NAME).hex()


def test_read_badge_flags_transferable():
    live = (2, NOW + 100, Web3.to_checksum_address(BOT), 7, 8)
    c, _ = make_client(registry_answers(live, can_transfer=True), resolve_answers())
    assert c.read_badge(NAME)["soulbound"] is False


def test_missing_setup_lists_manual_steps():
    s = eb.Settings(private_key="", parent_name="")
    assert len(eb.missing_setup(s)) == 2
