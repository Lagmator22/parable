"""Things every AI "mind" shares: asking any brain for one JSON answer (the swarm's mind uses this), and
remembering when the Anthropic account has no credit so Claude brains show as "not set up" honestly.
"""

import time

import anthropic
import httpx

from parable.config import get_settings

# If the Anthropic account has no credit, every Claude call fails the same way. Remember that for 10 minutes
# so Claude brains show as "not set up" instead of silently falling back to the rule (which would spoil comparisons).
_claude_off_until = 0.0
NO_CREDIT_PAUSE_S = 600


def note_claude_error(err: Exception) -> None:
    global _claude_off_until
    if "credit balance" in str(err).lower():
        _claude_off_until = time.time() + NO_CREDIT_PAUSE_S


def claude_usable() -> bool:
    return time.time() >= _claude_off_until


def probe_claude() -> None:
    """One tiny call at startup to learn whether the account has credit (a failed call costs nothing)."""
    s = get_settings()
    models = [model.strip() for model in s.claude_models.split(",") if model.strip()]
    if not s.anthropic_api_key or not models:
        return
    try:
        anthropic.Anthropic(api_key=s.anthropic_api_key, timeout=20).messages.create(
            model=models[0], max_tokens=1, messages=[{"role": "user", "content": "ok"}])
    except Exception as err:
        note_claude_error(err)


def chat_json(brain: str, prompt: str) -> dict:
    """Ask any AI brain for one JSON object (used by the swarm's mind). Raises if the brain can't answer."""
    from parable.bot_runner import GOOGLE_BASE, LLM_TIMEOUT_S, extract_json  # late: bot_runner imports this file

    s = get_settings()
    family, _, model = brain.partition(":")
    if family == "claude":
        client = anthropic.Anthropic(api_key=s.anthropic_api_key, timeout=LLM_TIMEOUT_S)
        try:
            reply = client.messages.create(model=model, max_tokens=1500, output_config={"effort": "low"},
                                           messages=[{"role": "user", "content": prompt}])
        except Exception as err:
            note_claude_error(err)
            raise
        return extract_json("".join(b.text for b in reply.content if b.type == "text"))
    if family in ("gemini", "gemma"):
        r = httpx.post(f"{GOOGLE_BASE}/chat/completions", timeout=LLM_TIMEOUT_S,
                       headers={"Authorization": f"Bearer {s.gemini_api_key}"},
                       json={"model": model, "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        return extract_json(r.json()["choices"][0]["message"]["content"])
    raise ValueError(f"{brain} is not an AI brain")
