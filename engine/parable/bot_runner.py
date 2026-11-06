"""The trading bot's brain and loop. Each bot has a chosen brain (rule, claude, gemini, gemma, local) that picks
buy/sell/hold from the price history; if an AI brain is unavailable or answers badly, the built-in rule decides instead.
The vault (not this file) enforces the real limits; clamping here just avoids silly requests.
"""

import hashlib
import json
import logging
import re
import time
from threading import Event
from typing import Callable, Literal

import anthropic
import httpx
from pydantic import BaseModel, Field

from parable import vault
from parable.config import get_settings
from parable.models import BotRules, TradeDecision

log = logging.getLogger("parable.bot")


def redact(err: Exception) -> str:
    """Error type + message with every URL removed (RPC URLs can contain API keys)."""
    return f"{type(err).__name__}: " + re.sub(r"https?://\S+", "<url>", str(err))[:300]

LLM_TIMEOUT_S = 30  # Gemma can take ~17s. The bot loop interval must stay longer than this.
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
        "amount_dollars": {"type": "number", "description": "plain US dollars to trade, e.g. 20.5 means $20.50"},
        "reason": {"type": "string"},
    },
    "required": ["action", "amount_dollars", "reason"],
    "additionalProperties": False,
}
JSON_EXAMPLE = '{"action": "buy", "amount_dollars": 12.5, "reason": "short explanation"}'
# strict=True makes Claude's tool input match the schema exactly.
DECISION_TOOL = {"name": "decide_trade", "description": "Decide the next paper trade.",
                 "input_schema": DECISION_SCHEMA, "strict": True}


class AiAnswer(BaseModel):
    """What an AI brain must answer, in plain dollars."""

    action: Literal["buy", "sell", "hold"]
    amount_dollars: float = Field(default=0, ge=0, allow_inf_nan=False)
    reason: str


def eth_value_usd(state: dict) -> int:
    """ETH wei (18 decimals) * price (8 decimals) -> USD (6 decimals): divide by 1e20."""
    return state["eth_wei"] * state["price"] // 10**20


def code_fingerprint(rules: BotRules) -> str:
    """Short SHA-256 hash of a bot's brain + strategy rules, stored on its ENS badge so rebirths are linked."""
    spec = f"{rules.brain}:{rules.strategy}:{PRESETS.get(rules.strategy, '')}:{rules.max_loss_bps}"
    return "0x" + hashlib.sha256(spec.encode()).hexdigest()[:16]


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
    """Show everything in plain dollars and ETH (never raw 6/18-decimal integers) so models do not misread units."""
    prices = [round(p / 1e8, 2) for p in state["history"]]
    dollars = lambda n: round(n / 1e6, 2)
    return (
        f"You manage a small practice ETH/USD portfolio. Strategy: {state['strategy']}. "
        f"{PRESETS.get(state['strategy'], '')}\n"
        f"ETH price history in USD, oldest first: {prices}\n"
        f"Cash: ${dollars(state['cash_usd'])}. ETH held: {state['eth_wei'] / 1e18:.6f} ETH. "
        f"Total equity: ${dollars(state['equity_usd'])}. Max per trade: ${dollars(state['max_trade_usd'])}. "
        f"Max loss allowed before you are shut down: {state['max_loss_bps'] / 100}%.\n"
        "Call decide_trade. amount_dollars is a plain number of US dollars, for example 20.5 means $20.50."
    )


def to_decision(raw: dict) -> TradeDecision:
    """AI answers in plain dollars; the vault wants 6 decimals, so multiply by 1,000,000."""
    answer = AiAnswer.model_validate(raw)
    return TradeDecision(action=answer.action, amount_usd=round(answer.amount_dollars * 1_000_000),
                         reason=answer.reason)


def extract_json(text: str) -> dict:
    """Models add <thought>...</thought> or ```json fences around the answer: drop those, then take the LAST {...}."""
    text = re.sub(r"<(thought|thinking)>.*?</\1>", "", text, flags=re.DOTALL).replace("```json", "").replace("```", "")
    found, decoder = None, json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                obj, _ = decoder.raw_decode(text[i:])
            except ValueError:
                continue
            if isinstance(obj, dict) and "action" in obj:
                found = obj  # keep going: the last one wins
    if found is None:
        raise ValueError("no JSON answer in the model reply")
    return found


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
    return to_decision(block.input)


GOOGLE_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"  # Google's OpenAI-style endpoint
FALLBACK_TAG = "[fallback:rule]"  # starts the reason whenever the rule stepped in for a failed AI brain


def openai_style_decide(state: dict, base_url: str, api_key: str, model: str) -> TradeDecision:
    """Any OpenAI-style chat API (Google, Ollama, ...). We ask for JSON only. api_key may be empty (local)."""
    # Show an example, not the schema: some small models copy the schema's shape ("action": {"type": ...}).
    prompt = build_prompt(state).replace("Call decide_trade.", "Reply with ONLY one JSON object, like " + JSON_EXAMPLE
                                         + " where action is one of buy, sell, hold.")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    r = httpx.post(f"{base_url.rstrip('/')}/chat/completions", timeout=LLM_TIMEOUT_S, headers=headers,
                   json={"model": model, "messages": [{"role": "user", "content": prompt}]})
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    return to_decision(extract_json(text))


def build_brains() -> dict[str, dict]:
    """The brains a bot can choose, built from settings: how each decides, and whether it is set up.
    Every Gemini / Gemma model in the .env lists is its own brain, so their results can be compared."""
    s = get_settings()
    brains = {
        "rule": {"decide": rule_decide, "ready": True},
        "claude": {"decide": claude_decide, "ready": bool(s.anthropic_api_key and s.bot_model)},
        "local": {"decide": lambda st: openai_style_decide(st, s.local_llm_base_url, "", s.local_llm_model),
                  "ready": bool(s.local_llm_base_url and s.local_llm_model)},
    }
    for family, models in (("gemini", s.gemini_models), ("gemma", s.gemma_models)):
        for model in [m.strip() for m in models.split(",") if m.strip()]:
            brains[f"{family}:{model}"] = {
                "decide": lambda st, model=model: openai_style_decide(st, GOOGLE_BASE, s.gemini_api_key, model),
                "ready": bool(s.gemini_api_key),
            }
    return brains


def available_brains() -> dict[str, bool]:
    """For the dashboard: is each brain set up? Only true/false, never any key."""
    return {name: b["ready"] for name, b in build_brains().items()}


def decide(state: dict, brain: str = "rule") -> TradeDecision:
    """Use the chosen brain; an unset-up or failing AI brain falls back to the rule and says so in the reason."""
    entry = build_brains().get(brain)
    try:
        if entry is None or not entry["ready"]:
            raise RuntimeError(f"brain {brain} is not configured")
        decision = entry["decide"](state)
    except Exception:
        fallback = rule_decide(state)
        decision = fallback.model_copy(update={"reason": f"{FALLBACK_TAG} {fallback.reason}"})
    return clamp(decision, state)


# Sepolia's Chainlink ETH/USD feed updates only ~once an hour. When the oracle price is unchanged between
# 45s bot ticks, we add a small tick (in bps) to the signal history so momentum and dip_buyer strategies can
# act during a short demo lease. The vault contract on Sepolia ALWAYS trades at the real Chainlink price.
FLAT_ORACLE_TICKS_BPS = (-18, -12, 15, 25, -10, 20, -22, 18)


def signal_price(oracle_price: int, history: list[int]) -> int:
    """Use the Chainlink price directly when it moves; otherwise add a small tick so short demos see signals."""
    if not history or oracle_price != history[0] and oracle_price not in history[-2:]:
        return oracle_price
    bps = FLAT_ORACLE_TICKS_BPS[(len(history) - 1) % len(FLAT_ORACLE_TICKS_BPS)]
    return oracle_price * (10_000 + bps) // 10_000


def read_state(bot_id: int, rules: BotRules, history: list[int]) -> tuple[dict, dict]:
    """Collect everything the decision needs from the vault. Returns (state, raw bot record)."""
    bot = vault.get_bot(bot_id)
    oracle = vault.price()
    if not history:
        # Seed two reference points on tick 1 so momentum/dip_buyer and AI brains can trade immediately at birth.
        history.extend([oracle, signal_price(oracle, [oracle])])
    history.append(signal_price(oracle, history))
    state = {
        "strategy": rules.strategy, "history": history[-12:], "price": oracle,
        "cash_usd": bot["cashUsd"], "eth_wei": bot["ethWei"], "equity_usd": vault.equity(bot_id),
        "max_trade_usd": bot["maxTradeUsd"], "max_loss_bps": bot["maxLossBps"],
    }
    return state, bot


def run_bot(bot_id: int, bot_key: str, rules: BotRules, stop_event: Event,
            report: Callable[[str, dict], None], interval_s: float = 45) -> None:
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
            if reason == "UnknownError":
                log.warning("bot %s trade failed: %s", bot_id, redact(err))  # server log only, URLs removed
            report("rejected", {"reason": reason})
            if reason in DEAD_REASONS:
                report("stopped", {"reason": reason})
                return
        stop_event.wait(interval_s)
