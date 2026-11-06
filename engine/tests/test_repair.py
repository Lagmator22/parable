"""Outbox (retry failed Arkiv writes) and repair (rebuild missing records from the vault)."""

import time

from parable.fake_chain import FakeArkiv
from parable.repair import Outbox, repair

NOW = int(time.time())


def test_outbox_keeps_a_failed_write_and_retries_it():
    box, tries = Outbox(), []

    def flaky():
        tries.append(1)
        if len(tries) == 1:
            raise RuntimeError("arkiv down")

    box.run("bot 1 record", flaky)  # must not raise
    assert len(box.items) == 1
    assert box.flush() == 0
    assert len(tries) == 2


def test_outbox_keeps_retrying_while_still_failing():
    box = Outbox()
    box.run("x", lambda: 1 / 0)
    assert box.flush() == 1
    assert box.flush() == 1


class VaultStub:
    """Just enough of the vault for repair: a few bots by id."""

    def __init__(self, bots):
        self.bots, self.expired = bots, []

    def total_born(self):
        return len(self.bots)

    def get_bot(self, bot_id):
        return dict(self.bots[bot_id])

    def expire(self, bot_id):
        self.expired.append(bot_id)
        self.bots[bot_id].update(status="dead", cause="expired", diedAt=NOW, finalEquityUsd=95_000_000)
        return "0xexpire"


def vault_bot(status="alive", expires_in=600, **extra):
    base = dict(bot="0x" + "33" * 20, creatorId="0x" + "aa" * 32, bornAt=NOW - 100, expiresAt=NOW + expires_in,
                startCashUsd=100_000_000, maxTradeUsd=20_000_000, maxLossBps=1000, status=status,
                cause="none", diedAt=0, finalEquityUsd=0)
    return {**base, **extra}


def test_orphan_bot_gets_a_record_rebuilt_from_the_vault():
    ark = FakeArkiv()
    fixes = repair(VaultStub({1: vault_bot()}), ark)
    assert fixes == ["bot 1: record rebuilt"]
    rec = ark.records[0]
    assert rec.strategy == "unknown" and rec.rules.brain == "unknown" and rec.status == "alive"
    assert ark.event_log[0].kind == "birth"


def test_expired_orphan_is_ended_and_gets_a_grave():
    ark, vault = FakeArkiv(), VaultStub({1: vault_bot(expires_in=-5)})
    fixes = repair(vault, ark)
    assert vault.expired == [1]
    assert "bot 1: grave written" in fixes
    grave = ark.deaths[0][0]
    assert grave.cause == "expired" and grave.pnl_bps == -500


def test_dead_bot_with_record_but_no_grave_gets_one_once():
    ark = FakeArkiv()
    vault = VaultStub({1: vault_bot(status="dead", cause="killed", diedAt=NOW, finalEquityUsd=110_000_000)})
    repair(vault, ark)
    assert len(ark.deaths) == 1 and ark.deaths[0][0].pnl_bps == 1000
    assert repair(vault, ark) == []  # complete now: nothing more to do, no duplicate grave


def test_bots_this_server_runs_are_skipped():
    ark = FakeArkiv()
    assert repair(VaultStub({1: vault_bot()}), ark, skip_ids={1}) == []
    assert ark.records == []
