# How Parable uses Arkiv

The Python engine writes to Rabdi through the official Arkiv SDK in the [Node bridge](../arkiv-bridge/index.mjs). The [store](../engine/parable/arkiv_store.py) scopes every production query to the configured writer wallet and active vault, so entries from other wallets or deployments do not enter Parable's reports.

| Arkiv feature | What readers see |
|---|---|
| Indexed schema, vault and bot ID | The Graveyard joins each death to the bot's metadata. The bot history filters events by bot ID. |
| Indexed creator, model and strategy | Reports can group or filter outcomes. The dashboard's model comparison includes stopped bots. |
| Read-only events and graves | The writer creates records whose recorded fields cannot be patched. The separate bot entity remains mutable so its status can change from alive to dead. |
| Entity expiry and extension | A live bot entry has a lease plus one hour of grace. The engine retains stopped bot entries and graves for about 180 days. Events are kept for 30 days. Permissionless extension lets other readers keep entities available longer. |

Open the [Graveyard](https://parable-demo.centralindia.cloudapp.azure.com/#register) and select an Arkiv link to inspect an entity. The page shows 10 rows at a time and compares the number of registered bots in the public record with the vault count. The engine retries failed writes and can reconstruct missing bot and death records from the vault. The earliest reconstructed record appears as bot #1.

See the [schema](schema.md) for fields and the [main README](../README.md#query-the-public-record) for a runnable query.
