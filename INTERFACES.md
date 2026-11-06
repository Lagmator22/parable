# Parable: module contracts (shared by all builders)

Every builder codes against these signatures. Changing a signature means updating this file in the same change. Python 3.12+, Pydantic v2, web3.py v7, FastAPI. All money values are integers: USD has 6 decimals (USDC style), ETH has 18.

## Repo layout
```
contracts/                 Foundry project (Solidity ^0.8.24)
  src/ParableVault.sol     the kernel: holds money, checks badge, trades at oracle price, measures loss
  src/interfaces/IBadgeOracle.sol
  src/adapters/EnsV2BadgeOracle.sol   ENSv2-backed IBadgeOracle (ENS builder)
  test/  script/
engine/                    Python package `parable` (uv project; deps already in pyproject, do NOT edit it)
  parable/config.py        env loading (Settings)
  parable/models.py        shared Pydantic models (below)
  parable/vault.py         web3 client for ParableVault
  parable/ens_badge.py     ENSv2 badge issue/read/revoke
  parable/arkiv_store.py   Arkiv records + queries
  parable/world_pass.py    World ID Agent Pass approval (FastAPI router)
  parable/bot_runner.py    bot loop: LLM decision + rule fallback
  parable/api.py           FastAPI app wiring everything
spikes/                    standalone proof scripts per sponsor
arkiv/                     Arkiv judging files
```

## ParableVault.sol (Sepolia)
- `constructor(address priceFeed, address badgeOracle, address operator, uint256 maxPriceAge)`
- Price: Chainlink `AggregatorV3Interface` ETH/USD (8 decimals). Reject if `updatedAt` is older than `maxPriceAge`, or if the answer is ≤ 0.
- Status: `0 None, 1 Alive, 2 Dead`. DeathCause: `0 None, 1 Expired, 2 Killed, 3 LossLimit`.
- `registerBot(address bot, bytes32 creatorId, address creatorWallet, bytes32 badgeNode, uint64 expiresAt, uint256 startCashUsd, uint256 maxTradeUsd, uint16 maxLossBps, bytes32 strategyId) returns (uint256 botId)`. Only callable by `operator`. Each `creatorId` (World nullifier) maps to exactly one `creatorWallet`; a second wallet for the same creatorId reverts, and so does a second creatorId for the same wallet.
- `trade(uint256 botId, bool buyEth, uint256 amountUsd)`. `msg.sender` must be the bot address. Requires: Alive, `block.timestamp < expiresAt`, `badgeOracle.isValid(badgeNode, bot)`, `amountUsd <= maxTradeUsd`, enough balance, fresh price. Executes inside the vault at the oracle price (buy: cash → eth; sell: eth worth amountUsd → cash). Updates `hwm` if equity > hwm. If drawdown ≥ maxLossBps after the trade → auto-kill with LossLimit.
- `checkAndRevoke(uint256 botId)`. **Anyone** can call it. Recomputes equity at the oracle price; if `(hwm - equity) * 10000 / hwm >= maxLossBps` → dies with LossLimit; otherwise reverts `NotOverLimit()`.
- `kill(uint256 botId)`: creatorWallet or operator → Killed. `expire(uint256 botId)`: anyone, once `block.timestamp >= expiresAt` → Expired.
- On death: status Dead, `badgeOracle.revoke(badgeNode)` (try/catch, must never block the death), counters updated, event emitted.
- Views: `equityUsd(botId)`, `getBot(botId)` (returns a struct), `totalBorn()`, `totalDead()`, `creatorBorn(creatorId)`, `creatorDead(creatorId)`, `botIdOf(address bot)`.
- Events: `BotBorn(botId, bot, creatorId, strategyId, badgeNode, expiresAt, startCashUsd, maxTradeUsd, maxLossBps)`, `Traded(botId, buyEth, amountUsd, ethAmount, priceUsd8, equityUsd)`, `BotDied(botId, cause, finalEquityUsd, startCashUsd, bornAt, diedAt)`.
- Custom errors for every rejection (e.g. `NotRegistered`, `NotAlive`, `Expired`, `BadgeInvalid`, `OverTradeLimit`, `InsufficientBalance`, `StalePrice`, `NotBot`, `NotOverLimit`, `CreatorIdentityMismatch`) so the engine can log *why* a trade was blocked.

## IBadgeOracle.sol
```solidity
interface IBadgeOracle {
    function isValid(bytes32 node, address bot) external view returns (bool);
    function revoke(bytes32 node) external; // only callable by the vault
}
```

## Python models (engine/parable/models.py)
```python
class BotRules(BaseModel): strategy: str; start_cash_usd: int; max_trade_usd: int; max_loss_bps: int; lease_seconds: int
class TradeDecision(BaseModel): action: Literal["buy","sell","hold"]; amount_usd: int = 0; reason: str  # LLM output, validated
class BotRecord(BaseModel): bot_id: int; bot_address: str; creator_id: str; ens_name: str; strategy: str; rules: BotRules; status: Literal["alive","dead"]; born_at: int; born_tx: str
class BotEvent(BaseModel): bot_id: int; kind: Literal["birth","trade","rejected","death"]; at: int; tx_hash: str | None; data: dict
class DeathRecord(BaseModel): bot_id: int; cause: Literal["expired","killed","loss_limit"]; final_equity_usd: int; start_cash_usd: int; pnl_bps: int; lifetime_s: int; tx_hash: str
class ReportCard(BaseModel): subject: str; launched: int; alive: int; dead: int; profitable: int; worst_pnl_bps: int; avg_pnl_bps: float; vault_count_matches: bool
```

## Module function contracts
- `ens_badge.py`: `issue_badge(label: str, bot_address: str, expires_at: int, records: dict[str,str]) -> tuple[str, str]` returns (ens_name, node_hex); `read_badge(ens_name) -> dict`; `revoke_badge(ens_name) -> str` (tx hash); `is_valid(ens_name, bot_address) -> bool`.
- `arkiv_store.py`: `put_bot(rec: BotRecord, lease_seconds: int) -> str` (entity key; alive record expires with the lease); `put_event(ev: BotEvent) -> str`; `put_death(d: DeathRecord) -> str`; `graveyard(creator_id: str) -> list[DeathRecord]`; `bots(creator_id: str | None = None, status: str | None = None) -> list[BotRecord]`; `report_card(creator_id: str | None = None, strategy: str | None = None) -> ReportCard`.
- `world_pass.py`: FastAPI `router` with `GET /world/start?purpose=launch_bot&ref=<pending_id>` → redirect to World; `GET /world/callback` → validates server-side, returns or redirects with an `Approval`; plus `get_approval(pending_id) -> Approval | None` where `Approval(BaseModel): pending_id, subject (World nullifier/subject), approved: bool, reason: str, at: int`. `WORLD_MOCK=1` env enables a mock approve/deny flow for local dev.
- `vault.py`: `register_bot(...) -> (bot_id, tx)`, `trade(bot_key, bot_id, buy, amount_usd) -> tx`, `check_and_revoke(bot_id) -> tx`, `kill(bot_id) -> tx`, `expire(bot_id) -> tx`, `equity(bot_id) -> int`, `get_bot(bot_id) -> dict`, `counts(creator_id) -> (born, dead)`, `decode_revert(err) -> str`.
- `bot_runner.py`: `decide(state) -> TradeDecision` (Claude Haiku with structured output; on any failure → `rule_decide(state)`), `run_bot(bot_id, bot_key, rules, stop_event)` loop.

## Env (.env, never committed; see .env.example)
`SEPOLIA_RPC_URL, OPERATOR_PRIVATE_KEY, VAULT_ADDRESS, CHAINLINK_ETH_USD=0x694AA1769357215DE4FAC081bf1f309aDC325306, ENS_PARENT_NAME, ARKIV_RPC_URL=https://rpc.rabdi.db-chain.testnet.arkiv.network, ARKIV_PRIVATE_KEY, WORLD_CLIENT_ID, WORLD_CLIENT_SECRET, WORLD_MOCK, ANTHROPIC_API_KEY, BOT_MODEL=claude-haiku-5-5`
