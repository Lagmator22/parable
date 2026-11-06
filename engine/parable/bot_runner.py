"""The trading bot's brain and loop. Claude Haiku picks buy/sell/hold from the price history;
if the AI is unavailable or answers badly, a simple built-in rule decides instead.
The vault (not this file) enforces the real limits; clamping here just avoids silly requests.
"""

import time
from threading import Event
from typing import Callable

import anthropic

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
DECISION_TOOL = {
    "name": "decide_trade",
    "description": "Decide the next paper trade.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["buy", "sell", "hold"]},
            "amount_usd": {"type": "integer", "description": "USD with 6 decimals, 1000000 = 1 USD"},
            "reason": {"type": "string"},
        },
        "required": ["action", "amount_usd", "reason"],
    },
}


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


def llm_decide(state: dict) -> TradeDecision:
    """Ask Claude, forcing it to answer through the decide_trade tool; Pydantic validates the result."""
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=LLM_TIMEOUT_S)
    reply = client.messages.create(
        model=settings.bot_model, max_tokens=300, tools=[DECISION_TOOL],
        tool_choice={"type": "tool", "name": "decide_trade"},
        messages=[{"role": "user", "content": build_prompt(state)}],
    )
    block = next(b for b in reply.content if b.type == "tool_use")
    return TradeDecision.model_validate(block.input)


def decide(state: dict) -> TradeDecision:
    """LLM first; on ANY failure fall back to the rule. Result is always clamped."""
    try:
        decision = llm_decide(state)
    except Exception:
        decision = rule_decide(state)
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
            decision = decide(state)
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
