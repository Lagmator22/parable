"""An in-memory pretend blockchain (vault, ENS, Arkiv, bot loop) for PARABLE_OFFLINE=1 and for tests.
It follows the same rules as ParableVault.sol but nothing here is real: no chain, no money.
The dashboard shows an OFFLINE SIMULATION banner whenever this is used.
"""

import hashlib
import random
import time
from types import SimpleNamespace

from eth_account import Account

from parable.models import ReportCard


class FakeRevert(Exception):
    """Plays the role of a Solidity custom error; the message is the error name."""


def fake_tx() -> str:
    return "0x" + random.getrandbits(256).to_bytes(32, "big").hex()


class FakeEns:
    def __init__(self):
        self.badges: dict[str, dict] = {}  # node -> {name, bot, revoked}

    def issue_badge(self, label, bot_address, expires_at, records):
        name = f"{label}.parable.eth"
        node = "0x" + hashlib.sha256(name.encode()).hexdigest()
        self.badges[node] = {"name": name, "bot": bot_address, "revoked": False}
        return name, node

    def is_valid(self, name: str, bot: str) -> bool:
        return any(b["name"] == name and b["bot"] == bot and not b["revoked"] for b in self.badges.values())

    def revoke_badge(self, name: str) -> str:
        for b in self.badges.values():
            b["revoked"] |= b["name"] == name
        return fake_tx()


class FakeVault:
    """Same rules as the real vault. Price is a seeded random walk that moves every 3 seconds."""

    def __init__(self, ens: FakeEns, seed: int = 7):
        self.ens, self.bots, self.start = ens, {}, time.time()
        self.rng, self.prices = random.Random(seed), [3000 * 10**8]

    def price(self) -> int:  # ETH/USD with 8 decimals, like Chainlink
        step = int((time.time() - self.start) / 3)
        while len(self.prices) <= step:
            self.prices.append(int(self.prices[-1] * (1 + self.rng.uniform(-0.03, 0.03))))
        return self.prices[step]

    def fund_gas(self, address: str) -> str:
        return fake_tx()

    def register_bot(self, bot_address, creator_id, creator_wallet, badge_node, expires_at,
                     start_cash_usd, max_trade_usd, max_loss_bps, strategy_id):
        for b in self.bots.values():  # one World identity <-> one wallet, in both directions
            if (b["creator_id"] == creator_id) != (b["creator_wallet"] == creator_wallet):
                raise FakeRevert("CreatorIdentityMismatch")
        bot_id = len(self.bots) + 1
        self.bots[bot_id] = dict(bot=bot_address, creator_id=creator_id, creator_wallet=creator_wallet,
                                 node=badge_node, expires_at=expires_at, cash=start_cash_usd, eth=0,
                                 hwm=start_cash_usd, max_trade=max_trade_usd, max_loss=max_loss_bps,
                                 status="alive", cause=None, final=None, died_at=None)
        return bot_id, fake_tx()

    def equity(self, bot_id: int) -> int:
        b = self.bots[bot_id]  # eth has 18 decimals, price 8, USD 6: divide by 10**20
        return b["final"] if b["status"] == "dead" else b["cash"] + b["eth"] * self.price() // 10**20

    def trade(self, bot_key, bot_id, buy, amount_usd):
        b = self.bots.get(bot_id)
        if b is None or Account.from_key(bot_key).address != b["bot"]:
            raise FakeRevert("NotBot")
        if b["status"] != "alive":
            raise FakeRevert("NotAlive")
        if time.time() >= b["expires_at"]:
            raise FakeRevert("Expired")
        badge = self.ens.badges[b["node"]]
        if badge["revoked"]:
            raise FakeRevert("BadgeInvalid")
        if amount_usd > b["max_trade"]:
            raise FakeRevert("OverTradeLimit")
        eth_wei = amount_usd * 10**20 // self.price()
        if (buy and amount_usd > b["cash"]) or (not buy and eth_wei > b["eth"]):
            raise FakeRevert("InsufficientBalance")
        sign = 1 if buy else -1
        b["cash"] -= sign * amount_usd
        b["eth"] += sign * eth_wei
        b["hwm"] = max(b["hwm"], self.equity(bot_id))
        if self._over_limit(bot_id):
            self._die(bot_id, 3)
        return fake_tx()

    def _over_limit(self, bot_id: int) -> bool:
        b = self.bots[bot_id]
        return (b["hwm"] - self.equity(bot_id)) * 10000 // b["hwm"] >= b["max_loss"]

    def _die(self, bot_id: int, cause: int) -> str:
        b = self.bots[bot_id]
        b["final"] = self.equity(bot_id)  # measured before the status flips
        b.update(status="dead", cause=cause, died_at=int(time.time()))
        self.ens.badges[b["node"]]["revoked"] = True  # the real vault revokes the badge on death
        return fake_tx()

    def _require(self, bot_id: int, ok: bool, error: str) -> None:
        if self.bots[bot_id]["status"] != "alive" or not ok:
            raise FakeRevert(error)

    def check_and_revoke(self, bot_id: int) -> str:
        self._require(bot_id, self._over_limit(bot_id), "NotOverLimit")
        return self._die(bot_id, 3)

    def kill(self, bot_id: int) -> str:
        self._require(bot_id, True, "NotAlive")
        return self._die(bot_id, 2)

    def expire(self, bot_id: int) -> str:
        self._require(bot_id, time.time() >= self.bots[bot_id]["expires_at"], "NotExpired")
        return self._die(bot_id, 1)

    def get_bot(self, bot_id: int) -> dict:
        b = self.bots[bot_id]
        cause = ["none", "expired", "killed", "loss_limit"][b["cause"] or 0]  # same names as vault.py
        return {"status": b["status"], "cause": cause, "finalEquityUsd": b["final"], "diedAt": b["died_at"]}

    def total_born(self) -> int:
        return len(self.bots)

    def counts(self, creator_id: str) -> tuple[int, int]:
        mine = [b for b in self.bots.values() if b["creator_id"] == creator_id]
        return len(mine), sum(b["status"] == "dead" for b in mine)

    def decode_revert(self, err: Exception) -> str:
        return str(err)


class FakeArkiv:
    def __init__(self):
        self.records, self.event_log, self.deaths = [], [], []  # deaths: (DeathRecord, creator_id, strategy)

    def put_bot(self, rec, lease_seconds):
        self.records.append(rec)
        return f"fake-key-{rec.bot_id}"

    def put_event(self, ev):
        self.event_log.append(ev)
        return f"fake-event-{len(self.event_log)}"

    def put_death(self, d, creator_id=None, strategy=None, brain=None):
        self.deaths.append((d, creator_id, strategy))
        for r in self.records:
            if r.bot_id == d.bot_id:
                r.status = "dead"
        return f"fake-death-{d.bot_id}"

    def all_graves(self):
        return sorted((d for d, _, _ in self.deaths), key=lambda d: d.bot_id)

    def graveyard(self, creator_id):
        return [d for d, cid, _ in self.deaths if cid == creator_id]

    def _deaths(self):
        return [d for d, _, _ in self.deaths]

    def bots(self, creator_id=None, status=None):
        return [r for r in self.records if creator_id in (None, r.creator_id) and status in (None, r.status)]

    def events(self, bot_id):
        return sorted((e for e in self.event_log if e.bot_id == bot_id), key=lambda e: e.at, reverse=True)

    def report_by_brain(self):
        out = {}
        for brain in {r.rules.brain for r in self.records}:
            card = self.report_card(brain=brain).model_dump()
            out[brain] = {k: card[k] for k in ("launched", "alive", "dead", "profitable", "worst_pnl_bps", "avg_pnl_bps")}
        return out

    def report_card(self, creator_id=None, strategy=None, brain=None):
        mine = [r for r in self.records if creator_id in (None, r.creator_id) and strategy in (None, r.strategy)
                and brain in (None, r.rules.brain)]
        pnls = [d.pnl_bps for d, _, _ in self.deaths if d.bot_id in {r.bot_id for r in mine}]
        return ReportCard(subject=creator_id or strategy or (f"brain:{brain}" if brain else "all"), launched=len(mine),
                          alive=sum(r.status == "alive" for r in mine), dead=len(pnls),
                          profitable=sum(p > 0 for p in pnls), worst_pnl_bps=min(pnls, default=0),
                          avg_pnl_bps=sum(pnls) / len(pnls) if pnls else 0.0, vault_count_matches=True)


class FakeRunner:
    """Stands in for bot_runner: every few seconds makes a random-ish trade through the vault."""

    def __init__(self, vault: FakeVault, step_s: float = 2):
        self.vault, self.step_s = vault, step_s

    def run_bot(self, bot_id, bot_key, rules, stop_event, report):
        rng = random.Random(bot_id)
        while not stop_event.wait(self.step_s):
            buy, amount = rng.random() < 0.5, rules.max_trade_usd // 2
            try:
                tx = self.vault.trade(bot_key, bot_id, buy, amount)
                report("traded", {"action": "buy" if buy else "sell", "amount_usd": amount, "tx": tx})
            except FakeRevert as err:
                report("rejected", {"reason": str(err)})


def fake_backends(world) -> SimpleNamespace:
    ens = FakeEns()
    vault = FakeVault(ens)
    return SimpleNamespace(vault=vault, ens=ens, arkiv=FakeArkiv(), runner=FakeRunner(vault), world=world)
