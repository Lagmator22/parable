# AGENTS.md — ETHGlobal Mumbai 2026 (solo)

Instructions for any AI agent (Claude Code, Codex, etc.) working with me on this hackathon.
Read this whole file AND `JUDGING.md` before doing anything — judging criteria and rules decide every
plan, build and submission choice. Verbatim sponsor text lives in `reference/prizes-official-2026-11-05.txt`
(older copy: `-11-03`). Precedence: live site (https://ethglobal.com/events/mumbai/prizes) > reference file
> JUDGING.md > this file.

Research assets: `DOMAIN_TRENDS.md` (4,297 past winners by domain), `WINNING_PATTERNS.md` (what finalists do
differently), `winners.txt` (every winner's write-up), `prev_winners/` (cloned winning repos + ANALYSIS.md),
`SPONSOR_TECH_CHECK.md` (doc-verified API facts: Uniswap testnets OK, Definitive mainnet-only, 0G verified mode).

## 0. PARABLE PROJECT RULES (read first, they override anything below)

**What we're building:** see `FINAL_PLAN.md`. **Module signatures:** `INTERFACES.md`. **Simple diagrams:** `ARCHITECTURE.md`.
Partners: **ENS + Arkiv + World**. Build order: **CORE first** (FINAL_PLAN section 4), then phases, then stretch.

**Code must be readable by a newcomer** (the owner is new to web3 and must explain every line to judges):
- Small files, short functions (aim for ≤ 40 lines each), plain names (`register_bot`, not `rb`). No clever one-liners, metaprogramming or deep class hierarchies.
- Every file starts with a 2–4 line comment: what this file does, in plain English.
- Comment the *why* in plain words wherever web3 or finance logic happens (e.g. "price has 8 decimals, USD has 6, so we divide by 100").
- Write the least code that works. No unused abstractions, no speculative features, no copy-paste walls. If a module passes ~300 lines, split it or simplify it.
- Prefer one obvious way: Python (FastAPI + Pydantic + web3.py) everywhere except the contract (Solidity) and tiny frontend JS.

**Tests ship WITH every feature (same commit), never later:** for each feature list its edge cases (denied, expired, replayed, unauthorized, over-limit, stale price, network/service down, bad input) and test each one: Python in `engine/tests` (`cd engine && uv run pytest -q`), contracts in `contracts/test` (`cd contracts && forge test`). Both suites must pass before every commit.

**Instructions to the owner:** every command says which folder to run it in, and every website step says exactly where to click.

**Docs to keep updated after every phase:**
- `ARCHITECTURE.md`: **only flowcharts and diagrams, in very simple language** (no jargon without a one-line explanation). Update it whenever a flow changes.
- `AGENTS.md` (this file): update section 0's "Iteration log" below after every phase: what works now, what changed, what's next.
- `AI_USAGE.md`: one row per meaningful AI-generated chunk.

**Iteration log**
- 2026-11-06 12:00: Plan locked (FINAL_PLAN.md). Skeleton + interfaces committed.
- 2026-11-06 12:30: Phase 1 started: 4 builders working in parallel on vault contract, Arkiv store, ENSv2 badge, World Agent Pass.
- 2026-11-06 13:15: Phase 1 done (52 Python tests pass; contract compiles with solc 0.8.24, Foundry tests not yet run, so Foundry install is needed). Nothing written on-chain yet: needs funded keys. Next: Phase 2 = Arkiv via official JS SDK bridge (fail-closed writer filter), engine core (vault client, bot loop, launch flow, API), dashboard, ENS module trim + deploy order (oracle → vault → setVault).
- 2026-11-06 13:45: Phase 2 done. Arkiv bridge (official JS SDK) + fail-closed client; vault.py + bot_runner.py (Claude Haiku + rule fallback); launcher + API + dashboard + offline simulation; ENS trimmed to 300 lines; deploy order fixed. Lead fixed 4 cross-module mismatches + 2 security holes (World approval hijack → server-created launch ids + claim token; creator wallet key derived from public data → HMAC with server secret PARABLE_CREATOR_SECRET). 69 tests pass; offline end-to-end smoke test passes. Security pass 2: kill is creator-only (owner token), raw errors never shown, arkiv-bridge needs ARKIV_BRIDGE_TOKEN + local Host + no browser Origin. Foundry installed: all 39 contract tests pass (2 test bugs fixed). Next: Phase 3 = real-chain run (needs keys: Foundry, Sepolia ETH, Arkiv funds, World portal app, ENS parent name, Anthropic key).
- 2026-11-06 16:30: First REAL launch (World approved) failed: nonce clash between the ENS and vault senders (`replacement transaction underpriced`) + Arkiv overload from dashboard polling (12 report calls every 3 s) + the page re-asking 'confirm' while the bot was still being born. Fixed: one shared transaction sender per wallet (`tx_sender.py`, remembers nonces, retries clashes); Arkiv reads cached 8 s, rows tagged with the vault address (spike rows excluded), one-call `/api/report/brains`, `/api/bots/{id}/events`; outbox retries failed Arkiv writes; `repair.py` rebuilds missing records from the vault each minute (fixes orphan bot #1); confirm is idempotent; launch failures return a clean 502. Frontend contract for Codex in `docs/FRONTEND_CONTRACT.md`; engine serves `frontend/dist` at `/` when built (old dashboard at `/classic`). 134 Python + 39 Foundry tests pass. Next: user retries a live launch.

## 1. Mission

- **Project name: Parable.** Use this name in the repo, README, submission and demo.
- I am hacking **solo**. Goal: **maximize prize money** (sponsor prizes + finalist).
- Secondary goals: learn web3 properly, and level up **Python** — prefer Python wherever the sponsor stack allows (Hedera Python SDK, 0G's OpenAI-compatible API, Arkiv JSON-RPC, backends). Use TS/Solidity only where a prize requires it.
- Explain web3 concepts briefly when they first come up; I'm still learning.

## 2. Hard dates (all IST)

| When | What |
|---|---|
| Nov 3–6 | Devcon 8, same venue (Jio World Convention Centre, BKC) |
| **Thu Nov 5, 3:30–6:00 PM** | Sponsor workshops (see §6) |
| **Thu Nov 5, 9:00 PM** | Hacking starts — **no project code before this** |
| **Sat Nov 7, 9:00 AM** | **Submission deadline. Late = rejected.** Target submitting by 7:30 AM. |
| Sat Nov 7, ~9:30 AM | Judging starts |

## 3. ETHGlobal rules (non-negotiable)

**Team & eligibility**
- Teams of 1–5; solo is explicitly allowed. Must be accepted, staked (ETH), checked in, and physically present. Don't lose the wristband (stake can be slashed).
- Stake is refunded (~4 weeks) if *any* project is submitted.

**Starting point — we are on "Classic From Scratch"**
- All project work must begin after hacking starts. Public libraries, boilerplate and starter kits are OK (disclose them).
- *"Pre-existing project-specific code, designs, or assets are not allowed."* Pre-built projects can't win partner prizes or Finalist.
- **Continuity-Track-only prizes are NOT available to us** — ignore them.

**Git**
- Version control required. *"Submissions with large single commits or missing histories may be disqualified."* → commit small and often (at least every ~30–60 min of work), meaningful messages, push regularly. Several sponsors (1inch, Whitechain) also check commit history explicitly.

**AI usage**
- Allowed to *assist*, not to create the entire project.
- *"Clearly document in your submission where and how AI tools were used."* → keep `AI_USAGE.md` in the project repo, updated as we go.
- Spec-driven workflows are allowed, but **all spec files, prompts, and planning artifacts must be in the repo**.

**Submission**
- Hacker Dashboard: title, description, repo link (+ proof work was done during the hackathon).
- Demo video: optional but strongly encouraged. **2–4 minutes exactly** (outside = auto-rejected), ≥720p, not sped up, **not recorded on a phone, no TTS/AI voiceover (I narrate)**, no music with on-screen text, ≤4 bullets per slide.
- Some sponsors want ≤5 min or <3 min — a 2:30–2:55 video satisfies everyone.

**Prize selection**
- Pick **up to 3 partners**. A partner with several tracks = 1 pick and you're eligible for all its tracks. Choose carefully — it's the only way partners see the project.
- Two paths: **Finalist + Partner** (live: 4 min demo + 3 min Q&A) or **Partner Prizes Only**.
- Finalist criteria: Technicality, Originality, Practicality, Usability (UI/UX/DX), WOW factor.
- Finalists = top 10 teams. **Solo finalist prize = 250 USDC (no travel)** + perks pack → sponsor prizes are the main money for us.

## 4. Prep vs. hack boundary (what's allowed before 9 PM Nov 5)

This folder (`~/ethglobal`) is the **prep workspace**, not the project repo.

| OK before start | NOT OK before start |
|---|---|
| This AGENTS.md, rules/sponsor notes, generic agent config & subagents | Any code for the actual project |
| Brainstorming, choosing the idea and target sponsors | Project-specific UI designs / mockups / assets |
| Reading docs, attending workshops, asking booths questions | Project-specific contracts, schemas, repos |
| Throwaway SDK quickstarts in `sandbox/` (never copied into the project) | Copying sandbox code into the project repo |
| Wallets, faucets, API keys, testnet accounts | |

At hack start: create a **new** repo, first commit = copy of AGENTS.md + a README note:
"Pre-hackathon: only generic rules/sponsor notes and agent config (AGENTS.md). No project code existed before 2026-11-05 21:00 IST."
Write the project spec/architecture *after* start (commit it — counts as a planning artifact).

## 5. Prize map — From-Scratch-eligible only

Verified against the live prizes page 2026-11-03 and the Discord partner channels.

| Partner (pick) | Track | Payout | Must-haves (abridged — check reference file) |
|---|---|---|---|
| **Hedera** $13.5k | AI Agents That Pay: x402 | 3k / 2k / 1.5k | x402 endpoint settling on Hedera testnet/mainnet via listed facilitator; agent pays end-to-end with no human approval; README with ≥1 Hedera tx ID; ≤5 min video showing settlement + HashScan link. Extra: spend controls, HCS audit log, HTS/USDC, Agent Kit, HCS-14/ERC-8004 |
| | Tokenize Anything (ATS / Stablecoin Studio) | 2.5k / 1.5k / 1k | Use ATS or Stablecoin Studio; testnet; verified contracts; video: issuance + config + ≥1 lifecycle op |
| | "No Solidity Allowed" | 2 × 1k | JS/TS **or Python SDK**, zero Solidity, ≥2 native services (e.g. HTS + HCS), README, ≤5 min video |
| **0G** $12k | Build with 0G Private Computer *(Discord calls it "Build with iAI")* | 2.5k / 1.5k / 1k | Consumer AI app; 0G PC inference in main flow with request IDs; live demo link; "what breaks without 0G"; bonus: sign in with 0G account & spend iAI credits. No chat wrappers. Video <3 min |
| | Physical AI: Agents with a Body | 2.5k / 1.5k / 1k (hardware) | 0G call in decision loop; episode log on 0G Storage w/ request id per decision; replayable sim (PyBullet/MuJoCo/zerobot OK) or hardware; safe-stop fallback (faking = DQ) |
| | Agents That Pay for Themselves *(Discord: "Wildcard: Weirdest Thing on 0G")* | 2 × 1k | Agent earns → credit lands in its 0G compute account → pays own inference; tx hashes + request IDs; spend cap & graceful degradation |
| | *0G pays only above its quality bar — places not guaranteed* | | |
| **Arc (Circle)** $12k | 4 tracks: DeFi app / Mobile consumer agent + Marketplace Discovery API / Advanced stablecoin contracts / Bridge Kit non-USDC | **1 winner each, $3k** | **Must start in Arc Studio**, shareable Studio URL, show Studio in demo; working frontend+backend + architecture diagram; state which bounty |
| **Whitechain** $12k | Operate: stablecoin payments for business | 2.5k / 1.5k / 1k | Whitechain Sepolia (chain 1874), verified contracts; ≥1 real USDT payment (`0xcedfB56113143d55b2358b8CFbB0dEB5Ad2f55a7`) w/ explorer link; README "why onchain"; steady commits; 2–4 min video showing each party; `WHITECHAIN_FEEDBACK.md` |
| | Tokenize: real-world finance | 2.5k / 1.5k | Same base reqs + transfer rules enforced in contract |
| | Scale: payments nobody notices | 2k / 1k | Same base reqs + gasless payer (permit/EIP-3009/relayer or x402 via own facilitator) |
| **Uniswap** $10k | Build with Uniswap | 4k / 3k / 2k / 1k | Any Uniswap stack (API, v2/v3/v4, hooks, CCA); public OSS repo; `FEEDBACK.md`; Uniswap feedback form linking it; README pointing to exact code lines |
| **Ethereum Foundation** $13.5k — **max 1 EF prize/project** | Anon-RPC | 2.5k / 1.5k / 1k | App routes RPC reads through Anon-RPC by default |
| | Frame Tx Alt Mempool (EIP-8141) | 2.5k / 1.5k / 1k | Admitted tx on devnet explorer or code submitting one |
| | Best CROPS App | 2k / 1k / 500 | FOSS license; README "CROPS" section (C/O/P/S); ≤3 min video showing the property; no trackers |
| **World** $7.5k | World ID Agent Pass | 2.5k / 1.5k / 1k | Full journey incl. a denied/expired path; backend validation; integration debrief. Proofs are mocked now |
| | Best Use of IDKit | 2 × 1.25k | Server/onchain verification; justify the minimum credential; success + alternate path; debrief |
| **ENS** $7k | Best Use of ENSv2 | 3k / 2k / 1k / 1k | ENSv2 on mainnet or Sepolia, central not cosmetic, no hard-coded values, live demo link, OSS. Bonus: AI agents as namespaces |
| **Arkiv** — **max 1 track/team** (+Swarm bonus) | Mirror public data / Build on Arkiv / Node tooling | 3k / 1k (node tooling 2k) | Writes to Arkiv testnet via SDK or JSON-RPC, user-facing feature reads it; `/arkiv/*.md` files per criterion; FOSS |
| | Arkiv + Swarm bonus | **$500 on site / $1,000 on Discord — confirm** | Uses both Arkiv & Swarm; `/arkiv/swarm.md` |
| **1inch** $5k | Build an Aqua App | 2.5k / 1.5k / 1k | Official Aqua/SwapVM contracts; onchain token transfers in demo (fork OK); SwapVM scores higher |
| **Chainlink** $5k | Best workflow with CRE | 1.5k (1 winner) | CRE workflow (simulation OK) connecting chain ↔ API/LLM/agent, meaningfully used |
| | Best use of CCIP 2.0 | 2 × 1.75k | CCIP used inside contracts for a state change |
| **Definitive** $2.5k | Flash Advanced Orders in a Social App | 2.5k (1 winner) | Flash API/MCP advanced orders, onchain execution in demo, post video on Discord + X tagging @DefinitiveFi |

**Discrepancies (screenshots vs live site, 2026-11-03)** — live site is newer; confirm at booths:
1. 0G track names: site "Build with 0G PC" / "Agents That Pay for Themselves" vs Discord "Build with iAI" / "Wildcard: Weirdest Thing on 0G". Amounts identical.
2. Arkiv + Swarm bonus: site $500 (from scratch) + $500 (existing) vs Discord $1,000 from-scratch only.
3. ENS Discord lists "3rd place" twice — it's 4 places ($3k/$2k/$1k/$1k).

## 6. Workshops — Thu Nov 5

| Time | Room 1 | Room 2 |
|---|---|---|
| 3:30 PM | 0G — Building on 0G Private Computer | Hedera × Claude Code — AI Skills |
| 4:00 PM | ENS — ENSv2 Identity | Arkiv (Discord) |
| 4:30 PM | Uniswap — Navigate the Stack | Whitechain |
| 5:00 PM | Arc — Smart Contracts with Arc Studio | Ethereum Foundation |
| 5:30 PM | World | 1inch — Aqua |
Chainlink, Definitive: TBA.

## 7. Strategy (working hypothesis — revisit after brainstorm)

- Best fits for solo + Python: **Hedera** (x402 + No-Solidity can plausibly stack on one Python project; confirm at booth no one-win-per-project rule), **0G** (OpenAI-compatible, Python sims accepted for Physical AI).
- Third pick candidates: **Arc** (Studio does heavy lifting, but 1 winner/track), **Uniswap** (biggest single prize, heavier competition), **World** (Agent Pass = human approval layer for agents — natural add-on).
- Paperwork-heavy tracks (Arkiv, Uniswap, Whitechain, World debriefs) deter competitors — a disciplined solo can win on completeness.
- Theme with cross-sponsor fit: **AI agents that pay** (Hedera x402, 0G self-funding agents, Whitechain Scale x402, World Agent Pass for human approval).

**Ask at booths:** expected # of submissions; can one project win multiple tracks of yours; anything that auto-disqualifies; 0G/Arkiv discrepancies above.

## 8. Hackathon workflow (agents follow this)

| Phase (IST) | Hours | Output |
|---|---|---|
| Thu 21:00–22:00 | H0–1 | New repo, AGENTS.md copied, README disclosure, `AI_USAGE.md`, `FINAL_PLAN.md` (idea, sponsor tracks targeted, requirement checklist), architecture sketch. Commit. |
| Thu 22:00–Fri 01:00 | H1–4 | **De-risk**: hello-world for every sponsor integration (one tx / one API call each). If one fails badly → swap sponsor now, not later. |
| Fri 01:00–08:00 | H4–11 | Core happy path end-to-end (ugly is fine). Nap ~3h in here when blocked/tired. |
| Fri 08:00–18:00 | H11–21 | Sponsor-specific requirements + "extra points" items, 2nd/3rd sponsor depth, error/denied paths. Booth check-ins for feedback. |
| Fri 18:00–Sat 02:00 | H21–29 | UI polish, README, sponsor docs (FEEDBACK.md, WHITECHAIN_FEEDBACK.md, /arkiv/*.md, CROPS section…), deploy live demo. Second nap ~2h. |
| **Sat 02:00** | H29 | **Feature freeze.** Run `prize-auditor` subagent against chosen tracks. |
| Sat 02:00–06:00 | H29–33 | Record demo video (own voice, 2:30–2:55), fill submission draft, AI usage disclosure. |
| Sat 06:00–07:30 | H33–34.5 | Final audit, **submit**. Buffer until 9:00 for emergencies only. |

**Agent conventions during the hack**
- Python first; ask before adding a new language/framework.
- Never commit secrets: `.env` + `.env.example`; private keys only testnet.
- Every sponsor requirement gets a checkbox in `FINAL_PLAN.md`; tick it only with evidence (tx hash, request ID, explorer link).
- Append to `AI_USAGE.md` whenever AI generates a meaningful chunk (what, which tool, what I changed).
- Commit after every working increment; push at least hourly.
- Prefer testnets; capture tx hashes/explorer links into README as they happen (needed for submissions).
- If something burns >45 min without progress → stop, report, propose a fallback.
