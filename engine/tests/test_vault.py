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


def test_decode_revert_unknown_hides_raw_text():
    # raw errors can contain node URLs or API keys, so they are never shown to users
    assert vault.decode_revert(Exception("https://rpc.example/KEY123 boom")) == "UnknownError"


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


def test_read_reconnects_once_on_dropped_connection():
    calls = []

    class Call:
        def call(self):
            calls.append(1)
            if len(calls) == 1:
                raise ConnectionResetError(54, "Connection reset by peer")
            return 42

    assert vault._read(Call) == 42
    assert len(calls) == 2


def test_out_of_gas_money_has_a_readable_name():
    from parable import vault as V

    assert V.decode_revert(ValueError({"code": -32000, "message": "insufficient funds for gas * price + value"})) == "BotOutOfGas"


def test_bot_top_up_asks_the_network_for_the_real_gas_cost(monkeypatch):
    """Sending ETH to a brand-new wallet costs ~207k gas on today's Sepolia; a fixed 21000 made every top-up fail."""
    from types import SimpleNamespace
    from parable import vault as V

    seen = {}
    fake_w3 = SimpleNamespace(eth=SimpleNamespace(estimate_gas=lambda tx: 207_391))
    monkeypatch.setattr(V, "_w3", lambda: fake_w3)
    monkeypatch.setattr(V, "_operator_key", lambda: "0x" + "11" * 32)

    def fake_send(w3, key, build, timeout):
        seen.update(build({"nonce": 0}))
        return {"status": 1, "transactionHash": bytes(32)}
    monkeypatch.setattr(V.tx_sender, "send", fake_send)
    V.fund_gas("0x" + "22" * 20)
    assert seen["gas"] == int(207_391 * 1.2) and seen["value"] == V.BOT_GAS_WEI
    assert V.FUND_GAS_FALLBACK > 207_391  # used only if the estimate itself fails