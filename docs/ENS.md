# ENSv2 trading permissions

Every bot registered by Parable receives an expiring ENSv2 subname under `parable.eth` on Sepolia. Its resolver stores the bot wallet, strategy, model, loss limit and a code fingerprint. The fingerprint identifies the configuration recorded at launch.

Before a trade, the vault calls `EnsV2BadgeOracle.isValid`. The oracle checks that the name is registered, unexpired, has a resolver, and resolves to the registered bot's wallet. It refuses unknown or revoked badges and fails closed if an ENS read fails.

| Role | Permission |
|---|---|
| Operator | Registers names and writes resolver records. |
| Badge owner | Receives the name with no transfer roles. |
| Vault's badge oracle | Can revoke a bound badge and unregister the name. |

The vault disables trading when a bot stops. It also attempts to unregister the badge. If ENS cleanup fails, the vault still records the bot as stopped.

## Verify on Sepolia

- [ENS parent name](https://sepolia.app.ens.domains/parable.eth)
- [Badge registration](https://sepolia.etherscan.io/tx/0x2fafde65460e158cb2d085a18ab72fbf8d65ea98f18482d3b20ab4330554e559)
- [Resolver records](https://sepolia.etherscan.io/tx/0x6bbc664fea34da2dae01cbfc58d916b6c1c0269268808cf19135ecae6821a919)
- [Oracle binding](https://sepolia.etherscan.io/tx/0x443c1073dc13a73812485b314f176dd7cef52117ac08bc08d2911965c15de388)
- [Badge revocation](https://sepolia.etherscan.io/tx/0x02204e998f0735ae4e2bcbde6eb78d1d48fd840f9731b4042f5df3f96ad8609b)

Network addresses and registry settings are configurable through [.env.example](../.env.example). See the [deployment reference](DEPLOYMENTS.md), [Solidity oracle](../contracts/src/adapters/EnsV2BadgeOracle.sol) and [Python badge issuer](../engine/parable/ens_badge.py).
