"""The trading bot's brain and loop. Each bot has a chosen brain (rule, claude, gemini, gemma, local) that picks
buy/sell/hold from the price history; if an AI brain is unavailable or answers badly, the built-in rule decides instead.
The vault (not this file) enforces the real limits; clamping here just avoids silly requests.
"""

import json
import time
from threading import Event
from typing import Callable

import anthropic
import httpx

from parable import vault
from parable.config import get_settings
from parable.models import BotRules, TradeDecision

LLM_TIMEOUT_S = 20
DEAD_REASONS = {"NotAlive", "Expired", "BadgeInvalid", "NotRegistered"}
PRESETS = {
    "momentum": "Buy when the price is rising over the recent history, sell when it is falling.",
    "dip_buyer": "Buy when the price dipped below its recent high, sell some after it recovers.",
    "yolo": "Always trade the maximum allowed size, buying if you hold cash, selling if you hold ETH.",
}
DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["buy", "sell", "hold"]},
        "amount_usd": {"type": "integer", "description": "USD with 6 decimals, 1000000 = 1 USD"},
        "reason": {"type": "string"},
    },
    "required": ["action", "amount_usd", "reason"],
    "additionalProperties": False,
}
# strict=True makes Claude's tool input match the schema exactly.
DECISION_TOOL = {"name": "decide_trade", "description": "Decide the next paper trade.",
                 "input_schema": DECISION_SCHEMA, "strict": True}


def eth_value_usd(state: dict) -> int:
    """ETH wei (18 decimals) * price (8 decimals) -> USD (6 decimals): divide by 1e20."""
    return state["eth_wei"] * state["price"] // 10**20


def clamp(decision: TradeDecision, state: dict) -> TradeDecision:
    """Never ask for more than the per-trade limit or than the bot actually has."""
    if decision.action == "hold":
        return decision
    have = state["cash_usd"] if decision.action == "buy" else eth_value_usd(state)
    amount = min(decision.amount_usd, state["max_trade_usd"], have)
    if amount <= 0:
        return TradeDecision(action="hold", reason=f"{decision.reason} (nothing to trade after limits)")
    return TradeDecision(action=decision.action, amount_usd=amount, reason=decision.reason)


def rule_decide(state: dict) -> TradeDecision:
    """Fallback when the LLM fails: tiny, readable rules per strategy. Prices are 8-decimal ints."""
    prices, size = state["history"], state["max_trade_usd"]
    strategy = state["strategy"]
    if strategy == "yolo":
        buy = state["cash_usd"] >= size or eth_value_usd(state) < size
        return TradeDecision(action="buy" if buy else "sell", amount_usd=size, reason="yolo: max size")
    if len(prices) < 2:
        return TradeDecision(action="hold", reason="not enough price history yet")
    last, prev = prices[-1], prices[-2]
    if strategy == "dip_buyer":
        high = max(prices)
        if last < high * 0.999:
            return TradeDecision(action="buy", amount_usd=size, reason="price is below its recent high")
        if last >= high and eth_value_usd(state) > 0:
            return TradeDecision(action="sell", amount_usd=size, reason="price recovered to its high")
    elif last > prev:  # momentum
        return TradeDecision(action="buy", amount_usd=size, reason="price rising")
    elif last < prev:
        return TradeDecision(action="sell", amount_usd=size, reason="price falling")
    return TradeDecision(action="hold", reason="no signal")


def build_prompt(state: dict) -> str:
    prices = [round(p / 1e8, 2) for p in state["history"]]
    return (
        f"You manage a small practice ETH/USD portfolio. Strategy: {state['strategy']}. "
        f"{PRESETS.get(state['strategy'], '')}\n"
        f"ETH price history in USD, oldest first: {prices}\n"
        f"Cash: {state['cash_usd']} (6 decimals). ETH held (wei, 18 decimals): {state['eth_wei']}. "
        f"Total equity: {state['equity_usd']}. Max per trade: {state['max_trade_usd']}. "
        f"Max loss allowed before you are shut down: {state['max_loss_bps']} bps.\n"
        "Call decide_trade. amount_usd uses 6 decimals."
    )


def claude_decide(state: dict) -> TradeDecision:
    """Ask Claude. Thinking is on by default for Haiku 5.5, which rules out FORCING a tool, so we
    offer the tool (auto) and ask for it in the prompt; low effort keeps it fast and cheap."""
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=LLM_TIMEOUT_S)
    reply = client.messages.create(
        model=settings.bot_model, max_tokens=2000, tools=[DECISION_TOOL], tool_choice={"type": "auto"},
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": build_prompt(state)}],
    )
    block = next(b for b in reply.content if b.type == "tool_use")  # no tool call -> error -> rule
    return TradeDecision.model_validate(block.input)


GOOGLE_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"  # Google's OpenAI-style endpoint
FALLBACK_TAG = "[fallback:rule]"  # starts the reason whenever the rule stepped in for a failed AI brain


def openai_style_decide(state: dict, base_url: str, api_key: str, model: str) -> TradeDecision:
    """Any OpenAI-style chat API (Google, Ollama, ...). We ask for JSON only. api_key may be empty (local)."""
    prompt = build_prompt(state).replace("Call decide_trade.", "Reply with ONLY a JSON object matching: "
                                         + json.dumps(DECISION_SCHEMA["properties"]) + ".")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    r = httpx.post(f"{base_url.rstrip('/')}/chat/completions", timeout=LLM_TIMEOUT_S, headers=headers,
                   json={"model": model, "messages": [{"role": "user", "content": prompt}],
                         "response_format": {"type": "json_object"}})
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    return TradeDecision.model_validate_json(text.strip().removeprefix("```json").removesuffix("```").strip())


def gemini_decide(state: dict) -> TradeDecision:
    s = get_settings()
    return openai_style_decide(state, GOOGLE_BASE, s.gemini_api_key, s.gemini_model)


def gemma_decide(state: dict) -> TradeDecision:
    s = get_settings()
    return openai_style_decide(state, GOOGLE_BASE, s.gemini_api_key, s.gemma_model)


def local_decide(state: dict) -> TradeDecision:
    s = get_settings()
    return openai_style_decide(state, s.local_llm_base_url, "", s.local_llm_model)


# The brains a bot can choose: how each decides, and what must be set before it can be used.
BRAINS = {
    "rule": {"decide": rule_decide, "ready": lambda s: True},
    "claude": {"decide": claude_decide, "ready": lambda s: bool(s.anthropic_api_key and s.bot_model)},
    "gemini": {"decide": gemini_decide, "ready": lambda s: bool(s.gemini_api_key and s.gemini_model)},
    "gemma": {"decide": gemma_decide, "ready": lambda s: bool(s.gemini_api_key and s.gemma_model)},
    "local": {"decide": local_decide, "ready": lambda s: bool(s.local_llm_base_url and s.local_llm_model)},
}


def available_brains() -> dict[str, bool]:
    """For the dashboard: is each brain set up? Only true/false, never any key."""
    s = get_settings()
    return {name: bool(b["ready"](s)) for name, b in BRAINS.items()}


def decide(state: dict, brain: str = "rule") -> TradeDecision:
    """Use the chosen brain; an unset-up or failing AI brain falls back to the rule and says so in the reason."""
    entry = BRAINS.get(brain, BRAINS["rule"])
    try:
        if not entry["ready"](get_settings()):
            raise RuntimeError(f"brain {brain} is not configured")
        decision = entry["decide"](state)
    except Exception:
        fallback = rule_decide(state)
        decision = fallback.model_copy(update={"reason": f"{FALLBACK_TAG} {fallback.reason}"})
    return clamp(decision, state)


def read_state(bot_id: int, rules: BotRules, history: list[int]) -> tuple[dict, dict]:
    """Collect everything the decision needs from the vault. Returns (state, raw bot record)."""
    bot = vault.get_bot(bot_id)
    history.append(vault.price())
    state = {
        "strategy": rules.strategy, "history": history[-12:], "price": history[-1],
        "cash_usd": bot["cashUsd"], "eth_wei": bot["ethWei"], "equity_usd": vault.equity(bot_id),
        "max_trade_usd": bot["maxTradeUsd"], "max_loss_bps": bot["maxLossBps"],
    }
    return state, bot


def run_bot(bot_id: int, bot_key: str, rules: BotRules, stop_event: Event,
            report: Callable[[str, dict], None], interval_s: float = 30) -> None:
    """Every interval: look, decide, trade. report(kind, data) gets 'traded', 'rejected', 'error', 'stopped'."""
    history: list[int] = []
    while not stop_event.is_set():
        try:
            state, bot = read_state(bot_id, rules, history)
            if bot["status"] != "alive" or time.time() >= bot["expiresAt"]:
                report("stopped", {"reason": bot["status"] if bot["status"] != "alive" else "expired"})
                return
            decision = decide(state, rules.brain)
            if decision.action != "hold":
                tx = vault.trade(bot_key, bot_id, decision.action == "buy", decision.amount_usd)
                report("traded", {"action": decision.action, "amount_usd": decision.amount_usd,
                                  "reason": decision.reason, "tx": tx})
        except Exception as err:  # a failed trade must not crash the loop
            reason = vault.decode_revert(err)
            report("rejected", {"reason": reason})
            if reason in DEAD_REASONS:
                report("stopped", {"reason": reason})
                return
        stop_event.wait(interval_s)
