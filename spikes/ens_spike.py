"""ENSv2 badge spike on Sepolia: issue -> read -> is_valid -> revoke -> is_valid false.

Run:  cd engine && uv run python ../spikes/ens_spike.py

Read-only checks always run. The write flow needs OPERATOR_PRIVATE_KEY (Sepolia ETH) and
ENS_PARENT_NAME (an ENSv2 name the operator owns); without them it prints the manual steps and exits 0.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

from eth_account import Account  # noqa: E402
from web3 import Web3  # noqa: E402

from parable import ens_badge as eb  # noqa: E402

TX = "https://sepolia.etherscan.io/tx/"

MANUAL_STEPS = """
MANUAL STEPS (the human has to do these once):
  1. Operator wallet: create a fresh key (e.g. `cast wallet new`, or any wallet) and put it in the repo-root
     .env as OPERATOR_PRIVATE_KEY=0x... . Never commit it.
  2. Sepolia ETH: send ~0.1 Sepolia ETH to that address from a faucet, e.g. https://sepoliafaucet.com ,
     https://www.alchemy.com/faucets/ethereum-sepolia or https://cloud.google.com/application/web3/faucet/ethereum/sepolia
  3. Register an ENSv2 .eth name on Sepolia with that same wallet: open https://sepolia.app.ens.domains ,
     connect the operator wallet, switch to Sepolia, search a name (e.g. parable.eth), and register it
     (commit, wait ~60s, register; fees are paid in the mock USDC the app offers). It must be the ENSv2
     registrar (ETHRegistrar 0xf633e7fc17e2bbe0d0965d18ec1821dcb754a3d3), not the legacy ENSv1 one.
  4. Put the name in .env: ENS_PARENT_NAME=parable.eth
  5. Re-run this script. It deploys (once) a UserRegistry subregistry + PermissionedResolver for the parent,
     grants the operator the needed roles, and prints ENS_RESOLVER=... to add to .env.
Roles the operator needs on the parent name: ROLE_SET_SUBREGISTRY (the owner has it by default after
registration; do not remove it). Nothing else has to be granted by hand.
"""


def link(h: str) -> str:
    return TX + h


def main() -> int:
    s = eb.Settings()
    w3 = Web3(Web3.HTTPProvider(s.rpc_url, request_kwargs={"timeout": 30}))
    print(f"rpc {s.rpc_url} chain_id={w3.eth.chain_id} block={w3.eth.block_number}")
    for name, addr in [
        ("RootRegistry", s.root_registry),
        ("VerifiableFactory", s.factory),
        ("UserRegistryImpl", s.registry_impl),
        ("PermissionedResolverImpl", s.resolver_impl),
    ]:
        has_code = len(w3.eth.get_code(Web3.to_checksum_address(addr))) > 0
        print(f"  {name:26} {addr} code={'yes' if has_code else 'NO (ENSv2 Sepolia may have been reset)'}")

    missing = eb.missing_setup(s)
    if missing:
        print("\nWrite flow skipped. Missing: " + "; ".join(missing))
        print(MANUAL_STEPS)
        return 0

    client = eb.EnsBadge(s, w3)
    op = client.operator
    print(f"\noperator {op} balance {Web3.from_wei(w3.eth.get_balance(op), 'ether')} ETH")
    if w3.eth.get_balance(op) == 0:
        print("Operator has no Sepolia ETH.\n" + MANUAL_STEPS)
        return 0

    # Log every tx with an explorer link.
    original_send = client._send

    def logged_send(fn) -> str:
        h = original_send(fn)
        print(f"  tx {fn.fn_name:16} {link(h)}")
        return h

    client._send = logged_send  # type: ignore[method-assign]

    # Parent must be an ENSv2 name this operator owns.
    label, _ = eb.split_name(s.parent_name)
    parent_reg = client._registry(client.registry_for(s.parent_name))
    state = parent_reg.functions.getState(eb.label_id(label)).call()
    ok, reason = eb.classify(state, client._now())
    if not ok or state[2].lower() != op.lower():
        print(f"\n{s.parent_name}: {reason}; owner={state[2]}. The operator must own it on ENSv2 Sepolia.")
        print(MANUAL_STEPS)
        return 0

    print("\n[setup] subregistry + resolver for the parent (idempotent)")
    addrs = client.setup_parent()
    for k, v in addrs.items():
        print(f"  {k}={v}")
    if not s.resolver:
        s.resolver = addrs["ENS_RESOLVER"]
        print("  (add ENS_RESOLVER to .env so later runs reuse it)")

    bot = Account.create().address
    label = f"spike-{int(time.time()) % 100000}"
    expires = client._now() + 3600
    print(f"\n[1] issue_badge {label}.{s.parent_name} for bot {bot}, expires in 1h")
    name, node = client.issue_badge(
        label, bot, expires, {"rules": "spike: hold only", "creator": "0xspike", "born": str(int(time.time()))}
    )
    print(f"  name={name} node={node}")

    print("\n[2] read_badge")
    info = client.read_badge(name)
    for k in ("registered", "reason", "seconds_left", "owner", "resolver", "addr", "soulbound", "texts"):
        print(f"  {k}: {info[k]}")
    assert info["registered"] and info["soulbound"] is True and info["addr"] == bot

    print("\n[3] is_valid(bot) and is_valid(other)")
    v1 = client.is_valid(name, bot)
    v2 = client.is_valid(name, Account.create().address)
    print(f"  bot={v1} other={v2}")
    assert v1 and not v2

    print("\n[4] revoke_badge")
    tx = client.revoke_badge(name)
    print(f"  revoked: {link(tx)}")

    print("\n[5] is_valid after revoke")
    v3 = client.is_valid(name, bot)
    print(f"  bot={v3}  ({client.read_badge(name)['reason']})")
    assert not v3

    print("\nENS spike OK: issue -> read -> valid -> revoke -> invalid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
