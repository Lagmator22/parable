# Why Arkiv: What users lose with Postgres, and what stays off Arkiv

## 1. What would users lose if we swapped Arkiv for Postgres?

If Parable stored its bot records, trade logs, and graveyard in a private Postgres database on our server, **the core guarantee of the product ("bots and operators cannot quietly hide failed runs") would break in four ways:**

| Capability | With Arkiv (Rabdi Testnet) | If swapped for Postgres |
|---|---|---|
| **1. Independent verification without our server** | Anyone—a user, a competing leaderboard, or an AI agent—can query `rpc.rabdi.db-chain.testnet.arkiv.network` directly for `$owner = addr(0x4Bf4...4570)` and `arkiv.schema = str('parable.death')` even if our FastAPI server is turned off. | If our server goes offline or blocks an IP, the entire graveyard and cohort history disappear. |
| **2. Immutability of graves (`readonly: true`)** | Every `parable.death` and `parable.event` entity is created with `flags: { readonly: true, permissionlessExtension: true }`. Once a bot dies (`tx 0xdfb8094e...` on Sepolia, mirrored to Arkiv), **not even our own operator private key (`ARKIV_PRIVATE_KEY`) can edit or soften the recorded `pnl_bps` or `cause`**. | A database admin can run `UPDATE deaths SET pnl_bps = 500` or `DELETE FROM deaths WHERE pnl_bps < -1000` at any time with zero public trace. |
| **3. Permissionless preservation (`permissionlessExtension: true`)** | If a creator or operator stops paying to keep an embarrassing graveyard alive, **any third party** (a watchdog, a regulator, or a burned follower) can call `extendEntity` on Arkiv to keep those `parable.death` records alive for another 180 days. | Only the server owner controls retention and backups. |
| **4. Protocol-enforced lease expiry on live bots** | Alive `parable.bot` entities are created with `ExpirationTime.fromSeconds(lease_seconds + 3600)`. Stale "alive" records expire automatically at the protocol level if abandoned, while dead bots are extended to `180 days` (`DEATH_LIFETIME`). | Requires custom cron jobs that a dishonest operator can pause or manipulate. |

In short: **Sepolia (`ParableVault`) proves the money math and counters; Arkiv makes the full structured cohort history (by creator, strategy, brain, cause of death, and PnL) publicly queryable, read-only, and independently preservable without running an Ethereum archive indexer.**

---

## 2. What we kept OFF Arkiv—and why

We deliberately kept four things **off** Arkiv:

1. **Bot private keys (`LiveBot.key`) — kept in server RAM only:**
   - Each bot gets a fresh ephemeral Ethereum keypair at birth (`Account.create()`) so only that bot can sign `ParableVault.trade()`. Writing private keys to a public chain would let anyone trade as the bot. If the server restarts, the key is gone forever and `repair.py` expires the bot cleanly once its lease ends.
2. **Launch claim tokens (`claim` / `owner_hash`) and World OIDC PKCE verifiers — kept in server RAM only:**
   - When a user starts a launch (`POST /api/launch`), the browser receives a secret `claim` token used as `x-claim` (to confirm the launch) and `x-owner-token` (to kill the bot early). Putting secrets or OIDC session state on a public database would allow session hijacking.
3. **Real-time custody balances (`cashUsd`, `ethWei`, `hwmUsd`) and badge validity enforcement — kept in `ParableVault.sol` on Sepolia:**
   - Arkiv is an indexed data-availability and query layer, not a smart-contract execution engine. The vault contract on Sepolia enforces `badgeOracle.isValid(badgeNode, bot)`, `amountUsd <= maxTradeUsd`, and `((hwmUsd - equity) * 10000) / hwmUsd >= maxLossBps` atomically during `trade()` and `checkAndRevoke()`. Arkiv stores the resulting public events and graves (`vault_tx` links every Arkiv row back to its Sepolia transaction).
4. **Raw LLM prompts and chain-of-thought `<thought>` blocks — stripped in `bot_runner.py`:**
   - Thinking models (like Gemma 4 and Gemini Flash) emit verbose reasoning before their JSON decision. We strip `<thought>...</thought>` in `extract_json()` and store only the compact `{action, amount_usd, reason}` in `parable.event` so Arkiv entities stay small (< 500 bytes), fast to query, and cheap on Rabdi gas.
