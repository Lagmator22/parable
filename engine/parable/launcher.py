"""The launch flow: World approval -> bot wallet -> gas -> ENS badge -> vault -> Arkiv -> bot loop.
Also ends bots (kill / check / expire) and copies deaths from the vault into the Arkiv graveyard.
Every outside service (vault, ENS, Arkiv, bot runner, World) is passed in, so tests can use fakes.
Bot private keys live in memory only. They are never logged or written to disk.
"""

import hashlib
import hmac
import logging
import secrets
import threading
import time
from dataclasses import dataclass, field
from types import SimpleNamespace

from eth_account import Account

from parable.models import BotEvent, BotRecord, BotRules, DeathRecord
from parable.repair import Outbox, repair

log = logging.getLogger("parable.launcher")
CAUSES = {1: "expired", 2: "killed", 3: "loss_limit"}  # the vault's DeathCause numbers (vault.py already gives names)


class LaunchError(Exception):
    pass


class ApprovalPending(LaunchError):
    pass


class ApprovalDenied(LaunchError):
    pass


class LaunchFailed(Exception):
    """Something broke on the way (chain, ENS). Any half-made bot is fixed later by repair.py."""


def real_backends() -> SimpleNamespace:
    """The real modules (imported late so offline mode never needs them)."""
    from parable import arkiv_store, bot_runner, ens_badge, vault, world_pass

    return SimpleNamespace(vault=vault, ens=ens_badge, arkiv=arkiv_store, runner=bot_runner, world=world_pass)


def to_bytes32(text: str) -> str:
    """The vault stores ids as 32 bytes, so we hash any text (World subject, strategy) into 32 bytes."""
    return "0x" + hashlib.sha256(text.encode()).hexdigest()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def creator_wallet(creator_id: str, secret: str) -> str:
    """One fixed wallet address per creator (the vault insists on one wallet per World identity).
    The key is derived with a SERVER SECRET, so nobody else can recompute it and kill this creator's bots."""
    key = hmac.new(secret.encode(), creator_id.encode(), hashlib.sha256).digest()
    return Account.from_key(key).address


@dataclass
class LiveBot:
    record: BotRecord
    key: str  # the bot's private key, memory only
    expires_at: int
    node: str
    owner_hash: str = ""  # sha256 of the creator's claim code; needed to kill the bot
    stop: threading.Event = field(default_factory=threading.Event)
    dead: bool = False


class Launcher:
    def __init__(self, backends, secret: str):
        if len(secret) < 16:
            raise LaunchError("PARABLE_CREATOR_SECRET must be set (16+ random characters)")
        self.b = backends
        self.secret = secret
        self.pending: dict[str, tuple[BotRules, str]] = {}  # pending_id -> (rules, claim token)
        self.live: dict[int, LiveBot] = {}
        self.lock = threading.Lock()
        self.counter = 0
        self.in_progress: set[str] = set()  # launches being created right now
        self.finished: dict[str, tuple[str, object]] = {}  # pending_id -> (claim hash, bot or error)
        self.outbox = Outbox()  # Arkiv writes that failed and will be retried (the vault already has them)

    # ---------------------------------------------------------------- launching
    def start_launch(self, rules: BotRules) -> tuple[str, str]:
        """Returns (pending_id, claim_token). Only the person holding the claim token can confirm the launch,
        so nobody else can hijack an approval. World only accepts pending ids we created here."""
        pending_id = "p-" + secrets.token_hex(12)
        claim = secrets.token_urlsafe(24)
        self.pending[pending_id] = (rules, claim)
        self.b.world.register_pending(pending_id)
        return pending_id, claim

    def confirm_launch(self, pending_id: str, claim: str) -> BotRecord:
        """Safe to call again and again (the page polls): while the bot is being born on-chain (about a
        minute) the answer is 'pending', and afterwards every call returns the same bot."""
        with self.lock:
            done = self.finished.get(pending_id)
            if done is not None and hmac.compare_digest(done[0], _hash(claim)):
                if isinstance(done[1], Exception):
                    raise done[1]
                return done[1]
            if pending_id in self.in_progress:
                raise ApprovalPending("approved: the bot is being born on-chain (about a minute)")
            entry = self.pending.get(pending_id)
            if entry is None or not hmac.compare_digest(entry[1], claim):
                raise LaunchError("unknown launch id or wrong claim token")
            rules = entry[0]
            approval = self.b.world.get_approval(pending_id)
            if approval is None:
                raise ApprovalPending("waiting for World ID approval")
            self.pending.pop(pending_id, None)  # an approval can launch only one bot
            if not approval.approved:
                raise ApprovalDenied(approval.reason)
            self.in_progress.add(pending_id)
        try:
            result = self._create_bot(to_bytes32(approval.subject), rules, claim)
        except Exception:
            log.exception("launch %s failed", pending_id)  # full detail stays in the server log
            result = LaunchFailed("the launch failed while creating the bot on-chain; please try again")
        with self.lock:
            self.in_progress.discard(pending_id)
            self.finished[pending_id] = (_hash(claim), result)
        if isinstance(result, Exception):
            raise result
        return result

    def _create_bot(self, creator_id: str, rules: BotRules, claim: str) -> BotRecord:
        v = self.b.vault
        wallet = Account.create()  # fresh wallet for this bot; the bot is the only one who holds the key
        now = int(time.time())
        expires_at = now + rules.lease_seconds
        self.counter += 1
        label = f"bot-{self.counter}-{secrets.token_hex(2)}"
        v.fund_gas(wallet.address)  # the bot needs a little ETH to pay gas for its own trades
        ens_name, node = self.b.ens.issue_badge(
            label, wallet.address, expires_at, {"strategy": rules.strategy, "max_loss_bps": str(rules.max_loss_bps)}
        )
        bot_id, tx = v.register_bot(
            bot_address=wallet.address, creator_id=creator_id,
            creator_wallet=creator_wallet(creator_id, self.secret), badge_node=node, expires_at=expires_at,
            start_cash_usd=rules.start_cash_usd, max_trade_usd=rules.max_trade_usd,
            max_loss_bps=rules.max_loss_bps, strategy_id=to_bytes32(rules.strategy),
        )
        record = BotRecord(bot_id=bot_id, bot_address=wallet.address, creator_id=creator_id, ens_name=ens_name,
                           strategy=rules.strategy, rules=rules, status="alive", born_at=now, born_tx=tx)
        bot = LiveBot(record=record, key="0x" + wallet.key.hex().removeprefix("0x"), expires_at=expires_at, node=node,
                      owner_hash=_hash(claim))
        self.live[bot_id] = bot
        self._start_runner(bot, rules)
        # From here the bot exists in the vault, so slow Arkiv writes run in the background and never hold up confirm.
        birth = BotEvent(bot_id=bot_id, kind="birth", at=now, tx_hash=tx, data={"ens_name": ens_name})
        writer = threading.Thread(target=self._write_birth, args=(record, rules.lease_seconds, birth), daemon=True)
        writer.start()
        writer.join(timeout=0.05)  # finishes at once in fast tests; returns immediately if Arkiv is slow on-chain
        return record

    def _write_birth(self, record: BotRecord, lease_seconds: int, birth: BotEvent) -> None:
        self.outbox.run(f"bot {record.bot_id} record", lambda: self.b.arkiv.put_bot(record, lease_seconds))
        self.outbox.run(f"bot {record.bot_id} birth", lambda: self.b.arkiv.put_event(birth))

    def _start_runner(self, bot: LiveBot, rules: BotRules) -> None:
        bot_id = bot.record.bot_id

        def report(kind: str, data: dict) -> None:
            """The bot loop tells us what happened; trades and blocked trades go to the public record."""
            if kind not in ("traded", "rejected"):
                log.info("bot %s %s: %s", bot_id, kind, data)  # deaths are recorded by sync_deaths from the vault
                return
            data = dict(data)
            tx_hash = data.pop("tx", None)
            event = BotEvent(bot_id=bot_id, kind="trade" if kind == "traded" else "rejected",
                             at=int(time.time()), tx_hash=tx_hash, data=data)
            self.outbox.run(f"bot {bot_id} {kind}", lambda: self.b.arkiv.put_event(event))  # never stops the bot

        args = (bot_id, bot.key, rules, bot.stop, report)
        threading.Thread(target=self.b.runner.run_bot, args=args, daemon=True).start()

    # ---------------------------------------------------------------- ending bots
    def kill(self, bot_id: int, owner_token: str) -> str:
        """Only the creator may kill (they hold the claim code from launch). Check and expire are open to anyone,
        because the vault itself only lets them succeed when the bot is really over its loss limit or out of time."""
        bot = self._get(bot_id)
        if not hmac.compare_digest(bot.owner_hash, _hash(owner_token)):
            raise LaunchError("only the bot's creator can kill it")
        return self._end(bot_id, self.b.vault.kill)

    def check(self, bot_id: int) -> str:
        """Anyone may call this. It only works if the bot really is over its loss limit."""
        return self._end(bot_id, self.b.vault.check_and_revoke)

    def expire(self, bot_id: int) -> str:
        return self._end(bot_id, self.b.vault.expire)

    def _end(self, bot_id: int, vault_call) -> str:
        bot = self._get(bot_id)
        tx = vault_call(bot_id)  # raises with the vault's reason if the rule is not met
        self._record_death(bot, tx)
        return tx

    def _get(self, bot_id: int) -> LiveBot:
        if bot_id not in self.live:
            raise LaunchError(f"bot {bot_id} is not known to this server")
        return self.live[bot_id]

    # ---------------------------------------------------------------- death sync
    def sync_deaths(self) -> None:
        """Look at the vault (the source of truth) and record any death we have not recorded yet."""
        now = int(time.time())
        for bot in list(self.live.values()):
            if bot.dead:
                continue
            try:
                info = self.b.vault.get_bot(bot.record.bot_id)
                if info["status"] in (2, "dead"):
                    self._record_death(bot, None)
                elif now >= bot.expires_at:
                    self.expire(bot.record.bot_id)  # anyone may expire a bot once its lease is over
            except Exception as err:
                # Sepolia block timestamps move in 12s steps; if the chain clock is a few seconds behind, wait a tick.
                if hasattr(self.b.vault, "decode_revert") and self.b.vault.decode_revert(err) == "NotExpired":
                    continue
                log.exception("death sync failed for bot %s", bot.record.bot_id)

    def _record_death(self, bot: LiveBot, tx_hash: str | None) -> None:
        with self.lock:
            if bot.dead:
                return
            bot.dead = True
        bot.stop.set()
        r = bot.record
        info = self.b.vault.get_bot(r.bot_id)
        cause = CAUSES.get(info["cause"], info["cause"])
        final = info["finalEquityUsd"]
        died_at = info.get("diedAt") or int(time.time())
        death = DeathRecord(bot_id=r.bot_id, cause=cause, final_equity_usd=final,
                            start_cash_usd=r.rules.start_cash_usd,
                            pnl_bps=(final - r.rules.start_cash_usd) * 10000 // r.rules.start_cash_usd,
                            lifetime_s=died_at - r.born_at, tx_hash=tx_hash or "")
        ark = self.b.arkiv
        self.outbox.run(f"bot {r.bot_id} grave",
                        lambda: ark.put_death(death, creator_id=r.creator_id, strategy=r.strategy, brain=r.rules.brain))
        event = BotEvent(bot_id=r.bot_id, kind="death", at=died_at, tx_hash=tx_hash,
                         data={"cause": cause, "pnl_bps": death.pnl_bps})
        self.outbox.run(f"bot {r.bot_id} death", lambda: ark.put_event(event))
        try:  # the vault already revoked its own badge check; also burn the ENS name (best effort)
            if self.b.ens.is_valid(r.ens_name, r.bot_address):
                self.b.ens.revoke_badge(r.ens_name)
        except Exception:
            log.exception("could not revoke ENS name %s", r.ens_name)

    def repair_record(self) -> list[str]:
        """Fill any gap between the vault and Arkiv (see repair.py). Bots this server runs are handled live."""
        if not hasattr(self.b.vault, "total_born"):
            return []
        fixes = repair(self.b.vault, self.b.arkiv, skip_ids=set(self.live))
        for line in fixes:
            log.info("repair: %s", line)
        return fixes

    def start_poller(self, every_s: float = 5, repair_every: int = 12) -> None:
        def loop():
            tick = 0
            while True:
                if tick % repair_every == 0:  # first pass at startup, then about once a minute
                    try:
                        self.repair_record()
                    except Exception:
                        log.exception("repair pass failed")
                time.sleep(every_s)
                tick += 1
                self.sync_deaths()
                self.outbox.flush()

        threading.Thread(target=loop, daemon=True).start()

    # ---------------------------------------------------------------- read helpers
    def report(self, creator_id: str | None, strategy: str | None, brain: str | None = None):
        card = self.b.arkiv.report_card(creator_id, strategy, brain=brain)
        if creator_id and not brain:  # compare Arkiv's count with the vault's own count (it cannot split by brain)
            try:
                born, _dead = self.b.vault.counts(creator_id)
                card = card.model_copy(update={"vault_count_matches": card.launched == born})
            except Exception:
                log.warning("could not read vault counts for %s", creator_id)
                card = card.model_copy(update={"vault_count_matches": False})
        return card
