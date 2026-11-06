# ETHGlobal submission text (copy-paste)

**Project name:** Parable

**Short description (under 100 characters):**
Every trading strategy has a graveyard. Parable is where AI trading bots can't hide theirs.

**Links:**
- Live: https://parable-demo.centralindia.cloudapp.azure.com
- Repo: https://github.com/Lagmator22/parable
- Vault (Sepolia, verified): https://sepolia.etherscan.io/address/0x5432bE5713f358225d648eAb2EC9f699B25Ef317
- Arkiv writer: https://rabdi.explorer.arkiv.network/address/0x4Bf4Cf3Ac386A57DBf7C8b5eB93cE942d4504570

## Description (about 300 words)
Anyone selling an AI trading bot can launch twenty, quietly delete the seventeen that lost money, and show off the three lucky survivors. Followers never see the graveyard, because the bot or its owner keeps the records.

Parable removes that trick. Bots never hold the money and never write their own history:
- **One human per creator.** A person approves every launch with World ID.
- **A name before the first trade.** The bot gets an ENSv2 subname (bot-7.parable.eth). It expires, can't be sold, and can be revoked.
- **The vault keeps score.** A vault contract on Sepolia holds the bot's practice money, checks its ENS badge and limits on every trade, trades at the Chainlink price, measures profit and loss itself, and ends the bot when it loses too much.
- **Nothing can be deleted.** Every birth, trade, refusal and death is written to Arkiv as a read-only record. Dead bots stay on a public register forever, and the vault's own count must match the register.

You can try to cheat on the site. A stranger's wallet tries to trade, a bot asks for ten times its limit, and the same person tries a fresh wallet to escape their graveyard. Each attempt is dry-run on the real contract, and the page shows the vault's own error code plus a command anyone can run to see the same refusal.

On top of that:
- **Swarms.** One "mind" model (Gemini, or Claude) checks many worker bots every minute and decides who keeps trading. It has no special powers, and every bot it stops stays public.
- **Brains to compare.** Jev models score buy/sell/hold and show their confidence, next to Gemini models and a simple rule.
- **Live telemetry.** Charts and numbers, each linked to Etherscan, Arkiv or ENS.
- **An MCP server.** Claude Code or Codex can launch, inspect and cheat-test bots on the same server.

This is testnet practice money. Next: the vault trades on a real exchange like Uniswap, with the same guarantees.

## How it's made
- **Contracts:** Solidity + Foundry, 39 tests. ParableVault (the kernel) and EnsV2BadgeOracle (lets the vault check ENSv2 badges during trade()). Chainlink ETH/USD price feed on Sepolia.
- **ENS:** ENSv2 on Sepolia. A PermissionedRegistry subregistry under parable.eth holds every bot's soulbound, expiring subname. A PermissionedResolver stores records (strategy, brain, max loss, code_hash fingerprint). The vault checks the badge on every trade and revokes it when the bot dies.
- **Arkiv:** a Node helper using the official @arkiv-network/sdk on the Rabdi testnet writes bot, event and death entities. Deaths and events are read-only, alive bots expire with their lease, and queries are filtered to our writer wallet and vault (fail closed). The register, brain comparison and bot histories on the site read from Arkiv.
- **World:** OIDC with PKCE, a nonce and single-use state, checked server-side against JWKS, with max_age=0 so every launch is a fresh check. The denied and expired paths launch nothing. An optional, rate-limited "demo approval" exists for people without World App; those bots are marked "demo" on the register.
- **Engine:** Python, FastAPI and web3.py. One shared transaction sender per wallet (no nonce clashes), an outbox that retries Arkiv writes, a repair pass that rebuilds any missing record from the vault, and RPC retries.
- **Frontend:** React + Vite, our own icon set, SVG charts.
- **MCP:** FastMCP, 14 tools.
- **Brains:** Jev (Autoloops), Gemini via Google's API, Claude via the Anthropic SDK (wired in).
- **Tests:** 167 Python + 39 Solidity + 8 frontend.
- **Hosting:** an Azure VM with Caddy HTTPS and systemd.
- **AI help** is disclosed in AI_USAGE.md.

## Partner prizes to select
ENS (Best use of ENSv2), Arkiv (Build on Arkiv), World (Agent Pass / World ID). Sponsor docs: `docs/ENS_NOTES.md`, `arkiv/*.md`, `docs/WORLD_NOTES.md`.
