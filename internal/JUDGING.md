# JUDGING.md — how every Mumbai prize is judged (ALWAYS apply before planning, building, submitting)

Source of truth: `reference/prizes-official-2026-11-05.txt` (verbatim live page, 13 prizes incl. Finalist). Re-download before submitting.
We are **Classic From Scratch**: every "Continuity Track only" prize below is off-limits. Max **3 partners** (all tracks of one partner = 1 pick).

## ETHGlobal (Finalist + general)
- **Finalists: top 10 teams.** Live 7 min = 4 min demo + 3 min Q&A. Criteria: Technicality, Originality, Practicality, Usability (UI/UX/DX), WOW.
- **Finalist prize is per person by team size — SOLO = 250 USDC, no travel** (2 people: 250 + 250 travel; 3–5: 1,000 + 500 travel each). Plus pack: $828 off ETHGlobal Plus, hoodie, $10k AWS credits. → For a solo hacker, **sponsor prizes are the real money**; Finalist is prestige + perks.
- Hard rules: deadline **Sat Nov 7, 09:00 IST**; steady commits (big single commits can DQ); disclose AI use (`AI_USAGE.md`) and commit specs/prompts; demo video **2–4 min**, ≥720p, own voice, no phone recording, no TTS, ≤4 bullets/slide.
- Data from 4,297 past winners: finalists write ~50% longer, concrete write-ups (problem → number → mechanism → tests → onchain proof); avoid any weak criterion (24% of non-winners score ≤6 somewhere vs 5% of winners).

## Per sponsor (From-Scratch tracks only)

### Uniswap Foundation — "Build with Uniswap" $4k / $3k / $2k / $1k
- Anything on the Uniswap stack: Trading API, v2/v3/v4, hooks, CCA, tooling.
- **Must:** public OSS repo · `FEEDBACK.md` · Uniswap feedback form submitted with link to FEEDBACK.md · README points to exact contracts/lines. Missing feedback ⇒ extra audit.

### 0G — max quality bar, places not guaranteed
- **Build with 0G Private Computer** $2.5k/$1.5k/$1k: consumer app where AI on 0G *is* the product; people come back tomorrow. **Must:** 0G PC inference in main flow **with request IDs**, a judge-tryable app, one sentence "what breaks if 0G is removed". Bonus: iAI sign-in (0G Privy app ID, only on localhost:3000/3001/5173) with credit balance going down. **Not wanted:** chat wrappers; AI that could be removed unnoticed.
- **Physical AI** $2.5k/$1.5k/$1k (hardware): 0G call in decision loop; episode log on 0G Storage with request id per decision; replayable sim or hardware; safe-stop fallback (fake fallback = DQ). Not wanted: robot-avatar chatbot, pre-recorded motion, 0G only for logs.
- **Agents That Pay for Themselves** 2 × $1k: full loop money in → agent's 0G compute credit → inference paid from it (tx hashes + request IDs); runs alone in demo; spend cap + graceful degradation. Not wanted: token + chatbot, self-traded "revenue", human-refilled wallet.
- All 0G: public repo + README/setup, **video < 3 min**, live demo link, contract addresses, team Telegram + X.

### Hedera
- **AI Agents That Pay (x402)** $3k/$2k/$1.5k: x402 endpoint settling on Hedera via listed facilitator (or own); agent pays end-to-end with no human approval; README with ≥1 Hedera tx ID; video ≤5 min with HashScan link. Extra: spend controls, HCS audit log, HTS/USDC, HCS-14/ERC-8004 identity, A2A, scheduled tx, Agent Kit/MCP.
- **Tokenize Anything** (ATS / Stablecoin Studio) $2.5k/$1.5k/$1k: issuance + config + ≥1 lifecycle op on testnet, verified contracts.
- **No Solidity Allowed** 2 × $1k: JS/TS or **Python SDK**, zero Solidity, ≥2 native services (HTS + HCS), README, ≤5 min video.

### World
- **World ID Agent Pass** $2.5k/$1.5k/$1k (proofs mocked): meaningful action needing a human approval layer (not a login screen). **Must:** full journey (request → completion → validated result → protected action), a **denied/expired/cancelled path** where the action doesn't happen, backend validation, integration debrief (time to first success, friction, missing docs, top improvement).
- **Best Use of IDKit** 2 × $1.25k: real "trust moment"; justify the *minimum sufficient* credential; server/onchain verification; success + alternative path; debrief.

### ENS — "Best Use of ENSv2" $3k/$2k/$1k/$1k
- ENSv2 on mainnet or Sepolia, **central not cosmetic**, no hard-coded values, live demo link, OSS. Bonus: AI agents as namespaces with own identity/permissions (subname registries, Enhanced Access Control, Permissioned Resolver, expiring/revocable/non-transferable names).

### Arkiv — one track win per team (+ Swarm bonus on top, doesn't use a pick)
- **Build on Arkiv** $3k/$1k and **Mirror something Ethereum depends on** $3k/$1k; **Node tooling** $2k.
- First-time ETHGlobal sponsor (no Arkiv/Golem prizes in 30 past events) → no winner template, few repeat competitors.
- **Build on Arkiv — judged 25% each, one file per criterion answering with links, numbers or a runnable query:**
  - `/arkiv/friction.md` (feedback): what should Arkiv improve today / what's missing; when something broke — what you expected, what happened, how to reproduce.
  - `/arkiv/reach.md`: who it's for and would they use it; can they try it today; will you keep building after Mumbai.
  - `/arkiv/why-arkiv.md`: what users lose if you swapped Arkiv for Postgres; what you kept off Arkiv and why.
  - `/arkiv/how-you-use-arkiv.md`: do your filter fields, entity owners/editors and expiries fit what the app does; does each Arkiv feature you use change something users see.
  - Plus `/arkiv/schema.md`: entities, queried fields, owners, expiry.
- **Mirror track** swaps the last two for `/arkiv/why-arkiv.md` (what people can do with your copy they can't with the source) and `/arkiv/data-quality.md` (freshness, re-runnable import, filterable the way people search); data license must allow republishing; not Sourcify. **Node tooling** uses `/arkiv/real-use.md`, `/arkiv/whats-new.md`, `/arkiv/easy-to-run.md`.
- **Must:** writes to Arkiv testnet (SDK or JSON-RPC) and a user-facing feature reads it; README has writer wallet(s) + one runnable query; OSS license; AI usage stated. Not counted: SDK never read from, Arkiv as write-only log.
- Swarm bonus $500: Arkiv + Swarm both used, `/arkiv/swarm.md` with refs, batch ID, steps.

### Whitechain (Whitechain Sepolia, chain 1874)
- **Operate** $2.5k/$1.5k/$1k (merchant checkout/invoices/subscriptions/refunds as a drop-in ~20 lines), **Tokenize RWA** $2.5k/$1.5k (rules enforced in contract), **Scale** $2k/$1k (gasless payer, incl. AI agent x402 via own facilitator).
- **Must:** verified contracts on Whitechain explorer · ≥1 real test-USDT payment (`0xcedfB561…f55a7`) in main flow with explorer link · README line "why onchain stablecoin settlement" · steady commit history · **video 2–4 min showing each party** · `WHITECHAIN_FEEDBACK.md`.

### Ethereum Foundation — max ONE EF prize per project
- **Anon-RPC** $2.5k/$1.5k/$1k: app routes RPC reads through Anon-RPC by default (worker/harness builds: a simple demo app is enough). **Judged on:** works end to end · UX quality · share of app traffic through Anon-RPC (intentional exclusions OK if explained) · could ship after the hackathon · technical depth. Ideas: portfolio dashboard, block explorer, dApp fork, multi-network health checker, light client/proof verification, new network or harness.
- **Alt mempool (EIP-8141 frame tx)** $2.5k/$1.5k/$1k: admitted tx on devnet explorer or code that submits one; you must explain design, code and trade-offs. **Judged on:** creativity · usefulness · practicality · how well it works · relation to the alt mempool. Areas: things only an alt mempool allows (>100k verification budget, e.g. PQ wallets; flexible paymasters), dev tooling (viem/ethers SDK, admission simulator, monitoring), breaking/improving the rules (DoS, fuzzers).
- **Best CROPS App** $2k/$1k/$500: FOSS license; README section **CROPS** (C: what you control and what happens if it goes away · O: license, buildable from repo · P: what each third party learns · S: key/data protection, trust assumptions); ≤3 min video showing the lead property at the moment it matters (switch off backend, swap RPC, show clean logs); no trackers; keys/personal data stay on device. **Judged on:** works end to end · structural (works without you) beats cosmetic · other three properties hold or trade-offs stated · UX for people who don't know what CROPS means · could ship.

### Arc (Circle) — every prize requires Arc Studio; one winner per $3k track
- DeFi app · Mobile consumer agent + Marketplace Discovery API (Nanopayments, spend limits, approvals) · Advanced stablecoin contracts · Bridge Kit non-USDC.
- **Must:** shareable Arc Studio project URL + Studio shown in demo · working frontend + backend + **architecture diagram** · video + docs · GitHub/Replit link · say which bounty.

### Chainlink
- **CRE workflow** $1.5k: CRE workflow (simulation via CLI is enough) connecting a chain with an API/LLM/agent, meaningfully used.
- **CCIP 2.0** 2 × $1.75k: CCIP inside contracts making a state change.

### Definitive — "Flash Advanced Orders in a Social App" $2.5k (1 winner)
- Social trading (copy trading, signals/leaderboards, agent-run products others follow) on Flash advanced orders.
- **Must:** working flow with Flash API/MCP advanced orders · **onchain execution in final demo (mainnet only — no testnet)** · short demo video posted on **Discord and X tagging @DefinitiveFi**.

## 1inch — "Build an Aqua App" $2.5k/$1.5k/$1k
- Official Aqua/SwapVM contracts (modified SwapVM redeploy OK; SwapVM scores higher), onchain token transfers in demo (forks OK), proper commit history.
