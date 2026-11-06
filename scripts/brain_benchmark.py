"""Runs every configured brain on the same 6 fixed market scenarios and prints one comparison table.

Run:  cd engine && uv run python ../scripts/brain_benchmark.py
Uses the real APIs for AI brains (costs a few tiny calls). Keys are read from the repo-root .env
through settings and are never printed. A failed answer (error, garbage, rate limit) counts as a fallback.
"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

from parable import bot_runner as B  # noqa: E402

USD = 10**6
# Each scenario: ETH price history in dollars, and cash in dollars. (Max trade is $20, equity $100.)
SCENARIOS = {
    "steady rise": ([3000, 3030, 3060, 3090, 3120, 3150], 100),
    "steady fall": ([3150, 3120, 3090, 3060, 3030, 3000], 100),
    "sharp dip": ([3000, 3010, 3000, 3005, 2850, 2800], 100),
    "flat": ([3000, 3001, 2999, 3000, 3001, 3000], 100),
    "spike then crash": ([3000, 3050, 3300, 3500, 3200, 2900], 100),
    "low cash": ([3000, 3030, 3060, 3090, 3120, 3150], 2),
}


def make_state(prices: list[float], cash: float) -> dict:
    history = [int(p * 10**8) for p in prices]
    return {"strategy": "momentum", "history": history, "price": history[-1], "cash_usd": int(cash * USD),
            "eth_wei": 0, "equity_usd": int(cash * USD), "max_trade_usd": 20 * USD, "max_loss_bps": 1000}


def short_error(err: Exception) -> str:
    """A few characters saying why an answer failed (HTTP status, timeout, or bad reply)."""
    if isinstance(err, httpx.HTTPStatusError):
        return f"HTTP{err.response.status_code}"
    return "timeout" if isinstance(err, httpx.TimeoutException) else type(err).__name__


def run_brain(name: str, entry: dict) -> dict:
    """Ask one brain every scenario. We call the brain directly (not decide) so failures stay visible."""
    out = {"brain": name, "valid": 0, "fallbacks": 0, "rate_limited": 0, "seconds": [], "answers": []}
    for prices, cash in SCENARIOS.values():
        start = time.time()
        try:
            d = entry["decide"](make_state(prices, cash))
            out["valid"] += 1
            out["answers"].append(f"{d.action}{'' if d.action == 'hold' else ' $%g' % (d.amount_usd / USD)}")
        except Exception as err:
            out["fallbacks"] += 1
            limited = isinstance(err, httpx.HTTPStatusError) and err.response.status_code == 429
            out["rate_limited"] += limited
            out["answers"].append("429" if limited else short_error(err))
        out["seconds"].append(time.time() - start)
    return out


def main() -> None:
    brains = {n: b for n, b in B.build_brains().items() if b["ready"]}
    print(f"Brains: {', '.join(brains)}\nScenarios: {', '.join(SCENARIOS)}\n")
    with ThreadPoolExecutor(max_workers=len(brains)) as pool:  # brains run side by side; scenarios in order
        results = list(pool.map(lambda kv: run_brain(*kv), brains.items()))
    print(f"{'brain':<36}{'valid':>6}{'fallbk':>7}{'429s':>5}{'avg s':>7}   decisions")
    for r in results:
        avg = sum(r["seconds"]) / len(r["seconds"])
        print(f"{r['brain']:<36}{r['valid']:>4}/6{r['fallbacks']:>7}{r['rate_limited']:>5}{avg:>7.1f}   "
              + " | ".join(r["answers"]))


if __name__ == "__main__":
    main()
