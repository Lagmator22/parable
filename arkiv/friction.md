# Arkiv developer feedback (from building Parable on Rabdi testnet)

Parable is a public record and graveyard of AI trading bots (born, traded, died) on the **Arkiv Rabdi testnet** (`chainId: 7794095`, RPC `https://rpc.rabdi.db-chain.testnet.arkiv.network`).
Writer wallet: [`0x4Bf4Cf3Ac386A57DBf7C8b5eB93cE942d4504570`](https://rabdi.explorer.arkiv.network/address/0x4Bf4Cf3Ac386A57DBf7C8b5eB93cE942d4504570).
All observations below come from live testnet runs on **2026-11-06**.

---

## 1. Python SDK (`arkiv-sdk` 1.0.0b3) cannot query Rabdi

- **What we expected:** `pip install arkiv-sdk`, point it at `https://rpc.rabdi.db-chain.testnet.arkiv.network`, and run `query_entities(...)`.
- **What happened:** Every query fails with `-32602` because the Python SDK sends the legacy `includeData` option name, which the Rabdi RPC node rejects:
  ```text
  web3.exceptions.Web3RPCError: {'code': -32602, 'message': 'invalid options param: ... unknown field
  `includeData`, expected one of `atBlock`, `select`, `limit`, `offset`, `cursor` ...'}
  ```
- **How to reproduce:**
  ```python
  from arkiv import Arkiv
  from arkiv.provider import ProviderBuilder
  c = Arkiv(ProviderBuilder().custom("https://rpc.rabdi.db-chain.testnet.arkiv.network").build())
  list(c.arkiv.query_entities("arkiv.schema = 'parable.bot'"))  # raises Web3RPCError -32602
  ```
- **How we solved it:** We built a 100-line local Node bridge ([`arkiv-bridge/index.mjs`](../arkiv-bridge/index.mjs)) using the official JS SDK (`@arkiv-network/sdk` 1.0.1), which speaks Rabdi's `{ select: { ... } }` format cleanly.
- **Suggestion:** Publish a version-to-testnet compatibility matrix in the Python SDK README, or align `arkiv-sdk` (Python) with `@arkiv-network/sdk` (JS) 1.0.1's `select` parameter.

---

## 2. `extendEntity` reverts if the new relative TTL is even 1 block shorter than current expiry

- **What we expected:** Calling `writer.extendEntity({ entityKey, expiration: ExpirationTime.fromSeconds(180 * 86400) })` when marking a bot dead should ensure the entity lives *at least* 180 days ("at-least" semantics).
- **What happened:** When our vault-to-Arkiv repair loop ([`repair.py`](../engine/parable/repair.py)) rebuilt orphan `bot #1`, `put_bot` created the entity with `180 days + 1 hour` (`lease_seconds + 3600`, expiring at block `8065229`). Immediately afterwards, `put_death` called `_mark_dead`, which called `extendEntity` with `180 days` (`DEATH_LIFETIME`, block `8063440`). Rabdi rejected the transaction with:
  ```text
  Transaction failed: entity 0x740a793d…9419a8 already expires at block 8065229,
  so extending it to 8063440 would shorten its life
  ```
- **How to reproduce:**
  1. Create an entity with `ExpirationTime.fromSeconds(7200)`.
  2. Call `writer.extendEntity({ entityKey, expiration: ExpirationTime.fromSeconds(3600) })`.
  3. The RPC reverts with `would shorten its life` because `extendEntity` sets an absolute target block (`now +seconds`) rather than adding to the current expiry or taking `max(currentExpiry, newExpiry)`.
- **Suggestion:** Notice that the error message itself is wonderfully clear! Still, an SDK helper like `ensureMinExpiration(entityKey, minSecondsFromNow)` (or making `extendEntity` a no-op when `currentExpiry >= targetExpiry`) would prevent two-step `patchEntity` + `extendEntity` flows from failing partway through.

---

## 3. Public query rate-limiting hangs for 60s instead of returning HTTP 429

- **What we expected:** When our dashboard polled uncached Arkiv queries every 3 seconds without an `accessKey`, we expected an immediate `429 Too Many Requests` error with a message pointing to `https://hub.arkiv.network/access-keys`.
- **What happened:** `reader.select(...).fetch()` on `rabdi()` without an `accessKey` simply hung until our 60-second HTTP timeout expired, while raw JSON-RPC calls to the node still answered in `< 1s`.
- **How we solved it:**
  1. Created a free access key at `https://hub.arkiv.network/access-keys` and passed `rabdi({ accessKey: process.env.ARKIV_ACCESS_KEY })` in `arkiv-bridge/index.mjs` (queries dropped from 60s timeout to **0.4s**).
  2. Added an 8-second read cache (`READ_CACHE_S = 8`) in [`arkiv_store.py`](../engine/parable/arkiv_store.py) and consolidated the 12-call brain comparison table into a single 2-query route (`GET /api/report/brains`).
- **Suggestion:** Return a fast `429` JSON error when the public query indexer throttles an unauthenticated client, and include the `hub.arkiv.network/access-keys` URL in the error string.

---

## 4. Other JS SDK (`@arkiv-network/sdk` 1.0.1) notes & what worked great

- **What worked great:**
  - `select().where(and(eq(...))).ownedBy(owner).limit(100).offset(offset).fetch()` worked on the first try across `str`, `u256`, `u64`, `i32`, and `addr` columns.
  - `.ownedBy(addr)` is the exact primitive needed for a public database where anyone can write entities; it let us enforce fail-closed writer filtering in 5 lines of code.
  - `flags: { readonly: true, permissionlessExtension: true }` is a killer feature for an audit log / graveyard.
- **Minor friction:**
  - Writing from an unfunded wallet returns `Transaction failed: Execution error without revert data` instead of `insufficient balance for gas (use the Rabdi faucet)`.
  - `createEntity` requires a `defineSchema(...)` object even for a dynamic bridge that receives attribute types at runtime; we construct `defineSchema(name, columns)` dynamically per call.
  - **Query syntax changed during the hackathon:** our README query using `&&` and `str("...")` started failing with `symbol operators (&& || ~) were removed — use AND, OR, STARTSWITH` and then `str takes a single-quoted string`. The error messages were excellent (they said exactly what to change), but the docs/examples we had copied still showed the old syntax. Suggestion: version the query language and keep a changelog link in the error message.
