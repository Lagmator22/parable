# ENS notes: bot badges on ENSv2 (Sepolia)

**In one minute:** every bot gets a name like `bot-07.parable.eth`. It is an ENSv2 subname that runs out when the bot's time is up, can be taken back by Parable, and cannot be moved to someone else. The vault looks the name up before **every** trade, so a bot with no name or a dead name cannot trade. The name is the bot's ID card.

## What a badge is
`bot-07.<ENS_PARENT_NAME>` (for example `bot-07.parable.eth`): an ENSv2 subname that is expiring, revocable by us, and soulbound. The vault reads it on every `trade()` through `EnsV2BadgeOracle`.

## Addresses (Ethereum Sepolia, chain 11155111)
Source: https://docs.ens.domains/learn/deployments (ENSv2 Sepolia section, ABIs pinned to `ensdomains/contracts-v2@07e55a05`). Each one was checked for code with `eth_getCode` on 2026-11-06 (`scripts/ens_spike.py` re-checks on every run).

| Contract | Address |
|---|---|
| RootRegistry | `0xb458d6a3a77919449d03e7a6903c26827c1ec43f` |
| ETHRegistry (`.eth`) | `0xd4ebcbbdf463c9c45784603db0ddd499bc44a8b4` |
| ETHRegistrar (register `.eth` names) | `0xf633e7fc17e2bbe0d0965d18ec1821dcb754a3d3` |
| VerifiableFactory | `0xda70306c98e97ece36f997a21368e53298572991` |
| UserRegistryImpl (subname registries) | `0x9bd8a88719068d09ecee662f36c0e3856708366a` |
| PermissionedResolverImpl | `0x115eb53f0c60696633855f90b138178fb40b2b2c` |
| UniversalResolverV2 | `0x24e1d8e068620b647ca097f961a61055f4f42d72` |
| ENS app | https://sepolia.app.ens.domains |

Prior-art addresses are **stale**: ENSign (`0xDEDB9291...`, deployment `sepolia-official-v1-20260525-r2`) and Batas (`UserRegistry` impl `0x624a25D6...`, factory `0x10Dc6333...`, resolver `0x9EAE5c27...`) used earlier staging deployments. Do not use them. Every address is a setting in `engine/parable/config.py`, overridable in `.env` (`ENS_ROOT_REGISTRY`, `ENS_FACTORY`, `ENS_USER_REGISTRY_IMPL`, `ENS_RESOLVER_IMPL`) because Sepolia ENSv2 has been reset before. The other ENS settings are `ENS_PARENT_NAME`, `ENS_RESOLVER` and `ENS_BADGE_ORACLE`.

Interface drift that mattered (the prior art is written against the older contracts):
- `UserRegistry.initialize(Grant[] grants)` and `PermissionedResolver.initialize(Grant[] grants, bytes[] calls)`, where `Grant = (address account, uint256 roleBitmap)`. Older code used `initialize(address, uint256)`.
- The resolver's setters take the DNS-encoded **name**, not a node: `setText(bytes name, string key, string value)`, `setAddress(bytes name, uint256 coinType, bytes addr)`. Reads go through `resolve(bytes name, bytes data)`, with the usual `addr(bytes32)` / `text(bytes32,string)` calldata inside (the node argument is ignored).
- The resolver's roles are per record **key**, not per name (`resource = keccak256(key)`), see "status text record" below.
- `ROLE_SET_ADDR` was renamed `ROLE_SET_ADDRESS`. Role bit values used here match `RegistryRolesLib` / `PermissionedResolverLib` at the pinned commit.

## Roles used
Registry roles (`RegistryRolesLib`, a role's admin is the role `<< 128`):

| Who | Where | Roles |
|---|---|---|
| Operator | subname registry **root** (set in `initialize`) | `REGISTRAR`, `UNREGISTER`, `RENEW`, `SET_RESOLVER` plus their admins |
| Operator | parent name token (given by registering it) | `SET_SUBREGISTRY` (used once, to attach our registry) |
| `EnsV2BadgeOracle` | subname registry root (granted by operator inside `setup_parent()`) | `UNREGISTER` only |
| Badge token owner (= operator) | the badge token | **no roles at all** (`roleBitmap = 0`) |

Resolver roles (`PermissionedResolverLib`): operator holds `SET_ADDRESS` and `SET_TEXT` plus admins, at the resolver root.

## How the three properties are achieved
- **Expiring**: `expiry` is an argument to `register()`. We pass the bot's lease end. ENS reports the name as not registered once `block.timestamp >= expiry`; the oracle checks `expiry > block.timestamp`.
- **Soulbound**: a transfer needs `ROLE_CAN_TRANSFER_ADMIN` on the token owner. We never grant it (`roleBitmap = 0`), so the token cannot move, not even by the operator. `read_badge()["soulbound"]` reads it back with `hasRoles`.
- **Revocable by us**: `unregister(labelId)` needs `ROLE_UNREGISTER`, which the operator and the oracle hold at the registry root. It burns the token and sets `expiry = now`. Death path: vault calls `oracle.revoke(node)` (only the vault may), the oracle marks it revoked locally and also calls `registry.unregister`, so the name really disappears from ENS. The local flag means `isValid` is false even if the ENS call fails. `revoke_badge()` is the same burn done by the operator from Python.
- **Bot binding**: the resolver's `addr` record is the bot address. `isValid(node, bot)` requires: bound to that bot, not revoked, status REGISTERED, `latestOwner != 0`, `expiry > now`, resolver set, and `resolve(addr) == bot`. Any ENS read failure returns false (no answer means no trade).
- **Why `bind()` exists**: `IBadgeOracle` passes only a namehash, which cannot be turned back into a registry and label. The operator calls `oracle.bind(node, registry, label, dnsName, bot)` once per badge (`issue_badge` does it when `ENS_BADGE_ORACLE` is set). `bind` checks that `dnsName` hashes to `node` and starts with `label`.

Distinguishing revoked from lapsed (Batas lesson): `unregister` clears `latestOwner` and sets expiry to the revoke moment, while a plain lapse keeps the owner. `classify()` uses the owner field for that. Token ids carry a version in the low 32 bits; the registry accepts the plain labelhash as an id and strips it itself, so we never derive token ids by hand.

## Deploy order
Contracts: `cd contracts && forge script script/Deploy.s.sol --rpc-url $SEPOLIA_RPC_URL --private-key $OPERATOR_PRIVATE_KEY --broadcast` with env `PRICE_FEED` (Chainlink ETH/USD), `OPERATOR` (the address of that key), `MAX_PRICE_AGE`. The script does, in this order:
1. Deploy `EnsV2BadgeOracle(operator)`.
2. Deploy `ParableVault(priceFeed, oracle, operator, maxPriceAge)`.
3. `oracle.setVault(vault)` (operator only, one-shot, so the broadcaster must be the operator).
It prints both addresses. Put them in `.env` as `ENS_BADGE_ORACLE` and `VAULT_ADDRESS`.

**Extra step after deploy (not done by the script):** the oracle must be allowed to burn badges when the vault kills a bot. With `ENS_BADGE_ORACLE` set in `.env`, run `EnsBadge().setup_parent()` (or `uv run python ../scripts/ens_spike.py`): it attaches the subregistry, deploys the resolver, and grants the oracle `ROLE_UNREGISTER` on the subregistry root. Re-running is safe. Without this grant `revoke` still marks the badge dead locally, it just cannot burn the ENS name.

**Fallback if ENS is blocked:** `USE_DEV_ORACLE=1` deploys `AlwaysValidBadgeOracle` instead (every badge counts as valid, no `setVault`). Dev only, and say so in the demo.

## Status text record: "bot may edit only its own `status`"
Not done, deliberately. In the current `PermissionedResolver` a setter role is scoped by record **key**, not by name: granting a bot `SET_TEXT` on `status` would let it write `status` for every name on that resolver (the name is just a function argument). Per-name scoping needs one resolver per bot. That is feasible (deploy a proxy through the VerifiableFactory, pre-set records with the `calls` argument of `initialize`, then `grantSetterRoles(setText(name,"status",""), bot)` so only that key is writable), but it costs two more transactions per bot, so the shared resolver with operator-only writes is the default. `issue_badge` writes `status=alive`; the engine can update it via the operator.

## Verified live on Sepolia (2026-11-06)
- **39 Foundry tests pass** (`contracts/test/EnsV2BadgeOracle.t.sol` — 15 tests; `contracts/test/ParableVault.t.sol` — 24 tests) and **17 Python unit tests pass** (`engine/tests/test_ens_badge.py`).
- **Live on-chain deployment & end-to-end verification on Sepolia (`chainId 11155111`):**
  - Parent name: `parable.eth` (owned by operator `0x4Bf4Cf3Ac386A57DBf7C8b5eB93cE942d4504570`)
  - Badge subregistry (`UserRegistry` proxy): [`0xf749a1584e70A2285E608DF192A485EB87186B4b`](https://sepolia.etherscan.io/address/0xf749a1584e70A2285E608DF192A485EB87186B4b)
  - Badge resolver (`PermissionedResolver` proxy): [`0xaba5B8A13Ac0c62AaF4d6FF2527BF8690DceAF80`](https://sepolia.etherscan.io/address/0xaba5B8A13Ac0c62AaF4d6FF2527BF8690DceAF80)
  - `EnsV2BadgeOracle` (verified on Sourcify): [`0x087077ceBb69d8617b41735aAe24232697Af4EcA`](https://repo.sourcify.dev/11155111/0x087077ceBb69d8617b41735aAe24232697Af4EcA)
  - `ParableVault` (verified on Sourcify): [`0x5432bE5713f358225d648eAb2EC9f699B25Ef317`](https://repo.sourcify.dev/11155111/0x5432bE5713f358225d648eAb2EC9f699B25Ef317)
  - Proven live lifecycle on Sepolia: [register subname badge](https://sepolia.etherscan.io/tx/0x2fafde65460e158cb2d085a18ab72fbf8d65ea98f18482d3b20ab4330554e559) → [write resolver records (`addr`, `strategy`, `brain`, `max_loss_bps`, `code_hash`)](https://sepolia.etherscan.io/tx/0x6bbc664fea34da2dae01cbfc58d916b6c1c0269268808cf19135ecae6821a919) → [bind to `EnsV2BadgeOracle`](https://sepolia.etherscan.io/tx/0x443c1073dc13a73812485b314f176dd7cef52117ac08bc08d2911965c15de388) → [revoke/burn via `unregister`](https://sepolia.etherscan.io/tx/0x02204e998f0735ae4e2bcbde6eb78d1d48fd840f9731b4042f5df3f96ad8609b), plus 4 real bot launches (`bot-1-bcc2.parable.eth`, `bot-2-3da0.parable.eth`, `bot-3-fad9.parable.eth`).

## Fallback if ENSv2 Sepolia subnames prove impossible today
1. Same Python/Solidity interface, but **skip the registry**: keep the badge record inside the oracle (`bind` stores expiry and bot, `revoke` sets a flag). Then ENS is only a text-record decoration on the parent name, as in FINAL_PLAN's fallback. `isValid` would check the stored expiry instead of `getState`.
2. If a reset removed the deployments, re-run `setup_parent()` after re-registering the parent (all addresses are env-overridable; re-read the table at https://docs.ens.domains/learn/deployments).
3. If ENS stays unusable by the 15:00 risk check, follow FINAL_PLAN: swap ENS out for 0G.
