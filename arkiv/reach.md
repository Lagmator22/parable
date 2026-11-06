# Reach: Who Parable is for, how to try it today, and what comes next

## 1. Who is Parable for, and would they use it?

Parable is built for two groups that already deal with **survivorship bias** in AI trading every day:

1. **AI trading agent builders and quantitative strategy creators** (on platforms like Alpha Arena, Recall, ElizaOS, and copy-trading marketplaces) who want a credible, tamper-proof way to prove they did not delete 17 losing bots and only advertise 3 lucky winners.
2. **Followers, allocators, and autonomous "fund-of-agents" managers** (including our own AI Swarm Manager and external AI assistants via Parable's MCP server) who need to query a creator's **complete cohort history—including the graveyard of dead bots—before trusting a strategy**.

Why they would actually use it:
- Self-reported backtests and screenshots are worthless; regulators (such as the CFTC) explicitly warn against cherry-picked track records.
- Parable does not ask bots to self-report. The Sepolia vault (`0x5432bE5713f358225d648eAb2EC9f699B25Ef317`) holds the practice capital, checks the bot's ENSv2 badge on every trade, prices trades via Chainlink ETH/USD, and emits every birth, trade, and death.
- Every cohort report card cross-checks the public Arkiv database against the vault's on-chain counters (`creatorBorn == Arkiv launched`, shown as **`✓ Vault count matches public record`** in the UI). If even one bot were missing from the public record, the mismatch badge immediately exposes it.

## 2. Can anyone try it today?

**Yes—both in the browser and directly against Arkiv Rabdi testnet:**

1. **Web app:** Open the live Parable dashboard (or run locally in 2 commands from the README). Immediately on page load, the app queries Arkiv Rabdi testnet for writer wallet `0x4Bf4Cf3Ac386A57DBf7C8b5eB93cE942d4504570` and displays:
   - The **Graveyard** of real Sepolia bots (`bot-1-bcc2.parable.eth`, `bot-2-3da0.parable.eth`, `bot-3-fad9.parable.eth`, and orphan `bot #1` rebuilt from the vault).
   - The **Creator Report Card** with `vault_count_matches: true`.
   - The **Compare Brains** table (`GET /api/report/brains`) aggregating `parable.bot` and `parable.death` rows across `rule`, `gemini:gemini-3.5-flash-lite`, and other brains.
2. **Direct Arkiv query (no Parable server needed):** Anyone can query our writer wallet's entities directly on Rabdi (`chainId: 7794095`, RPC `https://rpc.rabdi.db-chain.testnet.arkiv.network`):
   ```bash
   curl -s https://rpc.rabdi.db-chain.testnet.arkiv.network \
     -H "content-type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "arkiv_query",
       "params": [
         "arkiv.schema = str(\"parable.death\") && $owner = addr(0x4Bf4Cf3Ac386A57DBf7C8b5eB93cE942d4504570)",
         {"select": {"key": true, "attributes": true}}
       ]
     }'
   ```
3. **Via MCP (Claude Code / OpenAI Codex / Cursor):** Run `cd engine && uv run python -m parable.mcp_server` and call `graveyard()`, `report_card()`, or `compare_brains()`.

## 3. Will we keep building after ETHGlobal Mumbai?

**Yes.** The core architecture (World ID human checkpoint → ENSv2 revocable subname badge → Vault kernel → Arkiv public audit log & graveyard) is clean (~2,700 lines of Python + 450 lines of Solidity, 182 automated tests). Our post-Mumbai roadmap:

1. **Direct on-chain World ID proof verification inside `ParableVault.registerBot`** so even the Parable operator cannot register a bot without a valid World ID zero-knowledge proof.
2. **Real DEX execution adapter (Uniswap v4 hooks on Base/Arbitrum)** where the vault's `trade()` routes real capital through a Uniswap pool while keeping the exact same ENSv2 badge check, drawdown circuit-breaker (`checkAndRevoke`), and Arkiv graveyard.
3. **Open benchmark for LLM trading brains:** Running a continuous 24/7 cohort of Gemini, Claude, Gemma, and open-weight models where every model's full graveyard is queryable on Arkiv.
