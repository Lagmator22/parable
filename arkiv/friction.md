# Arkiv developer feedback (DRAFT, from building Parable)

Parable is a public record of AI trading bots (born, traded, died) kept on Arkiv Rabdi testnet.
All facts below were observed on 2026-11-06 against `https://rpc.rabdi.db-chain.testnet.arkiv.network`.

## 1. Python SDK (`arkiv-sdk` 1.0.0b3) cannot query Rabdi

Expected: `pip install arkiv-sdk`, point it at the testnet RPC from the docs, query entities.
Got: every query fails, because the SDK sends the old option name `includeData` and Rabdi rejects it:

```
web3.exceptions.Web3RPCError: {'code': -32602, 'message': 'invalid options param: ... unknown field
`includeData`, expected one of `atBlock`, `select`, `limit`, `offset`, `cursor` ...'}
```

Reproduce:
```python
from arkiv import Arkiv
from arkiv.provider import ProviderBuilder
c = Arkiv(ProviderBuilder().custom("https://rpc.rabdi.db-chain.testnet.arkiv.network").build())
list(c.arkiv.query_entities("arkiv.schema = 'x'"))   # raises as above (the iterator is lazy; list() triggers the call)
```
Same on the raw RPC: `arkiv_query` with `{"includeData":{...}}` is rejected, `{"select":{"key":true}}` works.
Our first attempt was 500 lines of hand-encoded JSON-RPC and ABI for this reason; we replaced it with the official JS SDK.
Suggestion: publish a compatibility table (SDK version vs network) and fail with a clear "SDK too old for this network" message.

## 2. JS SDK (`@arkiv-network/sdk` 1.0.1): what worked

- Read path worked first try: `select().where(and(eq(...))).ownedBy(addr).limit().offset().fetch()` against Rabdi, including `str`, `u256`, `u64`, `i32` and `addr` filters.
- `ownedBy` is the right primitive for a public database anyone can write to; we filter every query by our writer wallet.
- Typed schemas and `ExpirationTime.fromSeconds` made the bridge about 100 lines.

## 3. JS SDK friction

- `createEntity` requires a schema object, even for a generic proxy that only knows attribute names at runtime. We build one with `defineSchema(name, columns)` per call. A schema-less `createEntity(attributes, options)` would help.
- A write from an unfunded wallet fails with `Transaction failed: Execution error without revert data`. It reads like a contract bug; "insufficient funds, use the faucet" would have saved us time.
- The SDK prints a rate-limit warning at startup when no access key is set; fine, but the key is only mentioned in the README, not in the error you hit when throttled.
- Python SDK and JS SDK are on different protocol generations with the same major version (1.0.x); see section 1.
- `viem` is a peer dependency, so `npm install @arkiv-network/sdk` alone is not enough.

## 4. Not yet verified

Entity creation, patch and extend on chain (writer wallet was unfunded when this was written). Update this file after the first funded run.
