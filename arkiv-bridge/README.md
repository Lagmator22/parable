# arkiv-bridge

A ~100-line Node service that gives the Python engine access to Arkiv through the official
`@arkiv-network/sdk` (1.0.1). It signs with `ARKIV_PRIVATE_KEY` and listens on 127.0.0.1 only.

```
cd arkiv-bridge && npm install && npm start      # port 8787 (ARKIV_BRIDGE_PORT to change)
```

Reads `ARKIV_PRIVATE_KEY` (and optional `ARKIV_ACCESS_KEY`, free at hub.arkiv.network/access-keys) from the repo-root `.env`.
The writer wallet needs tGLM from https://hub.arkiv.network/faucet before it can write.

Attributes are sent as `{name: [type, value]}` with type one of `str u256 u64 i32 addr`.

| call | body | answer |
|---|---|---|
| `GET /health` | | `{writer, chainId}` |
| `POST /entities` | `{schema, attributes, expiresInSeconds, body, readonly?}` | `{key, txHash}` |
| `POST /patch` | `{schema, key, attributes, body, extendSeconds?}` | `{key, txHash}` |
| `POST /query` | `{schema, where, owner?}` | `[{key, attributes, body, expiresAt}]` |

`/query` only returns rows owned by `owner`, which defaults to our writer wallet, because anyone can write to Arkiv.
