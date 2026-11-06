# Parable on Arkiv: schema

Network: Arkiv **Rabdi** testnet (chain id 7794095, RPC `https://rpc.rabdi.db-chain.testnet.arkiv.network`, explorer https://rabdi.explorer.arkiv.network).
Code: `arkiv-bridge/index.mjs` (official JS SDK `@arkiv-network/sdk` 1.0.1, signs and queries), `engine/parable/arkiv_store.py` (Python client of the bridge), `engine/parable/repair.py` (outbox + vault-to-Arkiv self-healing repair), `engine/tests/test_arkiv_store.py`, `scripts/arkiv_spike.py`.
Status: **Verified live on Rabdi testnet (2026-11-06)** — real bot records, birth events, and graves written and queried back in `< 0.5s` using writer wallet [`0x4Bf4Cf3Ac386A57DBf7C8b5eB93cE942d4504570`](https://rabdi.explorer.arkiv.network/address/0x4Bf4Cf3Ac386A57DBf7C8b5eB93cE942d4504570) (sample Rabdi txs: [bot](https://rabdi.explorer.arkiv.network/tx/0x19865c864b2dce647f6c3041afdec6c178a3848cf9a0dfaf08f57f1f06a45fb3), [birth](https://rabdi.explorer.arkiv.network/tx/0x98b24330b21fb990bcee3a1d5dab8916cb9a16fe95cb1a132efed5adebe89615), [death](https://rabdi.explorer.arkiv.network/tx/0xc5714abb242c6d3eddc8a79272097f1febe88886dbe8fd7239dfdd6c8b150f15)).

Parable is a public record of AI trading bots: who launched them, what they did, and how they died. Arkiv is the public, queryable copy; the Sepolia vault is the source of truth, and every Arkiv record carries the Sepolia transaction hash in `vault_tx`.

## Owner (writer wallet)

All records are written by **one engine wallet** (`ARKIV_PRIVATE_KEY`), public address `0x4Bf4Cf3Ac386A57DBf7C8b5eB93cE942d4504570`. Its address is returned by the bridge `GET /health` and `GET /api/info` (`arkiv_writer`) and listed in the README.
Arkiv is a public database where anyone can write entities of any shape, so **every Parable query filters `$owner = addr(<writer>)`** next to the schema tag. A copycat writing fake `parable.death` rows is ignored by our app and by anyone who copies our query.
Bots never write their own record: the engine mirrors vault events, so a bot cannot hide or edit its death.

## Entities

Each entity carries the tag `arkiv.schema` (indexed `str`) that works as its type. Indexed attributes can be filtered; `body` (`bytes`, not indexed) holds the full record as JSON for readers that want everything.

### `parable.bot`: one per bot, alive or dead

| attribute | type | indexed | meaning |
|---|---|---|---|
| `arkiv.schema` | str | yes | `parable.bot` |
| `bot_id` | u256 | yes | vault bot id |
| `bot_address` | addr | yes | the bot's wallet |
| `creator_id` | str | yes | World ID nullifier (one real person), lowercased |
| `ens_name` | str | yes | ENS badge name, e.g. `bot-07.parable.eth` |
| `strategy` | str | yes | strategy preset id |
| `status` | str | yes | `alive` or `dead` |
| `born_at` | u64 | yes | unix seconds |
| `vault_tx` | str | yes | Sepolia tx hash of the vault `registerBot` |
| `body` | bytes | no | `BotRecord` JSON (rules included) |

Expiry: **alive bots expire with their lease** (`lease_seconds`, natural Arkiv expiry, so the "alive" list cleans itself). When the bot dies, the bridge patches `status` to `dead` and extends the entity to about 180 days (two transactions), so its life stays queryable.
Flags: permissionless extension (anyone can keep a record alive).

### `parable.event`: one per birth, trade, rejected trade and death

| attribute | type | indexed | meaning |
|---|---|---|---|
| `arkiv.schema` | str | yes | `parable.event` |
| `bot_id` | u256 | yes | |
| `kind` | str | yes | `birth`, `trade`, `rejected`, `death` |
| `at` | u64 | yes | unix seconds |
| `vault_tx` | str | yes | Sepolia tx hash (absent for rejected trades that never hit chain) |
| `body` | bytes | no | `BotEvent` JSON (`data` has amounts, price, revert reason) |

Expiry: 30 days. Flags: **read-only** (attributes can never change) and permissionless extension.

### `parable.death`: the graveyard

| attribute | type | indexed | meaning |
|---|---|---|---|
| `arkiv.schema` | str | yes | `parable.death` |
| `bot_id` | u256 | yes | |
| `creator_id` | str | yes | copied from the bot so the graveyard is one query |
| `strategy` | str | yes | copied from the bot |
| `cause` | str | yes | `expired`, `killed`, `loss_limit` |
| `pnl_bps` | i32 | yes | profit and loss in basis points, may be negative |
| `lifetime_s` | u64 | yes | seconds alive |
| `vault_tx` | str | yes | Sepolia tx hash of the death |
| `body` | bytes | no | `DeathRecord` JSON (final equity, start cash) |

Expiry: about 180 days, the longest Arkiv allows (`ExpirationTime.fromSeconds`); extend before then to keep it. Flags: **read-only** + permissionless extension, so even our own wallet cannot rewrite a death, and anyone can pay to keep it alive.

There is no separate `creator` entity: a creator is the set of `parable.bot` rows sharing one `creator_id`.

## Queries the app runs (and anyone can run)

All are `arkiv_query` strings; replace `<W>` with the writer wallet.

```
-- a creator's whole graveyard
arkiv.schema = str('parable.death') AND $owner = addr(<W>) AND creator_id = str('0x...')

-- every dead bot of one strategy, worst first
arkiv.schema = str('parable.death') AND $owner = addr(<W>) AND strategy = str('momentum') ORDER BY pnl_bps:i32 ASC

-- who died of the loss limit
arkiv.schema = str('parable.death') AND $owner = addr(<W>) AND cause = str('loss_limit')

-- live bots of a creator
arkiv.schema = str('parable.bot') AND $owner = addr(<W>) AND creator_id = str('0x...') AND status = str('alive')

-- the full story of one bot
arkiv.schema = str('parable.event') AND $owner = addr(<W>) AND bot_id = u256(7) ORDER BY at:u64 ASC

-- look up a record from a Sepolia transaction
arkiv.schema = str('parable.death') AND $owner = addr(<W>) AND vault_tx = str('0x...')
```

Report cards (launched, alive, dead, profitable, worst and average loss) are computed from **all** `parable.bot` and `parable.death` rows for the subject, graveyard included. A death whose bot entity has already expired still counts. The card shows "vault says N, Arkiv shows N" by comparing to the vault's own counter (`vault_count`).

## Limits we hit by design

- Rabdi has no `NOT` or `!=`, so "not dead" is expressed as `status = str('alive')`.
- `str` values are capped at 128 bytes, so full records live in `body` (bytes, up to 128 KiB) and are not filterable.
- Lifetimes are capped at about 182.5 days (2-second blocks).
- A death is written before the bot is patched, so a crash between the two leaves a grave and a bot still marked alive; report cards treat a bot with a death row as dead.
- An alive bot whose lease ran out before its death was recorded disappears from Arkiv; the vault counter is what exposes that gap in the report card.
