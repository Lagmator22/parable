"""Arkiv spike: write a bot, a birth event and a death to the Rabdi testnet through arkiv-bridge,
then read the graveyard and report card back.

Run (two terminals):  cd arkiv-bridge && npm start      then      cd engine && uv run python ../scripts/arkiv_spike.py
If the writer wallet has no tGLM the script runs the read-only checks, prints the faucet step and exits 0.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

from parable import arkiv_store as A  # noqa: E402
from parable.models import BotEvent, BotRecord, BotRules, DeathRecord  # noqa: E402

FAUCET = "https://hub.arkiv.network/faucet"


def link(store: A.ArkivStore, label: str, key: str) -> None:
    print(f"{label:<7} entity {key}\n{'':<7} tx     {A.EXPLORER}/tx/{store.last_tx}")


def main() -> int:
    store = A.default_store()
    wallet = store.writer()  # raises if the bridge is down: we never run without a trusted writer
    print(f"writer wallet {wallet}  ({A.EXPLORER}/address/{wallet})")
    print(f"read check    {len(store.bots())} parable.bot rows owned by the writer")

    now = int(time.time())
    creator = "0x" + "ab" * 32  # stands in for a World nullifier
    bot_id = now % 1_000_000  # unique per run so reruns do not collide
    rules = BotRules(strategy="momentum", start_cash_usd=100_000_000, max_trade_usd=20_000_000, max_loss_bps=1000, lease_seconds=900)
    rec = BotRecord(bot_id=bot_id, bot_address=wallet, creator_id=creator, ens_name=f"spike-{bot_id}.parable.eth",
                    strategy="momentum", rules=rules, status="alive", born_at=now, born_tx="0x" + "11" * 32)
    try:
        link(store, "bot", store.put_bot(rec, rules.lease_seconds))
    except A.ArkivError as err:
        print(f"\nwrite failed: {err}")
        print(f"MANUAL STEP: fund {wallet} with tGLM at {FAUCET}, then re-run this script.")
        return 0

    link(store, "birth", store.put_event(BotEvent(bot_id=bot_id, kind="birth", at=now, tx_hash=rec.born_tx, data={})))
    death = DeathRecord(bot_id=bot_id, cause="loss_limit", final_equity_usd=88_000_000, start_cash_usd=100_000_000,
                        pnl_bps=-1200, lifetime_s=300, tx_hash="0x" + "22" * 32)
    link(store, "death", store.put_death(death))

    print("\n-- graveyard(creator) read back from Arkiv")
    for d in store.graveyard(creator):
        print(f"  bot {d.bot_id}: {d.cause}, pnl {d.pnl_bps} bps, vault tx {d.tx_hash}")
    print("\n-- report card")
    print(store.report_card(creator_id=creator).model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
