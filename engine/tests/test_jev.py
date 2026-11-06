"""The Jev brain: one multiple-choice question, probabilities back, trade sized by confidence."""

import pytest

from parable import bot_runner as B
from parable import jev as J

STATE = {"strategy": "momentum", "history": [300_000_000_000, 301_000_000_000], "price": 301_000_000_000,
         "cash_usd": 100_000_000, "eth_wei": 0, "equity_usd": 100_000_000, "max_trade_usd": 20_000_000, "max_loss_bps": 1000}


class Reply:
    def __init__(self, body, status=200):
        self.body, self.status = body, status

    def raise_for_status(self):
        if self.status != 200:
            raise J.httpx.HTTPStatusError("bad", request=None, response=None)

    def json(self):
        return self.body


def test_question_is_one_choice_between_buy_sell_hold():
    q = J.jev_question(STATE)
    assert set(q["questions"]["action"]["criteria"]) == {"buy", "sell", "hold"}
    assert q["questions"]["action"]["type"] == "choice"
    text = q["state"][0]["content"][0]["text"]
    assert "momentum" in text and "decide_trade" not in text  # the tool-call line is for chat models only


def test_trade_size_follows_confidence():
    d = J.to_decision({"choice": "buy", "probabilities": {"buy": 0.87, "sell": 0.03, "hold": 0.10}}, 20_000_000)
    assert d.action == "buy" and d.amount_usd == 17_400_000 and "buy 87%" in d.reason


def test_hold_trades_nothing_and_tiny_confidence_still_trades_one_dollar():
    assert J.to_decision({"choice": "hold", "probabilities": {"hold": 0.9}}, 20_000_000).amount_usd == 0
    assert J.to_decision({"choice": "sell", "probabilities": {"sell": 0.01}}, 20_000_000).amount_usd == 1_000_000


def test_missing_choice_uses_the_most_likely_and_garbage_is_refused():
    assert J.to_decision({"probabilities": {"buy": 0.2, "sell": 0.7, "hold": 0.1}}, 10_000_000).action == "sell"
    with pytest.raises(ValueError):
        J.to_decision({"choice": "moon"}, 10_000_000)


def test_jev_brain_end_to_end_and_fallback(monkeypatch):
    s = B.get_settings()
    monkeypatch.setattr(s, "autoloops_api_key", "k")
    monkeypatch.setattr(s, "jev_models", "gemma-4-31b-it")
    seen = {}

    def post(url, timeout, headers, json):
        seen.update(url=url, auth=headers["Authorization"], model=json["model"])
        return Reply({"answers": {"action": {"type": "choice", "choice": "buy", "probabilities": {"buy": 0.6, "sell": 0.1, "hold": 0.3}}}})
    monkeypatch.setattr(J.httpx, "post", post)
    d = B.decide(STATE, "jev:gemma-4-31b-it")
    assert d.action == "buy" and d.amount_usd == 12_000_000
    assert seen == {"url": J.JEV_URL, "auth": "Bearer k", "model": "gemma-4-31b-it"}
    monkeypatch.setattr(J.httpx, "post", lambda *a, **k: Reply({}, status=500))
    assert B.decide(STATE, "jev:gemma-4-31b-it").reason.startswith(B.FALLBACK_TAG)  # down -> the rule decides


def test_jev_is_listed_but_not_ready_without_a_key(monkeypatch):
    monkeypatch.setattr(B.get_settings(), "autoloops_api_key", "")
    assert B.available_brains().get("jev:gemma-4-31b-it") is False
