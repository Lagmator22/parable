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
