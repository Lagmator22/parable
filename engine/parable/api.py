"""The web server: dashboard + JSON routes that wire World, ENS, the vault and Arkiv together.
PARABLE_OFFLINE=1 swaps the chain for an in-memory simulation (the dashboard shows a banner).
The "cheat" routes try things a dishonest creator would try; the vault must block each one.
"""

import logging
import os
import secrets
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from eth_account import Account
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from parable import world_pass
from parable.swarm_api import router as swarm_router
from parable.arena import MarketArena
from parable.bot_runner import PRESETS, available_brains, code_fingerprint
from parable.config import get_settings
from parable.erc8004 import build_erc8004_feed
from parable.launcher import (ApprovalDenied, ApprovalPending, Launcher, LaunchError, LaunchFailed, real_backends,
                              to_bytes32)
from parable.models import BotRules

STATIC = Path(__file__).parent / "static"
FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "dist"  # the new React site, once built
EXPLORER_TX = "https://sepolia.etherscan.io/tx/"
log = logging.getLogger("parable.api")
_launcher: Launcher | None = None
_arena = MarketArena()


def offline() -> bool:
    return os.environ.get("PARABLE_OFFLINE", "") == "1"


def get_launcher() -> Launcher:
    global _launcher
    if _launcher is None:
        if offline():
            from parable.fake_chain import fake_backends

            os.environ.setdefault("WORLD_MOCK", "1")  # no real World ID needed offline
            _launcher = Launcher(fake_backends(world_pass), secret=secrets.token_hex(16))
        else:
            _launcher = Launcher(real_backends(), secret=get_settings().parable_creator_secret)
    return _launcher


def set_launcher(launcher: Launcher | None) -> None:
    """Tests use this to plug in a launcher built from fakes."""
    global _launcher
    _launcher = launcher


def tx_url(tx: str | None) -> str | None:
    return EXPLORER_TX + tx if tx and not offline() else None


@asynccontextmanager
async def lifespan(_app):
    get_launcher().start_poller()  # copies deaths from the vault into the graveyard
    from parable.minds import probe_claude
    from parable.swarm_api import get_recorder

    get_recorder().start()  # live graph samples
    threading.Thread(target=probe_claude, daemon=True).start()  # learn whether Claude has credit
    yield


app = FastAPI(title="Parable", lifespan=lifespan)
app.include_router(world_pass.router)
app.include_router(swarm_router)


@app.exception_handler(Exception)
async def any_error(_request, err: Exception):
    """Never show a raw error or an HTML crash page: log it here, answer short JSON."""
    from parable.arkiv_store import ArkivError

    if isinstance(err, ArkivError):
        log.warning("Arkiv unavailable: %s", err)
        return JSONResponse({"detail": "the public record (Arkiv) is slow right now; try again in a moment"}, 503)
    log.exception("unexpected server error")
    return JSONResponse({"detail": "server error"}, 500)


class LaunchRequest(BaseModel):
    strategy: str = "momentum"
    start_cash_usd: int = 100_000_000  # $100 (USD has 6 decimals)
    max_trade_usd: int = 20_000_000  # $20 per trade
    max_loss_bps: int = 1000  # 10% (1 bps = 0.01%)
    lease_seconds: int = 3600
    brain: str = "rule"


def vault_call(fn, *args):
    """Run a vault action; if the vault rejects it, answer 409 with the decoded reason."""
    try:
        return fn(*args)
    except LaunchError as err:
        raise HTTPException(404, str(err))
    except Exception as err:
        log.warning("vault call failed: %r", err)  # full detail stays in the server log only
        raise HTTPException(409, get_launcher().b.vault.decode_revert(err))


def arkiv_writer() -> str:
    """The wallet that writes Parable's Arkiv rows (public address, worked out from the key locally)."""
    s = get_settings()
    if s.arkiv_writer_address:
        return s.arkiv_writer_address
    return Account.from_key(s.arkiv_private_key).address if s.arkiv_private_key else ""


@app.get("/api/info")
def info():
    """Public facts the website shows as proof links. Addresses only, never keys."""
    s = get_settings()
    lau = get_launcher()
    default_creator = next((b.record.creator_id for b in reversed(list(lau.live.values()))), "")
    if not default_creator:
        try:
            known = lau.b.arkiv.bots()
            default_creator = known[-1].creator_id if known else ""
        except Exception:
            default_creator = ""
    try:
        eth_price_usd = round(lau.b.vault.price() / 1e8, 2)
    except Exception:
        eth_price_usd = None
    return {"offline": offline(), "explorer": EXPLORER_TX, "vault_address": s.vault_address,
            "ens_parent": s.ens_parent_name, "arkiv_writer": arkiv_writer(),
            "arkiv_explorer": "https://rabdi.explorer.arkiv.network", "ens_app": "https://sepolia.app.ens.domains/",
            "strategies": list(PRESETS), "default_creator": default_creator, "eth_price_usd": eth_price_usd}


@app.get("/api/brains")
def brains():
    """Which brains are set up on this server (true/false only; no keys or settings are ever returned)."""
    return [{"brain": name, "available": ok} for name, ok in available_brains().items()]


@app.post("/api/launch")
def launch(req: LaunchRequest):
    known = available_brains()
    if req.brain not in known:
        raise HTTPException(422, f"unknown brain '{req.brain}'")
    if not known[req.brain]:  # a quiet fallback would spoil the brain comparison, so refuse
        raise HTTPException(400, f"brain '{req.brain}' is not set up on this server")
    pending_id, claim = get_launcher().start_launch(BotRules(**req.model_dump()))
    # the claim token stays in the requester's browser; only they can confirm this launch
    return {"pending_id": pending_id, "claim": claim,
            "approve_url": f"/world/start?purpose=launch_bot&ref={pending_id}"}


@app.post("/api/launch/{pending_id}/confirm")
def confirm(pending_id: str, claim: str = Header("", alias="x-claim")):
    try:
        bot = get_launcher().confirm_launch(pending_id, claim)
    except ApprovalPending as err:
        raise HTTPException(409, str(err))
    except ApprovalDenied as err:
        raise HTTPException(403, f"not approved: {err}")
    except LaunchError as err:
        raise HTTPException(404, str(err))
    except LaunchFailed as err:
        raise HTTPException(502, str(err))
    return {"bot": bot.model_dump(), "owner_token": claim, "tx_url": tx_url(bot.born_tx)}


@app.get("/api/bots")
def list_bots(creator: str | None = None, status: str | None = None):
    lau = get_launcher()
    records = {r.bot_id: r for r in lau.b.arkiv.bots(creator or None, status or None)}
    # Include bots just born on-chain whose background Arkiv write is still in flight.
    for b in list(lau.live.values()):
        st = "dead" if b.dead else "alive"
        if b.record.bot_id in records:
            # Arkiv takes a few seconds to record a death; this server knows at once, so it wins.
            if st == "dead" and status == "alive":
                records.pop(b.record.bot_id)
            elif st == "dead":
                records[b.record.bot_id] = records[b.record.bot_id].model_copy(update={"status": "dead"})
        elif (not creator or b.record.creator_id.lower() == creator.lower()) and (not status or status == st):
            records[b.record.bot_id] = b.record.model_copy(update={"status": st})
    out = []
    for rec in records.values():
        try:
            equity = lau.b.vault.equity(rec.bot_id)
        except Exception:
            equity = None
        pnl = (equity - rec.rules.start_cash_usd) * 10000 // rec.rules.start_cash_usd if equity is not None else None
        out.append({**rec.model_dump(), "code_hash": code_fingerprint(rec.rules),
                    "equity_usd": equity, "pnl_bps": pnl, "tx_url": tx_url(rec.born_tx)})
    return out


@app.get("/api/graveyard/{creator_id}")
def graveyard(creator_id: str):
    """Graves, newest data from Arkiv. Each carries its trade count and a link to its own Arkiv entity page."""
    lau = get_launcher()
    c = None if creator_id == "all" else creator_id
    bots = {b.bot_id: b for b in lau.b.arkiv.bots(c, None)}
    deaths = lau.b.arkiv.all_graves() if c is None else lau.b.arkiv.graveyard(c)
    try:
        keys, trades = lau.b.arkiv.death_keys(), lau.b.arkiv.trade_counts()
    except Exception:
        keys, trades = {}, {}
    explorer = "https://rabdi.explorer.arkiv.network/entity/"
    return [{**d.model_dump(), "ens_name": bots[d.bot_id].ens_name if d.bot_id in bots else f"bot #{d.bot_id}",
             "brain": bots[d.bot_id].rules.brain if d.bot_id in bots else "unknown",
             "code_hash": code_fingerprint(bots[d.bot_id].rules) if d.bot_id in bots else "",
             "trades": trades.get(d.bot_id, 0),
             "arkiv_url": explorer + keys[d.bot_id] if d.bot_id in keys and not offline() else None,
             "tx_url": tx_url(d.tx_hash)}
            for d in deaths]


@app.get("/api/report")
def report(creator: str | None = None, strategy: str | None = None, brain: str | None = None):
    return get_launcher().report(creator or None, strategy or None, brain or None)


@app.get("/api/report/brains")
def report_brains():
    """The 'compare brains' table in one call (two Arkiv reads in total, not one per brain)."""
    rows = get_launcher().b.arkiv.report_by_brain()
    empty = {"launched": 0, "alive": 0, "dead": 0, "profitable": 0, "worst_pnl_bps": 0, "avg_pnl_bps": 0.0}
    known = available_brains()
    names = list(known) + sorted(set(rows) - set(known))  # brains set up here first, then old ones from the record
    return [{"brain": b, "available": known.get(b, False), **rows.get(b, empty)} for b in names]


@app.get("/api/bots/{bot_id}/events")
def bot_events(bot_id: int):
    """One bot's public timeline from Arkiv: birth, trades, blocked trades, death (newest first)."""
    return [e.model_dump() for e in get_launcher().b.arkiv.events(bot_id)]


@app.post("/api/bots/{bot_id}/{action}")
def end_bot(bot_id: int, action: str, token: str = Header("", alias="x-owner-token")):
    lau = get_launcher()
    if action == "kill":  # creator only: needs the claim code their browser kept from launch
        tx = vault_call(lau.kill, bot_id, token)
    elif action in ("check", "expire"):  # anyone: the vault only allows it when the rule is really met
        tx = vault_call(getattr(lau, action), bot_id)
    else:
        raise HTTPException(404, "action must be kill, check or expire")
    return {"ok": True, "tx_hash": tx, "tx_url": tx_url(tx)}


PUBLIC_RPC = "https://ethereum-sepolia-rpc.publicnode.com"


def blocked(attack: str, check: str, fn, *args) -> dict:
    """Ask the vault to dry-run an attack (eth_call: no fee, nothing changes). A refusal means the defence
    worked, and the answer is the vault's own error name. `check` is the same call as a `cast` command,
    so anyone can ask the real contract themselves and see the same refusal."""
    try:
        fn(*args)
    except Exception as err:
        reason = get_launcher().b.vault.decode_revert(err)
        return {"attack": attack, "blocked": True, "reason": reason, "check": check, "code": error_code(reason)}
    return {"attack": attack, "blocked": False, "reason": "NOT BLOCKED (this should never happen)", "check": check}


def error_code(name: str) -> str:
    """The 4-byte id `cast call` prints for a vault error (e.g. NotBot -> 0xa03b20af), so people can match them."""
    try:
        from parable.vault import _error_selectors

        return next((sel for sel, n in _error_selectors().items() if n == name), "")
    except Exception:
        return ""


def cast(signature: str, args: list, sender: str) -> str:
    vault_address = get_settings().vault_address or "<vault>"
    return f'cast call {vault_address} "{signature}" {" ".join(str(a) for a in args)} --from {sender} --rpc-url {PUBLIC_RPC}'


@app.post("/api/cheat/unregistered-trade")
def cheat_unregistered():
    """A random wallet that was never registered tries to trade with a real bot's money."""
    lau = get_launcher()
    bot_id = next(iter(lau.live), 1)
    stranger = Account.create().address
    check = cast("trade(uint256,bool,uint256)", [bot_id, "true", 1_000_000], stranger)
    return blocked("unregistered wallet tries to trade", check, lau.b.vault.simulate_trade, stranger, bot_id, True, 1_000_000)


@app.post("/api/cheat/over-limit/{bot_id}")
def cheat_over_limit(bot_id: int):
    """A real bot tries to trade ten times more than its per-trade limit."""
    lau = get_launcher()
    bot = lau.live.get(bot_id)
    if bot is None:
        raise HTTPException(404, "unknown bot")
    big = bot.record.rules.max_trade_usd * 10
    check = cast("trade(uint256,bool,uint256)", [bot_id, "true", big], bot.record.bot_address)
    return blocked("bot trades 10x its limit", check, lau.b.vault.simulate_trade, bot.record.bot_address, bot_id, True, big)


@app.post("/api/cheat/second-identity")
def cheat_second_identity():
    """The same World identity tries to register a bot under a different creator wallet (fresh start)."""
    lau = get_launcher()
    known = [b.record for b in lau.live.values()] or lau.b.arkiv.bots()
    if not known:
        raise HTTPException(409, "launch a bot first")
    old = known[0]
    other_wallet, bot = Account.create().address, Account.create().address
    args = [bot, old.creator_id, other_wallet, to_bytes32("cheat"), old.born_at + 86400, 1_000_000, 1_000_000, 1000, to_bytes32("cheat")]
    operator = lau.b.vault.operator_address()  # only the operator may register, so the dry run comes from it
    check = cast("registerBot(address,bytes32,address,bytes32,uint64,uint256,uint256,uint16,bytes32)", args, operator)
    return blocked("same person, new wallet", check, lau.b.vault.simulate_register, operator, *args)


@app.get("/api/erc8004")
def erc8004_feed():
    """ERC-8004 agent registration + reputation feed (including graveyard deaths)."""
    return build_erc8004_feed(get_launcher())


class ArenaRequest(BaseModel):
    scenario: str = "flash_crash"
    live_llm: bool = True


@app.get("/api/arena")
def arena_status():
    return _arena.get_or_run()


@app.post("/api/arena/run")
def arena_run(req: ArenaRequest = ArenaRequest()):
    return _arena.run(req.scenario, use_live_llm=req.live_llm)


@app.get("/")
def home():
    """The new React site if it has been built (frontend/dist), otherwise the simple built-in dashboard."""
    built = FRONTEND / "index.html"
    return FileResponse(built if built.exists() else STATIC / "index.html")


@app.get("/classic")
def classic():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/assets/{name:path}")
def frontend_asset(name: str):
    """Serve built Vite assets even when `frontend/dist` was built after the server started."""
    root = (FRONTEND / "assets").resolve()
    target = (root / name).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise HTTPException(404, "asset not found")
    return FileResponse(target)
