"""Offline tests for arkiv_store: a fake in-memory bridge stands in for the Node service.

The fake keeps entities per owner and honours the owner filter, so we can prove that rows
written by anyone but our writer wallet are never returned.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parable import arkiv_store as A  # noqa: E402
from parable.models import BotEvent, BotRecord, BotRules, DeathRecord  # noqa: E402

WRITER = "0x1111111111111111111111111111111111111111"
CREATOR = "0xAbC0000000000000000000000000000000000000000000000000000000000001"


class FakeBridge:
    def __init__(self, writer: str = WRITER):
        self.writer = writer
        self.rows: list[dict] = []
        self.calls: list[tuple[str, dict | None]] = []

    def add(self, schema, attrs, body, owner=None, seconds=100):
        flat = {k: v[1] for k, v in attrs.items()}
        row = {"key": f"0x{len(self.rows) + 1:064x}", "schema": schema, "owner": owner or self.writer,
               "attributes": flat, "body": body, "expiresInSeconds": seconds}
        self.rows.append(row)
        return row

    def call(self, method, path, payload=None):
        self.calls.append((path, payload))
        if path == "/health":
            return {"writer": self.writer, "chainId": 7794095}
        if path == "/entities":
            row = self.add(payload["schema"], payload["attributes"], payload["body"], seconds=payload["expiresInSeconds"])
            return {"key": row["key"], "txHash": "0xabc"}
        if path == "/patch":
            row = next(r for r in self.rows if r["key"] == payload["key"])
            row["attributes"].update({k: v[1] for k, v in payload["attributes"].items()})
            row["body"], row["expiresInSeconds"] = payload["body"], payload["extendSeconds"]
            return {"key": row["key"], "txHash": "0xdef"}
        assert path == "/query"
        want = {k: v[1] for k, v in payload["where"].items()}
        return [r for r in self.rows if r["schema"] == payload["schema"] and r["owner"] == payload["owner"]
                and all(r["attributes"].get(k) == v for k, v in want.items())]


def make_bot(bot_id=1, creator=CREATOR, strategy="momentum") -> BotRecord:
    rules = BotRules(strategy=strategy, start_cash_usd=100, max_trade_usd=20, max_loss_bps=1000, lease_seconds=900)
    return BotRecord(bot_id=bot_id, bot_address="0x" + "33" * 20, creator_id=creator, ens_name=f"bot-{bot_id}.parable.eth",
                     strategy=strategy, rules=rules, status="alive", born_at=1000, born_tx="0x" + "11" * 32)


def make_death(bot_id=1, pnl=-1200) -> DeathRecord:
    return DeathRecord(bot_id=bot_id, cause="loss_limit", final_equity_usd=88, start_cash_usd=100,
                       pnl_bps=pnl, lifetime_s=300, tx_hash="0x" + "22" * 32)


@pytest.fixture
def setup():
    bridge = FakeBridge()
    return bridge, A.ArkivStore(bridge)


def test_put_bot_expires_with_lease_and_reads_back(setup):
    bridge, store = setup
    store.put_bot(make_bot(), 900)
    assert bridge.rows[0]["expiresInSeconds"] == 900
    assert bridge.rows[0]["attributes"]["creator_id"] == CREATOR.lower()
    assert store.bots(creator_id=CREATOR)[0].bot_id == 1
    assert store.bots(status="dead") == []


def test_death_marks_bot_dead_and_fills_graveyard(setup):
    bridge, store = setup
    store.put_bot(make_bot(), 900)
    store.put_death(make_death())
    bot_row = next(r for r in bridge.rows if r["schema"] == A.BOT)
    assert bot_row["attributes"]["status"] == "dead"
    assert bot_row["expiresInSeconds"] == A.DEATH_LIFETIME
    grave = store.graveyard(CREATOR)
    assert [d.bot_id for d in grave] == [1]
    assert next(r for r in bridge.rows if r["schema"] == A.DEATH)["attributes"]["strategy"] == "momentum"


def test_put_death_without_bot_needs_creator_and_strategy(setup):
    _, store = setup
    with pytest.raises(A.ArkivError):
        store.put_death(make_death(bot_id=9))
    store.put_death(make_death(bot_id=9), creator_id=CREATOR, strategy="dca")
    assert store.graveyard(CREATOR)[0].bot_id == 9


def test_event_without_tx_has_no_vault_tx(setup):
    bridge, store = setup
    store.put_event(BotEvent(bot_id=1, kind="rejected", at=5))
    assert "vault_tx" not in bridge.rows[0]["attributes"]


def test_ignores_rows_written_by_other_wallets(setup):
    bridge, store = setup
    bridge.add(A.DEATH, {"bot_id": ["u256", "66"], "creator_id": ["str", CREATOR.lower()]},
               make_death(66).model_dump_json(), owner="0x" + "99" * 20)
    store.put_bot(make_bot(), 900)
    assert store.graveyard(CREATOR) == []
    assert all(p["owner"] == WRITER for path, p in bridge.calls if path == "/query")


def test_fails_closed_without_trusted_writer():
    store = A.ArkivStore(FakeBridge(writer=""))
    with pytest.raises(A.ArkivError):
        store.graveyard(CREATOR)
    with pytest.raises(A.ArkivError):
        store.bots()


def test_configured_writer_skips_health_call():
    bridge = FakeBridge()
    store = A.ArkivStore(bridge, writer="0x" + "77" * 20)
    store.bots()
    assert all(path != "/health" for path, _ in bridge.calls)


def test_report_card_counts_graveyard_and_vault_check(setup):
    _, store = setup
    store.put_bot(make_bot(1), 900)
    store.put_bot(make_bot(2), 900)
    store.put_death(make_death(1, pnl=-1200))
    card = store.report_card(creator_id=CREATOR, vault_count=2)
    assert (card.launched, card.alive, card.dead, card.profitable) == (2, 1, 1, 0)
    assert card.worst_pnl_bps == -1200 and card.vault_count_matches
    assert not store.report_card(creator_id=CREATOR).vault_count_matches


def test_bridge_down_raises_arkiv_error():
    store = A.ArkivStore(A.Bridge("http://127.0.0.1:1"))
    with pytest.raises(A.ArkivError):
        store.bots()


def test_brain_is_stored_and_report_card_filters_by_brain(setup):
    bridge, store = setup
    for bot_id, brain in [(1, "rule"), (2, "gemini"), (3, "gemini")]:
        rules = BotRules(strategy="momentum", start_cash_usd=100, max_trade_usd=10, max_loss_bps=500,
                         lease_seconds=60, brain=brain)
        store.put_bot(make_bot(bot_id).model_copy(update={"rules": rules}), 900)
    store.put_death(make_death(2, pnl=-900))
    store.put_death(make_death(1, pnl=500))
    assert {r["attributes"]["brain"] for r in bridge.rows if r["schema"] == A.DEATH} == {"rule", "gemini"}
    card = store.report_card(brain="gemini")
    assert (card.launched, card.dead, card.profitable, card.worst_pnl_bps) == (2, 1, 0, -900)
    assert card.subject == "brain:gemini"
    assert store.report_card(brain="rule").profitable == 1
    assert store.report_card().launched == 3  # no filter = everyone
    assert store.report_card(brain="gemma").launched == 0


def test_bridge_token_comes_from_settings_not_shell(monkeypatch):
    """The bridge reads its password from .env, so the Python side must too (bug found in the first live run)."""
    from parable import arkiv_store as A
    monkeypatch.delenv("ARKIV_BRIDGE_TOKEN", raising=False)
    monkeypatch.setattr(A, "get_settings", lambda: type("S", (), {"arkiv_bridge_token": "from-dotenv-123456"})())
    assert A.Bridge("http://127.0.0.1:1").token == "from-dotenv-123456"
