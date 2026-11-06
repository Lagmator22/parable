# Deployments (Sepolia practice network, chain id 11155111)

| What | Address | Explorer |
|---|---|---|
| ParableVault (holds bot money, keeps score) | `0x5432bE5713f358225d648eAb2EC9f699B25Ef317` | [Etherscan](https://sepolia.etherscan.io/address/0x5432bE5713f358225d648eAb2EC9f699B25Ef317) · [Sourcify](https://repo.sourcify.dev/11155111/0x5432bE5713f358225d648eAb2EC9f699B25Ef317) |
| EnsV2BadgeOracle (lets the vault check ENS name tags) | `0x087077ceBb69d8617b41735aAe24232697Af4EcA` | [Etherscan](https://sepolia.etherscan.io/address/0x087077ceBb69d8617b41735aAe24232697Af4EcA) · [Sourcify](https://repo.sourcify.dev/11155111/0x087077ceBb69d8617b41735aAe24232697Af4EcA) |
| Operator (Parable's server wallet) | `0x4Bf4Cf3Ac386A57DBf7C8b5eB93cE942d4504570` | [Etherscan](https://sepolia.etherscan.io/address/0x4Bf4Cf3Ac386A57DBf7C8b5eB93cE942d4504570) |
| Price feed (Chainlink ETH/USD, Sepolia) | `0x694AA1769357215DE4FAC081bf1f309aDC325306` | [Etherscan](https://sepolia.etherscan.io/address/0x694AA1769357215DE4FAC081bf1f309aDC325306) |

Deployed 2026-11-06 14:19 IST with `contracts/script/Deploy.s.sol` (MAX_PRICE_AGE = 7200 s, because the Sepolia price feed updates about once an hour). Source published on Sourcify.
