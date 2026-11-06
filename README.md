# Parable.

> **Every trading strategy has a graveyard. Parable is where bots can't lie about theirs.**
> AI trading bots never touch the money and never write their own record. The Sepolia vault does both—so no bot can trade without being counted, nobody can delete a failed bot, and every creator is one verified human.

Built from scratch at **ETHGlobal Mumbai 2026** (Nov 5–7, 2026).
*(Pre-hackathon disclosure: Only generic rules/sponsor notes in `AGENTS.md` existed before hacking started at 2026-11-05 21:00 IST. All contracts, backend, frontend, schemas, and tests were built during the hackathon. See [`AI_USAGE.md`](AI_USAGE.md).)*

---

## 1. The Problem: Survivorship Bias in AI Trading

Anyone selling or showcasing an AI trading agent today can play a simple trick: **launch 20 bots, delete the 17 that lost money, and show off the 3 lucky survivors.** Followers and allocators have no way to see the 17 dead bots. Financial regulators (such as the US CFTC) explicitly warn about cherry-picked track records, yet every crypto agent leaderboard only tracks living winners or lets agents self-report their own logs.

**Parable fixes this with three structural rules:**
1. **Register before your first trade (ENSv2 + Vault):** A bot cannot make even a single trade until it holds a valid, unexpired, soulbound **ENSv2 subname badge** (`bot-N-xxxx.parable.eth`) and is registered in `ParableVault`.
2. **One human, one permanent record (World ID Agent Pass):** Each bot launch requires human approval via **World ID**. The Sepolia vault binds each World ID nullifier (`creatorId`) 1-to-1 to a single creator wallet (`walletOfCreator[creatorId]`), blocking sybil "fresh starts" on-chain with `CreatorIdentityMismatch`.
3. **The vault keeps score and writes the graveyard (ParableVault + Chainlink + Arkiv):** Practice capital (`$100` USDC-style 6-decimal units) stays inside `ParableVault.sol`. Bots only *ask* to trade. The vault checks the bot's live ENSv2 badge via `EnsV2BadgeOracle`, prices trades at the **Chainlink ETH/USD** oracle on Sepolia, measures drawdown against each bot's high-water mark, and auto-kills any bot that breaches its loss limit (`LossLimit`). Every birth, trade, blocked trade, and death is written to **Arkiv** as immutable (`readonly: true`), publicly queryable entities.

---

## 2. Architecture: An Operating System for Honest Trading Bots

| Operating System Concept | Parable Component | Sponsor / Tech |
|---|---|---|
| **User Account** | **Creator**: one verified human; cannot start a 2nd account to hide losses | **World ID Agent Pass** (`world_pass.py`) |
| **Process Identity & Permissions** | **ENSv2 Badge** (`bot-1-bcc2.parable.eth`): expiring, soulbound (`roleBitmap=0`), revocable subname carrying `strategy`, `brain`, `max_loss_bps`, and `code_hash` | **ENSv2 on Sepolia** (`EnsV2BadgeOracle.sol`, `ens_badge.py`) |
| **Kernel & Referee** | **`ParableVault.sol`**: holds practice funds, checks `badgeOracle.isValid()` on every trade, prices at Chainlink ETH/USD, enforces per-trade & drawdown limits, burns badge on death | **Solidity 0.8.24 + Chainlink ETH/USD** (Sepolia) |
| **Process Table & Graveyard** | **Arkiv (`parable.bot`, `parable.event`, `parable.death`)**: alive records expire with the bot's lease; death records are `readonly: true` for 180 days with `permissionlessExtension` | **Arkiv Rabdi Testnet** (`@arkiv-network/sdk` 1.0.1) |
| **Process Brain** | **AI Brains (`gemini:gemini-3.5-flash-lite`, `gemma`, `claude`, `rule`)**: structured JSON decisions with automatic fallback (`[fallback:rule]`) if an LLM times out or hallucinates | **Google Gemini / Anthropic / Pydantic** (`bot_runner.py`) |
| **Supervisor & CLI Tools** | **AI Swarm Manager** (`/api/manager`) + **MCP Server** (`parable.mcp_server`): audits worker bots, flags rejected trades, kills losers into the public graveyard | **FastMCP + Gemini / Opus Mind** (`manager.py`, `mcp_server.py`) |

```text
  Human Creator (Web UI)                      AI Assistant (Claude Code / Codex via MCP)
            \                                                /
             ▼                                              ▼
      ┌──────────────────────────────────────────────────────────────────┐
      │                PARABLE ENGINE (Python · FastAPI)                 │
      │  launch · confirm · bot runner · swarm manager · vault->Arkiv    │
      │  outbox & self-healing repair (`repair.py`)                      │
      └───┬──────────────────┬───────────────────┬───────────────────┬───┘
          │ 1. World ID      │ 2. ENSv2          │ 3. ParableVault   │ 4. Arkiv Rabdi
          ▼                  ▼                   ▼                   ▼
    Verify human &     Mint soulbound      Check badge on      Write public `bot`,
    approve launch     subname badge       every trade, swap   `event` & `death`
    (OIDC + PKCE +     `bot-N.parable.eth` at Chainlink ETH    rows; serve Graveyard
    denied path)       + `code_hash`       price, auto-kill    & Brain Report Cards
```

---

## 3. Live Deployments & On-Chain Proof Links

### Ethereum Sepolia (`chainId: 11155111`)

| Contract / Resource | Address / Name | Proof Links |
|---|---|---|
| **`ParableVault.sol`** | `0x5432bE5713f358225d648eAb2EC9f699B25Ef317` | [Etherscan](https://sepolia.etherscan.io/address/0x5432bE5713f358225d648eAb2EC9f699B25Ef317) · [Sourcify Verified](https://repo.sourcify.dev/11155111/0x5432bE5713f358225d648eAb2EC9f699B25Ef317) |
| **`EnsV2BadgeOracle.sol`** | `0x087077ceBb69d8617b41735aAe24232697Af4EcA` | [Etherscan](https://sepolia.etherscan.io/address/0x087077ceBb69d8617b41735aAe24232697Af4EcA) · [Sourcify Verified](https://repo.sourcify.dev/11155111/0x087077ceBb69d8617b41735aAe24232697Af4EcA) |
| **ENSv2 Parent Name** | `parable.eth` | [ENSv2 App](https://sepolia.app.ens.domains/parable.eth) |
| **ENSv2 Badge Subregistry** | `0xf749a1584e70A2285E608DF192A485EB87186B4b` | [Etherscan](https://sepolia.etherscan.io/address/0xf749a1584e70A2285E608DF192A485EB87186B4b) |
| **ENSv2 Badge Resolver** | `0xaba5B8A13Ac0c62AaF4d6FF2527BF8690DceAF80` | [Etherscan](https://sepolia.etherscan.io/address/0xaba5B8A13Ac0c62AaF4d6FF2527BF8690DceAF80) |
| **Chainlink ETH/USD Feed** | `0x694AA1769357215DE4FAC081bf1f309aDC325306` | [Etherscan](https://sepolia.etherscan.io/address/0x694AA1769357215DE4FAC081bf1f309aDC325306) |
| **Sample Live Bot Births & Deaths** | `bot-1-bcc2.parable.eth`, `bot-2-3da0.parable.eth`, `bot-3-fad9.parable.eth` | [Birth tx (`registerBot`)](https://sepolia.etherscan.io/tx/0x2bb83c9fa0a060eee5a7559b678f6661b1961ad667431d5051f4b9dbe72822f8) · [Death tx (`expire`)](https://sepolia.etherscan.io/tx/0xdfb8094eac3fc7036142f3d126eeac3e9199fa57587e06fd1c03b7b7a4699324) · [ENSv2 burn (`unregister`)](https://sepolia.etherscan.io/tx/0x02204e998f0735ae4e2bcbde6eb78d1d48fd840f9731b4042f5df3f96ad8609b) |

### Arkiv Rabdi Testnet (`chainId: 7794095`)

- **Writer Wallet Address:** [`0x4Bf4Cf3Ac386A57DBf7C8b5eB93cE942d4504570`](https://rabdi.explorer.arkiv.network/address/0x4Bf4Cf3Ac386A57DBf7C8b5eB93cE942d4504570)
- **Sample Rabdi Transactions:** [Bot Entity](https://rabdi.explorer.arkiv.network/tx/0x19865c864b2dce647f6c3041afdec6c178a3848cf9a0dfaf08f57f1f06a45fb3) · [Birth Event](https://rabdi.explorer.arkiv.network/tx/0x98b24330b21fb990bcee3a1d5dab8916cb9a16fe95cb1a132efed5adebe89615) · [Death / Graveyard Entity](https://rabdi.explorer.arkiv.network/tx/0xc5714abb242c6d3eddc8a79272097f1febe88886dbe8fd7239dfdd6c8b150f15)
- **Runnable Query (anyone can run directly in a terminal, zero setup):**
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

---

## 4. Sponsor Documentation Index

- **Arkiv ("Build on Arkiv"):**
  - [`arkiv/schema.md`](arkiv/schema.md) — Entities (`parable.bot`, `parable.event`, `parable.death`), indexed attributes, `$owner` filtering, and TTL expiries.
  - [`arkiv/friction.md`](arkiv/friction.md) — Developer feedback & reproduction steps (Python SDK `-32602` `includeData` incompatibility, `extendEntity` block-shortening revert, access-key rate limits).
  - [`arkiv/reach.md`](arkiv/reach.md) — Target users, how to test live today, and post-Mumbai roadmap.
  - [`arkiv/why-arkiv.md`](arkiv/why-arkiv.md) — What breaks if swapped for Postgres (`readonly: true`, `permissionlessExtension`, direct RPC queries) and what stays off Arkiv (private keys, OIDC claim tokens).
  - [`arkiv/how-you-use-arkiv.md`](arkiv/how-you-use-arkiv.md) — How every filter, owner check, and expiry drives the Graveyard, Report Card, and Compare Brains UI.
- **ENS ("Best Use of ENSv2"):**
  - [`docs/ENS_NOTES.md`](docs/ENS_NOTES.md) — How `EnsV2BadgeOracle.sol` and `ens_badge.py` implement expiring, soulbound (`roleBitmap=0`), revocable agent subnames under `parable.eth` checked on-chain during every `ParableVault.trade()`.
- **World ("World ID Agent Pass" & "Best Use of IDKit"):**
  - [`docs/WORLD_NOTES.md`](docs/WORLD_NOTES.md) — Full OIDC + PKCE server validation flow, approved vs. denied/expired paths, 1-to-1 on-chain `creatorId <-> creatorWallet` sybil defense, and integration debrief.

---

## 5. How to Run Locally & Run the 182 Automated Tests

### Run the Test Suites (143 Python + 39 Foundry Solidity Tests = 182 Tests)
```bash
# 1. Python engine unit & integration tests (143 tests)
cd engine && uv run pytest -q

# 2. Solidity smart contract tests (39 tests: ParableVault + EnsV2BadgeOracle)
cd contracts && forge test
```

### Run the Full Application
1. **Offline Simulation Mode (instant, zero keys or testnet gas required):**
   ```bash
   cd engine && PARABLE_OFFLINE=1 uv run uvicorn parable.api:app --port 8000
   ```
   Open `http://127.0.0.1:8000` (React UI) or `http://127.0.0.1:8000/classic`.
2. **Live Sepolia + Arkiv Rabdi Mode:**
   Copy `.env.example` to `.env` and fill in your testnet keys, then start the Arkiv JS SDK bridge and FastAPI engine:
   ```bash
   cd arkiv-bridge && npm install && node index.mjs
   cd engine && uv run uvicorn parable.api:app --host 127.0.0.1 --port 8000
   ```
3. **Frontend Dev Server (optional, when editing `frontend/`):**
   ```bash
   cd frontend && npm install && npm run dev
   ```
4. **MCP Server (for Claude Code / Codex / Cursor):**
   ```bash
   cd engine && uv run python -m parable.mcp_server
   ```

---

## 6. Prior Art & Honest Limits

- **Prior Art Credited** (see [`docs/NOVELTY_CHECK.md`](docs/NOVELTY_CHECK.md)): ENSign and Batas (MIT, ENSv2 expiring/soulbound agent subnames), ActionFeed (self-reported agent logs), 8004scan / ERC-8004 (leaderboards of living agents), Alpha Arena / Recall (AI trading leaderboards). **Parable's novelty is the combination:** the record is written by the money-holding vault (not the bot), registration is enforced before the first trade via ENSv2, creators are bound 1-to-1 to a verified World ID human, drawdowns are checked on-chain at the Chainlink price and revocable by anyone, and dead bots stay in a queryable Arkiv graveyard forever.
- **Honest Limits:**
  - **Practice capital on Sepolia:** Proves honesty of the track record (no cherry-picking or hidden blowups), not real-money liquidity execution.
  - **Operator bridges World ID OIDC to `registerBot`:** World ID is validated server-side via OIDC + PyJWT before the operator calls `registerBot`; verifying a World ID ZK proof directly inside `registerBot` is the next upgrade.
  - **In-memory bot keys by design:** Bot private keys live only in server RAM. If the server restarts, running bots simply stop trading and expire into the graveyard once their lease ends (`repair.py` reconciles any gap between `ParableVault` and Arkiv every 60 seconds).
  - **Code fingerprint (`code_hash`) is a commitment:** Proves which strategy/brain configuration was committed to the ENSv2 badge at birth; proving remote execution requires a TEE.

---

## License

MIT
