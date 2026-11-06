"""The web server: dashboard + JSON routes that wire World, ENS, the vault and Arkiv together.
PARABLE_OFFLINE=1 swaps the chain for an in-memory simulation (the dashboard shows a banner).
The "cheat" routes try things a dishonest creator would try; the vault must block each one.
"""

import logging
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from eth_account import Account
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from parable import world_pass
from parable.arena import MarketArena
from parable.bot_runner import PRESETS, available_brains, code_fingerprint
from parable.config import get_settings
from parable.erc8004 import build_erc8004_feed
from parable.launcher import (ApprovalDenied, ApprovalPending, Launcher, LaunchError, LaunchFailed, real_backends,
                              to_bytes32)
from parable.manager import SwarmManager
from parable.models import BotRules

STATIC = Path(__file__).parent / "static"
FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "dist"  # the new React site, once built
EXPLORER_TX = "https://sepolia.etherscan.io/tx/"
log = logging.getLogger("parable.api")
_launcher: Launcher | None = None
_manager: SwarmManager | None = None
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
    global _launcher, _manager
    _launcher = launcher
    _manager = None


def get_manager() -> SwarmManager:
    global _manager
    if _manager is None:
        _manager = SwarmManager(get_launcher())
    return _manager


def tx_url(tx: str | None) -> str | None:
    return EXPLORER_TX + tx if tx and not offline() else None


@asynccontextmanager
async def lifespan(_app):
    get_launcher().start_poller()  # copies deaths from the vault into the graveyard
    yield


app = FastAPI(title="Parable", lifespan=lifespan)
app.include_router(world_pass.router)


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
        if b.record.bot_id not in records and (not creator or b.record.creator_id.lower() == creator.lower()):
            if not status or status == st:
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
    lau = get_launcher()
    c = None if creator_id == "all" else creator_id
    bots = {b.bot_id: b for b in lau.b.arkiv.bots(c, None)}
    deaths = lau.b.arkiv.all_graves() if c is None else lau.b.arkiv.graveyard(c)
    return [{**d.model_dump(), "ens_name": bots[d.bot_id].ens_name if d.bot_id in bots else f"bot #{d.bot_id}",
             "brain": bots[d.bot_id].rules.brain if d.bot_id in bots else "unknown",
             "code_hash": code_fingerprint(bots[d.bot_id].rules) if d.bot_id in bots else "",
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


def blocked(attack: str, fn, *args, **kwargs) -> dict:
    """Run an attack. The vault is supposed to reject it, so a revert means the defence worked."""
    try:
        tx = fn(*args, **kwargs)
    except Exception as err:
        return {"attack": attack, "blocked": True, "reason": get_launcher().b.vault.decode_revert(err)}
    return {"attack": attack, "blocked": False, "reason": "NOT BLOCKED (this should never happen)", "tx_hash": tx}


@app.post("/api/cheat/unregistered-trade")
def cheat_unregistered():
    """A random wallet that was never registered tries to trade with a real bot's money."""
    lau = get_launcher()
    bot_id = next(iter(lau.live), 1)
    stranger = Account.create().key.hex()
    return blocked("unregistered wallet tries to trade", lau.b.vault.trade, "0x" + stranger.removeprefix("0x"), bot_id, True, 1_000_000)


@app.post("/api/cheat/over-limit/{bot_id}")
def cheat_over_limit(bot_id: int):
    """A real bot tries to trade ten times more than its per-trade limit."""
    lau = get_launcher()
    bot = lau.live.get(bot_id)
    if bot is None:
        raise HTTPException(404, "unknown bot")
    big = bot.record.rules.max_trade_usd * 10
    return blocked("bot trades 10x its limit", lau.b.vault.trade, bot.key, bot_id, True, big)


@app.post("/api/cheat/second-identity")
def cheat_second_identity():
    """The same World identity tries to register a bot under a different creator wallet (fresh start)."""
    lau = get_launcher()
    known = [b.record for b in lau.live.values()] or lau.b.arkiv.bots()
    if not known:
        raise HTTPException(409, "launch a bot first")
    old = known[0]
    other_wallet, bot = Account.create().address, Account.create().address
    return blocked("same person, new wallet", lau.b.vault.register_bot,
                   bot_address=bot, creator_id=old.creator_id, creator_wallet=other_wallet,
                   badge_node=to_bytes32("cheat"), expires_at=old.born_at + 86400, start_cash_usd=1_000_000,
                   max_trade_usd=1_000_000, max_loss_bps=1000, strategy_id=to_bytes32("cheat"))


class ManagerRequest(BaseModel):
    bots: int = 3
    minutes: int = 15


@app.get("/api/manager")
def manager_status():
    return get_manager().status()


@app.post("/api/manager/start")
def manager_start(req: ManagerRequest = ManagerRequest()):
    return get_manager().start(count=req.bots, minutes=req.minutes, spawn_offline=offline())


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
