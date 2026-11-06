"""Offline tests for bot_runner.py: clamping, fallbacks, and loop stop (all mocked)."""

import sys
from pathlib import Path
from threading import Event
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parable import bot_runner as B  # noqa: E402
from parable.models import BotRules, TradeDecision  # noqa: E402

PRICE = 3000 * 10**8
STATE = {"strategy": "momentum", "history": [PRICE, PRICE + 10**8], "price": PRICE,
         "cash_usd": 50_000_000, "eth_wei": 0, "equity_usd": 50_000_000,
         "max_trade_usd": 10_000_000, "max_loss_bps": 500}
RULES = BotRules(strategy="momentum", start_cash_usd=50_000_000, max_trade_usd=10_000_000,
                 max_loss_bps=500, lease_seconds=600)


def test_clamp_to_max_trade_and_balance():
    big = TradeDecision(action="buy", amount_usd=99_000_000, reason="x")
    assert B.clamp(big, STATE).amount_usd == 10_000_000
    poor = dict(STATE, cash_usd=3_000_000)
    assert B.clamp(big, poor).amount_usd == 3_000_000


def test_clamp_sell_with_no_eth_becomes_hold():
    sell = TradeDecision(action="sell", amount_usd=5_000_000, reason="x")
    assert B.clamp(sell, STATE).action == "hold"


def test_llm_failure_falls_back_to_rule(monkeypatch):
    def boom(state):
        raise TimeoutError("slow")
    monkeypatch.setattr(B, "llm_decide", boom)
    d = B.decide(STATE)  # rising price -> momentum buys
    assert d.action == "buy" and d.amount_usd == 10_000_000


def test_invalid_llm_output_falls_back(monkeypatch):
    class FakeClient:
        def __init__(self, **kw):
            self.messages = SimpleNamespace(create=lambda **k: SimpleNamespace(
                content=[SimpleNamespace(type="tool_use", input={"action": "moon", "reason": "?"})]))
    monkeypatch.setattr(B.anthropic, "Anthropic", FakeClient)
    assert B.decide(STATE).action == "buy"  # validation error -> rule


def test_valid_llm_output_used(monkeypatch):
    class FakeClient:
        def __init__(self, **kw):
            self.messages = SimpleNamespace(create=lambda **k: SimpleNamespace(
                content=[SimpleNamespace(type="tool_use",
                                         input={"action": "hold", "amount_usd": 0, "reason": "wait"})]))
    monkeypatch.setattr(B.anthropic, "Anthropic", FakeClient)
    assert B.decide(STATE).action == "hold"


def test_yolo_trades_max():
    d = B.rule_decide(dict(STATE, strategy="yolo"))
    assert d.action == "buy" and d.amount_usd == STATE["max_trade_usd"]


def test_loop_stops_on_dead_bot(monkeypatch):
    dead = {"status": "dead", "expiresAt": 2**40, "cashUsd": 0, "ethWei": 0, "maxTradeUsd": 1, "maxLossBps": 1}
    monkeypatch.setattr(B.vault, "get_bot", lambda i: dead)
    monkeypatch.setattr(B.vault, "price", lambda: PRICE)
    monkeypatch.setattr(B.vault, "equity", lambda i: 0)
    events = []
    B.run_bot(1, "key", RULES, Event(), lambda k, d: events.append(k), interval_s=0)
    assert events == ["stopped"]


def test_loop_reports_traded_and_rejected(monkeypatch):
    alive = {"status": "alive", "expiresAt": 2**40, "cashUsd": 50_000_000, "ethWei": 0,
             "maxTradeUsd": 10_000_000, "maxLossBps": 500}
    monkeypatch.setattr(B.vault, "get_bot", lambda i: alive)
    monkeypatch.setattr(B.vault, "price", lambda: PRICE)
    monkeypatch.setattr(B.vault, "equity", lambda i: 50_000_000)
    monkeypatch.setattr(B, "llm_decide", lambda s: TradeDecision(action="buy", amount_usd=1_000_000, reason="t"))
    stop, events, calls = Event(), [], []

    def fake_trade(key, bot_id, buy, amount):
        calls.append(1)
        if len(calls) == 2:
            raise Exception("execution reverted: " + "0x00")
        return "0xabc"

    def report(kind, data):
        events.append(kind)
        if len(events) == 2:
            stop.set()
    monkeypatch.setattr(B.vault, "trade", fake_trade)
    monkeypatch.setattr(B.vault, "decode_revert", lambda e: "OverTradeLimit")
    B.run_bot(1, "key", RULES, stop, report, interval_s=0)
    assert events == ["traded", "rejected"]
