# Parable: how it works (pictures only, simple words)

> **Parable in one line:** AI trading bots can't hide their failures here, because the bots never touch the money and never write their own record.

**Words used below**
- **Bot:** a small AI program that decides "buy", "sell" or "wait".
- **Vault:** a program on the blockchain that holds the money and keeps score. Nobody can secretly change it.
- **Badge:** the bot's name tag, e.g. `bot-07.parable.eth` (made with **ENS**). It has an expiry date and can be taken away.
- **Public record:** a shared notebook anyone can read (made with **Arkiv**).
- **World ID:** proof that the creator is one real, unique person.
- **Practice network (Sepolia):** a blockchain with fake money, used for testing.

---

## 1. The big picture
```
   You (website)          or       Your AI assistant (Claude Code / Codex)
          \                                  /
           ▼                                ▼
     ┌─────────────────────────────────────────────┐
     │        PARABLE ENGINE (Python program)       │
     │   launches bots · runs them · ends them      │
     └──┬────────────┬──────────────┬───────────┬──┘
        ▼            ▼              ▼           ▼
   World ID       ENS badge       VAULT       Arkiv
   "is this a     "name tag       "holds the  "public
    real person?"  with rules"     money,      notebook of
                                   keeps       every bot,
                                   score"      dead or alive"
```

## 2. A bot's life (from birth to the graveyard)
```
  Creator clicks "Launch bot"
            │
            ▼
  World ID: "Do you approve this bot?" ──── No ───▶ no bot is born (stop)
            │ Yes
            ▼
  ENS gives it a name tag: bot-07.parable.eth  (expires in 1 hour, can't be sold)
            │
            ▼
  Vault writes it down: "bot-07 is born, has $100, may lose at most 10%"
            │
            ▼
  Public notebook (Arkiv): "bot-07 born" ← anyone can read this
            │
            ▼
  ┌──── Bot loop (every few seconds) ────────────────────┐
  │  look at ETH price → AI decides buy / sell / wait     │
  │  → asks the vault to trade → vault checks the rules   │
  │  → trade recorded in the notebook                     │
  └───────────────────────────────────────────────────────┘
            │
            ▼  the bot dies when ONE of these happens:
     time runs out · creator stops it · it lost too much
            │
            ▼
  Name tag taken away · Vault marks it dead · Notebook: "bot-07 died"
            │
            ▼
  🪦 It stays in the GRAVEYARD forever. Nobody can delete it.
```

## 3. What the vault checks before every trade
```
  Bot asks: "Please buy $20 of ETH"
            │
            ▼
   Is this bot registered?        ── no ──▶ ❌ BLOCKED
            │ yes
   Is it still alive and not expired? ── no ──▶ ❌ BLOCKED
            │ yes
   Is its name tag still valid?   ── no ──▶ ❌ BLOCKED
            │ yes
   Is $20 within its limit?       ── no ──▶ ❌ BLOCKED
            │ yes
   Is the price fresh (Chainlink)? ── no ──▶ ❌ BLOCKED
            │ yes
            ▼
   ✅ Trade done at the real price
            │
   Lost more than its limit now?  ── yes ──▶ 🪦 bot dies automatically
```

## 4. Why nobody can hide a loser
```
  Cheating trick                         What Parable does
  ─────────────────────────────────      ───────────────────────────────────
  "Run secret bots, show only winners"   Bots can't trade unless registered first
  "Delete the losing bot"                Deaths are written by the vault, not by you
  "Make a new account, start fresh"      One real person = one account (World ID)
  "Lie about profits"                    The vault measures profit itself, at the real price
```

## 5. Where each piece lives
```
  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
  │ Practice blockchain  │  │ Arkiv network        │  │ Your laptop / server │
  │ (Sepolia)            │  │                      │  │                      │
  │  • Vault             │  │  • bot records       │  │  • Parable engine    │
  │  • ENS name tags     │  │  • trades, deaths    │  │  • website           │
  │  • Chainlink price   │  │  • report cards      │  │  • bots (AI loops)   │
  └──────────────────────┘  └──────────────────────┘  └──────────────────────┘
```

*Diagrams are updated after every build phase.*

---

## 6. What is built so far (after Phase 2), and which file does what
```
                         YOUR BROWSER  (dashboard: engine/parable/static/)
                         Launch · Live bots · 🪦 Graveyard · Report card · Try to cheat
                                        │  (asks every 3 seconds)
                                        ▼
  ┌──────────────────────────────────────────────────────────────────────────────┐
  │ api.py        the web server: receives button clicks, sends back results     │
  │   │                                                                          │
  │   ▼                                                                          │
  │ launcher.py   the "manager": runs the launch steps in order, ends bots,      │
  │               copies every death from the vault into the graveyard           │
  │   │                                                                          │
  │   ├─▶ world_pass.py  asks World ID "is this a real person, do you approve?"  │
  │   ├─▶ ens_badge.py   makes / reads / removes the bot's name tag (ENS)        │
  │   ├─▶ vault.py       talks to the vault contract on the practice blockchain  │
  │   ├─▶ arkiv_store.py writes / reads the public notebook (Arkiv)              │
  │   │        │                                                                 │
  │   │        ▼                                                                 │
  │   │   arkiv-bridge/  tiny helper program using Arkiv's official tool (JS SDK)│
  │   │                                                                          │
  │   └─▶ bot_runner.py  the bot's brain loop: price → AI decides → ask to trade │
  │                       (AI down or confused? → simple backup rule)            │
  │                                                                              │
  │ fake_chain.py  a pretend vault/ENS/Arkiv for practice when the internet or   │
  │                keys are missing. The page then shows "OFFLINE SIMULATION".   │
  └──────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
               contracts/src/ParableVault.sol   (the vault: holds money, keeps score)
               contracts/src/adapters/EnsV2BadgeOracle.sol (lets the vault check name tags)
```

## 7. Launching a bot, with the safety locks
```
  You click "Launch"
        │
        ▼
  Server makes a launch ticket:  launch id + secret claim code (only YOUR browser gets the code)
        │
        ▼
  World ID page opens ──▶ accepts ONLY launch ids the server made (fake ids → refused)
        │  you approve
        ▼
  Your browser says "confirm" + claim code ──▶ wrong code → refused (nobody can steal your approval)
        │
        ▼
  New bot wallet → a little test ETH for fees → ENS name tag → vault registers it → notebook "born"
        │
        ▼
  Bot loop starts
```

## 7b. Who is allowed to do what (security locks)
```
  Action                     Who can do it                 How we check
  ─────────────────────────  ────────────────────────────  ───────────────────────────────────────
  Approve a launch           only the person who started   secret claim code kept in their browser
  Kill a bot                 only its creator              same secret code (owner token)
  "Check loss" / "Expire"    ANYONE                        the vault only agrees if the rule is truly met
  Write to the notebook      only Parable's server         Arkiv helper needs a password + local only
  See error details          nobody (only the server log)  users see just the rule name, e.g. OverTradeLimit
```

## 8. Holes we know about, and how we'll fix them (improvement pipeline)
| # | Hole (plain words) | How bad | Fix / plan |
|---|---|---|---|
| 1 | **Nothing has run on a real blockchain yet.** All tests use pretend versions | 🔴 Big | Needs your keys + test money, then run the 3 spike scripts and deploy the vault |
| 2 | Contract tests never actually ran (Foundry not installed) | 🔴 Big | Install Foundry, run `forge test` |
| 3 | Writing to Arkiv and creating ENS names is untested for real | 🟠 Medium | Fund the Arkiv wallet + register an ENS name, run spikes |
| 4 | Parable's server is trusted to say "this creator passed World ID" when it registers a bot | 🟡 Known limit | Say it honestly in README; stretch: check World proof on-chain |
| 5 | The vault's "best score so far" only updates when the bot trades | 🟡 Small | Fine for demo; note in README |
| 6 | If the server restarts, running bots lose their keys (kept in memory only, on purpose) and simply expire | 🟡 Small | Document; short leases for demo |
| 7 | World approvals are kept in memory: a restart forgets pending launches | 🟡 Small | Fine for demo |
| 8 | Each bot needs 0.003 test ETH for fees, so the operator wallet must hold enough | 🟡 Small | Keep ~0.1 Sepolia ETH in the operator wallet |
| 9 | Sepolia's Chainlink price updates about once an hour | 🟡 Small | Set MAX_PRICE_AGE to 7200 seconds |
| 10 | "Unregistered bot" demo shows `NotBot`; clearer to also show `NotRegistered` | 🟢 Polish | Add a second cheat button |
| 11 | MCP (Claude Code / Codex access) and the Opus manager are not started | ⚪ Stretch | Phase 4, only after the core runs for real |

*Phase 2 status: 69 automated tests pass; full flow works in offline simulation; real-chain run waits for keys.*
