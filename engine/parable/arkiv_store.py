"""Arkiv records for Parable: bots, events and deaths, plus the queries behind the graveyard.

Why raw JSON-RPC and not the `arkiv-sdk` Python package: the installed SDK (1.0.0b3) speaks the
old arkiv-op-geth protocol (payload + content type, `arkiv_query` with `includeData`). The
Rabdi testnet runs the new protocol (typed attributes, no payload, `arkiv_query` with
`select/limit/offset`, writes via `execute` on 0x4400...0044). The SDK's query call is rejected by
Rabdi ("unknown field `includeData`"), so this module talks to the node directly with web3.py
and eth_abi. See arkiv/friction.md.

Entity model (every entity is a set of typed attributes; indexed ones can be filtered):
  arkiv.schema = parable.bot | parable.event | parable.death   (the "type" of the record)
  filter fields: creator_id, strategy, bot_id, status, cause, kind, vault_tx
  body (bytes, not indexed): the full pydantic record as JSON
"""

from __future__ import annotations

import json
import secrets
import threading
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from eth_abi import encode as abi_encode
from eth_account import Account
from eth_utils import keccak
from web3 import Web3

from .config import get_settings
from .models import BotEvent, BotRecord, DeathRecord, ReportCard

ARKIV_ADDRESS = "0x4400000000000000000000000000000000000044"
EXECUTE_SELECTOR = bytes.fromhex("49650044")  # execute((uint8,bytes)[])
ENTITY_CREATED_TOPIC = "0x" + keccak(text="EntityCreated(bytes32,address,uint64,uint8)").hex()
EXPLORER = "https://rabdi.explorer.arkiv.network"

BLOCK_SECONDS = 2
MAX_LIFETIME_BLOCKS = 7_884_000  # ~182.5 days, chain limit
EVENT_LIFETIME_BLOCKS = 30 * 86400 // BLOCK_SECONDS  # 30 days
DEATH_LIFETIME_BLOCKS = 7_800_000  # ~180.5 days: as close to "forever" as the chain allows

SCHEMA_BOT = "parable.bot"
SCHEMA_EVENT = "parable.event"
SCHEMA_DEATH = "parable.death"

# creationFlags bits: 1 = read-only (attributes never change), 2 = anyone may extend expiry
FLAG_READONLY = 1
FLAG_PERMISSIONLESS_EXTEND = 2

OP_CREATE, OP_PATCH, OP_EXTEND = 1, 2, 3
INDEXED = 0x80
T_I32, T_U64, T_U256, T_ADDR, T_BYTES, T_STR = 2, 3, 4, 9, 7, 8

PAGE = 100  # node maximum page size


# ---------------------------------------------------------------- attribute encoding


@dataclass(frozen=True)
class Attr:
    name: str
    type_id: int
    value: Any
    indexed: bool = True

    def encode(self) -> tuple[bytes, int, bytes]:
        name = self.name.encode("ascii")
        if len(name) > 32:
            raise ValueError(f"attribute name too long: {self.name}")
        type_id = self.type_id | (INDEXED if self.indexed else 0)
        return name.ljust(32, b"\0"), type_id, _encode_value(self.type_id, self.value)


def _encode_value(type_id: int, v: Any) -> bytes:
    if type_id == T_STR:
        raw = str(v).encode("utf-8")
        if len(raw) > 128:
            raise ValueError(f"str attribute over 128 bytes: {v!r}")
        return raw
    if type_id == T_BYTES:
        return bytes(v)
    if type_id == T_ADDR:
        return bytes(12) + bytes.fromhex(str(v).removeprefix("0x"))
    if type_id == T_I32:
        if not -(2**31) <= int(v) < 2**31:
            raise ValueError(f"i32 out of range: {v}")
        return (int(v) % 2**256).to_bytes(32, "big")  # sign-extended two's complement
    if type_id in (T_U64, T_U256):
        if int(v) < 0:
            raise ValueError(f"unsigned attribute is negative: {v}")
        return int(v).to_bytes(32, "big")
    raise ValueError(f"unsupported type id {type_id}")


def S(name: str, v: str, indexed: bool = True) -> Attr:
    return Attr(name, T_STR, v, indexed)


def U256(name: str, v: int) -> Attr:
    return Attr(name, T_U256, v)


def U64(name: str, v: int) -> Attr:
    return Attr(name, T_U64, v)


def I32(name: str, v: int) -> Attr:
    return Attr(name, T_I32, v)


def ADDR(name: str, v: str) -> Attr:
    return Attr(name, T_ADDR, v)


def BODY(v: bytes) -> Attr:
    return Attr("body", T_BYTES, v, indexed=False)


_ATTR_TUPLE = "(bytes32,uint8,bytes)[]"


def _sorted_attrs(attrs: list[Attr]) -> list[tuple[bytes, int, bytes]]:
    # the chain demands strictly ascending names
    return [a.encode() for a in sorted(attrs, key=lambda a: a.name)]


def create_op(attrs: list[Attr], lifetime_blocks: int, flags: int) -> tuple[int, bytes]:
    if not 1 <= lifetime_blocks <= MAX_LIFETIME_BLOCKS:
        raise ValueError(f"lifetime {lifetime_blocks} blocks outside 1..{MAX_LIFETIME_BLOCKS}")
    salt = secrets.randbits(128)  # random salt: key unpredictable to anyone but the creator
    data = abi_encode(
        [f"(uint128,uint64,uint64,uint8,{_ATTR_TUPLE})"],
        [(salt, 0, lifetime_blocks, flags, _sorted_attrs(attrs))],
    )
    return OP_CREATE, data


def patch_op(key: str, attrs: list[Attr]) -> tuple[int, bytes]:
    data = abi_encode([f"(bytes32,{_ATTR_TUPLE})"], [(bytes.fromhex(key[2:]), _sorted_attrs(attrs))])
    return OP_PATCH, data


def extend_op(key: str, lifetime_blocks: int) -> tuple[int, bytes]:
    data = abi_encode(
        ["(bytes32,uint64,uint64)"], [(bytes.fromhex(key[2:]), 0, lifetime_blocks)]
    )
    return OP_EXTEND, data


def encode_execute(ops: list[tuple[int, bytes]]) -> bytes:
    return EXECUTE_SELECTOR + abi_encode(["(uint8,bytes)[]"], [ops])


# ---------------------------------------------------------------- query literals


def q_str(v: str) -> str:
    return "str('" + v.replace("'", "''") + "')"  # a quote inside is doubled


def q_u256(v: int) -> str:
    return f"u256({int(v)})"


def q_addr(v: str) -> str:
    return f"addr({Web3.to_checksum_address(v)})"


# ---------------------------------------------------------------- low-level node client


@dataclass
class RawEntity:
    key: str
    owner: str | None
    expires_at: int | None
    attrs: dict[str, Any]  # name -> decoded value (bytes attrs come back as bytes)


@dataclass
class ExecResult:
    tx_hash: str
    block: int
    created_keys: list[str]


class Node(Protocol):
    """What the store needs from a node. Tests substitute an in-memory implementation."""

    address: str | None  # writer wallet, None for read-only use

    def query(self, where: str) -> list[RawEntity]: ...
    def execute(self, ops: list[tuple[int, bytes]]) -> ExecResult: ...
    def block_number(self) -> int: ...


class RpcNode:
    """Real Arkiv node over JSON-RPC (reads) and signed `execute` transactions (writes)."""

    def __init__(self, rpc_url: str, private_key: str = "", access_key: str = ""):
        self.url = rpc_url.rstrip("/") + (f"/{access_key}" if access_key else "")
        self.w3 = Web3(Web3.HTTPProvider(self.url, request_kwargs={"timeout": 30}))
        self._account = Account.from_key(private_key) if private_key else None
        self.address = self._account.address if self._account else None
        self._lock = threading.Lock()  # one writer at a time keeps nonces ordered

    # reads -------------------------------------------------------------

    def _rpc(self, method: str, params: list) -> Any:
        body = self.w3.provider.make_request(method, params)
        if "error" in body:
            err = body["error"]
            raise ArkivError(f"{method}: {err.get('message')} {err.get('data', '')}")
        return body["result"]

    def query(self, where: str) -> list[RawEntity]:
        out: list[RawEntity] = []
        offset = 0
        select = {"key": True, "owner": True, "expiresAt": True, "attributes": True}
        while True:
            # ORDER BY $key keeps pages stable (see JSON-RPC docs, "Paginate")
            res = self._rpc(
                "arkiv_query",
                [f"{where} ORDER BY $key ASC", {"select": select, "limit": hex(PAGE), "offset": hex(offset)}],
            )
            rows = res.get("data", [])
            out.extend(_parse_entity(row) for row in rows)
            if len(rows) < PAGE:
                return out
            offset += PAGE

    def block_number(self) -> int:
        return int(self._rpc("eth_blockNumber", []), 16)

    # writes ------------------------------------------------------------

    def simulate(self, ops: list[tuple[int, bytes]], sender: str) -> None:
        """eth_call the batch; raises ArkivError with the node's revert reason. Needs no funds."""
        self._rpc(
            "eth_call",
            [{"from": sender, "to": ARKIV_ADDRESS, "data": "0x" + encode_execute(ops).hex()}, "latest"],
        )

    def execute(self, ops: list[tuple[int, bytes]]) -> ExecResult:
        if self._account is None:
            raise ArkivError("no ARKIV_PRIVATE_KEY configured: this store is read-only")
        data = encode_execute(ops)
        with self._lock:
            tx = {
                "to": ARKIV_ADDRESS,
                "data": "0x" + data.hex(),
                "value": 0,
                "chainId": self.w3.eth.chain_id,
                "nonce": self.w3.eth.get_transaction_count(self._account.address, "pending"),
                "gasPrice": self.w3.eth.gas_price,
            }
            tx["gas"] = int(self.w3.eth.estimate_gas({**tx, "from": self._account.address}) * 1.3)
            signed = self._account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=90)
        if receipt["status"] != 1:
            raise ArkivError(f"execute reverted in tx {tx_hash.hex()}")
        keys = [
            "0x" + log["topics"][1].hex().removeprefix("0x")
            for log in receipt["logs"]
            if log["address"].lower() == ARKIV_ADDRESS and "0x" + log["topics"][0].hex().removeprefix("0x") == ENTITY_CREATED_TOPIC
        ]
        return ExecResult("0x" + tx_hash.hex().removeprefix("0x"), receipt["blockNumber"], keys)


class ArkivError(RuntimeError):
    pass


def _parse_entity(row: dict) -> RawEntity:
    attrs: dict[str, Any] = {}
    for a in row.get("attributes", []):
        t, v = a["type"], a["value"]
        if t in ("u64", "u256"):
            v = int(v, 16)
        elif t == "bytes":
            v = bytes.fromhex(v.removeprefix("0x"))
        attrs[a["name"]] = v
    exp = row.get("expiresAt")
    return RawEntity(row["key"], row.get("owner"), int(exp, 16) if exp else None, attrs)


# ---------------------------------------------------------------- the store


def _norm(s: str) -> str:
    return s.lower() if s.startswith("0x") else s


def _blocks(seconds: int) -> int:
    return max(1, -(-int(seconds) // BLOCK_SECONDS))


class ArkivStore:
    def __init__(self, node: Node, writer: str | None = None):
        """`writer` is the wallet whose records we trust; every query is filtered by $owner."""
        self.node = node
        self.writer = writer or node.address
        # bot_id -> (creator_id, strategy): lets put_death work after the bot entity expired
        self._bot_meta: dict[int, tuple[str, str]] = {}
        self.last_tx: str | None = None  # tx hash of the most recent write, for explorer links

    # -- helpers

    def _where(self, schema: str, **eq: str | int | None) -> str:
        parts = [f"arkiv.schema = {q_str(schema)}"]
        if self.writer:
            parts.append(f"$owner = {q_addr(self.writer)}")
        for name, v in eq.items():
            if v is None:
                continue
            parts.append(f"{name} = {q_u256(v) if name == 'bot_id' else q_str(str(v))}")
        return " AND ".join(parts)

    def _bot_entity(self, bot_id: int) -> RawEntity | None:
        found = self.node.query(self._where(SCHEMA_BOT, bot_id=bot_id))
        return found[0] if found else None

    # -- writes

    def put_bot(self, rec: BotRecord, lease_seconds: int) -> str:
        """Alive bot entity. It expires with the lease (natural Arkiv expiry)."""
        creator = _norm(rec.creator_id)
        attrs = [
            S("arkiv.schema", SCHEMA_BOT),
            U256("bot_id", rec.bot_id),
            ADDR("bot_address", rec.bot_address),
            S("creator_id", creator),
            S("ens_name", rec.ens_name),
            S("strategy", rec.strategy),
            S("status", rec.status),
            U64("born_at", rec.born_at),
            S("vault_tx", _norm(rec.born_tx)),
            BODY(rec.model_dump_json().encode()),
        ]
        res = self.node.execute([create_op(attrs, _blocks(lease_seconds), FLAG_PERMISSIONLESS_EXTEND)])
        self.last_tx = res.tx_hash
        self._bot_meta[rec.bot_id] = (creator, rec.strategy)
        return res.created_keys[0]

    def put_event(self, ev: BotEvent) -> str:
        attrs = [
            S("arkiv.schema", SCHEMA_EVENT),
            U256("bot_id", ev.bot_id),
            S("kind", ev.kind),
            U64("at", ev.at),
            BODY(ev.model_dump_json().encode()),
        ]
        if ev.tx_hash:
            attrs.append(S("vault_tx", _norm(ev.tx_hash)))
        flags = FLAG_READONLY | FLAG_PERMISSIONLESS_EXTEND
        res = self.node.execute([create_op(attrs, EVENT_LIFETIME_BLOCKS, flags)])
        self.last_tx = res.tx_hash
        return res.created_keys[0]

    def put_death(self, d: DeathRecord, creator_id: str | None = None, strategy: str | None = None) -> str:
        """Death entity (read-only, long expiry) and, in the same transaction, flips the bot
        entity to dead and extends it so the whole life stays queryable.

        creator_id/strategy are looked up from the bot entity when omitted. Pass them when a
        bot died by lease expiry: its alive entity may already have expired.
        """
        bot = self._bot_entity(d.bot_id)
        meta = self._bot_meta.get(d.bot_id)
        if bot is not None:
            creator = bot.attrs["creator_id"]
            strat = bot.attrs["strategy"]
        elif creator_id and strategy:
            creator, strat = _norm(creator_id), strategy
        elif meta:
            creator, strat = meta
        else:
            raise ValueError(
                f"bot {d.bot_id}: creator_id/strategy unknown (bot entity gone); pass them to put_death"
            )
        creator = _norm(creator_id) if creator_id else creator
        strat = strategy or strat

        death_attrs = [
            S("arkiv.schema", SCHEMA_DEATH),
            U256("bot_id", d.bot_id),
            S("creator_id", creator),
            S("strategy", strat),
            S("cause", d.cause),
            I32("pnl_bps", d.pnl_bps),
            U64("lifetime_s", d.lifetime_s),
            S("vault_tx", _norm(d.tx_hash)),
            BODY(d.model_dump_json().encode()),
        ]
        ops = [create_op(death_attrs, DEATH_LIFETIME_BLOCKS, FLAG_READONLY | FLAG_PERMISSIONLESS_EXTEND)]
        if bot is not None:
            rec = BotRecord.model_validate_json(bot.attrs["body"]).model_copy(update={"status": "dead"})
            ops.append(patch_op(bot.key, [S("status", "dead"), BODY(rec.model_dump_json().encode())]))
            # extend only if it would not move the expiry earlier (the chain reverts otherwise)
            if bot.expires_at is None or bot.expires_at < self.node.block_number() + DEATH_LIFETIME_BLOCKS:
                ops.append(extend_op(bot.key, DEATH_LIFETIME_BLOCKS))
        res = self.node.execute(ops)
        self.last_tx = res.tx_hash
        return res.created_keys[0]

    # -- reads (these are what dashboards and the report card use)

    def bots(self, creator_id: str | None = None, status: str | None = None) -> list[BotRecord]:
        where = self._where(SCHEMA_BOT, creator_id=_norm(creator_id) if creator_id else None, status=status)
        return [BotRecord.model_validate_json(e.attrs["body"]) for e in self.node.query(where)]

    def _deaths(self, creator_id: str | None = None, strategy: str | None = None) -> list[DeathRecord]:
        where = self._where(
            SCHEMA_DEATH, creator_id=_norm(creator_id) if creator_id else None, strategy=strategy
        )
        return [DeathRecord.model_validate_json(e.attrs["body"]) for e in self.node.query(where)]

    def graveyard(self, creator_id: str) -> list[DeathRecord]:
        return sorted(self._deaths(creator_id=creator_id), key=lambda d: d.bot_id)

    def events(self, bot_id: int, kind: Literal["birth", "trade", "rejected", "death"] | None = None) -> list[BotEvent]:
        where = self._where(SCHEMA_EVENT, kind=kind) + f" AND bot_id = {q_u256(bot_id)}"
        evs = [BotEvent.model_validate_json(e.attrs["body"]) for e in self.node.query(where)]
        return sorted(evs, key=lambda e: e.at)

    def report_card(
        self,
        creator_id: str | None = None,
        strategy: str | None = None,
        vault_count: int | None = None,
    ) -> ReportCard:
        """Computed from ALL bot and death records, graveyard included.

        `vault_count` (optional, deviation from INTERFACES.md) is the vault's own count of bots
        for the same subject. vault_count_matches is False when it is not supplied: we never
        claim a check we did not do.
        """
        c = _norm(creator_id) if creator_id else None
        bot_where = self._where(SCHEMA_BOT, creator_id=c, strategy=strategy)
        bots = [BotRecord.model_validate_json(e.attrs["body"]) for e in self.node.query(bot_where)]
        deaths = self._deaths(creator_id=c, strategy=strategy)

        dead_ids = {d.bot_id for d in deaths} | {b.bot_id for b in bots if b.status == "dead"}
        all_ids = {b.bot_id for b in bots} | dead_ids
        alive_ids = {b.bot_id for b in bots if b.status == "alive"} - dead_ids
        pnls = [d.pnl_bps for d in deaths]

        if creator_id:
            subject = creator_id
        elif strategy:
            subject = f"strategy:{strategy}"
        else:
            subject = "all"
        return ReportCard(
            subject=subject,
            launched=len(all_ids),
            alive=len(alive_ids),
            dead=len(dead_ids),
            profitable=sum(1 for p in pnls if p > 0),
            worst_pnl_bps=min(pnls, default=0),
            avg_pnl_bps=(sum(pnls) / len(pnls)) if pnls else 0.0,
            vault_count_matches=vault_count is not None and vault_count == len(all_ids),
        )


# ---------------------------------------------------------------- module-level API (INTERFACES.md)

_store: ArkivStore | None = None
_store_lock = threading.Lock()


def default_store() -> ArkivStore:
    global _store
    with _store_lock:
        if _store is None:
            s = get_settings()
            node = RpcNode(s.arkiv_rpc_url, s.arkiv_private_key, s.arkiv_access_key)
            _store = ArkivStore(node, writer=node.address or s.arkiv_writer_address or None)
        return _store


def put_bot(rec: BotRecord, lease_seconds: int) -> str:
    return default_store().put_bot(rec, lease_seconds)


def put_event(ev: BotEvent) -> str:
    return default_store().put_event(ev)


def put_death(d: DeathRecord, creator_id: str | None = None, strategy: str | None = None) -> str:
    return default_store().put_death(d, creator_id, strategy)


def graveyard(creator_id: str) -> list[DeathRecord]:
    return default_store().graveyard(creator_id)


def bots(creator_id: str | None = None, status: str | None = None) -> list[BotRecord]:
    return default_store().bots(creator_id, status)


def report_card(
    creator_id: str | None = None, strategy: str | None = None, vault_count: int | None = None
) -> ReportCard:
    return default_store().report_card(creator_id, strategy, vault_count)
