"""Offline tests: ArkivStore against an in-memory Node that decodes the real calldata.

The fake decodes every op with eth_abi (so encoding bugs fail here), applies it, and answers
`arkiv_query`-style where clauses (AND of `name = type(value)`), honouring expiry.
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eth_abi import decode as abi_decode  # noqa: E402

from parable import arkiv_store as A  # noqa: E402
from parable.models import BotEvent, BotRecord, BotRules, DeathRecord  # noqa: E402

WRITER = "0x1111111111111111111111111111111111111111"
OTHER = "0x2222222222222222222222222222222222222222"
BOT_ADDR = "0x3333333333333333333333333333333333333333"
CREATOR = "0xAbC0000000000000000000000000000000000000000000000000000000000001"
TYPES = {2: "i32", 3: "u64", 4: "u256", 7: "bytes", 8: "str", 9: "addr"}


class FakeNode:
    def __init__(self, address: str | None = WRITER):
        self.address = address
        self.block = 1000
        self.entities: dict[str, dict] = {}
        self.txs: list[list[tuple[int, bytes]]] = []
        self._n = 0

    def block_number(self) -> int:
        return self.block

    def advance(self, blocks: int) -> None:
        self.block += blocks

    # --- writes: decode the same bytes the chain would receive
    def execute(self, ops):
        calldata = A.encode_execute(ops)
        assert calldata[:4] == A.EXECUTE_SELECTOR
        (decoded,) = abi_decode(["(uint8,bytes)[]"], calldata[4:])
        self.txs.append(list(ops))
        created: list[str] = []
        for tag, data in decoded:
            if tag == A.OP_CREATE:
                (salt, expires_at, min_life, flags, attrs), = abi_decode(
                    [f"(uint128,uint64,uint64,uint8,{A._ATTR_TUPLE})"], data
                )
                names = [a[0] for a in attrs]
                assert names == sorted(names) and len(set(names)) == len(names), "attrs must be strictly sorted"
                self._n += 1
                key = "0x" + f"{self._n:064x}"
                self.entities[key] = {
                    "owner": self.address,
                    "expires": max(expires_at, self.block + min_life),
                    "flags": flags,
                    "attrs": {a[0].rstrip(b"\0").decode(): (a[1], a[2]) for a in attrs},
                }
                created.append(key)
            elif tag == A.OP_PATCH:
                (key, muts), = abi_decode([f"(bytes32,{A._ATTR_TUPLE})"], data)
                e = self.entities["0x" + key.hex()]
                assert not e["flags"] & A.FLAG_READONLY, "patch of read-only entity"
                for m in muts:
                    e["attrs"][m[0].rstrip(b"\0").decode()] = (m[1], m[2])
            elif tag == A.OP_EXTEND:
                (key, exp, min_life), = abi_decode(["(bytes32,uint64,uint64)"], data)
                e = self.entities["0x" + key.hex()]
                new = max(exp, self.block + min_life)
                assert new >= e["expires"], "ExpiryNotExtended"
                e["expires"] = new
        return A.ExecResult(f"0x{len(self.txs):064x}", self.block, created)

    # --- reads
    def query(self, where: str):
        conds = re.findall(r"(\$?[\w.]+) = (str|u256|u64|i32|addr)\(((?:[^')]|'')*'?|[^)]*)\)", where)
        out = []
        for key, e in self.entities.items():
            if e["expires"] <= self.block:
                continue
            row = self._row(key, e)
            if all(self._match(row, e, n, t, v) for n, t, v in conds):
                out.append(A._parse_entity(row))
        return out

    @staticmethod
    def _match(row, e, name, typ, raw):
        if name == "$owner":
            return e["owner"].lower() == raw.lower()
        want = raw[1:-1].replace("''", "'") if typ == "str" else raw
        have = next((a["value"] for a in row["attributes"] if a["name"] == name and a["type"] == typ), None)
        if have is None:
            return False
        if typ == "str":
            return have == want
        if typ in ("u256", "u64"):
            return int(have, 16) == int(want)
        if typ == "i32":
            return have == int(want)
        return have.lower() == want.lower()

    def _row(self, key, e):
        attrs = []
        for name, (tid, val) in e["attrs"].items():
            t = TYPES[tid & 0x7F]
            if t == "str":
                v = val.decode()
            elif t in ("u64", "u256"):
                v = hex(int.from_bytes(val, "big"))
            elif t == "i32":
                n = int.from_bytes(val, "big")
                v = n - 2**256 if n >= 2**255 else n
            elif t == "addr":
                v = "0x" + val[12:].hex()
            else:
                v = "0x" + val.hex()
            attrs.append({"name": name, "type": t, "value": v})
        return {"key": key, "owner": e["owner"], "expiresAt": hex(e["expires"]), "attributes": attrs}


def bot(bot_id=1, creator=CREATOR, strategy="momentum", status="alive") -> BotRecord:
    rules = BotRules(strategy=strategy, start_cash_usd=100_000_000, max_trade_usd=20_000_000, max_loss_bps=1000, lease_seconds=3600)
    return BotRecord(
        bot_id=bot_id, bot_address=BOT_ADDR, creator_id=creator, ens_name=f"bot-{bot_id:02d}.parable.eth",
        strategy=strategy, rules=rules, status=status, born_at=1_700_000_000, born_tx="0xBEEF",
    )


def death(bot_id=1, pnl=-1200, cause="loss_limit") -> DeathRecord:
    return DeathRecord(
        bot_id=bot_id, cause=cause, final_equity_usd=100_000_000 + pnl * 10_000, start_cash_usd=100_000_000,
        pnl_bps=pnl, lifetime_s=600, tx_hash="0xDEAD",
    )


@pytest.fixture
def node() -> FakeNode:
    return FakeNode()


@pytest.fixture
def store(node) -> A.ArkivStore:
    return A.ArkivStore(node)


def test_put_bot_encoding_and_lease_expiry(store, node):
    key = store.put_bot(bot(), lease_seconds=3600)
    e = node.entities[key]
    assert e["expires"] == 1000 + 1800  # 3600 s at 2 s per block
    assert e["flags"] == A.FLAG_PERMISSIONLESS_EXTEND
    found = store.bots(creator_id=CREATOR.lower())
    assert [b.bot_id for b in found] == [1]
    assert found[0].born_tx == "0xBEEF"
    row = node._row(key, e)
    attrs = {a["name"]: (a["type"], a["value"]) for a in row["attributes"]}
    assert attrs["arkiv.schema"] == ("str", "parable.bot")
    assert attrs["creator_id"] == ("str", CREATOR.lower())  # normalised
    assert attrs["vault_tx"] == ("str", "0xbeef")
    assert attrs["bot_id"] == ("u256", hex(1))
    assert attrs["bot_address"] == ("addr", BOT_ADDR)


def test_alive_bot_vanishes_when_lease_expires(store, node):
    store.put_bot(bot(), lease_seconds=3600)
    node.advance(1800)
    assert store.bots(status="alive") == []


def test_death_flips_bot_and_extends_expiry(store, node):
    bot_key = store.put_bot(bot(), lease_seconds=3600)
    death_key = store.put_death(death())
    # one atomic tx: create death + patch bot + extend bot
    assert [op[0] for op in node.txs[-1]] == [A.OP_CREATE, A.OP_PATCH, A.OP_EXTEND]
    assert node.entities[death_key]["flags"] == A.FLAG_READONLY | A.FLAG_PERMISSIONLESS_EXTEND
    assert node.entities[bot_key]["expires"] == 1000 + A.DEATH_LIFETIME_BLOCKS
    node.advance(5000)  # well past the original lease
    assert [b.status for b in store.bots(creator_id=CREATOR)] == ["dead"]
    assert store.bots(status="alive") == []
    g = store.graveyard(CREATOR)
    assert [(d.bot_id, d.pnl_bps, d.cause) for d in g] == [(1, -1200, "loss_limit")]
    assert g[0].tx_hash == "0xDEAD"


def test_negative_pnl_roundtrips_as_i32(store, node):
    key = store.put_bot(bot(), 3600)
    dk = store.put_death(death(pnl=-9999))
    row = node._row(dk, node.entities[dk])
    assert {a["name"]: a["value"] for a in row["attributes"]}["pnl_bps"] == -9999
    assert key != dk


def test_death_after_bot_entity_expired_needs_creator_and_strategy():
    node = FakeNode()
    s = A.ArkivStore(node)
    s.put_bot(bot(), lease_seconds=60)
    node.advance(100)  # lease over, alive entity gone
    s.put_death(death(cause="expired"))  # in-process cache still knows creator/strategy
    assert [d.bot_id for d in s.graveyard(CREATOR)] == [1]

    fresh = A.ArkivStore(node)  # new process: no cache
    with pytest.raises(ValueError, match="creator_id/strategy unknown"):
        fresh.put_death(death(bot_id=2, cause="expired"))
    fresh.put_death(death(bot_id=2, cause="expired"), creator_id=CREATOR, strategy="momentum")
    assert sorted(d.bot_id for d in fresh.graveyard(CREATOR)) == [1, 2]


def test_report_card_counts_graveyard_and_vault_check(store):
    store.put_bot(bot(1), 3600)
    store.put_bot(bot(2), 3600)
    store.put_bot(bot(3, strategy="mean_reversion"), 3600)
    store.put_death(death(1, pnl=-1500))
    store.put_death(death(2, pnl=800, cause="expired"))
    rc = store.report_card(creator_id=CREATOR, vault_count=3)
    assert (rc.launched, rc.alive, rc.dead, rc.profitable) == (3, 1, 2, 1)
    assert rc.worst_pnl_bps == -1500
    assert rc.avg_pnl_bps == pytest.approx(-350.0)
    assert rc.vault_count_matches is True
    assert store.report_card(creator_id=CREATOR, vault_count=4).vault_count_matches is False
    assert store.report_card(creator_id=CREATOR).vault_count_matches is False  # unverified is never a tick
    # per-strategy card
    rc2 = store.report_card(strategy="momentum")
    assert (rc2.subject, rc2.launched, rc2.dead) == ("strategy:momentum", 2, 2)


def test_report_card_counts_deaths_whose_bot_entity_is_gone():
    node = FakeNode()
    s = A.ArkivStore(node)
    s.put_bot(bot(1), 60)
    s.put_death(death(1, cause="expired"))
    # simulate a deleted bot entity: the death record alone must still count
    for k, e in list(node.entities.items()):
        if e["attrs"]["arkiv.schema"][1] == b"parable.bot":
            del node.entities[k]
    rc = s.report_card(creator_id=CREATOR, vault_count=1)
    assert (rc.launched, rc.dead, rc.alive, rc.vault_count_matches) == (1, 1, 0, True)


def test_empty_report_card():
    rc = A.ArkivStore(FakeNode()).report_card()
    assert (rc.launched, rc.worst_pnl_bps, rc.avg_pnl_bps, rc.subject) == (0, 0, 0.0, "all")


def test_records_from_other_wallets_are_ignored():
    node = FakeNode(address=OTHER)  # an attacker writing look-alike records
    A.ArkivStore(node).put_bot(bot(9), 3600)
    A.ArkivStore(node).put_bot(bot(10), 3600)
    node.address = WRITER
    trusted = A.ArkivStore(node, writer=WRITER)
    trusted.put_bot(bot(1), 3600)
    reader = A.ArkivStore(node, writer=WRITER)
    assert [b.bot_id for b in reader.bots()] == [1]
    assert reader.report_card().launched == 1


def test_event_without_tx_and_ordering(store, node):
    store.put_event(BotEvent(bot_id=1, kind="trade", at=20, tx_hash="0xAA", data={"usd": 5}))
    k = store.put_event(BotEvent(bot_id=1, kind="rejected", at=10, tx_hash=None, data={"why": "OverTradeLimit"}))
    store.put_event(BotEvent(bot_id=2, kind="trade", at=5))
    names = {a["name"] for a in node._row(k, node.entities[k])["attributes"]}
    assert "vault_tx" not in names
    assert node.entities[k]["expires"] == 1000 + A.EVENT_LIFETIME_BLOCKS
    evs = store.events(1)
    assert [e.kind for e in evs] == ["rejected", "trade"]
    assert evs[0].data == {"why": "OverTradeLimit"}
    assert [e.at for e in store.events(1, kind="trade")] == [20]


def test_query_escapes_quotes(store):
    store.put_bot(bot(1, strategy="o'brien"), 3600)
    assert store.report_card(strategy="o'brien").launched == 1
    assert A.q_str("o'brien") == "str('o''brien')"


def test_attribute_validation():
    with pytest.raises(ValueError):
        A.S("strategy", "x" * 129).encode()
    with pytest.raises(ValueError):
        A.I32("pnl", 2**31).encode()
    with pytest.raises(ValueError):
        A.create_op([A.S("a", "b")], A.MAX_LIFETIME_BLOCKS + 1, 0)
    name, tid, val = A.I32("pnl", -1).encode()
    assert tid == A.T_I32 | A.INDEXED and val == b"\xff" * 32 and name.startswith(b"pnl\0")
    assert A.BODY(b"x").encode()[1] == A.T_BYTES  # bytes can never be indexed


def test_read_only_store_cannot_write():
    node = A.RpcNode("http://127.0.0.1:1")  # never contacted
    with pytest.raises(A.ArkivError, match="read-only"):
        node.execute([A.create_op([A.S("a", "b")], 10, 0)])
