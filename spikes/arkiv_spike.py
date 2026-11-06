"""Arkiv spike: write a bot + birth event + death to the Rabdi testnet, then read the graveyard
and report card back.

Run:  cd engine && uv run python ../spikes/arkiv_spike.py

Without ARKIV_PRIVATE_KEY it generates a throwaway testnet key (saved to the gitignored
.env.arkiv-spike at the repo root), prints the address to fund at the faucet, runs the
read-only checks that need no funds, and exits 0.
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from eth_account import Account  # noqa: E402

from parable import arkiv_store as A  # noqa: E402
from parable.config import get_settings  # noqa: E402
from parable.models import BotEvent, BotRecord, BotRules, DeathRecord  # noqa: E402

FAUCET = "https://hub.arkiv.network/faucet"
ACCESS_KEYS = "https://hub.arkiv.network/access-keys"
KEYFILE = ROOT / ".env.arkiv-spike"  # matches .env.* in .gitignore


def load_key() -> tuple[str, bool]:
    s = get_settings()
    if s.arkiv_private_key:
        return s.arkiv_private_key, False
    if KEYFILE.exists():
        for line in KEYFILE.read_text().splitlines():
            if line.startswith("ARKIV_PRIVATE_KEY="):
                return line.split("=", 1)[1].strip(), False
    acct = Account.create()
    KEYFILE.write_text(f"ARKIV_PRIVATE_KEY={acct.key.hex()}\n")
    KEYFILE.chmod(0o600)
    return acct.key.hex(), True


def main() -> int:
    s = get_settings()
    key, generated = load_key()
    node = A.RpcNode(s.arkiv_rpc_url, key, s.arkiv_access_key)
    wallet = node.address
    print(f"RPC            {s.arkiv_rpc_url}  (chain id {node.w3.eth.chain_id})")
    print(f"writer wallet  {wallet}" + ("  (freshly generated)" if generated else ""))
    if not s.arkiv_access_key:
        print(f"note: no ARKIV_ACCESS_KEY, using the rate-limited public RPC. Free key: {ACCESS_KEYS}")

    # read-only checks that need no funds
    print(f"query works    {len(node.query('arkiv.schema = ' + A.q_str(A.SCHEMA_BOT)))} parable.bot entities on chain (any writer)")
    probe = [A.create_op([A.S("arkiv.schema", A.SCHEMA_BOT)], 100, 0)]
    node.simulate(probe, wallet)
    print("eth_call       create op simulates OK (encoding accepted by the node)")

    balance = node.w3.eth.get_balance(wallet)
    if balance == 0:
        print("\nMANUAL STEP NEEDED: the writer wallet has 0 tGLM.")
        print(f"  1. Open {FAUCET} and request tGLM for {wallet}")
        if generated or KEYFILE.exists():
            print(f"  2. Copy the key from {KEYFILE} into .env as ARKIV_PRIVATE_KEY (it is a throwaway testnet key)")
        print("  3. Re-run this script.")
        return 0

    print(f"balance        {node.w3.from_wei(balance, 'ether')} tGLM\n")
    store = A.ArkivStore(node)
    now = int(time.time())
    creator = "0x" + "ab" * 32  # stands in for a World nullifier
    rules = BotRules(strategy="momentum", start_cash_usd=100_000_000, max_trade_usd=20_000_000, max_loss_bps=1000, lease_seconds=900)
    bot_id = now % 1_000_000  # unique per run so reruns do not collide
    rec = BotRecord(
        bot_id=bot_id, bot_address=wallet, creator_id=creator, ens_name=f"spike-{bot_id}.parable.eth",
        strategy="momentum", rules=rules, status="alive", born_at=now, born_tx="0x" + "11" * 32,
    )

    def link(label: str, key: str) -> None:
        print(f"{label:<12} entity {key}\n{'':<12} tx     {A.EXPLORER}/tx/{store.last_tx}")

    link("bot", store.put_bot(rec, rec.rules.lease_seconds))
    link("birth", store.put_event(BotEvent(bot_id=bot_id, kind="birth", at=now, tx_hash=rec.born_tx, data={"strategy": "momentum"})))
    dead = DeathRecord(
        bot_id=bot_id, cause="loss_limit", final_equity_usd=88_000_000, start_cash_usd=100_000_000,
        pnl_bps=-1200, lifetime_s=300, tx_hash="0x" + "22" * 32,
    )
    link("death", store.put_death(dead))

    print("\n-- graveyard(creator) read back from Arkiv")
    for d in store.graveyard(creator):
        print(f"  bot {d.bot_id}: {d.cause}, pnl {d.pnl_bps} bps, vault tx {d.tx_hash}")
    print("\n-- report card (computed from bot + death records)")
    print(store.report_card(creator_id=creator).model_dump_json(indent=2))
    print("\n-- anyone can run this query (needs no key):")
    print(
        f"curl -s {s.arkiv_rpc_url} -H 'content-type: application/json' -d "
        f"'{{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"arkiv_query\",\"params\":[\"arkiv.schema = str('\\''parable.death'\\'') "
        f"AND $owner = addr({wallet}) ORDER BY $key ASC\",{{\"select\":{{\"key\":true,\"attributes\":true}}}}]}}'"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
