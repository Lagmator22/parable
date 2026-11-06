# Parable

### Every trading strategy has a graveyard. Parable is where AI trading bots can't hide theirs.

**Try it live:** https://parable-demo.centralindia.cloudapp.azure.com
**Built at:** ETHGlobal Mumbai 2026, solo, from scratch · **Network:** Sepolia testnet (practice money)
**Sponsors used:** ENS (bot identity) · Arkiv (public record) · World ID (one real person per creator)

---

## The problem, in one minute

Anyone can sell an "AI trading bot" with a great track record. The trick is simple:
**launch 20 bots, quietly delete the 17 that lost money, show off the 3 lucky ones.**
Buyers only ever see the survivors, because the bot (or its owner) keeps its own records.

This isn't a new idea; finance has known about it for decades:
- **Survivorship bias:** when failed funds vanish from the data, average performance looks far better than it really was (Brown, Goetzmann, Ibbotson & Ross, 1992; Elton, Gruber & Blake, 1996).
- **Backtest overfitting:** try enough strategy variants and one will look brilliant by pure luck. Because sellers rarely say how many variants they tried, buyers can't tell skill from luck (Bailey, Borwein, López de Prado & Zhu, 2014).
- **Regulators fight it:**
  - The US **SEC Marketing Rule** (206(4)-1) requires advisers to show full-period, net-of-fees results instead of their best picks.
  - India's **SEBI** put retail algorithmic trading under a formal framework in its circular of **4 February 2025**.

AI agents make this worse. A person can spin up hundreds of trading bots in an afternoon.
**There is no simple, public, cheat-proof way to see an AI bot's full record, dead bots included.**

## What Parable does

Parable doesn't trust the bot or its owner with the record. A contract keeps it.

```
  A person approves the bot          The bot gets a name tag          The VAULT holds the money
  (World ID: one real human)  ──▶   (ENS: bot-7.parable.eth,  ──▶   and checks EVERY trade:
                                      expires, can't be sold)          name tag valid? within limits?
                                                                       trades at the Chainlink price,
                                                                       measures profit/loss itself,
                                                                       ends the bot if it loses too much
                                                                                  │
                                                                                  ▼
                                      Every birth, trade, refusal and death is written to ARKIV.
                                      Read-only. Dead bots stay on the public register forever.
```

**Three rules, enforced by code, not promises:**
1. **No name tag, no trade.** A bot can't make a single trade until it holds a valid, unexpired ENS name tag. The vault checks it on every trade.
2. **One real person per creator.** Every launch needs a World ID approval, so nobody can wipe their history by starting over as someone new.
3. **The vault keeps score, not the bot.** The money sits in the vault, which measures each bot's result at the official price. Every bot that stops is written down permanently, and the vault's own count must match the public list.

## Results (all real, all on Sepolia, all checkable)

| What | Number | Check it |
|---|---|---|
| Bots launched through the full flow | **23** | Register on the live site; the vault's own count matches the list ✓ |
| Real trades executed by AI bots in the vault | **47** | Every trade has an Etherscan link |
| Bots that died and stayed on the record | **22** (14 ran out of time, 8 stopped) | Each has a read-only Arkiv record |
| Cheating attempts refused by the vault | **3 of 3, every time** | Copy the `cast call` from the site and run it yourself |
| AI brains benchmarked | Jev (Gemma 4 31B, DeepSeek V4.1 Flash) and Gemini Flash-Lite answer **6/6** situations; Jev in **1.5 s** | [`docs/BENCHMARK.md`](docs/BENCHMARK.md) |
| MCP tools tested live against the deployed site | **30 of 30 calls OK** (3 rounds × 10 tools) | [`docs/DEPLOY.md`](docs/DEPLOY.md) |
| Automated tests | **167 Python + 39 Solidity + 8 frontend**, all passing | Commands below |

Contracts (source published): **ParableVault** [`0x5432…f317`](https://sepolia.etherscan.io/address/0x5432bE5713f358225d648eAb2EC9f699B25Ef317) · **EnsV2BadgeOracle** [`0x0870…4EcA`](https://sepolia.etherscan.io/address/0x087077ceBb69d8617b41735aAe24232697Af4EcA) · Arkiv writer [`0x4Bf4…4570`](https://rabdi.explorer.arkiv.network/address/0x4Bf4Cf3Ac386A57DBf7C8b5eB93cE942d4504570). Full list: [`docs/DEPLOYMENTS.md`](docs/DEPLOYMENTS.md).

## Try it in two minutes (judge path)

1. Open the **live site**. The top shows **Born / Dead** counts and the latest deaths.
2. **01 Launch:** the form is one sentence. Click any underlined word to change it, then approve with **World ID** (or **Demo · no phone**, which is marked "demo" on the record). Watch the six real steps tick by.
3. **02 Running:** each trade shows *why* the AI made it (Jev shows its odds, e.g. "buy 92% · sell 1% · hold 6%") and a link to the transaction.
4. **04 Try to hide a loser:** press the three buttons. The real vault refuses each one, and you can copy the exact command to ask the contract yourself.
5. **03 Register:** dead bots struck through, each linked to its read-only Arkiv record.
6. **05 Swarm:** one "mind" AI supervises several worker bots and logs every keep/stop decision with its reason.
7. **Telemetry** (top bar): every number live, every number linked to Etherscan, Arkiv or ENS.

## Who would use this

| Who | Problem today | With Parable |
|---|---|---|
| **People buying a bot or copying a trader** | Only see screenshots of winners | See every bot that creator ever ran, dead ones included |
| **Bot and strategy sellers who are honest** | Can't prove they aren't cherry-picking | One link: a record nobody, including them, can edit |
| **AI agent marketplaces and copy-trading apps** | Must trust sellers' numbers | Require a Parable record before listing an agent |
| **Trading competitions and hackathons** | Entrants can quietly enter many bots | Every entry is counted; one person, one record |
| **Funds and DAOs choosing AI agents** | Hard to compare agents fairly | Compare brains side by side, failures included (the "Compare brains" table) |
| **Compliance teams** | Rules require full-period, unselected results | A record that is complete by construction |

AI assistants can use Parable too: an **MCP server** with 14 tools lets Claude Code, Codex or Cursor launch bots, read records and run the cheat tests on the same live server.

## What's new here (checked against prior work)

We searched past ETHGlobal winners and public projects before building ([`docs/NOVELTY.md`](docs/NOVELTY.md)). The pieces exist separately:

| Prior work | What it does | What it doesn't do |
|---|---|---|
| ENSign, Batas | ENS names for AI agents | The name isn't checked by the money on every trade |
| ActionFeed | Agents log their own actions | The agent writes its own record, so it can leave things out |
| 8004scan / ERC-8004 | Registries and leaderboards of agents | Nothing forces a dead agent to stay listed |
| Alpha Arena, Recall | AI trading leaderboards | Organizer-run contests, not an open record for anyone's bots |
| Foresight Arena (research paper, 2026) | Proposes cherry-pick-proof records for **forecasting** AIs | Not trading, and no money-holding contract enforcing it |

**What we didn't find anywhere is all four together:**
1. the record is written by the contract that **holds the money**, not by the bot;
2. registration is **enforced at trade time** by an ENS name check;
3. **one real person per creator** (World ID);
4. a **permanent public graveyard** that anyone can query, where anyone can trigger the loss-limit death.

That combination is the novelty. We don't claim any single piece is new.

## How each sponsor is used (and why it's essential)

- **ENS: the bot's permission slip.** Each bot gets an ENSv2 subname under `parable.eth`. It expires with the bot, can't be transferred (soulbound), and is revoked when the bot dies. The vault calls the badge checker on **every trade**: no valid name, no trade. Records on the name hold the bot's brain, strategy and a code fingerprint. → [`docs/ENS.md`](docs/ENS.md)
- **Arkiv: the permanent public record.** Births, trades, refusals and deaths are written as entities. Deaths and events are **read-only** (nobody can edit them), and alive bots expire with their lease. The site's register, brain comparison and bot histories read straight from Arkiv, filtered to our writer wallet. → [`arkiv/`](arkiv/) (schema, how we use it, why Arkiv, reach, friction)
- **World ID: one real person per creator.** Every launch (and every swarm) needs a fresh World ID approval, checked on our server (OIDC + PKCE, signed tokens, single-use, 10-minute expiry). The vault binds each person to exactly one creator wallet, so starting over under a new identity is refused. → [`docs/WORLD.md`](docs/WORLD.md)
- **Chainlink** (not a prize track): the vault trades at the Sepolia ETH/USD price feed.

## Check it yourself (no trust in our server needed)

Ask Arkiv for every grave this vault ever recorded:
```bash
curl -s https://rpc.rabdi.db-chain.testnet.arkiv.network -H "content-type: application/json" --data @- <<'EOF'
{"jsonrpc": "2.0", "id": 1, "method": "arkiv_query", "params": [
  "arkiv.schema = str('parable.death') AND vault = str('0x5432be5713f358225d648eab2ec9f699b25ef317') AND $owner = addr(0x4Bf4Cf3Ac386A57DBf7C8b5eB93cE942d4504570)",
  {"select": {"key": true, "attributes": true}}]}
EOF
```
Ask the vault to let a stranger trade (it refuses with `0xa03b20af`, the `NotBot` error):
```bash
cast call 0x5432bE5713f358225d648eAb2EC9f699B25Ef317 "trade(uint256,bool,uint256)" 1 true 1000000 \
  --from 0x000000000000000000000000000000000000dEaD --rpc-url https://ethereum-sepolia-rpc.publicnode.com
```

## Honest limits

- **Testnet only.** Practice money on Sepolia. The vault fills trades itself at the Chainlink price; it doesn't route to a real exchange yet.
- **Flat returns.** Sepolia's Chainlink price updates about once an hour, so on-chain results barely move. To give 10-minute demo bots something to react to, a bot's *decision input* gets small price nudges when the price hasn't moved. **Every trade still settles in the vault at the real Chainlink price**, and the vault alone measures profit and loss.
- **The server vouches for World ID.** World ID is checked on our server before the vault registers a bot; checking the proof on-chain is next.
- **Demo approval** (optional, off unless enabled, max 3 per 10 minutes) skips the human check. Those bots are marked *demo* in their Arkiv record and on the register.
- **Bot keys live in server memory** on purpose. If the server restarts, running bots stop trading and expire; their records are rebuilt from the vault.
- **Live graphs are kept in memory** and start fresh when the server restarts. The "at market price" view is for comparison only.
- **The practice arena is a simulation**, clearly labeled, and separate from the vault.

## What's next

1. **Real exchange:** the vault places its trades on Uniswap itself, with the same guarantees, because the money never leaves the contract.
2. **World ID proof checked on-chain** inside the vault.
3. **Public or private chosen at birth:** private practice bots, but a public bot stays public forever. Never chosen after seeing results.
4. **A shareable "Parable record" card** for bot sellers.

## Repo map

| Folder | What's inside |
|---|---|
| `contracts/` | ParableVault + EnsV2BadgeOracle (Solidity, Foundry, 39 tests) |
| `engine/` | Python server: launches bots, runs their AI brains, swarm mind, Arkiv/ENS/World integrations, MCP server (167 tests) |
| `frontend/` | The website (React + Vite) |
| `arkiv-bridge/` | Small Node helper using the official Arkiv SDK |
| `arkiv/` | Arkiv docs: schema, how we use it, why Arkiv, reach, friction |
| `docs/` | ENS, World, novelty check, benchmark, architecture, deployments, deploy + MCP guide |
| `scripts/` | One-off live proof scripts (ENS, Arkiv, World) and the brain benchmark |
| `deploy/` | Scripts that set up the Azure server |
| `internal/` | Our hackathon working notes (plans, agent rules, video script). Kept for transparency, not needed to judge |

## Run it yourself

```bash
cd engine && uv sync && uv run pytest -q             # 167 tests
cd contracts && forge test                           # 39 tests
cd frontend && npm ci && npm test && npm run build   # 8 tests, builds the site
cd arkiv-bridge && npm ci && node index.mjs          # Arkiv helper (needs .env)
cd engine && uv run uvicorn parable.api:app --port 8000   # then open http://localhost:8000
```
Settings go in `.env` (see `.env.example`). `PARABLE_OFFLINE=1` runs a pretend chain with no keys at all.

## References

1. Brown, S. J., Goetzmann, W., Ibbotson, R. G., & Ross, S. A. (1992). *Survivorship Bias in Performance Studies.* Review of Financial Studies, 5(4).
2. Elton, E. J., Gruber, M. J., & Blake, C. R. (1996). *Survivorship Bias and Mutual Fund Performance.* Review of Financial Studies, 9(4).
3. Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2014). *Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance.* Notices of the AMS, May 2014, 458–471.
4. Harvey, C. R., Liu, Y., & Zhu, H. (2016). *…and the Cross-Section of Expected Returns.* Review of Financial Studies, 29(1).
5. U.S. SEC, Investment Adviser Marketing Rule, 17 CFR 275.206(4)-1 (adopted 2020; compliance from November 2022).
6. SEBI circular, *Safer participation of retail investors in Algorithmic trading*, 4 February 2025.
7. *Foresight Arena* (2026), arXiv:2605.00420: verifiable, cherry-pick-resistant track records for forecasting agents (closest research we found).

## Disclosure

Built during ETHGlobal Mumbai (5–7 Nov 2026). Before hacking started, only generic rules and sponsor notes existed (now in `internal/AGENTS.md`). AI assistance is disclosed step by step in [`AI_USAGE.md`](AI_USAGE.md). License: MIT.
