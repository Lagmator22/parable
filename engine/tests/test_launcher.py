"""Launcher tests using the in-memory fake chain (no network, no money)."""

import time
from types import SimpleNamespace

import pytest

from parable.fake_chain import FakeRunner, fake_backends
from parable.launcher import LaunchError, ApprovalDenied, ApprovalPending, Launcher
from parable.models import BotRules
from parable.world_pass import Approval

RULES = BotRules(strategy="momentum", start_cash_usd=100_000_000, max_trade_usd=20_000_000,
                 max_loss_bps=1000, lease_seconds=3600)


class FakeWorld:
    def __init__(self):
        self.approvals = {}

    def decide(self, pending_id, approved):
        self.approvals[pending_id] = Approval(pending_id=pending_id, subject="human-1", approved=approved,
                                              reason="ok" if approved else "denied", at=int(time.time()))

    def register_pending(self, pending_id):
        pass

    def get_approval(self, pending_id):
        return self.approvals.get(pending_id)


@pytest.fixture
def setup():
    world = FakeWorld()
    backends = fake_backends(world)
    backends.runner = FakeRunner(backends.vault, step_s=0.01)
    lau = Launcher(backends, secret="test-secret-1234567")
    yield lau, world
    for bot in lau.live.values():
        bot.stop.set()


def test_no_approval_means_no_bot(setup):
    lau, world = setup
    pid, claim = lau.start_launch(RULES)
    with pytest.raises(ApprovalPending):
        lau.confirm_launch(pid, claim)
    world.decide(pid, False)
    with pytest.raises(ApprovalDenied):
        lau.confirm_launch(pid, claim)
    assert lau.b.vault.bots == {} and lau.b.arkiv.records == []


def test_approved_launch_writes_every_record(setup):
    lau, world = setup
    pid, claim = lau.start_launch(RULES)
    world.decide(pid, True)
    bot = lau.confirm_launch(pid, claim)
    assert bot.ens_name.startswith("bot-1-") and bot.ens_name.endswith(".parable.eth")
    assert lau.b.vault.bots[bot.bot_id]["status"] == "alive"
    assert lau.b.arkiv.events[0].kind == "birth"
    assert lau.b.ens.is_valid(bot.ens_name, bot.bot_address)
    with pytest.raises(Exception):  # an approval is single-use
        lau.confirm_launch(pid, claim)


def test_bot_trades_and_kill_goes_to_graveyard(setup):
    lau, world = setup
    pid, claim = lau.start_launch(RULES)
    world.decide(pid, True)
    bot = lau.confirm_launch(pid, claim)
    time.sleep(0.2)
    assert any(e.kind == "trade" for e in lau.b.arkiv.events)
    with pytest.raises(LaunchError):
        lau.kill(bot.bot_id, "not-the-owner")  # strangers cannot kill
    lau.kill(bot.bot_id, claim)
    dead = lau.b.arkiv.graveyard(bot.creator_id)
    assert len(dead) == 1 and dead[0].cause == "killed"
    assert not lau.b.ens.is_valid(bot.ens_name, bot.bot_address)
    assert lau.report(bot.creator_id, None).vault_count_matches


def test_check_fails_when_not_over_limit_and_expiry_is_synced(setup):
    lau, world = setup
    pid, claim = lau.start_launch(BotRules(**{**RULES.model_dump(), "lease_seconds": 0}))
    world.decide(pid, True)
    bot = lau.confirm_launch(pid, claim)
    with pytest.raises(Exception, match="NotOverLimit"):
        lau.check(bot.bot_id)
    lau.sync_deaths()  # lease is over, so the poller expires it and records the death
    assert lau.b.arkiv.graveyard(bot.creator_id)[0].cause == "expired"
