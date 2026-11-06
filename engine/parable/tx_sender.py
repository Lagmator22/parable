"""The post office: every blockchain transaction Parable signs goes out through here, one at a time per wallet.

Why: each wallet numbers its transactions 0, 1, 2... (the "nonce"). If two pieces of code (the vault client
and the ENS client) pick a number at the same time, or a load-balanced RPC node answers with an old count,
two transactions get the same number and the node refuses the second one
("replacement transaction underpriced"). So we keep ONE lock per wallet for the whole process, remember
the last number we used, and retry with the next number if a node still says the number is taken.
"""

import logging
import threading

from eth_account import Account

log = logging.getLogger("parable.tx")
RECEIPT_TIMEOUT_S = 180
NONCE_ERRORS = ("replacement transaction underpriced", "nonce too low", "already known")
MAX_TRIES = 3

_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}
_next_nonce: dict[str, int] = {}  # wallet -> the number its next transaction should use


def _lock_for(address: str) -> threading.Lock:
    with _guard:
        return _locks.setdefault(address.lower(), threading.Lock())


def _fees(w3) -> dict:
    """EIP-1559 fees: pay at most 2x the current base fee, plus the node's suggested tip."""
    tip = w3.eth.max_priority_fee
    base = w3.eth.get_block("latest")["baseFeePerGas"]
    return {"maxPriorityFeePerGas": tip, "maxFeePerGas": 2 * base + tip}


def _is_nonce_clash(err: Exception) -> bool:
    text = str(err).lower()
    return any(marker in text for marker in NONCE_ERRORS)


def send(w3, private_key: str, build, timeout: int = RECEIPT_TIMEOUT_S) -> dict:
    """Sign and send one transaction, wait until it is mined, return the receipt.

    `build(base_fields) -> tx dict` makes the transaction from {from, nonce, fees, chainId}; for a contract
    call that is `fn.build_transaction`, which also estimates gas and raises early if the call would revert.
    The wallet's lock is held until the receipt arrives, so the next transaction always sees a fresh count.
    """
    account = Account.from_key(private_key)
    key = account.address.lower()
    with _lock_for(key):
        nonce = max(w3.eth.get_transaction_count(account.address, "pending"), _next_nonce.get(key, 0))
        for attempt in range(1, MAX_TRIES + 1):
            fields = {"from": account.address, "nonce": nonce, "chainId": w3.eth.chain_id, **_fees(w3)}
            signed = account.sign_transaction(build(fields))
            try:
                tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
                break
            except Exception as err:
                if not _is_nonce_clash(err) or attempt == MAX_TRIES:
                    raise
                log.warning("nonce %s already taken for %s, trying the next one", nonce, key[:10])
                nonce += 1
        _next_nonce[key] = nonce + 1
        return w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)


def reset() -> None:
    """Forget remembered nonces (tests)."""
    with _guard:
        _next_nonce.clear()
