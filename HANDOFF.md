# HANDOFF: read this first (written Fri 6 Nov 2026, ~15:45 IST)

You are taking over **Parable**, a solo ETHGlobal Mumbai 2026 project. The previous assistant (Claude Code, Opus)
ran out of usage. Everything below is the current truth. Also read: `AGENTS.md` (rules + iteration log),
`FINAL_PLAN.md` (locked plan + timeline + demo script), `JUDGING.md` / `../JUDGING.md` (prize criteria),
`ARCHITECTURE.md` (diagrams), `INTERFACES.md` (module contracts), `docs/FRONTEND_CONTRACT.md` (API for the UI),
`DEPLOYMENTS.md` (addresses + live proof links).

## 0. Deadlines
- Hacking ends **Sat 7 Nov 09:00 IST (hard)**. Our target: **submit by 07:30**.
- Video 2–4 min (aim 2:30–2:55) in the user's own voice. Repo must be **made public** before submit
  (GitHub `Lagmator22/parable` is private now). Steady commits required. `AI_USAGE.md` disclosure required.
- Partner picks (max 3): **ENS + Arkiv + World**.

## 1. About the user (follow strictly)
- Solo, new to web3/finance, strong agentic-AI dev (GSoC, OVAT). Prefers Python. Spent ~$400 to attend; wants to WIN.
- **Very simple language always**: explain every jargon word once, short sentences, tables, small diagrams.
- Every install/run step must say **which folder** and **exactly where to click**.
- **Be honest/ruthless** about odds, bugs and novelty. Never claim something works without proof.
- Code: small readable files (≤ ~300 lines), short functions, plain-English header comment per file, comments on the
  web3/finance "why". **Edge-case tests in the same commit as each feature.**
- Before every commit: `cd ~/ethglobal/parable/engine && uv run pytest -q` and
  `cd ~/ethglobal/parable/contracts && ~/.foundry/bin/forge test` (forge is not on PATH in non-login shells).
- After each phase: commit + push; update `ARCHITECTURE.md` (diagrams only, simple words, holes table),
  `AGENTS.md` section 0 iteration log, `AI_USAGE.md`; explain to the user simply.
- User also has **OpenAI Codex** (GPT-6 Sol): delegate scoped tasks with a paste-ready prompt + say which model /
  reasoning level to pick. Codex is currently building the **frontend** in `frontend/` (see section 6).
- LLMs: free first (Gemini/Gemma). Anthropic key exists but **$0 credit**. Opus only for final eval / swarm mind.

## 2. Security rules (never break)
- Never commit secrets. `.env` and `.env.*` are gitignored (except `.env.example`). Never print keys.
- The operator wallet `0x4Bf4Cf3Ac386A57DBf7C8b5eB93cE942d4504570` is **test-only**: never real money.
- Users never see raw errors (only short `detail` text / vault error names).
- The auto-mode classifier blocked `curl | bash` installs and starting cloudflared tunnels: ask the user to run those.

## 3. What Parable is (pitch)
"Every trading strategy has a graveyard. Parable is where bots can't lie about theirs."
AI trading bots never touch money and never write their own record. A World ID human approves a launch → the bot
gets a soulbound, expiring **ENSv2 name tag** (`bot-N-xxxx.parable.eth`) → the **ParableVault** contract (Sepolia)
holds its practice money, checks the badge + limits on every trade, trades at the **Chainlink** ETH/USD price,
measures loss itself and auto-kills at the loss limit → every birth / trade / blocked trade / death is written to
**Arkiv** (public DB) → dead bots stay in a **graveyard** nobody can delete. Report cards count failed bots too and
check "vault count = Arkiv count". "Agentic OS for trading" is an explanation only, not the headline.
Novelty is the **combination** (prior art credited in FINAL_PLAN.md §10 / docs/NOVELTY_CHECK.md).

## 4. What works (proven live)
- Vault + EnsV2BadgeOracle deployed and source-verified on Sepolia (addresses in DEPLOYMENTS.md).
- ENS live spike: issue → read → valid → revoke → invalid. Parent `parable.eth` owned by operator.
- Arkiv live spike: write bot/birth/death, read graveyard + report card back.
- World ID real login worked ("approved: World ID verified server-side").
- Brains: `rule` always; Gemini models via free key (best: `gemini:gemini-3.5-flash-lite` 6/6, 1.4 s).
  Gemma had Google-side 500s. `claude` needs credit. `local` (Ollama) = very last stretch.
- Tests: **135 Python + 39 Foundry pass** (last commit `ea8b64c`).

## 5. Current state of the FIRST REAL LAUNCH (most important open item)
First real launch failed (World approved, then): nonce clash ("replacement transaction underpriced") + Arkiv overload
+ the page re-polling confirm while the bot was still being born. **All fixed and pushed** (commits `ce5c144`, `ea8b64c`):
- `engine/parable/tx_sender.py`: one shared sender per wallet (lock + remembered nonce + retry on clash). Used by
  `vault.py` and `ens_badge.py`.
- `arkiv_store.py`: reads cached 8 s; rows tagged `vault=<vault address>` (spike rows excluded); `events(bot_id)`;
  `report_by_brain()` (2 queries total); alive rows live lease + 1 h.
- `repair.py`: `Outbox` (failed Arkiv writes retried every 5 s, launch never fails because of Arkiv) and
  `repair()` (once a minute: for vault bot ids 1..totalBorn rebuild missing records, expire finished leases,
  write missing graves). This will fix **orphan bot #1** (in vault, no Arkiv record).
- `launcher.confirm_launch` is idempotent (409 "being born on-chain" while in progress; returns same bot after).
  Chain failures → `LaunchFailed` → 502 clean text.
- `api.py`: `/api/info` (public addresses + strategies), `/api/report/brains`, `/api/bots/{id}/events`,
  global JSON error handler (Arkiv down → 503 short message), serves `frontend/dist` at `/` when built,
  old dashboard at `/classic` (also `/` until frontend is built).

**BLOCKER right now:** Arkiv's public query endpoint hangs (60 s, no answer) — likely rate-limited after the flood.
The RPC itself answers in <1 s. Fix = free access key. **User must:** create a key at
https://hub.arkiv.network/access-keys and add `ARKIV_ACCESS_KEY=<key>` to `~/ethglobal/parable/.env`.
Then restart the bridge (it already passes `rabdi({accessKey})`).

**Next steps, in order:**
1. After the key: restart bridge, check `curl` query through bridge returns fast (command in section 8).
2. Watch `/tmp/parable_app.log` for `repair: bot 1: record rebuilt` (orphan fixed).
3. User retries a real launch via the tunnel URL (hard refresh Cmd+Shift+R), brain `gemini:gemini-3.5-flash-lite`.
   Verify: bot born (6 txs, ~1 min), trades appear, kill → grave in graveyard, report "vault count matches ✓".
4. Then hardening + permanent public HTTPS deployment (ENS judges want a live demo link; register its
   `/world/callback` in the World portal via "Manage" → redirect URIs; update `WORLD_REDIRECT_URI` in .env).
5. Stretch in order: MCP server (Claude Code/Codex can launch/inspect bots) → Opus manager "swarm" → code
   fingerprint → ERC-8004 → local models (very last).
6. Docs for judging (section 7), video, prize-auditor check (`~/ethglobal/.claude/agents/prize-auditor.md`), submit.

## 6. Frontend (being built by Codex in parallel)
- Codex got a full prompt; contract = `docs/FRONTEND_CONTRACT.md`. It works only in `frontend/`
  (Vite + React + TS + Tailwind, components copied from quarry-ui / 21st.dev), commits prefixed `frontend:`,
  notes in `frontend/AI_NOTES.md`, questions in `frontend/CONTRACT_QUESTIONS.md` (check it!).
- Build output `frontend/dist/` (gitignored) is served by FastAPI at `/`. Dev: Vite proxy `/api` + `/world` to
  `PARABLE_API` (default `http://127.0.0.1:8000`). Offline backend for UI work:
  `cd ~/ethglobal/parable/engine && PARABLE_OFFLINE=1 uv run uvicorn parable.api:app --port 8001`.
- `/api/manager` is reserved (planned) for the swarm panel; frontend hides it on 404.
- Do NOT edit `frontend/` from the backend side; if the API must change, update the contract file in the same commit.

## 7. Judging must-haves (details in JUDGING.md)
- **ENS "Best use of ENSv2"**: ENSv2 central (badges are the permission layer the vault checks), live demo link,
  open source, bonus: agents as namespaces (each bot = subname). Show names, not addresses, in the UI.
- **Arkiv "Build on Arkiv"** (first-time sponsor, 25% each): `/arkiv/friction.md`, `/arkiv/reach.md`,
  `/arkiv/why-arkiv.md`, `/arkiv/how-you-use-arkiv.md` + `/arkiv/schema.md`. A user-facing feature must read from
  Arkiv (the graveyard does). README: writer wallet + one runnable query. NOT WRITTEN YET.
- **World Agent Pass / IDKit**: full journey + denied/expired path + backend validation + integration debrief
  (`docs/WORLD_NOTES.md`, NOT WRITTEN YET).
- Finalist signals: explain the problem, state numbers, mention tests, live demo, verifiable, 200+ word write-up.
- README not written yet: problem, OS table, how it works, prior art, honest limits, deployments, how to run.

## 8. Running it (folders + commands)
- Secrets: `~/ethglobal/parable/.env` (has operator key, Gemini key, Anthropic key ($0), World client id/secret,
  `WORLD_MOCK=0`, `WORLD_REDIRECT_URI=https://director-tourist-dolls-feedback.trycloudflare.com/world/callback`,
  vault/ENS addresses, `SEPOLIA_RPC_URL=https://sepolia.gateway.tenderly.co`, `PARABLE_CREATOR_SECRET`,
  `ARKIV_BRIDGE_TOKEN`). Missing: `ARKIV_ACCESS_KEY`.
- Arkiv bridge (Node, official SDK; Python SDK is incompatible with Rabdi):
  `cd ~/ethglobal/parable/arkiv-bridge && nohup node index.mjs > /tmp/arkiv_bridge.log 2>&1 &` (port 8787).
- Engine: `cd ~/ethglobal/parable/engine && nohup uv run uvicorn parable.api:app --host 127.0.0.1 --port 8000 > /tmp/parable_app.log 2>&1 &`
  Before restarting, make sure the old one is gone: `ps aux | grep "[u]vicorn parable"` (an old copy once kept running).
- Tunnel (user runs it in their own Warp tab): `cloudflared tunnel --url http://localhost:8000`.
  A new tunnel = new URL → user adds `<url>/world/callback` in the World portal (Manage), and update `.env`.
- Test a bridge query directly:
  `TOKEN=$(grep ^ARKIV_BRIDGE_TOKEN= ~/ethglobal/parable/.env | cut -d= -f2); curl -s -m 30 -H "x-bridge-token: $TOKEN" -H "content-type: application/json" -d '{"schema":"parable.bot","where":{},"owner":"0x4Bf4Cf3Ac386A57DBf7C8b5eB93cE942d4504570"}' localhost:8787/query`
- Wallet: operator had ~0.06 SepoliaETH (each launch ≈ 0.002–0.004 ETH). 10 tGLM on Arkiv.

## 9. Code map (engine/parable)
`api.py` routes · `launcher.py` launch/kill/check/expire + death sync + poller · `repair.py` outbox + vault→Arkiv
repair · `tx_sender.py` shared tx sender · `vault.py` web3 client · `ens_badge.py` ENSv2 badges · `arkiv_store.py`
Arkiv client (via bridge) · `world_pass.py` World OIDC (PKCE, JWKS, mock mode) · `bot_runner.py` brains + bot loop
(45 s interval, 30 s AI timeout, rule fallback) · `fake_chain.py` offline simulation · `static/` old dashboard.
Contracts: `contracts/src/ParableVault.sol`, `contracts/src/adapters/EnsV2BadgeOracle.sol`, `contracts/script/Deploy.s.sol`.
Units: USD 6 decimals, ETH 18, price 8, bps for percentages.

## 10. Swarm / Opus manager design (stretch, agreed)
Opus = the "mind", called every 2–3 min with a summary (cheap). It launches 4–6 worker bots (cheap brains:
Gemini flash-lite / Haiku, every 45 s; NOT full Sonnet agents), reads scores + timelines from Arkiv, kills losers,
keeps winners, and **flags** suspicious bots (e.g. blocked 5× for OverTradeLimit = broken/malicious) and kills them.
It has NO special powers: only creator actions (kill own bots, check, expire). **The vault stays the security guard.**
All its kills land in its public graveyard: "even an AI manager can't hide its failed bots." Needs Anthropic credit
(~$5); fallback mind = Gemini. Expose as `/api/manager` (GET status, POST start) per FRONTEND_CONTRACT.md.

## 11. Known limits (say them honestly in README)
Server is trusted to say "this creator passed World ID" at registration · high-water mark updates only on trades ·
bot keys are memory-only (server restart → bots just expire; repair records them) · World approvals in memory ·
Sepolia Chainlink updates ~hourly (MAX_PRICE_AGE 7200) · spike test rows exist on Arkiv without the vault tag
(now ignored).
