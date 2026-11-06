# Parable — FINAL PLAN

> **Every trading strategy has a graveyard. Parable is where bots can't lie about theirs.**
> Bots never touch the money and never write their own record. The vault does both. So no bot can trade without being counted, nobody can hide a dead bot, and every creator is one real person.

Status: locked 2026-11-06 12:00 IST · Deadline **Sat 2026-11-07 09:00 IST** · target submit **07:30**
Partners (max 3): **ENS · Arkiv · World**. Trades are priced by Chainlink's ETH/USD feed on Sepolia (we use it, but it's not a prize pick).

---

## 1. What we're building, in plain words

**The problem:** people sell and share AI trading bots by showing only the winners. Someone runs 20 bots, deletes the 17 that lost money, and shows the 3 lucky ones. Buyers can't tell. This is called **survivorship bias**, and the US regulator (CFTC) specifically warns about cherry-picked results.

**Parable's 3 rules:**
1. **Register before you play.** A bot can't make even one trade until it's in the public record. The vault refuses unregistered bots.
2. **One person, one account.** Each creator is one verified human (World), so they can't start a fresh account to hide failures.
3. **The vault keeps the score.** Money sits in the vault and the bot can only *ask* it to trade. The vault values every bot using an independent price feed and records wins, losses and deaths. The bot never reports anything about itself.

**Result:** look up any creator and you see **every** bot they ever ran, **including the graveyard.**

## 2. How it works, explained like an operating system

| Normal OS | Parable |
|---|---|
| User account | **Creator**: one verified human (World) |
| Process | **Bot**: born, trades, dies |
| Permissions | **ENS badge** `bot-07.parable.eth`: limits, expiry, soulbound, revocable |
| Kernel | **Vault contract** (Sepolia): holds the money, checks the badge, executes trades, measures loss |
| System call | Bot **asks** the vault to trade |
| Process table and audit log | **Arkiv**: every birth, trade and death, queryable by anyone |
| `kill` | Badge revoked: by the creator, by the auto-loss check (anyone can trigger it), or by expiry |
| Scheduler | *(stretch)* **Opus manager** that launches and kills a swarm of bots |

```
   PEOPLE: Dashboard (web)          AI TOOLS: Claude Code / Codex via MCP (stretch)
                 \                         /
                  ▼                       ▼
   ┌──────────────────────────────────────────────────────────┐
   │ PARABLE ENGINE  (Python · FastAPI)                       │
   │  creators · launch bot · run bots · kill · report card   │
   └───┬──────────────┬──────────────┬──────────────┬─────────┘
       │ World        │ ENS          │ Vault        │ Arkiv
       ▼              ▼              ▼              ▼
  verify human    bot badge     trades + loss    public record:
  (approve each   (expiry,      maths at the     births, trades,
   bot launch)    soulbound,    Chainlink        deaths, graveyard,
                  revocable)    price            report cards
```

**Source of truth:** the vault on Sepolia (its counters and events). Arkiv is the public, searchable copy. Every Arkiv record carries the Sepolia transaction hash, and the report card shows "vault says 12 bots, Arkiv shows 12 ✓".

## 3. A bot's life, step by step

1. Creator clicks **Launch bot** (or a tool calls it via MCP) and chooses a preset (e.g. "momentum, $100, max loss 10%, 1 hour").
2. **World Agent Pass** asks the creator to approve this bot's birth. No approval means no bot (the denied path).
3. Engine creates the bot's wallet and an **ENS badge** `bot-07.parable.eth`. Text records: rules, creator, birth time. Expiry is set, transfers are disabled, and the vault keeps the right to revoke.
4. **Vault `register(bot)`** records the birth and funds the bot's balance inside the vault (fake practice money).
5. **Arkiv** gets a `bot` record (status: alive, expires when the lease ends) and a `birth` event.
6. The **bot loop** runs every N seconds: read price → AI (Claude Haiku) answers in a fixed format `{action, amount}` → if it's broken or the AI is down, fall back to a simple rule → ask the vault `trade()`.
7. **Vault `trade()`** checks the badge is valid, the bot is registered, and the amount is within limits. It executes at the Chainlink price, updates equity, and emits an event. The engine mirrors it to Arkiv.
8. **Death**, one of:
   - lease expires;
   - creator kills it;
   - **anyone** calls `checkAndRevoke(bot)`, the vault recomputes equity vs high-water mark at the Chainlink price, and the loss is past the limit.

   Then: vault marks it dead, ENS badge is unregistered, Arkiv gets a `death` record (cause, final profit/loss, lifetime). **It stays in the graveyard forever.**
9. **Report card** (per creator and per strategy): launched, alive, dead, win rate, worst loss. Calculated from **all** records, graveyard included.

## 4. Scope: CORE first, STRETCH only when the core is green

| CORE (must work end to end) | STRETCH (in this order) |
|---|---|
| Vault contract: register, trade at oracle price, equity + high-water mark, `checkAndRevoke`, events, counters. Foundry tests, verified on Etherscan | 1. MCP server (`launch_bot`, `list_bots`, `kill_bot`, `report_card`, `graveyard`) |
| ENS badge: create, expiry, soulbound, revoke; vault reads it during `trade()` | 2. Opus manager: launches 4–6 bots, kills losers, so its graveyard is public too |
| World Agent Pass: approve each bot launch + denied path, verified on the server | 3. Code fingerprint stored at badge issue, linking rebirths |
| Arkiv: bot / birth / trade / death records, with every page reading from Arkiv | 4. Bounty for whoever triggers `checkAndRevoke` |
| Bot loop: Claude Haiku + Pydantic + rule fallback | 5. ERC-8004 death records (shows up in 8004scan) |
| Dashboard: creators, live bots, **graveyard**, report card, "try to cheat" buttons | 6. TUI / CLI polish |
| Deployed live demo link + 2:30–2:55 video | |

## 5. Sponsor checklists (tick only with evidence; see `JUDGING.md`)

**ENS: Best Use of ENSv2** ($3k / $2k / $1k / $1k)
- [x] Built on ENSv2 on Sepolia; ENS is central (vault reads the badge on every trade)
- [x] Subnames: expiring + revocable (we keep the unregister role) + soulbound (transfer-admin role withheld). Bot may edit only `status`.
- [x] Agents as namespaces (bonus)
- [x] No hard-coded values; live demo link; open-source repo

**Arkiv: Build on Arkiv** ($3k / $1k)
- [x] Writes to the Arkiv testnet (Python SDK or JSON-RPC); the dashboard **reads** the graveyard and report cards from Arkiv
- [x] README: writer wallet address(es) and one query anyone can run
- [x] `/arkiv/schema.md`, `/arkiv/friction.md`, `/arkiv/reach.md`, `/arkiv/why-arkiv.md`, `/arkiv/how-you-use-arkiv.md`
- [x] Open-source license; AI usage stated
- Why Arkiv: anyone, or any app, can query any creator's graveyard without asking us. Alive-bot records **expire with the bot's lease** (natural use of expiry). Death records live long. Filters match real questions (creator, strategy, cause of death, profit/loss).

**World: World ID Agent Pass** ($2.5k / $1.5k / $1k). IDKit (2 × $1.25k) is the same partner pick, so apply to both if eligible.
- [x] Full journey: request → human completes → server validates → protected action (bot is born)
- [x] Denied / expired / cancelled path → no bot is born
- [x] Validation on our server; no secrets in the browser
- [x] Integration debrief: time to first success, friction, missing docs, top improvement

**ETHGlobal (all)**
- [x] Steady commits · `AI_USAGE.md` kept up to date · README pre-hackathon disclosure
- [ ] Video 2–4 min, ≥720p, own voice, not on a phone, no TTS
- [ ] Repo **public** before submitting · select ENS + Arkiv + World

## 6. Hour-by-hour (IST)

| Time | Do | Done when |
|---|---|---|
| **12:00–12:45** | Accounts: Sepolia ETH (faucet), Anthropic key, Arkiv faucet + access key, World Agent Pass portal app, ENSv2 Sepolia name. **Show this plan to the ENS / Arkiv / World mentors** ("has this been done? what would make you pick it?") | Keys in `.env`; mentor feedback noted below |
| **12:45–15:00** | **Risk checks**, ≤40 min each: (1) ENSv2 subname create / expiry / revoke from Python (read Batas, MIT); (2) Arkiv create + query + expiry from Python; (3) World Agent Pass verify in FastAPI; (4) read the Chainlink ETH/USD price on Sepolia | Each one has a working script in `spikes/` |
| **15:00** | **DECISION GATE**: any red → use the fallback (section 8) | Logged in this file |
| 15:00–19:00 | Vault contract + Foundry tests + deploy + verify | Tests pass; verified address in README |
| 19:00–22:00 | Engine: launch flow (World → ENS → vault → Arkiv), bot loop with fallback, death handling | One bot born → trades → dies, fully recorded |
| 22:00–01:00 | Dashboard: creator page, live bots, graveyard, report card, "try to cheat" buttons | Full demo flow clickable locally |
| **01:00–03:30** | **Sleep** | — |
| 03:30–05:00 | Hardening + deploy live; then stretch 1 (MCP), then 2 (Opus manager) only if the core is green | Live link works from a phone |
| 05:00–06:30 | README (problem, OS table, prior art, limits), `/arkiv/*.md`, World debrief, `AI_USAGE.md`, diagram; run `prize-auditor` | Auditor: no FAIL |
| 06:30–07:30 | Record video (2:30–2:55), submit, make repo public | Submitted |
| 07:30–09:00 | Buffer for emergencies only | — |

**Rule:** if anything burns more than 45 minutes, stop and take the fallback.

## 7. Demo script (2:45)

1. **0:00** Problem: "20 bots, 17 deleted, 3 shown. You can't tell." Then the Parable graveyard of a real creator.
2. **0:30** Launch a bot → World approval → ENS badge appears → Arkiv record. Show the explorer links.
3. **1:00** The bot trades within its limits (vault event, Arkiv record).
4. **1:20** **Try to cheat:**
   - an unregistered bot tries to trade → blocked;
   - an over-limit trade → blocked;
   - a second identity → World blocks it.
5. **1:50** A losing bot: anyone presses "check" → the vault recomputes the loss → auto-revoked → appears in the **graveyard**.
6. **2:15** *(if built)* The Opus manager launched 5 bots and killed 3: all 3 are in its graveyard.
7. **2:30** "Bots can't lie about their graveyard, because they never touch the money or write their own record."

## 8. Fallbacks

| Breaks | Fallback |
|---|---|
| ENSv2 subnames won't work by 15:00 | Keep the badge record in the vault plus an ENS **text record** on the parent name; if ENS is unusable, swap ENS out for 0G (verified bot decisions) |
| Arkiv SDK issues | Use the JSON-RPC API directly; queue writes on disk and retry; page shows "pending" |
| World Agent Pass blocked | IDKit Proof of Human (same partner) |
| Claude API down / weird output | Pydantic rejects → retry once → simple rule (e.g. buy on a 2% dip, sell on a 2% gain); shown on screen |
| Chainlink feed stale on Sepolia | Vault rejects stale prices (an `updatedAt` check); demo uses the last good price with a visible warning |
| Wi-Fi dies during the demo | Pre-recorded backup run + video |
| ENS Sepolia reset | Re-run the setup script; keep the video |

## 9. Honest limits (put these in the README)
- Practice network with fake money: the report card proves **honesty**, not real trading skill.
- Only bots that trade **through Parable** are covered; trading elsewhere isn't.
- We use mark-to-market equity against a high-water mark; price manipulation is limited by using Chainlink feeds, not by a pool price.
- The code fingerprint (stretch) proves which code was **committed to**, not what actually ran (that needs TEE).

## 10. Prior art (we credit it; Parable's contribution is the combination)
ENSign (agent subnames with spend limits and expiry, ENS 1st) · Batas (expiring, soulbound, revocable agent name + kill switch, ENS 2nd; MIT, used as reference) · Capsule · allowance.eth · ActionFeed (signed agent action history + authority gate; but self-written) · 8004scan / ERC-8004 (leaderboards of *living* agents) · Alpha Arena, Recall (AI trading leaderboards).
**New in Parable:** the record is written by the money-holder (the vault), not the bot · registration enforced before the first trade · one verified human per creator · loss measured by the vault and revocable by anyone · a full graveyard and cohort report cards.

## 11. Mentor feedback
- ENS: _
- Arkiv: _
- World: _
