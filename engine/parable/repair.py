"""Keeps the public record (Arkiv) complete, using the vault as the source of truth.

Two jobs:
1. Outbox: if an Arkiv write fails AFTER the vault already did its part (bot born, bot died), the write
   is queued here and retried later instead of failing the whole launch. The vault never forgets, so
   neither may the public record.
2. Repair: walk every bot id the vault has ever registered (1..totalBorn). Any bot with no Arkiv record
   gets one rebuilt from the vault's own data; any vault death with no grave gets a grave. A bot whose
   lease is over gets expired (anyone may do that). So a crash can never leave a hidden bot behind.
"""

import logging
import threading
import time

from parable.models import BotEvent, BotRecord, BotRules, DeathRecord

log = logging.getLogger("parable.repair")
GRAVE_LIFETIME_S = 180 * 86400
UNKNOWN = "unknown"  # used when the vault does not store a detail (the brain and strategy name live off-chain)


class Outbox:
    """A list of Arkiv writes still to do. Each item is (description, function with no arguments)."""

    def __init__(self):
        self.items: list[tuple[str, object]] = []
        self.lock = threading.Lock()

    def run(self, what: str, fn) -> None:
        """Try the write now; if it fails, keep it for later. Never raises."""
        try:
            fn()
        except Exception:
            log.warning("Arkiv write failed, queued for retry: %s", what)
            with self.lock:
                self.items.append((what, fn))

    def flush(self) -> int:
        """Retry every queued write once, in order. Returns how many are still waiting."""
        with self.lock:
            todo, self.items = self.items, []
        for what, fn in todo:
            self.run(what, fn)
        with self.lock:
            return len(self.items)


def _record_from_vault(bot_id: int, info: dict, now: int) -> BotRecord:
    """Rebuild a bot's public record from what the vault stores about it."""
    rules = BotRules(strategy=UNKNOWN, brain=UNKNOWN, start_cash_usd=info["startCashUsd"],
                     max_trade_usd=info["maxTradeUsd"], max_loss_bps=info["maxLossBps"],
                     lease_seconds=max(int(info["expiresAt"]) - int(info["bornAt"]), 1))
    status = "dead" if info["status"] in ("dead", 2) else "alive"
    return BotRecord(bot_id=bot_id, bot_address=info["bot"], creator_id=info["creatorId"],
                     ens_name=f"bot #{bot_id} (record rebuilt from the vault)", strategy=UNKNOWN, rules=rules,
                     status=status, born_at=int(info["bornAt"]), born_tx="")


def _grave_from_vault(bot_id: int, info: dict) -> DeathRecord:
    start, final = int(info["startCashUsd"]), int(info["finalEquityUsd"])
    return DeathRecord(bot_id=bot_id, cause=info["cause"], final_equity_usd=final, start_cash_usd=start,
                       pnl_bps=(final - start) * 10000 // start if start else 0,
                       lifetime_s=int(info["diedAt"]) - int(info["bornAt"]), tx_hash="")


def repair(vault, arkiv, skip_ids: set[int] = frozenset()) -> list[str]:
    """One repair pass. `skip_ids` are bots this server is running itself (they are handled live).
    Returns a short line per fix, for the log."""
    now = int(time.time())
    known = {b.bot_id: b for b in arkiv.bots()}
    fixes = []
    for bot_id in range(1, vault.total_born() + 1):
        if bot_id in skip_ids:
            continue
        rec = known.get(bot_id)
        if rec is not None and rec.status == "dead":
            continue  # already complete
        info = vault.get_bot(bot_id)
        if info["status"] in ("alive", 1) and now >= int(info["expiresAt"]):
            vault.expire(bot_id)  # lease over: anyone may end it, so the vault records the death
            info = vault.get_bot(bot_id)
            fixes.append(f"bot {bot_id}: expired")
        if rec is None:
            rec = _record_from_vault(bot_id, info, now)
            arkiv.put_bot(rec, GRAVE_LIFETIME_S if rec.status == "dead" else max(int(info["expiresAt"]) - now, 60))
            arkiv.put_event(BotEvent(bot_id=bot_id, kind="birth", at=rec.born_at, tx_hash=None,
                                     data={"note": "record rebuilt from the vault"}))
            fixes.append(f"bot {bot_id}: record rebuilt")
        graves = {d.bot_id for d in arkiv.graveyard(rec.creator_id)}
        if info["status"] in ("dead", 2) and bot_id not in graves:
            arkiv.put_death(_grave_from_vault(bot_id, info), creator_id=rec.creator_id, strategy=rec.strategy,
                            brain=rec.rules.brain)
            fixes.append(f"bot {bot_id}: grave written")
    return fixes
