"""Python client for the ParableVault smart contract on Sepolia (web3.py).
Units: USD has 6 decimals, ETH has 18, the Chainlink price has 8. Every write is
signed locally with a private key; the vault checks who signed, so keys matter.
"""

import json
from functools import lru_cache
from pathlib import Path

from web3 import Web3

from parable import tx_sender
from parable.config import get_settings

ABI = json.loads((Path(__file__).parent / "abi" / "ParableVault.json").read_text())
STATUS = ["none", "alive", "dead"]
CAUSE = ["none", "expired", "killed", "loss_limit"]
RECEIPT_TIMEOUT_S = 120


@lru_cache
def _w3() -> Web3:
    return Web3(Web3.HTTPProvider(get_settings().sepolia_rpc_url, request_kwargs={"timeout": 30}))


@lru_cache
def _vault():
    address = Web3.to_checksum_address(get_settings().vault_address)
    return _w3().eth.contract(address=address, abi=ABI)


def to_bytes32(value: str) -> bytes:
    """Accept a 0x..64-hex id as-is; hash any other text (e.g. 'momentum') into 32 bytes."""
    if value.startswith("0x") and len(value) == 66:
        return bytes.fromhex(value[2:])
    return Web3.keccak(text=value)


# ---------------------------------------------------------------- sending transactions

def _send(fn, private_key: str) -> dict:
    """Sign and send one contract call through the shared post office, return the receipt.
    build_transaction also estimates gas, which raises if the vault would revert (so we never pay for a failure)."""
    receipt = tx_sender.send(_w3(), private_key, fn.build_transaction, timeout=RECEIPT_TIMEOUT_S)
    if receipt["status"] != 1:
        raise RuntimeError(f"transaction {_tx_hex(receipt)} reverted on-chain")
    return receipt


def _operator_key() -> str:
    return get_settings().operator_private_key


def _tx_hex(receipt) -> str:
    h = receipt["transactionHash"].hex()
    return h if h.startswith("0x") else "0x" + h


# ---------------------------------------------------------------- vault writes

def register_bot(bot_address: str, creator_id: str, creator_wallet: str, badge_node: str, expires_at: int,
                 start_cash_usd: int, max_trade_usd: int, max_loss_bps: int, strategy_id: str) -> tuple[int, str]:
    """Operator creates the bot's account in the vault. Returns (bot_id, tx_hash)."""
    fn = _vault().functions.registerBot(
        Web3.to_checksum_address(bot_address), to_bytes32(creator_id), Web3.to_checksum_address(creator_wallet),
        to_bytes32(badge_node), expires_at, start_cash_usd, max_trade_usd, max_loss_bps, to_bytes32(strategy_id))
    receipt = _send(fn, _operator_key())
    born = _vault().events.BotBorn().process_receipt(receipt)
    return born[0]["args"]["botId"], _tx_hex(receipt)


def trade(bot_key: str, bot_id: int, buy: bool, amount_usd: int) -> str:
    """The bot itself signs this. buy=True spends cash on ETH, buy=False sells ETH for cash."""
    return _tx_hex(_send(_vault().functions.trade(bot_id, buy, amount_usd), bot_key))


def check_and_revoke(bot_id: int, key: str | None = None) -> str:
    """Anyone can call this: kills the bot if it is past its loss limit."""
    return _tx_hex(_send(_vault().functions.checkAndRevoke(bot_id), key or _operator_key()))


def kill(bot_id: int) -> str:
    return _tx_hex(_send(_vault().functions.kill(bot_id), _operator_key()))


def expire(bot_id: int) -> str:
    return _tx_hex(_send(_vault().functions.expire(bot_id), _operator_key()))


BOT_GAS_WEI = 10**15  # 0.001 test ETH: enough gas for a bot's trades on Sepolia (gas there is very cheap)


def fund_gas(bot_address: str, wei: int = BOT_GAS_WEI) -> str:
    """Send a little Sepolia ETH so the bot's own key can pay gas for its trades."""
    to = Web3.to_checksum_address(bot_address)
    build = lambda fields: {**fields, "to": to, "value": wei, "gas": 21000}  # a plain ETH transfer costs 21000 gas
    return _tx_hex(tx_sender.send(_w3(), _operator_key(), build, timeout=RECEIPT_TIMEOUT_S))


# ---------------------------------------------------------------- vault reads

def equity(bot_id: int) -> int:
    """Bot's total value in USD (6 decimals), cash plus ETH at the oracle price."""
    return _vault().functions.equityUsd(bot_id).call()


def price() -> int:
    """ETH/USD from Chainlink, 8 decimals (so 3000.00 USD is 300000000000)."""
    return _vault().functions.priceView().call()


def total_born() -> int:
    """How many bots the vault has ever registered. Bot ids are 1..total_born."""
    return _vault().functions.totalBorn().call()


def counts(creator_id: str) -> tuple[int, int]:
    """(bots born, bots dead) for one creator, straight from the vault."""
    node = to_bytes32(creator_id)
    return _vault().functions.creatorBorn(node).call(), _vault().functions.creatorDead(node).call()


def struct_to_dict(raw) -> dict:
    """The contract returns an unnamed tuple; label each value with its field name from the ABI."""
    entry = next(e for e in ABI if e.get("name") == "getBot")
    names = [c["name"] for c in entry["outputs"][0]["components"]]
    out = dict(zip(names, raw))
    for key, value in out.items():
        if isinstance(value, bytes):
            out[key] = "0x" + value.hex()
    out["status"] = STATUS[out["status"]]
    out["cause"] = CAUSE[out["cause"]]
    return out


def get_bot(bot_id: int) -> dict:
    return struct_to_dict(_vault().functions.getBot(bot_id).call())


# ---------------------------------------------------------------- explaining reverts

def _error_selectors() -> dict[str, str]:
    """Map each custom error's 4-byte id (like 0x1234abcd) to its name, computed from the ABI."""
    table = {}
    for entry in ABI:
        if entry["type"] == "error":
            types = ",".join(i["type"] for i in entry["inputs"])
            table["0x" + bytes(Web3.keccak(text=f"{entry['name']}({types})")[:4]).hex()] = entry["name"]
    return table


def decode_revert(err: Exception) -> str:
    """Turn a failed call into the contract's error name, e.g. 'OverTradeLimit'."""
    table = _error_selectors()
    text = " ".join(dict.fromkeys([str(err)] + [str(a) for a in err.args]))  # args can repeat the message
    for selector, name in table.items():
        if selector in text.lower():
            return name
    return "UnknownError"  # never echo raw error text: it can contain node URLs or API keys
