# Deployments (Sepolia practice network, chain id 11155111)

| What | Address | Explorer |
|---|---|---|
| ParableVault (holds bot money, keeps score) | `0x5432bE5713f358225d648eAb2EC9f699B25Ef317` | [Etherscan](https://sepolia.etherscan.io/address/0x5432bE5713f358225d648eAb2EC9f699B25Ef317) · [Sourcify](https://repo.sourcify.dev/11155111/0x5432bE5713f358225d648eAb2EC9f699B25Ef317) |
| EnsV2BadgeOracle (lets the vault check ENS name tags) | `0x087077ceBb69d8617b41735aAe24232697Af4EcA` | [Etherscan](https://sepolia.etherscan.io/address/0x087077ceBb69d8617b41735aAe24232697Af4EcA) · [Sourcify](https://repo.sourcify.dev/11155111/0x087077ceBb69d8617b41735aAe24232697Af4EcA) |
| Operator (Parable's server wallet) | `0x4Bf4Cf3Ac386A57DBf7C8b5eB93cE942d4504570` | [Etherscan](https://sepolia.etherscan.io/address/0x4Bf4Cf3Ac386A57DBf7C8b5eB93cE942d4504570) |
| Price feed (Chainlink ETH/USD, Sepolia) | `0x694AA1769357215DE4FAC081bf1f309aDC325306` | [Etherscan](https://sepolia.etherscan.io/address/0x694AA1769357215DE4FAC081bf1f309aDC325306) |

Deployed 2026-11-06 14:19 IST with `contracts/script/Deploy.s.sol` (MAX_PRICE_AGE = 7200 s, because the Sepolia price feed updates about once an hour). Source published on Sourcify.

## ENS (ENSv2 on Sepolia)
| What | Address / link |
|---|---|
| Parent name | `parable.eth` (owned by the operator wallet) |
| Badge subregistry (holds every bot's name tag) | `0xf749a1584e70A2285E608DF192A485EB87186B4b` |
| Badge resolver (holds each badge's records) | `0xaba5B8A13Ac0c62AaF4d6FF2527BF8690DceAF80` |

**Live proof (2026-11-06):** issue → read → valid → revoke → invalid, all on Sepolia:
[register badge](https://sepolia.etherscan.io/tx/0x2fafde65460e158cb2d085a18ab72fbf8d65ea98f18482d3b20ab4330554e559) ·
[write records](https://sepolia.etherscan.io/tx/0x6bbc664fea34da2dae01cbfc58d916b6c1c0269268808cf19135ecae6821a919) ·
[bind to vault's checker](https://sepolia.etherscan.io/tx/0x443c1073dc13a73812485b314f176dd7cef52117ac08bc08d2911965c15de388) ·
[revoke (burn)](https://sepolia.etherscan.io/tx/0x02204e998f0735ae4e2bcbde6eb78d1d48fd840f9731b4042f5df3f96ad8609b)
