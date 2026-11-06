"""The shared transaction sender: one queue per wallet, never reuse a transaction number (nonce)."""

from types import SimpleNamespace

import pytest
from eth_account import Account

from parable import tx_sender

KEY = "0x" + "11" * 32


class FakeEth:
    def __init__(self, chain_count=5, clashes=0, other_error=None):
        self.chain_count, self.clashes, self.other_error = chain_count, clashes, other_error
        self.sent_nonces = []
        self.chain_id, self.max_priority_fee = 11155111, 1

    def get_transaction_count(self, address, block):
        return self.chain_count  # a lagging node keeps answering the same old number

    def get_block(self, _):
        return {"baseFeePerGas": 10}

    def send_raw_transaction(self, raw):
        if self.other_error:
            raise self.other_error
        if self.clashes:
            self.clashes -= 1
            raise ValueError({"code": 3, "message": "replacement transaction underpriced"})
        self.sent_nonces.append(len(self.sent_nonces))
        return b"\x01" * 32

    def wait_for_transaction_receipt(self, tx_hash, timeout):
        return {"status": 1, "transactionHash": tx_hash}


def build_transfer(fields):
    self_nonces.append(fields["nonce"])
    return {**fields, "to": "0x" + "22" * 20, "value": 1, "gas": 21000}


self_nonces: list[int] = []


@pytest.fixture(autouse=True)
def clean():
    tx_sender.reset()
    self_nonces.clear()


def test_lagging_node_does_not_cause_a_reused_nonce():
    w3 = SimpleNamespace(eth=FakeEth(chain_count=5))
    tx_sender.send(w3, KEY, build_transfer)
    tx_sender.send(w3, KEY, build_transfer)  # node still says 5, but we remember we used 5
    assert self_nonces == [5, 6]


def test_nonce_clash_retries_with_the_next_number():
    w3 = SimpleNamespace(eth=FakeEth(chain_count=3, clashes=1))
    receipt = tx_sender.send(w3, KEY, build_transfer)
    assert receipt["status"] == 1
    assert self_nonces == [3, 4]


def test_gives_up_after_max_tries():
    w3 = SimpleNamespace(eth=FakeEth(clashes=10))
    with pytest.raises(ValueError):
        tx_sender.send(w3, KEY, build_transfer)
    assert len(self_nonces) == tx_sender.MAX_TRIES


def test_other_errors_are_not_retried():
    w3 = SimpleNamespace(eth=FakeEth(other_error=RuntimeError("insufficient funds")))
    with pytest.raises(RuntimeError):
        tx_sender.send(w3, KEY, build_transfer)
    assert len(self_nonces) == 1


def test_one_lock_per_wallet_shared_by_everyone():
    addr = Account.from_key(KEY).address
    assert tx_sender._lock_for(addr) is tx_sender._lock_for(addr.lower())


def test_fees_cap_at_twice_base_plus_tip():
    w3 = SimpleNamespace(eth=FakeEth())
    assert tx_sender._fees(w3) == {"maxPriorityFeePerGas": 1, "maxFeePerGas": 21}
