"""The AI Swarm Manager ("boss brain"): launches or audits a cohort of worker bots, flags broken/malicious
bots that hit vault rejections, and kills losers. It has NO special powers: the Sepolia vault still enforces
every trade limit, and every bot the manager kills stays in the public Arkiv graveyard forever.
"""

import logging
import time
from dataclasses import dataclass

import httpx

from parable.bot_runner import GOOGLE_BASE, available_brains, extract_json
from parable.config import get_settings
from parable.models import BotRules

log = logging.getLogger("parable.manager")
STRATEGIES = ("momentum", "dip_buyer", "yolo")
MIND_TIMEOUT_S = 15


@dataclass
class Decision:
    at: int
    action: str  # "launch" | "kill" | "flag" | "keep"
    bot_id: int
    reason: str

    def to_dict(self) -> dict:
        return {"at": self.at, "action": self.action, "bot_id": self.bot_id, "reason": self.reason}


def pick_mind() -> str:
    """Choose the best configured brain for the swarm manager (prefers Gemini Flash-Lite, then Claude, else rule)."""
    avail = available_brains()
    for preferred in ("gemini:gemini-3.5-flash-lite", "gemini:gemini-2.5-flash", "claude"):
        if avail.get(preferred):
            return preferred
    for name, ok in avail.items():
        if ok and name.startswith("gemini:"):
            return name
    return "rule"


def ask_mind_reason(mind: str, summary: str, fallback: str) -> str:
    """Ask Gemini for a short 1-sentence audit note; if unconfigured or slow, return the rule note."""
    s = get_settings()
    if not mind.startswith("gemini:") or not s.gemini_api_key:
        return fallback
    model = mind.split(":", 1)[1]
    prompt = (
        f"You are Parable's AI Swarm Manager auditing a trading bot.\n{summary}\n"
        'Reply with ONLY one JSON object: {"action": "keep", "reason": "<under 18 words explaining why>"}'
    )
    try:
        r = httpx.post(
            f"{GOOGLE_BASE}/chat/completions", timeout=MIND_TIMEOUT_S,
            headers={"Authorization": f"Bearer {s.gemini_api_key}"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}]},
        )
        r.raise_for_status()
        obj = extract_json(r.json()["choices"][0]["message"]["content"])
        return str(obj.get("reason") or fallback)[:140]
    except Exception:
        return fallback


class SwarmManager:
    def __init__(self, launcher):
        self.launcher = launcher
        self.decisions: list[Decision] = []
        self.claims: dict[int, str] = {}  # bot_id -> owner claim token for bots the manager launched itself
        self.tracked_ids: list[int] = []

    def _record(self, action: str, bot_id: int, reason: str) -> None:
        self.decisions = [d for d in self.decisions if not (d.bot_id == bot_id and d.action == action)]
        self.decisions.insert(0, Decision(at=int(time.time()), action=action, bot_id=bot_id, reason=reason))
        del self.decisions[30:]  # keep the 30 most recent decisions

    def status(self) -> dict:
        if not self.decisions and not self.tracked_ids:
            self.audit("rule")
        bots = sorted({*self.tracked_ids, *self.launcher.live.keys()})
        return {
            "enabled": True,
            "mind": pick_mind(),
            "bots": bots,
            "decisions": [d.to_dict() for d in self.decisions],
        }

    def start(self, count: int = 3, minutes: int = 15, spawn_offline: bool = False) -> dict:
        """Launch a worker swarm (in offline/mock mode) and run an audit pass across all known bots."""
        count = max(1, min(count, 6))
        lease_s = max(60, min(minutes * 60, 7200))
        mind = pick_mind()
        worker_brain = mind if mind != "claude" else "rule"

        if spawn_offline and hasattr(self.launcher.b.world, "decide"):
            for i in range(count):
                strat = STRATEGIES[i % len(STRATEGIES)]
                rules = BotRules(strategy=strat, brain=worker_brain, start_cash_usd=100_000_000,
                                 max_trade_usd=20_000_000, max_loss_bps=1000, lease_seconds=lease_s)
                pid, claim = self.launcher.start_launch(rules)
                self.launcher.b.world.decide(pid, True)
                rec = self.launcher.confirm_launch(pid, claim)
                self.claims[rec.bot_id] = claim
                self.tracked_ids.append(rec.bot_id)
                self._record("launch", rec.bot_id,
                             f"started {rec.ens_name} ({strat}, {worker_brain})")

        self.audit(mind)
        return self.status()

    def audit(self, mind: str | None = None) -> list[dict]:
        """Inspect every live and recent bot's on-chain equity and Arkiv events; flag or kill bad actors."""
        mind = mind or pick_mind()
        try:
            known = {b.bot_id: b for b in self.launcher.b.arkiv.bots()}
        except Exception:
            known = {}
        for bot_id, live in list(self.launcher.live.items()):
            known.setdefault(bot_id, live.record)

        for bot_id, rec in sorted(known.items()):
            if bot_id not in self.tracked_ids:
                self.tracked_ids.append(bot_id)
            try:
                events = self.launcher.b.arkiv.events(bot_id)
            except Exception:
                events = []
            rejected = [e for e in events if e.kind == "rejected"]
            trades = [e for e in events if e.kind == "trade"]
            try:
                eq = self.launcher.b.vault.equity(bot_id)
            except Exception:
                eq = rec.rules.start_cash_usd
            pnl_bps = (eq - rec.rules.start_cash_usd) * 10000 // rec.rules.start_cash_usd

            if rejected:
                last_err = rejected[0].data.get("reason") or rejected[0].data.get("error") or "VaultRevert"
                self._record("flag", bot_id,
                             f"{rec.ens_name}: the vault refused {len(rejected)} of its trades")
            if bot_id in self.launcher.live and not self.launcher.live[bot_id].dead:
                if (pnl_bps <= -300 or len(rejected) >= 2) and bot_id in self.claims:
                    self.launcher.kill(bot_id, self.claims[bot_id])
                    self._record("kill", bot_id,
                                 f"stopped {rec.ens_name}: return {pnl_bps / 100:.1f}%, {len(rejected)} refused trades")
                else:
                    summary = f"Bot {rec.ens_name} ({rec.strategy}): {len(trades)} trades, PnL {pnl_bps / 100:.1f}%."
                    note = ask_mind_reason(
                        mind, summary,
                        f"{rec.ens_name}: running, {len(trades)} trades, return {pnl_bps / 100:+.1f}%",
                    )
                    self._record("keep", bot_id, note)
            elif not rejected:
                self._record("keep", bot_id,
                             f"{rec.ens_name}: in the graveyard, {len(trades)} trades, return {pnl_bps / 100:+.1f}%")
        return [d.to_dict() for d in self.decisions]
