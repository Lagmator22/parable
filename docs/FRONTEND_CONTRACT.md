# Frontend ↔ engine contract (read this before touching the frontend)

The Python engine (`engine/`, FastAPI on port 8000) owns all logic. The frontend (`frontend/`) only
shows data and sends button clicks. If the frontend and this file disagree, this file wins; if this
file and `engine/parable/api.py` disagree, tell the backend side (Claude Code) and do not guess.

## Ground rules
- **Relative URLs only** (`/api/...`, `/world/...`). Never hard-code a host. The same build must work on
  `localhost`, behind the cloudflared tunnel, and on the final public URL.
- **Money is integers.** USD has **6 decimals** (`100_000_000` = $100.00). Percentages are **bps**
  (basis points, 1 bps = 0.01%, so `1000` = 10%). Times are **unix seconds**. Durations are **seconds**.
- **Secrets travel in headers only, never in a URL**: `x-claim` (confirm a launch), `x-owner-token` (kill).
- **Store in `localStorage`** (wrap every access in try/catch; private windows throw):
  - `creator`: the creator id (0x + 64 hex) of this browser's user, set after the first launch.
  - `owners`: JSON object `{ "<bot_id>": "<owner_token>" }`. Only this browser can kill its bots.
- **Errors**: every error response *should* be JSON `{"detail": "<short text>"}`, but a crash or the tunnel can
  return HTML or nothing. Always do `res.json().catch(() => ({detail: "Server error (" + res.status + ")"}))`.
  Show only `detail`, never a stack trace or the raw body.
- **Do not hammer the server.** Arkiv (the public database behind the graveyard) is rate-limited.
  Poll live bots every **5 s**, graveyard / report / compare every **15 s**, and pause polling when the tab is hidden.
- React escapes text by default. Never use `dangerouslySetInnerHTML` with server data (bot names come from users).

## Words the UI shows
| Field value | Show as |
|---|---|
| `status: "alive" / "dead"` | Alive / Dead |
| `cause: "expired"` | Lease ran out |
| `cause: "killed"` | Stopped by creator |
| `cause: "loss_limit"` | Hit its loss limit (vault killed it) |
| `brain: "rule"` | Simple rule (no AI) |
| `brain: "gemini:<model>"`, `"gemma:<model>"`, `"claude"`, `"local"` | show the model name |
| vault error names (`OverTradeLimit`, `NotBot`, `BadgeInvalid`, `StalePrice`, `NotOverLimit`, `CreatorIdentityMismatch`, `NotAlive`, `Expired`, `NotExpired`, `InsufficientBalance`, `Unauthorized`, `UnknownError`) | show the name plus a one-line plain explanation |

## Routes

### `GET /api/info`
```json
{ "offline": false, "explorer": "https://sepolia.etherscan.io/tx/",
  "vault_address": "0x5432...", "ens_parent": "parable.eth", "arkiv_writer": "0x4Bf4...",
  "arkiv_explorer": "https://rabdi.explorer.arkiv.network", "ens_app": "https://sepolia.app.ens.domains/",
  "strategies": ["momentum", "dip_buyer", "yolo"],
  "default_creator": "0xa4b3...", "eth_price_usd": 2233.24 }
```
`offline: true` means the engine runs a fake chain: show a clear **OFFLINE SIMULATION** banner.
If `localStorage.creator` is empty on load, initialize `creator` to `info.default_creator` so visitors and judges immediately see the public bots, graveyard, and report card without an empty screen!

### `GET /api/brains` → `[{"brain": "rule", "available": true}, {"brain": "gemini:gemini-3.5-flash-lite", "available": true}, ...]`
Only `available: true` brains may be picked in the launch form.

### `POST /api/launch` (JSON body) → start a launch
Body (all optional, defaults shown):
```json
{ "strategy": "momentum", "brain": "rule", "start_cash_usd": 100000000, "max_trade_usd": 20000000,
  "max_loss_bps": 1000, "lease_seconds": 3600 }
```
200 → `{"pending_id": "p-...", "claim": "<secret>", "approve_url": "/world/start?purpose=launch_bot&ref=p-..."}`
400/422 → brain unknown or not set up.

### The launch flow (World ID approval)
```
POST /api/launch ──▶ open approve_url in a NEW TAB (window.open) ──▶ user proves they're human in World App
       │                                                                  (or presses Approve/Deny in mock mode)
       ▼
every 2 s: POST /api/launch/{pending_id}/confirm  with header  x-claim: <claim>
       409 → still waiting (keep polling, show "Waiting for World ID…"; give up after 10 min)
       403 → denied or expired (show the detail: this is the "denied path" World's judges want to see)
       404 → unknown launch (stop)
       200 → born! {"bot": BotRecord, "owner_token": "...", "tx_url": "https://sepolia.etherscan.io/tx/..."}
             save localStorage.creator = bot.creator_id and owners[bot.bot_id] = owner_token
```
A real launch takes **30–90 s** after approval (6 blockchain transactions). Show progress, not a frozen button.

### `GET /api/bots?creator=<id>&status=alive|dead` → `[BotView]`
```json
{ "bot_id": 3, "bot_address": "0x...", "creator_id": "0x...", "ens_name": "bot-3-ab12.parable.eth",
  "strategy": "momentum", "status": "alive", "born_at": 1762412345, "born_tx": "0x...",
  "rules": {"strategy": "momentum", "brain": "rule", "start_cash_usd": 100000000, "max_trade_usd": 20000000,
            "max_loss_bps": 1000, "lease_seconds": 3600},
  "code_hash": "0x8f3a1c902b4e7d11", "equity_usd": 98500000, "pnl_bps": -150, "tx_url": "https://..." }
```
`equity_usd` / `pnl_bps` may be `null` (chain read failed). Time left = `born_at + rules.lease_seconds - now`. `code_hash` is the SHA-256 fingerprint of the bot's brain + strategy stored on its ENSv2 badge.

### `GET /api/bots/{bot_id}/events` → `[BotEvent]`, newest first
```json
{ "bot_id": 3, "kind": "birth|trade|rejected|death", "at": 1762412400, "tx_hash": "0x..." ,
  "data": { "action": "buy", "amount_usd": 20000000, "reason": "price rising", "error": "OverTradeLimit" } }
```
`data` keys differ by kind; render unknown keys generically. `rejected` = the vault refused the trade (no tx).

### `GET /api/graveyard/{creator_id}` → `[Grave]` (read from Arkiv: label it "Read live from Arkiv")
```json
{ "bot_id": 2, "cause": "loss_limit", "final_equity_usd": 89000000, "start_cash_usd": 100000000,
  "pnl_bps": -1100, "lifetime_s": 2460, "tx_hash": "0x...", "ens_name": "bot-2-ff01.parable.eth",
  "brain": "gemini:gemini-3.5-flash-lite", "tx_url": "https://..." }
```

### `GET /api/report?creator=<id>&strategy=<s>&brain=<b>` → `ReportCard`
```json
{ "subject": "0x...", "launched": 5, "alive": 1, "dead": 4, "profitable": 1,
  "worst_pnl_bps": -1100, "avg_pnl_bps": -420.5, "vault_count_matches": true }
```
`vault_count_matches: true` = "the vault's own count equals the public record: nothing hidden". Show it as a ✓ badge.

### `GET /api/report/brains` → one row per brain, in one call (use this for the "Compare brains" table)
```json
[{ "brain": "rule", "available": true, "launched": 4, "alive": 0, "dead": 4, "profitable": 1,
   "worst_pnl_bps": -1000, "avg_pnl_bps": -300.0 }]
```

### `POST /api/bots/{bot_id}/kill` (header `x-owner-token`) · `/check` · `/expire`
200 → `{"ok": true, "tx_hash": "0x...", "tx_url": "https://..."}`
409 → `{"detail": "NotOverLimit"}` (the vault refused: show it as "the vault said no: <reason>")
404 → bot unknown or not your bot.

### "Try to cheat" (each returns `{"attack": "...", "blocked": true, "reason": "NotBot"}`)
- `POST /api/cheat/unregistered-trade`: a random wallet tries to trade.
- `POST /api/cheat/over-limit/{bot_id}`: a real bot tries 10× its limit.
- `POST /api/cheat/second-identity`: the same human tries a fresh wallet (409 `launch a bot first` if none alive).
`blocked: true` is the GOOD outcome: show a green "Blocked by the vault ✓".

### World pages (served by the engine, not the frontend)
`/world/start`, `/world/callback`, `/world/mock/decision` return plain HTML. Don't rebuild them.

### AI Swarm Manager (LIVE — Stretch Goal #2)
- `GET /api/manager` → the AI manager ("swarm") status: `{ "enabled": true, "mind": "gemini:gemini-3.5-flash-lite", "bots": [bot_id], "decisions": [{at, action: "launch|kill|flag|keep", bot_id, reason}] }`
- `POST /api/manager/start` `{ "bots": 3, "minutes": 15 }` → runs an AI Swarm Manager audit pass (and spawns worker bots in offline mode), returning the updated status + decisions.

## How the frontend is served
- **Dev:** `cd ~/ethglobal/parable/frontend && npm run dev` (Vite on 5173) proxies `/api` and `/world` to
  `PARABLE_API` (default `http://127.0.0.1:8000`).
- **Fake backend for UI work (no gas, no keys):**
  `cd ~/ethglobal/parable/engine && PARABLE_OFFLINE=1 uv run uvicorn parable.api:app --port 8001`
  then `PARABLE_API=http://127.0.0.1:8001 npm run dev`. Approval opens a mock Approve/Deny page.
- **Final:** `npm run build` writes `frontend/dist/`. The engine serves `frontend/dist/index.html` at `/` and
  `frontend/dist/assets/*` at `/assets/*` when that folder exists (the old dashboard stays at `/classic`).
  So: a single-page app with no client-side routes other than `#hash` anchors (or use hash routing).
