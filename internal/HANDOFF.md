# HANDOFF — MORNING CHECKLIST (Sat 7 Nov 2026, written 01:00 IST). Submission deadline 09:00, target 07:30.

**State:** everything works live on Sepolia and was tested repeatedly overnight (see AGENTS.md log, 01:00 entry).
Tests: 167 Python + 39 Foundry + 8 frontend, all passing. Brains in use: Jev (Gemma 4 31B, DeepSeek V4.1 Flash),
Gemini 3.5 / 3.1 Flash-Lite, simple rule (docs/BENCHMARK.md). Claude is wired but hidden (no credit, by choice).

**Left for the user (in order):**
1. Deploy (5 min, docs/DEPLOY.md): copy `.env` to the VM (`scp …`), start the two services, add
   `https://parable-demo.centralindia.cloudapp.azure.com/world/callback` in the World portal, stop the laptop server
   (only ONE engine may use the wallet at a time).
2. Make the GitHub repo public (Settings → bottom → Change visibility).
3. 15 min before recording: start a swarm + a solo bot on the live site (internal/VIDEO_SCRIPT.md "Before recording").
4. Record the 3:30 video following internal/VIDEO_SCRIPT.md (includes a live MCP part via Claude Code; setup command in docs/DEPLOY.md).
5. Submit to ENS + Arkiv + World on the ETHGlobal dashboard with the live link, repo link and video.

**Gotchas:** press Cmd+Shift+R if the page looks old. "Demo · no phone" approval needs WORLD_ALLOW_DEMO=1 (already in .env),
max 3 demo launches per 10 minutes; demo bots are marked "demo". Returns look flat because the vault scores at the
Chainlink price (barely moves on testnet) — say so in the video. Bot #12 shows approval "world" although it was
approved in the global test mode before per-launch marking existed (the only such row).

---

# HANDOFF: CURRENT STATE (Fri 6 Nov 2026, ~21:00 IST, after commit fe419ee). Read this section first.

**Built and pushed since the older notes below:**
- Bot gas top-ups were failing on-chain (21000 gas limit) so no bot could trade. Fixed (100k limit). First real AI trade: bot 5 (Gemini) bought $20 of ETH on Sepolia.
- Website rebuilt in a "public register" style (black/white, square edges, Archivo + IBM Plex Mono, orange only for death/refusal, blinking squares for running things). Designed first on a Claude Design canvas (private link in chat).
- Sections: hero (Born/Dead counts, latest deaths) · 01 Launch (one sentence; click a word, pick from the tray) · 02 Running · 03 Register (dead names struck through) · 04 Try to cheat (black band) · 05 Swarm · 06 Benchmarks · How it works. Plus a **Telemetry** panel that slides down from the top bar (12 numbers, 3 live charts, agent table, event feed, "check it yourself" links + copy commands, both commands tested).
- Brains: `rule`, `claude:<model>` (Haiku/Sonnet/Opus 5.5), `gemini:<model>`, `gemma:<model>`. `local` removed. Claude shows "not set up" while the Anthropic account has no credit (probe at server start, `engine/parable/minds.py`). **No credit yet** (tested: "credit balance is too low").
- Swarm v2 (`engine/parable/manager.py`, routes in `swarm_api.py`): pick mind + worker brains, ONE World ID approval launches all workers on Sepolia, mind checks every 60 s, safety rule (−3% or 2 refusals) overrides it, live status. Race condition found by security review: fixed + test.
- Live graph recorder (`engine/parable/series.py`): every 10 s, each bot's vault value AND its holdings at the live Coinbase price; ETH market vs Chainlink. In memory only.
- Launch progress shows the server's REAL steps ("step N/6 done"), never a timer.
- Tests: **153 Python + 39 Foundry + 8 frontend** pass. API contract: `internal/FRONTEND_CONTRACT.md` (bottom section has swarm + series routes).

**Decisions locked with the user:** practice money on Sepolia only; the register is ALWAYS public (future work: choose public/private at birth, never after results); "real platform" = roadmap line "next, the vault swaps on Uniswap itself" (a centralized exchange would break the guarantee, do not promise it).

**Still to do:** live run (1 bot + 1 swarm) by the user; Claude credit then server restart; a public deploy (see the user's chosen platform); README/ARCHITECTURE/video script updates; make repo public; record video; submit to ENS + Arkiv + World by 07:30 Sat.

---

# HANDOFF: read this first (updated Fri 6 Nov 2026, ~18:48 IST)

You are auditing / taking over **Parable**, a solo ETHGlobal Mumbai 2026 project.
Everything below is the **exact, verified truth** as of commit `53eb608` (plus this handoff update).
Also read: `internal/AGENTS.md` (rules + iteration log), `FINAL_PLAN.md` (locked plan + checklists + demo script),
`JUDGING.md` / `../JUDGING.md` (prize criteria), `ARCHITECTURE.md` (diagrams), `INTERFACES.md` (module contracts),
`internal/FRONTEND_CONTRACT.md` (API for the UI), `docs/DEPLOYMENTS.md` (addresses + live proof links).

---

## 0. Deadlines & Submission Rules
- Hacking ends **Sat 7 Nov 09:00 IST (hard)**. Target: **submit by 07:30 IST**.
- Video 2–4 min (aim 2:30–2:55) in the user's own voice (no TTS, ≥720p, not recorded on a phone).
- Repo must be **made public** before submit (GitHub `Lagmator22/parable` is currently private).
- Steady commits required (we have 18+ clean, atomic commits). `AI_USAGE.md` disclosure updated at every step.
- Partner picks (max 3): **ENS + Arkiv + World**. (Chainlink Sepolia ETH/USD feed is also used on-chain, not a prize pick.)

---

## 1. About the User (Follow Strictly)
- Solo, new to web3/finance, strong agentic-AI dev (GSoC, OVAT). Prefers Python. Spent ~$400 to attend; wants to WIN.
- **Very simple language always**: explain every jargon word once, short sentences, tables, small ASCII diagrams.
- Every install/run step must say **which folder** and **exactly where to click**.
- **Be honest/ruthless** about odds, bugs, and novelty. Never claim something works without proof.
- Code: small readable files (≤ ~300 lines), short functions, plain-English header comment per file, comments on the
  web3/finance "why". **Edge-case tests in the same commit as each feature.**
- Before every commit:
  - `cd ~/ethglobal/parable/engine && uv run pytest -q` (**144 passed**)
  - `cd ~/ethglobal/parable/contracts && ~/.foundry/bin/forge test` (**39 passed**; forge is not on PATH in non-login shells)
  - `cd ~/ethglobal/parable/frontend && npm test && npm run build` (**5 passed**, builds `frontend/dist/`)
- After each phase: commit + push; update `ARCHITECTURE.md`, `internal/AGENTS.md` section 0 iteration log, `AI_USAGE.md`.
- Note on other tools: **OpenAI Codex ran out of usage limits** around 18:08 IST right after finishing `ProofBar.tsx`,
  `Swarm.tsx`, and `useDashboard.test.tsx`. Antigravity (Gemini) took over both backend and frontend from that point.

---

## 2. Security Rules (Never Break)
- Never commit secrets. `.env` and `.env.*` are gitignored (except `.env.example`). Never print keys.
- Operator wallet `0x4Bf4Cf3Ac386A57DBf7C8b5eB93cE942d4504570` is **test-only**: never real money.
- Users never see raw errors (only short `detail` text / decoded vault error names).
- `arkiv-bridge` (`127.0.0.1:8787`) requires `x-bridge-token: <ARKIV_BRIDGE_TOKEN>`, checks local `Host`, and rejects any
  browser `Origin` header.

---

## 3. What Parable Is (Pitch)
"Every trading strategy has a graveyard. Parable is where bots can't lie about theirs."
AI trading bots never touch money and never write their own record. A World ID human approves a launch → the bot
gets a soulbound, expiring **ENSv2 name tag** (`bot-N-xxxx.parable.eth`) with a `code_hash` fingerprint → the
**ParableVault** contract (Sepolia) holds its practice money, checks the badge + limits on every trade, trades at the
**Chainlink** ETH/USD price, measures loss itself against the bot's high-water mark (`hwmUsd`), and auto-kills at the
loss limit → every birth / trade / blocked trade / death is written to **Arkiv** (public DB) → dead bots stay in a
**graveyard** nobody can delete. Report cards count failed bots too and verify `vault_count_matches: true`
("vault count == Arkiv count").

---

## 4. Complete Verification Scoreboard (What Is Built & Proven Live)

### 4.1 Test Suites (188 / 188 Passing)
- **Solidity (`contracts/`):** `39 passed` (`24 ParableVaultTest + 15 EnsV2BadgeOracleTest`).
- **Python (`engine/`):** `144 passed` across `test_api.py`, `test_arkiv_store.py`, `test_bot_runner.py`,
  `test_ens_badge.py`, `test_launcher.py`, `test_repair.py`, `test_tx_sender.py`, `test_vault.py`, `test_world_pass.py`.
- **Frontend (`frontend/`):** `5 passed` across 4 test files (`App.test.tsx`, `SelectMenu.test.tsx`, `api.test.ts`,
  `useDashboard.test.tsx`), plus clean `tsc -b && vite build` into `frontend/dist/`.

### 4.2 On-Chain Sepolia & Arkiv State (Verified Live)
- **`ParableVault` (Sepolia, verified):** `0x5432bE5713f358225d648eAb2EC9f699B25Ef317`
- **`EnsV2BadgeOracle` (Sepolia, verified):** `0x087077ceBb69d8617b41735aAe24232697Af4EcA`
- **ENSv2 Parent (`parable.eth`):** Registry `0x944523b32916F123923920d32aD92877341990f4`
- **Chainlink ETH/USD Feed (Sepolia):** `0x694AA1769357215DE4FAC081bf1f309aDC325306` (live price ~$2,238.11)
- **Operator & Arkiv Writer Wallet:** `0x4Bf4Cf3Ac386A57DBf7C8b5eB93cE942d4504570` (~0.0645 Sepolia ETH, ~10 tGLM)
- **Verified Creator (`creator_id`):** `0xa4b35b7ef915b074605a2a193e3355a99b9072047a20d98b2f6a048fbd504411`
- **4 Real Bots on Sepolia (`totalBorn = 4`, `totalDead = 4`, `vault_count_matches = true`):**
  - `bot #1` (orphan from first launch before nonce fix → automatically rebuilt into Arkiv by `repair.py`!)
  - `bot #2` (`bot-1-bcc2.parable.eth`) → expired after 10-min lease, archived in Arkiv graveyard
  - `bot #3` (`bot-2-3da0.parable.eth`) → expired after 10-min lease, archived in Arkiv graveyard
  - `bot #4` (`bot-3-fad9.parable.eth`) → expired after 10-min lease, archived in Arkiv graveyard

---

## 5. Every Post-15:45 Fix & Feature Shipped (`9bae1e7` → `ad79033` → `503364f` → `9f76883` → `53eb608`)

### 5.1 Live-Run Bug Fixes (`9bae1e7`)
1. **Non-blocking Arkiv birth writes (`engine/parable/launcher.py` & `api.py`):**
   - `_create_bot()` now runs `put_bot` and `put_event(birth)` in a daemon thread (`writer.join(timeout=0.05)` so fast
     unit tests still complete synchronously, while slow on-chain Arkiv writes never stall `/api/launch/{id}/confirm`).
   - `GET /api/bots` merges in-memory `lau.live` bots so newly born bots appear immediately on the dashboard before the
     background Arkiv write completes.
2. **Flat Sepolia Chainlink Oracle Signal Ticks (`engine/parable/bot_runner.py`):**
   - Because Sepolia Chainlink updates only ~once an hour, `signal_price()` injects small ±10–25 bps signal ticks into
     the bot's `history` (and seeds 2 reference points on tick 1 in `read_state()`) when the oracle is unchanged between
     ticks. Result: `momentum`, `dip_buyer`, `yolo`, and `gemini:gemini-3.5-flash-lite` all trade **immediately on tick 1**
     upon birth, while `state["price"]` and the Sepolia `ParableVault` still settle strictly at the real Chainlink price.
3. **Arkiv `extendEntity` TTL Fix (`arkiv_store.py` & `arkiv-bridge/index.mjs`):**
   - Previously, `put_bot` added `+ 3600` seconds even to rebuilt dead bots (`180d + 1h`), causing `put_death`'s
     `extendEntity(180d)` to revert with `would shorten its life`. Fixed in both `arkiv_store.py` (cap dead-bot TTL at
     `DEATH_LIFETIME` and skip `_mark_dead` when already `"dead"`) and `arkiv-bridge/index.mjs` (ignore `shorten its life`
     on `extendEntity`).
4. **RPC Keep-Alive Reconnect & Clock-Skew Guard (`vault.py` & `launcher.py`):**
   - `vault.py` `_read()` clears cached `_w3`/`_vault` and retries once on Tenderly idle `ConnectionResetError(54)`.
   - `Launcher.sync_deaths()` catches `NotExpired` when `time.time() >= bot.expires_at` locally before the next 12s
     Sepolia block timestamp catches up.
   - `Launcher.report()` catches RPC errors on `vault.counts()` and degrades gracefully (`vault_count_matches=False`)
     instead of crashing `/api/report` with 500.

### 5.2 All Stretch Goals Completed (`ad79033`, `503364f`, `53eb608`)
1. **Stretch #1 — MCP Server (`engine/parable/mcp_server.py`):**
   - Built with `FastMCP("Parable")` (`uv run python -m parable.mcp_server`).
   - Exposes 7 tools for Claude Code / Cursor / Codex: `launch_bot`, `list_bots`, `graveyard`, `report_card`,
     `compare_brains`, `bot_events`, `kill_bot`.
2. **Stretch #2 — AI Swarm Manager (`engine/parable/manager.py` + `frontend/src/dashboard/Swarm.tsx`):**
   - `GET /api/manager` & `POST /api/manager/start`.
   - Uses `gemini:gemini-3.5-flash-lite` (with automatic rule fallback) to audit all known bots, flag bots with
     `rejected` vault events, and kill losing bots (`pnl_bps <= -300` or `>= 2` rejected trades) that it owns.
   - Auto-populates on first `GET /api/manager` read and deduplicates `(bot_id, action)` so the `#swarm` panel is
     populated immediately on page load.
3. **Stretch #3 — Code Fingerprint on ENSv2 Badges (`bot_runner.py`, `launcher.py`, `api.py`):**
   - `code_fingerprint(rules)` computes a short SHA-256 hash (`0x` + 16 hex chars) of `brain:strategy:preset:max_loss_bps`.
   - Written to the ENSv2 subname text records (`code_hash` + `brain`) at badge issue time and returned on `/api/bots`
     and `/api/graveyard/{creator_id}`. Displayed as an `ENSv2 code: 0x...` pill on every bot card and grave card.
4. **Stretch #4 — Market Arena Benchmark Simulator (`engine/parable/arena.py` + `frontend/src/dashboard/Arena.tsx`):**
   - Modeled after **nof1 Alpha Arena**, **Recall Network**, and **FinAI Agent Market Arena (AMA)**.
   - Live at `GET /api/arena` and `POST /api/arena/run` (Section 04 `#arena` in the React UI).
   - Runs 4 contenders (`Gemini 3.5 Flash-Lite · Momentum`, `Gemini 3.5 Flash-Lite · Dip Buyer`, `Rule Baseline · Dip Buyer`,
     `Rule Baseline · YOLO (+ Rogue Attack)`) across 4 crypto market regimes:
     - `flash_crash` (`$2,500 → $2,050`, `-18%`): aggressive dip-buyers breach the `-8%` max loss limit and get
       **auto-killed by the Vault (`checkAndRevoke` → `loss_limit`)**, while a rogue `$150` trade is blocked (`OverTradeLimit`).
     - `bull_breakout` (`$2,300 → $2,670`, `+16%`): Momentum & Gemini brains ride the rally and finish profitable (`+5.8%`).
     - `whipsaw_chop` (`$2,400 → $2,550 → $2,220 → $2,460 → $2,090`): tests over-trading vs discipline.
     - `live_binance`: fetches real 1-minute ETH/USDT candles from Binance's public API and amplifies moves 15x.
   - Uses an isolated `FakeVault` + `FakeEns` so it never pollutes the real Sepolia/Arkiv `vault_count_matches` check.
5. **Stretch #5 & #6 — ERC-8004 Agent & Graveyard Feed + Terminal TUI (`engine/parable/erc8004.py`):**
   - `GET /api/erc8004` exports all living and dead Parable bots in ERC-8004 JSON format (`standard: "ERC-8004"`,
     `chain: "eip155:11155111"`, including graveyard `causeOfDeath`, `pnlBps`, `codeHash`, `birthTx`, `deathTx`).
   - `cd ~/ethglobal/parable/engine && uv run python -m parable.erc8004` prints an ASCII TUI table of all agents.

### 5.3 Frontend Visibility Upgrades (`9f76883`, `53eb608`)
- **Never-empty page in a fresh browser (`useDashboard.ts`):** `GET /api/info` returns `default_creator` (the latest
  known creator on Sepolia/Arkiv) and `eth_price_usd`. When `localStorage.getItem("parable.creator")` is empty, the UI
  automatically loads `info.default_creator` so judges immediately see the 4 Sepolia bots, graveyard, and report card.
- **Sponsor Proof Bar (`ProofBar.tsx`):** Always-visible top bar displaying live **World ID** pass, **ENSv2 (`parable.eth`)**
  oracle link, **Chainlink ETH/USD (`$2,238.11`)** Sepolia price, and **Arkiv Rabdi** explorer + writer address.
- **Graveyard Scope Switch (`Record.tsx`):** Toggle between `"Creator record"` and `"All Graves on Arkiv"` (`/api/graveyard/all`).
- **Always-Enabled Second Identity Cheat (`Live.tsx` & `api.py`):** `POST /api/cheat/second-identity` uses historical
  bots from `arkiv.bots()` when no bots are currently alive, hitting the real Sepolia `ParableVault` and returning
  `{"attack": "same person, new wallet", "blocked": true, "reason": "CreatorIdentityMismatch"}`.

### 5.4 Mandatory Sponsor Judging Docs (All Written & Committed)
- **Arkiv (`arkiv/`):** `schema.md`, `friction.md`, `reach.md`, `why-arkiv.md`, `how-you-use-arkiv.md`.
- **World (`docs/WORLD.md`):** Integration debrief (time to first success, friction, missing docs, top improvement).
- **ENS (`docs/ENS.md`):** ENSv2 Registry + UserPermissionedResolver bitmask architecture, `code_hash`, oracle checks.
- **Root `README.md`:** Problem, OS table, architecture diagram, live Sepolia/ENS/Arkiv addresses, runnable Arkiv query,
  test commands, prior art credit, and honest limits.

---

## 6. How to Verify Everything Right Now (Commands for Claude)

```bash
# 1. Run all 3 test suites (144 Python + 39 Solidity + 5 Frontend = 188 tests)
cd ~/ethglobal/parable/engine && uv run pytest -q
cd ~/ethglobal/parable/contracts && ~/.foundry/bin/forge test
cd ~/ethglobal/parable/frontend && npm test

# 2. Check live running daemons (arkiv-bridge on :8787, uvicorn on :8000, cloudflared tunnel)
ps aux | grep -E "uvicorn|arkiv|index.mjs|cloudflared" | grep -v grep

# 3. Probe live endpoints on localhost:8000
curl -s http://127.0.0.1:8000/api/info | jq .
curl -s http://127.0.0.1:8000/api/manager | jq .
curl -s http://127.0.0.1:8000/api/arena | jq .summary
curl -s http://127.0.0.1:8000/api/erc8004 | jq '{standard, totalAgents, aliveAgents, deadAgents}'
curl -s "http://127.0.0.1:8000/api/report?creator=0xa4b35b7ef915b074605a2a193e3355a99b9072047a20d98b2f6a048fbd504411" | jq .

# 4. Run the terminal ERC-8004 scoreboard
cd ~/ethglobal/parable/engine && uv run python -m parable.erc8004
```

---

## 7. Remaining Pre-Submit Checklist (What Is Left)
1. **Launch 1 more live bot on Sepolia (`bot #5`) from the UI:**
   - Why: Bots `#1`–`#4` were launched before the tick-1 `signal_price` seed fix, so they expired with `0 trades`.
     Launching 1 new bot (`yolo` or `momentum` + `gemini:gemini-3.5-flash-lite`, 10-min lease) will execute a real
     Sepolia trade immediately on tick 1 (~5 seconds after birth) and write a `parable.event` (`kind="trade"`) with a
     real Sepolia Etherscan tx hash to Arkiv.
2. **Run `prize-auditor` check** against `JUDGING.md` / `reference/prizes-official-2026-11-05.txt`.
3. **Make GitHub repo `Lagmator22/parable` public** before submitting on the ETHGlobal Hacker Dashboard.
4. **Record the 2:30–2:55 demo video** in the user's own voice following `FINAL_PLAN.md` §7.
