"""Offline tests for bot_runner.py: clamping, fallbacks, and loop stop (all mocked)."""

import sys
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

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
    monkeypatch.setattr(B, "claude_decide", boom)
    monkeypatch.setattr(B.get_settings(), "anthropic_api_key", "k")
    d = B.decide(STATE, "claude")  # rising price -> momentum buys
    assert d.action == "buy" and d.amount_usd == 10_000_000


def test_invalid_llm_output_falls_back(monkeypatch):
    class FakeClient:
        def __init__(self, **kw):
            self.messages = SimpleNamespace(create=lambda **k: SimpleNamespace(
                content=[SimpleNamespace(type="tool_use", input={"action": "moon", "reason": "?"})]))
    monkeypatch.setattr(B.anthropic, "Anthropic", FakeClient)
    assert B.decide(STATE, "claude").action == "buy"  # validation error -> rule


def test_valid_llm_output_used(monkeypatch):
    class FakeClient:
        def __init__(self, **kw):
            self.messages = SimpleNamespace(create=lambda **k: SimpleNamespace(
                content=[SimpleNamespace(type="tool_use",
                                         input={"action": "hold", "amount_dollars": 0, "reason": "wait"})]))
    monkeypatch.setattr(B.anthropic, "Anthropic", FakeClient)
    assert B.decide(STATE, "claude").action == "hold"


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
    monkeypatch.setattr(B, "claude_decide", lambda s: TradeDecision(action="buy", amount_usd=1_000_000, reason="t"))
    monkeypatch.setattr(B.get_settings(), "anthropic_api_key", "k")
    rules = RULES.model_copy(update={"brain": "claude"})
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
    B.run_bot(1, "key", rules, stop, report, interval_s=0)
    assert events == ["traded", "rejected"]


# ---------------------------------------------------------------- choosing the brain (edge cases)

def test_claude_is_not_forced_to_use_the_tool(monkeypatch):
    """Haiku 5.5 thinks by default; forcing a tool would be rejected, so we must ask with tool_choice=auto."""
    seen = {}

    class FakeClient:
        def __init__(self, **kw):
            def create(**k):
                seen.update(k)
                return SimpleNamespace(content=[SimpleNamespace(type="tool_use",
                                                                input={"action": "hold", "amount_dollars": 0, "reason": "w"})])
            self.messages = SimpleNamespace(create=create)
    monkeypatch.setattr(B.anthropic, "Anthropic", FakeClient)
    B.claude_decide(STATE)
    assert seen["tool_choice"] == {"type": "auto"} and seen["tools"][0]["strict"] is True


def test_claude_reply_without_tool_call_falls_back(monkeypatch):
    class FakeClient:
        def __init__(self, **kw):
            self.messages = SimpleNamespace(create=lambda **k: SimpleNamespace(
                content=[SimpleNamespace(type="text", text="I think you should buy")]))
    monkeypatch.setattr(B.anthropic, "Anthropic", FakeClient)
    assert B.decide(STATE, "claude").action == "buy"  # no tool call -> rule


# ---------------------------------------------------------------- the brain registry

class FakeHttp:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": self.content}}]}


HOLD = '{"action":"hold","amount_dollars":0,"reason":"calm"}'


@pytest.fixture
def configured(monkeypatch):
    """Every brain is set up, with fake keys and models; returns the list of HTTP calls the brains make."""
    s = B.get_settings()
    for name, value in dict(anthropic_api_key="k-claude", gemini_api_key="k-google", gemini_models="gem-a, gem-b",
                            gemma_models="gemma-x", local_llm_base_url="http://local:1/v1",
                            local_llm_model="llama-x").items():
        monkeypatch.setattr(s, name, value)
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "model": json["model"]})
        return FakeHttp(HOLD)
    monkeypatch.setattr(B.httpx, "post", fake_post)
    return calls


def test_rule_brain_never_calls_any_ai(monkeypatch):
    def must_not_run(*a, **k):
        raise AssertionError("AI was called in free rule mode")
    monkeypatch.setattr(B.httpx, "post", must_not_run)
    monkeypatch.setattr(B.anthropic, "Anthropic", must_not_run)
    d = B.decide(STATE, "rule")
    assert d.action == "buy" and not d.reason.startswith(B.FALLBACK_TAG)


@pytest.mark.parametrize("brain,url,model,key", [
    ("gemini:gem-a", B.GOOGLE_BASE + "/chat/completions", "gem-a", "k-google"),
    ("gemini:gem-b", B.GOOGLE_BASE + "/chat/completions", "gem-b", "k-google"),
    ("gemma:gemma-x", B.GOOGLE_BASE + "/chat/completions", "gemma-x", "k-google"),
    ("local", "http://local:1/v1/chat/completions", "llama-x", None),
])
def test_each_brain_calls_its_own_endpoint_and_model(configured, brain, url, model, key):
    assert B.decide(STATE, brain).action == "hold"
    call = configured[0]
    assert (call["url"], call["model"]) == (url, model)
    assert call["headers"] == ({"Authorization": f"Bearer {key}"} if key else {})  # local sends no key


def test_claude_brain_uses_claude_not_http(configured, monkeypatch):
    class FakeClient:
        def __init__(self, **kw):
            self.messages = SimpleNamespace(create=lambda **k: SimpleNamespace(
                content=[SimpleNamespace(type="tool_use", input={"action": "hold", "amount_dollars": 0, "reason": "c"})]))
    monkeypatch.setattr(B.anthropic, "Anthropic", FakeClient)
    assert B.decide(STATE, "claude").reason == "c" and configured == []


@pytest.mark.parametrize("brain", ["claude", "gemini:gem-a", "gemma:gemma-x", "local", "gemini:not-listed"])
def test_unconfigured_brain_falls_back_with_tag(monkeypatch, brain):
    s = B.get_settings()
    for name in ("anthropic_api_key", "gemini_api_key", "local_llm_model"):
        monkeypatch.setattr(s, name, "")
    monkeypatch.setattr(s, "gemini_models", "gem-a")
    monkeypatch.setattr(s, "gemma_models", "gemma-x")
    monkeypatch.setattr(B.httpx, "post", lambda *a, **k: pytest.fail("must not call out when unconfigured"))
    d = B.decide(STATE, brain)
    assert d.action == "buy" and d.reason.startswith(B.FALLBACK_TAG)


def test_http_error_falls_back_with_tag(configured, monkeypatch):
    def down(*a, **k):
        raise B.httpx.ConnectError("no internet")
    monkeypatch.setattr(B.httpx, "post", down)
    d = B.decide(STATE, "gemini:gem-a")
    assert d.action == "buy" and d.reason.startswith(B.FALLBACK_TAG)


def test_bad_status_falls_back(configured, monkeypatch):
    class Bad(FakeHttp):
        def raise_for_status(self):
            raise B.httpx.HTTPStatusError("429", request=None, response=None)
    monkeypatch.setattr(B.httpx, "post", lambda *a, **k: Bad(HOLD))
    assert B.decide(STATE, "gemma:gemma-x").reason.startswith(B.FALLBACK_TAG)


@pytest.mark.parametrize("garbage", ["buy everything!!!", "{not json", '{"action":"moon","reason":"?"}'])
def test_garbage_reply_falls_back(configured, monkeypatch, garbage):
    monkeypatch.setattr(B.httpx, "post", lambda *a, **k: FakeHttp(garbage))
    assert B.decide(STATE, "local").reason.startswith(B.FALLBACK_TAG)


def test_reply_without_choices_falls_back(configured, monkeypatch):
    class Empty(FakeHttp):
        def json(self):
            return {"error": "quota"}
    monkeypatch.setattr(B.httpx, "post", lambda *a, **k: Empty(HOLD))
    assert B.decide(STATE, "gemini:gem-a").reason.startswith(B.FALLBACK_TAG)


def test_code_fenced_json_is_accepted(configured, monkeypatch):
    monkeypatch.setattr(B.httpx, "post", lambda *a, **k: FakeHttp("```json\n" + HOLD + "\n```"))
    assert B.decide(STATE, "gemini:gem-a").reason == "calm"


def test_ai_answer_is_still_clamped(configured, monkeypatch):
    big = '{"action":"buy","amount_dollars":999,"reason":"all in"}'
    monkeypatch.setattr(B.httpx, "post", lambda *a, **k: FakeHttp(big))
    assert B.decide(STATE, "gemini:gem-a").amount_usd == STATE["max_trade_usd"]


def test_available_brains_reports_only_true_false(configured):
    avail = B.available_brains()
    assert avail == {"rule": True, "claude": True, "local": True, "gemini:gem-a": True, "gemini:gem-b": True,
                     "gemma:gemma-x": True}
    assert all(isinstance(v, bool) for v in avail.values())


def test_rule_is_always_available_even_with_nothing_set(monkeypatch):
    s = B.get_settings()
    for name in ("anthropic_api_key", "gemini_api_key", "gemini_models", "gemma_models", "local_llm_model"):
        monkeypatch.setattr(s, name, "")
    assert B.available_brains() == {"rule": True, "claude": False, "local": False}


def test_google_models_without_a_key_are_listed_but_unavailable(monkeypatch):
    s = B.get_settings()
    monkeypatch.setattr(s, "gemini_api_key", "")
    monkeypatch.setattr(s, "gemini_models", "a,b")
    monkeypatch.setattr(s, "gemma_models", "")
    avail = B.available_brains()
    assert avail["gemini:a"] is False and avail["gemini:b"] is False


# ---------------------------------------------------------------- units and messy replies

def test_dollars_become_six_decimal_integers():
    d = B.to_decision({"action": "buy", "amount_dollars": 20.5, "reason": "x"})
    assert d.amount_usd == 20_500_000


def test_the_old_gemini_unit_bug_is_now_harmless():
    """Gemini once answered 50.000000 meaning $50. As dollars that is exactly $50, not $0.00005."""
    assert B.to_decision({"action": "buy", "amount_dollars": 50.000000, "reason": "x"}).amount_usd == 50_000_000


@pytest.mark.parametrize("bad", [-5, float("inf"), float("nan"), "lots"])
def test_bad_dollar_amounts_are_rejected(bad):
    with pytest.raises(Exception):
        B.to_decision({"action": "buy", "amount_dollars": bad, "reason": "x"})


def test_prompt_shows_plain_dollars_not_raw_integers():
    p = B.build_prompt(STATE)
    assert "$50.0" in p and "$10.0" in p and "50000000" not in p and "5.0%" in p


GEMMA_REPLY = """<thought>
The price rose twice. A sample answer would look like {"action": "hold", "amount_dollars": 0, "reason": "x"}.
Momentum says buy.
</thought>
```json
{"action": "buy", "amount_dollars": 8.25, "reason": "price rising"}
```"""


def test_gemma_thought_block_and_fence_are_stripped():
    assert B.extract_json(GEMMA_REPLY) == {"action": "buy", "amount_dollars": 8.25, "reason": "price rising"}


def test_last_json_object_wins():
    text = 'first {"action":"sell","amount_dollars":1,"reason":"a"} then {"action":"hold","amount_dollars":0,"reason":"b"}'
    assert B.extract_json(text)["reason"] == "b"


def test_unclosed_thought_with_json_after_and_no_json_at_all():
    assert B.extract_json('thinking... {"action":"hold","amount_dollars":0,"reason":"ok"}')["reason"] == "ok"
    with pytest.raises(ValueError):
        B.extract_json("<thought>only thinking</thought> I would buy")


def test_gemma_brain_end_to_end_with_thought_text(configured, monkeypatch):
    monkeypatch.setattr(B.httpx, "post", lambda *a, **k: FakeHttp(GEMMA_REPLY))
    d = B.decide(STATE, "gemma:gemma-x")
    assert (d.action, d.amount_usd, d.reason) == ("buy", 8_250_000, "price rising")


def test_ai_timeout_is_shorter_than_the_loop_interval():
    import inspect
    interval = inspect.signature(B.run_bot).parameters["interval_s"].default
    assert B.LLM_TIMEOUT_S == 30 and interval > B.LLM_TIMEOUT_S


def test_json_prompt_gives_an_example_not_the_schema(configured, monkeypatch):
    """Small Gemini models copied the schema shape ('action': {'type': ...}); a plain example avoids that."""
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["prompt"] = json["messages"][0]["content"]
        return FakeHttp(HOLD)
    monkeypatch.setattr(B.httpx, "post", fake_post)
    B.decide(STATE, "gemini:gem-a")
    assert B.JSON_EXAMPLE in seen["prompt"] and '"type"' not in seen["prompt"]


def test_action_given_as_an_object_is_rejected_not_guessed(configured, monkeypatch):
    bad = '{"action": {"type": "buy"}, "amount_dollars": 20, "reason": "x"}'
    monkeypatch.setattr(B.httpx, "post", lambda *a, **k: FakeHttp(bad))
    assert B.decide(STATE, "gemini:gem-a").reason.startswith(B.FALLBACK_TAG)


def test_flat_oracle_price_adds_signal_ticks_so_momentum_and_dip_buyer_trade(monkeypatch):
    """Sepolia Chainlink updates ~hourly; signal_price adds small ticks when the oracle is flat, while state['price'] stays the oracle price."""
    bot = {"status": "alive", "expiresAt": 2**40, "cashUsd": 50_000_000, "ethWei": 0,
           "maxTradeUsd": 10_000_000, "maxLossBps": 500}
    monkeypatch.setattr(B.vault, "get_bot", lambda i: bot)
    monkeypatch.setattr(B.vault, "price", lambda: PRICE)
    monkeypatch.setattr(B.vault, "equity", lambda i: 50_000_000)
    history = []
    state, _ = B.read_state(1, RULES, history)
    assert state["price"] == PRICE  # the vault still trades at the real Chainlink price
    assert len(set(history)) == 3  # seeded on tick 1 so bots trade immediately at birth
    assert B.rule_decide(state).action == "buy"
    assert B.rule_decide({**state, "strategy": "dip_buyer"}).action == "buy"
    # When the real Chainlink price moves, signal_price uses it directly.
    assert B.signal_price(PRICE + 50 * 10**8, history) == PRICE + 50 * 10**8


def test_redact_removes_rpc_urls_from_logged_errors():
    from parable.bot_runner import redact

    out = redact(RuntimeError("HTTPError for https://sepolia.example.io/v3/SECRETKEY123 timed out"))
    assert "SECRETKEY123" not in out and out.startswith("RuntimeError: ")
