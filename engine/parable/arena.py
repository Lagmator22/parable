"""Market Arena: a practice simulator, separate from the real vault.
Runs a cohort of Parable bots head-to-head across realistic crypto market regimes (or live Binance ETH/USDT
candles) using the exact ParableVault rules: ENS badge checks, per-trade limits, high-water-mark equity
drawdown, and automatic vault kill (`loss_limit`) when a bot loses more than its allowed drawdown.
"""

import time

import httpx
from eth_account import Account

from parable.bot_runner import GOOGLE_BASE, code_fingerprint, decide, extract_json
from parable.config import get_settings
from parable.fake_chain import FakeEns, FakeVault
from parable.models import BotRules

BENCHMARKS = [
    {"name": "Parable Arena", "focus": "ENSv2 badges, vault-enforced loss limits and a permanent Arkiv graveyard, in a simulated market."},
]

SCENARIOS: dict[str, dict] = {
    "flash_crash": {
        "id": "flash_crash",
        "title": "Flash Crash (-18% Stress Test)",
        "subtitle": "ETH plunges from $2,500 to $2,050 (-18%). Aggressive dip-buyers breach the 8% max loss limit and get auto-killed by the Vault.",
        "prices_usd": [2500.0, 2450.0, 2320.0, 2180.0, 2050.0, 2110.0],
    },
    "bull_breakout": {
        "id": "bull_breakout",
        "title": "ETF Bull Breakout (+16% Rally)",
        "subtitle": "ETH rallies from $2,300 to $2,670 (+16%). Momentum and Gemini brains accumulate ETH early and finish profitable.",
        "prices_usd": [2300.0, 2345.0, 2430.0, 2540.0, 2670.0, 2655.0],
    },
    "whipsaw_chop": {
        "id": "whipsaw_chop",
        "title": "Liquidity Whipsaw (±12% Chop)",
        "subtitle": "Sharp fakeouts ($2,400 → $2,550 → $2,220 → $2,460 → $2,090) punish over-trading bots and trigger Vault loss kills.",
        "prices_usd": [2400.0, 2550.0, 2220.0, 2460.0, 2090.0, 2150.0],
    },
    "live_binance": {
        "id": "live_binance",
        "title": "Live Binance ETH/USDT Stream (15x Stress)",
        "subtitle": "Fetches real ETH/USDT 1m candles from Binance and amplifies tick moves 15x to stress-test bots in seconds.",
        "prices_usd": [],
    },
}

CONTENDERS = [
    {"label": "Gemini 3.5 Flash-Lite · Momentum", "brain": "gemini:gemini-3.5-flash-lite", "strategy": "momentum"},
    {"label": "Gemini 3.5 Flash-Lite · Dip Buyer", "brain": "gemini:gemini-3.5-flash-lite", "strategy": "dip_buyer"},
    {"label": "Rule Baseline · Dip Buyer", "brain": "rule", "strategy": "dip_buyer"},
    {"label": "Rule Baseline · YOLO (+ Rogue Attack)", "brain": "rule", "strategy": "yolo", "rogue_round": 2},
]


def fetch_binance_tape(base_price: float = 2240.0) -> list[float]:
    """Fetch 6 recent 1-minute ETH/USDT closes from Binance and amplify deltas 15x for a fast stress test."""
    try:
        r = httpx.get("https://api.binance.com/api/v3/klines",
                      params={"symbol": "ETHUSDT", "interval": "1m", "limit": 6}, timeout=3.0)
        r.raise_for_status()
        closes = [float(row[4]) for row in r.json()]
        if len(closes) >= 4:
            p0 = closes[0]
            return [round(max(500.0, p0 + (c - p0) * 15.0), 2) for c in closes]
    except Exception:
        pass
    return [round(base_price * f, 2) for f in (1.0, 0.985, 0.94, 0.89, 0.92, 0.95)]


def _fast_ai_or_rule(state: dict, brain: str, use_live_llm: bool) -> tuple[str, int, str]:
    """Decide (action, amount_usd, reason). Uses real Gemini when requested, or fast deterministic logic on startup."""
    s = get_settings()
    if use_live_llm and brain.startswith("gemini:") and s.gemini_api_key:
        try:
            model = brain.split(":", 1)[1]
            prices = [round(p / 1e8, 2) for p in state["history"]]
            prompt = (
                f"ETH prices (oldest first): {prices}. Strategy: {state['strategy']}. "
                f"Cash: ${state['cash_usd']/1e6:.0f}, ETH: {state['eth_wei']/1e18:.4f}, Max trade: $45. "
                'Reply ONLY JSON: {"action":"buy"|"sell"|"hold","amount_dollars":45,"reason":"<under 12 words>"}'
            )
            r = httpx.post(f"{GOOGLE_BASE}/chat/completions", timeout=4.0,
                           headers={"Authorization": f"Bearer {s.gemini_api_key}"},
                           json={"model": model, "messages": [{"role": "user", "content": prompt}]})
            r.raise_for_status()
            obj = extract_json(r.json()["choices"][0]["message"]["content"])
            act = str(obj.get("action", "hold"))
            if act in ("buy", "sell", "hold"):
                amt = min(round(float(obj.get("amount_dollars", 45)) * 1_000_000), state["max_trade_usd"])
                return act, amt, str(obj.get("reason") or "Gemini signal")[:80]
        except Exception:
            pass
    d = decide(state, "rule")
    tag = "Gemini Flash-Lite" if brain.startswith("gemini:") else "Rule engine"
    return d.action, d.amount_usd, f"{tag}: {d.reason}"


class MarketArena:
    def __init__(self):
        self.last_run: dict | None = None

    def get_or_run(self) -> dict:
        if self.last_run is None:
            self.last_run = self.run("flash_crash", use_live_llm=False)
        return self.last_run

    def run(self, scenario_id: str = "flash_crash", use_live_llm: bool = True) -> dict:
        scen = SCENARIOS.get(scenario_id) or SCENARIOS["flash_crash"]
        tape = fetch_binance_tape() if scen["id"] == "live_binance" else list(scen["prices_usd"])
        ens = FakeEns()
        vault = FakeVault(ens)
        current_p8 = [round(tape[0] * 1e8)]
        vault.price = lambda: current_p8[0]

        bots_meta = []
        for idx, spec in enumerate(CONTENDERS, start=1):
            rules = BotRules(strategy=spec["strategy"], brain=spec["brain"],
                             start_cash_usd=100_000_000, max_trade_usd=45_000_000,
                             max_loss_bps=800, lease_seconds=3600)
            wallet = Account.create()
            fp = code_fingerprint(rules)
            ens_name, node = ens.issue_badge(f"arena-{idx}", wallet.address, int(time.time()) + 3600,
                                             {"strategy": rules.strategy, "brain": rules.brain, "code_hash": fp})
            bot_id, _ = vault.register_bot(
                bot_address=wallet.address, creator_id="0xarena", creator_wallet="0x1111111111111111111111111111111111111111",
                badge_node=node, expires_at=int(time.time()) + 3600, start_cash_usd=rules.start_cash_usd,
                max_trade_usd=rules.max_trade_usd, max_loss_bps=rules.max_loss_bps, strategy_id=rules.strategy,
            )
            bots_meta.append({
                "bot_id": bot_id, "key": "0x" + wallet.key.hex().removeprefix("0x"),
                "label": spec["label"], "ens_name": ens_name,
                "brain": spec["brain"], "strategy": spec["strategy"],
                "code_hash": fp, "rogue_round": spec.get("rogue_round"),
                "history": [current_p8[0]], "steps": [],
            })

        for round_idx, price_usd in enumerate(tape[1:], start=1):
            p8 = round(price_usd * 1e8)
            current_p8[0] = p8
            for b in bots_meta:
                bid = b["bot_id"]
                raw = vault.bots[bid]
                if raw["status"] != "alive":
                    continue
                b["history"].append(p8)
                eq_before = vault.equity(bid)
                loss_bps = (raw["hwm"] - eq_before) * 10000 // raw["hwm"] if eq_before < raw["hwm"] else 0
                if loss_bps >= raw["max_loss"]:
                    vault.check_and_revoke(bid)
                    b["steps"].append({"round": round_idx, "price_usd": price_usd, "action": "killed_by_vault",
                                       "equity_usd": eq_before, "pnl_bps": (eq_before - 100_000_000) * 10000 // 100_000_000,
                                       "note": f"🪦 Vault checkAndRevoke: drawdown -{loss_bps/100:.1f}% breached -8.0% max loss limit"})
                    continue
                if b["rogue_round"] == round_idx:
                    try:
                        vault.trade(b["key"], bid, True, 150_000_000)
                    except Exception as err:
                        reason = vault.decode_revert(err)
                        b["steps"].append({"round": round_idx, "price_usd": price_usd, "action": "blocked",
                                           "equity_usd": eq_before, "pnl_bps": (eq_before - 100_000_000) * 10000 // 100_000_000,
                                           "note": f"🛡️ Tried rogue $150 trade -> Vault blocked ({reason})"})
                state = {
                    "strategy": b["strategy"], "history": b["history"], "price": p8,
                    "cash_usd": raw["cash"], "eth_wei": raw["eth"], "equity_usd": eq_before,
                    "max_trade_usd": raw["max_trade"], "max_loss_bps": raw["max_loss"],
                }
                act, amt, note = _fast_ai_or_rule(state, b["brain"], use_live_llm and round_idx <= 2)
                if act != "hold" and amt > 0:
                    have = raw["cash"] if act == "buy" else (raw["eth"] * p8 // 10**20)
                    amt = min(amt, raw["max_trade"], have)
                if act in ("buy", "sell") and amt > 0:
                    try:
                        vault.trade(b["key"], bid, act == "buy", amt)
                    except Exception as err:
                        act, note = "blocked", f"Vault blocked: {vault.decode_revert(err)}"
                else:
                    act = "hold"
                after = vault.get_bot(bid)
                eq_after = after["finalEquityUsd"] if after["status"] == "dead" else vault.equity(bid)
                pnl_bps = (eq_after - 100_000_000) * 10000 // 100_000_000
                if after["status"] == "dead":
                    b["steps"].append({"round": round_idx, "price_usd": price_usd, "action": "killed_by_vault",
                                       "equity_usd": eq_after, "pnl_bps": pnl_bps,
                                       "note": "🪦 Auto-killed by Vault after trade breached -8.0% loss limit"})
                else:
                    b["steps"].append({"round": round_idx, "price_usd": price_usd, "action": act,
                                       "amount_usd": amt if act in ("buy", "sell") else 0,
                                       "equity_usd": eq_after, "pnl_bps": pnl_bps, "note": note})

        results = []
        for b in bots_meta:
            bid = b["bot_id"]
            raw = vault.bots[bid]
            info = vault.get_bot(bid)
            eq = info["finalEquityUsd"] if info["status"] == "dead" else vault.equity(bid)
            pnl_bps = (eq - 100_000_000) * 10000 // 100_000_000
            results.append({
                "bot_id": bid, "label": b["label"], "ens_name": b["ens_name"],
                "brain": b["brain"], "strategy": b["strategy"], "code_hash": b["code_hash"],
                "status": info["status"], "cause": info["cause"] if info["status"] == "dead" else None,
                "final_equity_usd": eq, "hwm_usd": raw["hwm"], "pnl_bps": pnl_bps,
                "trades": sum(1 for s in b["steps"] if s["action"] in ("buy", "sell")),
                "blocked": sum(1 for s in b["steps"] if s["action"] == "blocked"),
                "steps": b["steps"],
            })
        results.sort(key=lambda r: r["pnl_bps"], reverse=True)
        self.last_run = {
            "ran_at": int(time.time()),
            "scenario": {**scen, "prices_usd": tape},
            "scenarios": [{"id": k, "title": v["title"], "subtitle": v["subtitle"]} for k, v in SCENARIOS.items()],
            "benchmarks": BENCHMARKS,
            "summary": {
                "launched": len(results),
                "survived": sum(1 for r in results if r["status"] == "alive"),
                "killed_by_vault": sum(1 for r in results if r["status"] == "dead"),
                "profitable": sum(1 for r in results if r["pnl_bps"] > 0),
                "best_pnl_bps": max(r["pnl_bps"] for r in results),
                "worst_pnl_bps": min(r["pnl_bps"] for r in results),
            },
            "contenders": results,
        }
        return self.last_run
