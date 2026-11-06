# How Parable Uses Arkiv: Filters, Ownership, Expiries, and UI Impact

Every Arkiv feature we use in [`arkiv-bridge/index.mjs`](../arkiv-bridge/index.mjs) and [`engine/parable/arkiv_store.py`](../engine/parable/arkiv_store.py) maps directly to a security rule or user-visible feature in the Parable dashboard.

---

## 1. How our filter fields match real user questions

We define three schemas (`parable.bot`, `parable.event`, `parable.death`) with typed, `.indexed()` columns (`str`, `u256`, `u64`, `i32`, `addr`) plus an unindexed `body: bytes()` payload:

| Indexed Attribute | Type | Schema(s) | Exact UI / API Feature It Powers |
|---|---|---|---|
| `vault` | `str` | all 3 | Scopes every query to our active Sepolia `ParableVault` (`0x5432be5713f358225d648eab2ec9f699b25ef317`), cleanly isolating production bots from early spike/test rows. |
| `creator_id` | `str` | `bot`, `death` | Powers **Live Bots** (`GET /api/bots?creator=0x...`), **The Graveyard** (`GET /api/graveyard/0x...`), and **Creator Report Card** (`GET /api/report?creator=0x...`) for one World ID human. |
| `status` | `str` | `bot` | Filters `status = "alive"` vs `"dead"` so the **Live Bots** panel only fetches active bots in one indexed query. |
| `brain` | `str` | `bot`, `death` | Powers **Compare Brains** (`GET /api/report/brains` & `GET /api/report?brain=gemini:...`), letting users compare `rule` vs `gemini:gemini-3.5-flash-lite` across all living and dead bots. |
| `strategy` | `str` | `bot`, `death` | Powers strategy cohort filtering (`momentum`, `dip_buyer`, `yolo`) in `GET /api/report?strategy=momentum`. |
| `cause` | `str` | `death` | Records how each bot died (`expired`, `killed`, `loss_limit`), rendered as human-readable tombstones in the **Graveyard**. |
| `pnl_bps` | `i32` | `death` | Signed 32-bit basis points (e.g. `-1100` = `-11.0%`), used to compute **Profitable count**, **Worst Return**, and **Average Return** in the Report Card. |
| `bot_id` | `u256` | all 3 | Joins `parable.bot` and `parable.death` and fetches a single bot's chronological **Public Timeline** (`GET /api/bots/{id}/events` on `parable.event`). |
| `vault_tx` | `str` | all 3 | Stores the Sepolia transaction hash (`0x2bb83c9f...`, `0xdfb8094e...`) so every bot card, event row, and tombstone in the UI has a clickable **View on Etherscan ↗** proof link. |

---

## 2. How entity ownership and `readonly` flags protect the graveyard

Arkiv is a permissionless network where any wallet can create entities with `arkiv.schema = "parable.death"`. Without an ownership discipline, an attacker could pollute a creator's graveyard with fake losses or fake wins.

1. **Fail-closed `$owner` filtering (`ownedBy`):**
   - Every Parable write is signed by our single engine writer wallet (`0x4Bf4Cf3Ac386A57DBf7C8b5eB93cE942d4504570`).
   - In [`arkiv_store.py`](../engine/parable/arkiv_store.py), `ArkivStore._query()` **always** calls `self.writer()` and passes `owner` to the bridge's `.ownedBy(owner)` clause. If the writer address is unknown, `self.writer()` raises `ArkivError` (fail-closed) rather than querying unfiltered data.
2. **Immutable graves and events (`readonly: true`):**
   - `put_event()` and `put_death()` pass `readonly: true` (`flags: { readonly: true, permissionlessExtension: true }`).
   - Once a trade, blocked trade (`OverTradeLimit`), or death is written to Arkiv, **not even our writer wallet can call `patchEntity` on it**.
3. **Mutable lifecycle state only on `parable.bot` (`readonly: false`):**
   - Only `parable.bot` is created with `readonly: false` so that when the bot dies on Sepolia, `_mark_dead()` can call `writer.patchEntity` to flip its indexed `status` attribute from `"alive"` to `"dead"`.

---

## 3. How entity expiries (`ExpirationTime`) match bot lifetimes

Instead of picking an arbitrary TTL for every row, each entity's Arkiv expiration matches its domain lifecycle:

| Entity | Arkiv Expiration (`expiresInSeconds`) | Why this TTL fits what the app does |
|---|---|---|
| `parable.bot` (at birth) | `lease_seconds + 3600` (bot's lease + 1 hour grace) | A bot born with a 10-minute lease lives on Arkiv for 70 minutes—long enough for `sync_deaths()` or `repair.py` to record its death and patch it, while automatically cleaning up if abandoned. |
| `parable.bot` (on death) | Extended via `writer.extendEntity` to `180 days` (`DEATH_LIFETIME`) | Once dead, the bot's metadata (`ens_name`, `brain`, `rules`) is kept alongside its grave so cohort report cards can join `bot_id` for 6 months. |
| `parable.event` | `30 days` (`EVENT_LIFETIME`) | Per-trade and rejected-trade timeline logs stay inspectable in the expandable **Public Timeline** for a month. |
| `parable.death` | `180 days` (`DEATH_LIFETIME`, near Rabdi's 182.5-day cap) + `permissionlessExtension: true` | **The Graveyard is long-lived.** Anyone can extend a grave before 180 days so a creator's failed bots never vanish. |

---

## 4. Does every Arkiv feature change something users see?

Yes—nothing on Arkiv is write-only:
- **Graveyard section (`#graveyard`):** Reads `parable.death` + `parable.bot` live from Arkiv and renders tombstone cards with cause of death, return %, lifetime, brain, and Sepolia death tx link.
- **Creator Report Card (`#graveyard` header):** Compares the count of `parable.bot` + `parable.death` rows on Arkiv against `ParableVault.creatorBorn(creatorId)` on Sepolia and renders **`✓ Vault count matches public record`**.
- **Compare Brains table (`#compare`):** Runs two Arkiv queries (`parable.bot` and `parable.death` via `report_by_brain()`), groups by the indexed `brain` attribute, and displays every brain's launched, alive, dead, profitable, average return, and worst return.
- **Bot Public Timeline (`#live` → View events):** Queries `parable.event` by `bot_id` and displays every birth, trade, and vault-rejected trade (`OverTradeLimit`).
- **Self-healing Vault → Arkiv repair (`engine/parable/repair.py`):** Every 60 seconds, the engine walks `1..vault.totalBorn()` on Sepolia and compares against `arkiv.bots()` and `arkiv.graveyard()`. When our very first Sepolia bot (`bot #1`) lost its Arkiv write during an early nonce clash, `repair.py` automatically rebuilt `bot #1 (record rebuilt from the vault)` and wrote its grave to Arkiv—visible live in the graveyard today.
