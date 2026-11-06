"""The "Jev" brain (Autoloops, https://autoloops.ai/jev). Jev doesn't write text: the model scores a fixed
list of answers and returns a probability for each, which makes it very fast and leaves nothing to misparse.
A bot's decision IS a fixed list (buy, sell, hold), so we ask one choice question and get e.g.
{"buy": 0.87, "hold": 0.10, "sell": 0.03}. The trade size follows the confidence: 87% sure -> 87% of the
bot's per-trade limit (the vault still enforces the limit). Any error -> the caller falls back to the rule.
"""

import httpx

from parable.config import get_settings
from parable.models import TradeDecision

JEV_URL = "https://api.autoloops.ai/v1/systemone"
CHOICES = ("buy", "sell", "hold")
TIMEOUT_S = 20


def jev_question(state: dict) -> dict:
    """The request body: the bot's situation as the conversation state, and one multiple-choice question."""
    from parable.bot_runner import build_prompt  # late import: bot_runner imports this module

    situation = build_prompt(state).split("Call decide_trade.")[0].strip()
    return {
        "state": [{"role": "user", "content": [{"type": "text", "text": situation}]}],
        "questions": {"action": {
            "type": "choice",
            "instructions": "Following the strategy above, what should the bot do right now?",
            "criteria": {c: None for c in CHOICES},
        }},
    }


def to_decision(answer: dict, max_trade_usd: int) -> TradeDecision:
    """Turn {"choice": "buy", "probabilities": {...}} into a trade sized by how sure the model is."""
    probs = {c: float(answer.get("probabilities", {}).get(c, 0.0)) for c in CHOICES}
    choice = str(answer.get("choice") or max(probs, key=probs.get))
    if choice not in CHOICES:
        raise ValueError(f"unexpected Jev choice {choice!r}")
    sure = probs.get(choice, 0.0)
    amount = 0 if choice == "hold" else max(1_000_000, int(max_trade_usd * sure))  # at least $1 when trading
    odds = " · ".join(f"{c} {probs[c]:.0%}" for c in CHOICES)
    return TradeDecision(action=choice, amount_usd=amount, reason=f"Jev: {choice} ({odds})")


def jev_decide(state: dict, model: str) -> TradeDecision:
    s = get_settings()
    r = httpx.post(JEV_URL, timeout=TIMEOUT_S, headers={"Authorization": f"Bearer {s.autoloops_api_key}"},
                   json={"model": model, **jev_question(state)})
    r.raise_for_status()
    return to_decision(r.json()["answers"]["action"], state["max_trade_usd"])
