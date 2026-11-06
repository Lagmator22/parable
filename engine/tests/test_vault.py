"""Offline tests for vault.py: error-name decoding and struct labelling (no network)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from web3 import Web3  # noqa: E402

from parable import vault  # noqa: E402


def selector(sig: str) -> str:
    return "0x" + bytes(Web3.keccak(text=sig)[:4]).hex()


def test_decode_revert_known_errors():
    for name in ["OverTradeLimit", "BadgeInvalid", "StalePrice", "NotOverLimit", "InsufficientBalance"]:
        err = Exception(f"execution reverted: {selector(name + '()')}")
        assert vault.decode_revert(err) == name


def test_decode_revert_reads_error_args():
    err = Exception()
    err.args = (selector("NotBot()"),)
    assert vault.decode_revert(err) == "NotBot"


def test_decode_revert_unknown_returns_text():
    assert vault.decode_revert(Exception("boom")) == "boom"


def test_struct_to_dict_names_and_enums():
    entry = next(e for e in vault.ABI if e.get("name") == "getBot")
    comps = entry["outputs"][0]["components"]
    values = [b"\x01" * 32 if c["type"] == "bytes32" else 2 if c["name"] == "status"
              else 3 if c["name"] == "cause" else 7 for c in comps]
    out = vault.struct_to_dict(tuple(values))
    assert out["status"] == "dead" and out["cause"] == "loss_limit"
    assert out["cashUsd"] == 7 and out["creatorId"] == "0x" + "01" * 32


def test_to_bytes32():
    assert vault.to_bytes32("0x" + "ab" * 32) == bytes.fromhex("ab" * 32)
    assert len(vault.to_bytes32("momentum")) == 32
