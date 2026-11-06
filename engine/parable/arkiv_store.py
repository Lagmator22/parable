"""Arkiv records for Parable (bots, events, deaths) and the queries behind the graveyard.

Arkiv is a public on-chain database. We talk to it through arkiv-bridge/, a small local Node
service that uses the official @arkiv-network/sdk (the Python SDK cannot talk to the Rabdi testnet).
SECURITY: anyone can write fake rows to Arkiv, so every query is limited to rows owned by OUR writer
wallet, and if we do not know that wallet we refuse to read at all (fail closed).
Every row also carries the vault's address ("vault" attribute), so test rows and rows from an old vault
never mix into the real graveyard. Reads are cached for a few seconds because the public endpoint is rate-limited.
"""

from __future__ import annotations

import json
import threading
import time
from collections import defaultdict

import httpx

from .config import get_settings
from .models import BotEvent, BotRecord, DeathRecord, ReportCard

EXPLORER = "https://rabdi.explorer.arkiv.network"
BOT, EVENT, DEATH = "parable.bot", "parable.event", "parable.death"
DAY = 86400
EVENT_LIFETIME = 30 * DAY
DEATH_LIFETIME = 180 * DAY  # about the longest an Arkiv entity may live (182.5 days)
READ_CACHE_S = 8  # the dashboard asks often; Arkiv's public endpoint allows few requests per second
READ_TIMEOUT_S, WRITE_TIMEOUT_S = 20, 60


class ArkivError(RuntimeError):
    pass


class Bridge:
    """Plain HTTP calls to the local arkiv-bridge. Swapped for a fake in tests."""

    def __init__(self, url: str, token: str = ""):
        self.url = url.rstrip("/")
        self.token = token or get_settings().arkiv_bridge_token  # shared password with the bridge (from .env)

    def call(self, method: str, path: str, payload: dict | None = None):
        try:
            timeout = READ_TIMEOUT_S if path in ("/query", "/health") else WRITE_TIMEOUT_S
            r = httpx.request(method, self.url + path, json=payload, timeout=timeout,
                              headers={"x-bridge-token": self.token})
        except httpx.HTTPError as err:
            raise ArkivError(f"arkiv-bridge not reachable at {self.url} (cd arkiv-bridge && npm start): {err}") from err
        if r.status_code != 200:
            raise ArkivError(f"arkiv-bridge {path}: {r.text}")
        return r.json()


# Attributes are sent as {name: [type, value]} so the bridge knows each column's Arkiv type.
def _s(v: str) -> list:
    return ["str", v]


def _n(type_name: str, v: int) -> list:
    return [type_name, str(v)]


def _creator(creator_id: str) -> str:
    return creator_id.lower()  # World ids are hex; lowercase so filters always match


class ArkivStore:
    def __init__(self, bridge: Bridge, writer: str = "", vault: str = ""):
        self.bridge = bridge
        self._writer = writer
        self.vault = vault.lower()  # empty = no vault filter (unit tests)
        self.last_tx = ""
        self._cache: dict[str, tuple[float, list]] = {}
        self._cache_lock = threading.Lock()

    def _scoped(self, attrs: dict) -> dict:
        return {**attrs, "vault": _s(self.vault)} if self.vault else attrs

    def writer(self) -> str:
        """The one wallet whose rows we trust. Raises if we cannot find out which it is."""
        if not self._writer:
            self._writer = self.bridge.call("GET", "/health").get("writer", "")
        if not self._writer:
            raise ArkivError("no trusted Arkiv writer address (start arkiv-bridge or set ARKIV_WRITER_ADDRESS)")
        return self._writer

    def _query(self, schema: str, **where: list) -> list[dict]:
        owner = self.writer()  # always filter by owner: never read other people's rows
        filters = self._scoped({k: v for k, v in where.items() if v is not None})
        payload = {"schema": schema, "where": filters, "owner": owner}
        cache_key = json.dumps(payload, sort_keys=True)
        with self._cache_lock:
            hit = self._cache.get(cache_key)
        if hit and time.monotonic() - hit[0] < READ_CACHE_S:
            return hit[1]
        rows = self.bridge.call("POST", "/query", payload)
        with self._cache_lock:
            self._cache[cache_key] = (time.monotonic(), rows)
        return rows

    def _forget_reads(self) -> None:
        with self._cache_lock:
            self._cache.clear()

    def _create(self, schema: str, attrs: dict, seconds: int, body: str, readonly: bool = False) -> str:
        out = self.bridge.call("POST", "/entities", {
            "schema": schema, "attributes": self._scoped(attrs), "expiresInSeconds": seconds, "body": body,
            "readonly": readonly,
        })
        self._forget_reads()  # a write makes cached reads stale
        self.last_tx = out["txHash"]
        return out["key"]

    # -- writes

    def put_bot(self, rec: BotRecord, lease_seconds: int) -> str:
        """Alive bots expire with their lease (+1h grace), while rebuilt dead bots keep their full grave lifetime."""
        attrs = {
            "bot_id": _n("u256", rec.bot_id), "bot_address": ["addr", rec.bot_address],
            "creator_id": _s(_creator(rec.creator_id)), "ens_name": _s(rec.ens_name),
            "strategy": _s(rec.strategy), "brain": _s(rec.rules.brain), "status": _s(rec.status),
            "born_at": _n("u64", rec.born_at), "vault_tx": _s(rec.born_tx.lower()),
        }
        ttl = lease_seconds + 3600 if rec.status == "alive" else min(lease_seconds, DEATH_LIFETIME)
        return self._create(BOT, attrs, ttl, rec.model_dump_json())

    def put_event(self, ev: BotEvent) -> str:
        attrs = {"bot_id": _n("u256", ev.bot_id), "kind": _s(ev.kind), "at": _n("u64", ev.at)}
        if ev.tx_hash:  # rejected trades never reach the chain, so they have no tx
            attrs["vault_tx"] = _s(ev.tx_hash.lower())
        return self._create(EVENT, attrs, EVENT_LIFETIME, ev.model_dump_json(), readonly=True)

    def put_death(self, d: DeathRecord, creator_id: str | None = None, strategy: str | None = None,
                  brain: str | None = None) -> str:
        """Write the grave (read-only, long-lived), then mark the bot entity dead and keep it around."""
        bot = self._bot_row(d.bot_id)
        if bot is not None:
            creator_id = creator_id or bot["attributes"]["creator_id"]
            strategy = strategy or bot["attributes"]["strategy"]
            brain = brain or bot["attributes"].get("brain")
        if not creator_id or not strategy:
            raise ArkivError(f"bot {d.bot_id}: creator_id/strategy unknown (bot entity gone); pass them in")
        attrs = {
            "bot_id": _n("u256", d.bot_id), "creator_id": _s(_creator(creator_id)), "strategy": _s(strategy),
            "brain": _s(brain or "rule"), "cause": _s(d.cause), "pnl_bps": _n("i32", d.pnl_bps), "lifetime_s": _n("u64", d.lifetime_s),
            "vault_tx": _s(d.tx_hash.lower()),
        }
        key = self._create(DEATH, attrs, DEATH_LIFETIME, d.model_dump_json(), readonly=True)
        if bot is not None and bot["attributes"].get("status") != "dead":
            self._mark_dead(bot)
        return key

    def _bot_row(self, bot_id: int) -> dict | None:
        rows = self._query(BOT, bot_id=_n("u256", bot_id))
        return rows[0] if rows else None

    def _mark_dead(self, bot_row: dict) -> None:
        rec = BotRecord.model_validate_json(bot_row["body"]).model_copy(update={"status": "dead"})
        self.bridge.call("POST", "/patch", {
            "schema": BOT, "key": bot_row["key"], "attributes": {"status": _s("dead")},
            "body": rec.model_dump_json(), "extendSeconds": DEATH_LIFETIME,
        })
        self._forget_reads()

    # -- reads

    def bots(self, creator_id: str | None = None, status: str | None = None) -> list[BotRecord]:
        rows = self._query(
            BOT,
            creator_id=_s(_creator(creator_id)) if creator_id else None,
            status=_s(status) if status else None,
        )
        return [BotRecord.model_validate_json(r["body"]) for r in rows]

    def _deaths(self, creator_id: str | None = None, strategy: str | None = None,
                brain: str | None = None) -> list[DeathRecord]:
        rows = self._query(
            DEATH,
            creator_id=_s(_creator(creator_id)) if creator_id else None,
            strategy=_s(strategy) if strategy else None,
            brain=_s(brain) if brain else None,
        )
        return [DeathRecord.model_validate_json(r["body"]) for r in rows]

    def graveyard(self, creator_id: str) -> list[DeathRecord]:
        return sorted(self._deaths(creator_id=creator_id), key=lambda d: d.bot_id)

    def events(self, bot_id: int) -> list[BotEvent]:
        """One bot's timeline (birth, trades, blocked trades, death), newest first."""
        rows = self._query(EVENT, bot_id=_n("u256", bot_id))
        return sorted((BotEvent.model_validate_json(r["body"]) for r in rows), key=lambda e: e.at, reverse=True)

    def report_by_brain(self) -> dict[str, dict]:
        """Report-card numbers for every brain from just TWO queries (all bots, all deaths), grouped here."""
        bots = [BotRecord.model_validate_json(r["body"]) for r in self._query(BOT)]
        deaths = self._deaths()
        brain_of = {b.bot_id: b.rules.brain for b in bots}
        groups: dict[str, dict] = defaultdict(lambda: {"bots": [], "deaths": []})
        for b in bots:
            groups[b.rules.brain]["bots"].append(b)
        for d in deaths:
            groups[brain_of.get(d.bot_id, "unknown")]["deaths"].append(d)
        return {brain: _card_numbers(g["bots"], g["deaths"]) for brain, g in groups.items()}

    def report_card(
        self, creator_id: str | None = None, strategy: str | None = None, vault_count: int | None = None,
        brain: str | None = None,
    ) -> ReportCard:
        """Counted from ALL bot and death rows, graveyard included.

        `vault_count` is the vault's own count of bots for the same subject; without it
        vault_count_matches is False, because we never claim a check we did not do.
        """
        c = _creator(creator_id) if creator_id else None
        bot_rows = self._query(BOT, creator_id=_s(c) if c else None, strategy=_s(strategy) if strategy else None,
                               brain=_s(brain) if brain else None)
        bots = [BotRecord.model_validate_json(r["body"]) for r in bot_rows]
        deaths = self._deaths(creator_id=c, strategy=strategy, brain=brain)

        nums = _card_numbers(bots, deaths)
        return ReportCard(
            subject=creator_id or (f"strategy:{strategy}" if strategy else f"brain:{brain}" if brain else "all"),
            **nums, vault_count_matches=vault_count is not None and vault_count == nums["launched"],
        )


def _card_numbers(bots: list[BotRecord], deaths: list[DeathRecord]) -> dict:
    """Counted from ALL bot and death rows, graveyard included (a bot counts once even if it has both)."""
    dead_ids = {d.bot_id for d in deaths} | {b.bot_id for b in bots if b.status == "dead"}
    all_ids = {b.bot_id for b in bots} | dead_ids
    pnls = [d.pnl_bps for d in deaths]
    return {
        "launched": len(all_ids),
        "alive": len({b.bot_id for b in bots if b.status == "alive"} - dead_ids),
        "dead": len(dead_ids),
        "profitable": sum(1 for p in pnls if p > 0),
        "worst_pnl_bps": min(pnls, default=0),
        "avg_pnl_bps": sum(pnls) / len(pnls) if pnls else 0.0,
    }


# ---- module-level functions (INTERFACES.md)

_store: ArkivStore | None = None


def default_store() -> ArkivStore:
    global _store
    if _store is None:
        s = get_settings()
        _store = ArkivStore(Bridge(s.arkiv_bridge_url), writer=s.arkiv_writer_address, vault=s.vault_address)
    return _store


def put_bot(rec: BotRecord, lease_seconds: int) -> str:
    return default_store().put_bot(rec, lease_seconds)


def put_event(ev: BotEvent) -> str:
    return default_store().put_event(ev)


def put_death(d: DeathRecord, creator_id: str | None = None, strategy: str | None = None, brain: str | None = None) -> str:
    return default_store().put_death(d, creator_id, strategy, brain)


def graveyard(creator_id: str) -> list[DeathRecord]:
    return default_store().graveyard(creator_id)


def bots(creator_id: str | None = None, status: str | None = None) -> list[BotRecord]:
    return default_store().bots(creator_id, status)


def report_card(creator_id: str | None = None, strategy: str | None = None, vault_count: int | None = None,
                brain: str | None = None) -> ReportCard:
    return default_store().report_card(creator_id, strategy, vault_count, brain)


def events(bot_id: int) -> list[BotEvent]:
    return default_store().events(bot_id)


def report_by_brain() -> dict[str, dict]:
    return default_store().report_by_brain()


def all_graves() -> list[DeathRecord]:
    """Every grave this vault ever produced, any creator (the 'All graves on Arkiv' view)."""
    return sorted(default_store()._deaths(), key=lambda d: d.bot_id)
