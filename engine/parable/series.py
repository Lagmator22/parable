"""Live graph data. Every few seconds we write down, for each running bot, two numbers:
- what the VAULT says it is worth (cash + ETH at the Chainlink price): the official score;
- what its holdings are worth at the LIVE MARKET price (Coinbase, Binance as backup), so the lines move
  between Chainlink's hourly testnet updates. Labelled as such on the page; it never changes any score.
Kept in memory only, so the graphs start fresh when the server restarts.
"""

import logging
import threading
import time

import httpx

log = logging.getLogger("parable.series")
KEEP_POINTS = 720  # 2 hours at one sample every 10 s
SOURCES = (
    ("https://api.coinbase.com/v2/prices/ETH-USD/spot", lambda j: float(j["data"]["amount"])),
    ("https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT", lambda j: float(j["price"])),
)


def market_eth_usd() -> float | None:
    """The live ETH price in dollars from a public exchange API, or None if none answers."""
    for url, read in SOURCES:
        try:
            return read(httpx.get(url, timeout=5).json())
        except Exception:
            continue
    return None


def bps(value: float, start: float) -> int:
    return int((value - start) * 10000 // start) if start else 0


class Recorder:
    def __init__(self, launcher, swarm_ids=lambda: [], every_s: float = 10, price_source=market_eth_usd):
        self.launcher, self.swarm_ids, self.every_s, self.price_source = launcher, swarm_ids, every_s, price_source
        self.prices: list[list] = []  # [time, market dollars or None, chainlink dollars or None]
        self.bots: dict[int, dict] = {}
        self.lock = threading.Lock()

    def sample(self) -> None:
        now = int(time.time())
        market = self.price_source()
        try:
            chain = self.launcher.b.vault.price() / 1e8  # Chainlink answers with 8 decimals
        except Exception:
            chain = None
        with self.lock:
            self.prices = (self.prices + [[now, market, chain]])[-KEEP_POINTS:]
        swarm = set(self.swarm_ids())
        for bot_id, live in list(self.launcher.live.items()):
            row = self.bots.setdefault(bot_id, {"bot_id": bot_id, "ens_name": live.record.ens_name,
                                                "brain": live.record.rules.brain, "strategy": live.record.strategy,
                                                "points": []})
            row["swarm"], row["status"] = bot_id in swarm, "dead" if live.dead else "alive"
            if live.dead:
                continue  # its line simply ends where it died
            try:
                self._add_point(row, live, now, market)
            except Exception:
                log.debug("could not sample bot %s", bot_id)

    def _add_point(self, row: dict, live, now: int, market: float | None) -> None:
        start = live.record.rules.start_cash_usd
        vault_value = self.launcher.b.vault.equity(live.record.bot_id)
        info = self.launcher.b.vault.get_bot(live.record.bot_id)
        cash, eth_wei = info.get("cashUsd"), info.get("ethWei")
        # Holdings at the market price: cash (6 decimals) + ETH (18 decimals) x dollars per ETH.
        market_value = cash + eth_wei / 1e18 * market * 1e6 if market and cash is not None else vault_value
        with self.lock:
            row["points"] = (row["points"] + [[now, bps(vault_value, start), bps(market_value, start)]])[-KEEP_POINTS:]

    def to_dict(self) -> dict:
        with self.lock:
            return {"every_s": self.every_s, "prices": list(self.prices),
                    "bots": [dict(r, points=list(r["points"])) for r in self.bots.values()]}

    def start(self) -> None:
        def loop():
            while True:
                try:
                    self.sample()
                except Exception:
                    log.exception("graph sample failed")
                time.sleep(self.every_s)

        threading.Thread(target=loop, daemon=True).start()
