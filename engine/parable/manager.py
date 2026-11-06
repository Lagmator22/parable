"""The swarm: one "mind" model watches a group of worker bots and decides, every minute, which to keep and
which to stop. The person picks the mind (e.g. Claude Opus) and the workers' brains, and approves the whole
swarm once with World ID.

The mind has NO special powers. It can only do what a creator can do (stop its own bots), the vault still
checks every trade, and every bot it stops stays in the public graveyard. If the mind is down or answers
nonsense, a plain safety rule decides instead and the note says so.
"""

import logging
import secrets
import threading
import time
from dataclasses import asdict, dataclass

from parable.bot_runner import available_brains
from parable.launcher import ApprovalPending, LaunchError, to_bytes32
from parable.minds import chat_json
from parable.models import BotRules

log = logging.getLogger("parable.swarm")
STRATEGIES = ("momentum", "dip_buyer", "yolo")
CHECK_EVERY_S = 60
STOP_LOSS_BPS = -300  # safety rule: stop a worker that is down 3% or more
STOP_REFUSALS = 2  # safety rule: stop a worker the vault refused twice (broken or trying to cheat)


@dataclass
class Decision:
    at: int
    action: str  # "launch" | "keep" | "flag" | "stop"
    bot_id: int | None
    reason: str
    by: str  # which brain decided: the mind's name, or "safety rule"


@dataclass
class SwarmPlan:
    mind: str
    workers: list[str]
    bots: int
    minutes: int
    approval: str = "world"


def mind_prompt(name: str, pnl_bps: int, trades: int, refused: int, left_s: int) -> str:
    return (f"You supervise trading bots in a practice vault. Bot {name}: return {pnl_bps / 100:+.2f}%, "
            f"{trades} trades, {refused} trades refused by the vault, {left_s // 60} minutes left. "
            "Stop a bot that is losing badly or that the vault keeps refusing; otherwise keep it. "
            'Reply with ONLY one JSON object like {"action": "keep", "reason": "under 15 words"} '
            'where action is "keep" or "stop".')


class SwarmManager:
    def __init__(self, launcher, check_every_s: float = CHECK_EVERY_S):
        self.launcher = launcher
        self.check_every_s = check_every_s
        self.lock = threading.Lock()  # guards starting and confirming
        self.notes_lock = threading.Lock()
        self.pending: dict[str, tuple[SwarmPlan, str]] = {}  # swarm launch id -> (plan, claim token)
        self.plan: SwarmPlan | None = None
        self.claim = ""
        self.phase = "idle"  # idle -> waiting -> launching -> running -> done
        self.bot_ids: list[int] = []
        self.decisions: list[Decision] = []
        self.next_check_at = 0
        self.stop_event = threading.Event()

    # ------------------------------------------------------------ starting a swarm
    def start(self, mind: str, workers: list[str], bots: int, minutes: int, demo: bool = False) -> tuple[str, str]:
        """Check the plan and ask World ID to approve it. Returns (swarm launch id, claim token)."""
        known = available_brains()
        for brain in [mind, *workers]:
            if not known.get(brain):
                raise LaunchError(f"brain '{brain}' is not set up on this server")
        if mind == "rule":
            raise LaunchError("the mind must be an AI model")
        if self.phase in ("launching", "running"):
            raise LaunchError("a swarm is already running; stop it first")
        plan = SwarmPlan(mind=mind, workers=workers or ["rule"], bots=max(1, min(bots, 6)), minutes=max(2, min(minutes, 120)),
                         approval="demo" if demo else "world")
        pid, claim = "s-" + secrets.token_hex(12), secrets.token_urlsafe(24)
        self.pending[pid] = (plan, claim)
        self.launcher.b.world.register_pending(pid, demo=demo)
        return pid, claim  # the page waits for the approval; the swarm's phase only changes once it starts

    def confirm(self, pid: str, claim: str) -> dict:
        """Poll after World approval. The first approved call starts launching the workers in the background.
        Done under the lock: an approval is used once, and a running swarm can't be replaced by another."""
        with self.lock:
            entry = self.pending.get(pid)
            if entry is None or not secrets.compare_digest(entry[1], claim):
                if self.claim and secrets.compare_digest(self.claim, claim):
                    return self.status()  # asked again after it started: same answer
                raise LaunchError("unknown swarm launch or wrong claim token")
            approval = self.launcher.b.world.get_approval(pid)
            if approval is None:
                raise ApprovalPending("waiting for World ID approval")
            self.pending.pop(pid, None)
            if not approval.approved:
                self.phase = "idle"
                raise LaunchError(f"not approved: {approval.reason}")
            if self.phase in ("launching", "running"):
                raise LaunchError("a swarm is already running; stop it first")
            self.pending.clear()  # any other approval in flight is void once a swarm starts
            self.plan, self.claim, self.bot_ids, self.decisions = entry[0], claim, [], []
            self.phase = "launching"
            self.stop_event = threading.Event()
            args = (to_bytes32(approval.subject), entry[0], claim, self.stop_event)
        threading.Thread(target=self._run, args=args, daemon=True).start()
        return self.status()

    def stop(self, claim: str) -> dict:
        """Stop the mind (the creator's browser holds the claim). Running workers keep their own leases."""
        if not self.claim or not secrets.compare_digest(self.claim, claim):
            raise LaunchError("only the person who started the swarm can stop it")
        self.stop_event.set()
        self.phase = "done"
        return self.status()

    # ------------------------------------------------------------ the swarm's life
    def _run(self, creator_id: str, plan: SwarmPlan, claim: str, stop_event: threading.Event) -> None:
        """One swarm's life. It keeps its own plan, claim and stop switch, never reading ones a later swarm set."""
        for i in range(plan.bots):
            if stop_event.is_set():
                return
            brain, strategy = plan.workers[i % len(plan.workers)], STRATEGIES[i % len(STRATEGIES)]
            rules = BotRules(strategy=strategy, brain=brain, start_cash_usd=100_000_000, max_trade_usd=20_000_000,
                             max_loss_bps=1000, lease_seconds=plan.minutes * 60, approval=plan.approval)
            try:
                rec = self.launcher._create_bot(creator_id, rules, claim)  # same steps as a normal launch
            except Exception:
                log.exception("swarm worker %s failed to launch", i + 1)
                self._note("flag", None, f"worker {i + 1} could not be launched; skipped it", "swarm")
                continue
            self.bot_ids.append(rec.bot_id)
            self._note("launch", rec.bot_id, f"started {rec.ens_name} ({strategy}, {brain})", plan.mind)
        self.phase = "running"
        while not stop_event.is_set() and self._alive_ids():
            self.next_check_at = int(time.time() + self.check_every_s)
            if stop_event.wait(self.check_every_s):
                break
            self.check_once()
        if self.phase == "running":
            self.phase = "done"

    def _alive_ids(self) -> list[int]:
        return [i for i in self.bot_ids if i in self.launcher.live and not self.launcher.live[i].dead]

    def check_once(self) -> None:
        """Ask the mind about every live worker; the safety rule overrides it for clear cases."""
        for bot_id in self._alive_ids():
            row = self._bot_row(bot_id)
            if row["refused"] >= STOP_REFUSALS or row["pnl_bps"] <= STOP_LOSS_BPS:
                action, by = "stop", "safety rule"
                reason = f"return {row['pnl_bps'] / 100:+.1f}%, {row['refused']} refused trades"
            else:
                try:
                    answer = chat_json(self.plan.mind, mind_prompt(row["ens_name"], row["pnl_bps"], row["trades"],
                                                                   row["refused"], row["left_s"]))
                    action = "stop" if str(answer.get("action")).lower() == "stop" else "keep"
                    reason, by = str(answer.get("reason") or "no reason given")[:140], self.plan.mind
                except Exception:
                    action, reason, by = "keep", "the mind didn't answer; nothing looks wrong, so keep it", "safety rule"
            if action == "stop":
                try:
                    self.launcher.kill(bot_id, self.claim)
                except Exception:
                    log.exception("swarm could not stop bot %s", bot_id)
                    continue
            self._note(action, bot_id, f"{row['ens_name']}: {reason}", by)

    def _note(self, action: str, bot_id: int | None, reason: str, by: str) -> None:
        with self.notes_lock:
            self.decisions.insert(0, Decision(int(time.time()), action, bot_id, reason, by))
            del self.decisions[40:]

    # ------------------------------------------------------------ what the page shows
    def _bot_row(self, bot_id: int) -> dict:
        lb = self.launcher.live[bot_id]
        rec = lb.record
        try:
            events = self.launcher.b.arkiv.events(bot_id)
        except Exception:
            events = []
        try:
            equity = self.launcher.b.vault.equity(bot_id)
        except Exception:
            equity = rec.rules.start_cash_usd
        return {"bot_id": bot_id, "ens_name": rec.ens_name, "brain": rec.rules.brain, "strategy": rec.strategy,
                "status": "dead" if lb.dead else "alive", "equity_usd": equity,
                "pnl_bps": (equity - rec.rules.start_cash_usd) * 10000 // rec.rules.start_cash_usd,
                "trades": sum(e.kind == "trade" for e in events), "refused": sum(e.kind == "rejected" for e in events),
                "left_s": max(0, lb.expires_at - int(time.time()))}

    def status(self) -> dict:
        return {"phase": self.phase, "plan": asdict(self.plan) if self.plan else None,
                "born": len(self.bot_ids), "total": self.plan.bots if self.plan else 0,
                "next_check_in": max(0, self.next_check_at - int(time.time())) if self.phase == "running" else None,
                "bots": [self._bot_row(i) for i in self.bot_ids if i in self.launcher.live],
                "decisions": [asdict(d) for d in self.decisions]}
