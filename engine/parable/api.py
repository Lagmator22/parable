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
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from parable import world_pass
from parable.config import get_settings
from parable.launcher import ApprovalDenied, ApprovalPending, Launcher, LaunchError, real_backends, to_bytes32
from parable.models import BotRules

STATIC = Path(__file__).parent / "static"
EXPLORER_TX = "https://sepolia.etherscan.io/tx/"
log = logging.getLogger("parable.api")
_launcher: Launcher | None = None


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
    yield


app = FastAPI(title="Parable", lifespan=lifespan)
app.include_router(world_pass.router)


class LaunchRequest(BaseModel):
    strategy: str = "momentum"
    start_cash_usd: int = 100_000_000  # $100 (USD has 6 decimals)
    max_trade_usd: int = 20_000_000  # $20 per trade
    max_loss_bps: int = 1000  # 10% (1 bps = 0.01%)
    lease_seconds: int = 3600


def vault_call(fn, *args):
    """Run a vault action; if the vault rejects it, answer 409 with the decoded reason."""
    try:
        return fn(*args)
    except LaunchError as err:
        raise HTTPException(404, str(err))
    except Exception as err:
        log.warning("vault call failed: %r", err)  # full detail stays in the server log only
        raise HTTPException(409, get_launcher().b.vault.decode_revert(err))


@app.get("/api/info")
def info():
    return {"offline": offline(), "explorer": EXPLORER_TX}


@app.post("/api/launch")
def launch(req: LaunchRequest):
    pending_id, claim = get_launcher().start_launch(BotRules(**req.model_dump()))
    # the claim token stays in the requester's browser; only they can confirm this launch
    return {"pending_id": pending_id, "claim": claim,
            "approve_url": f"/world/start?purpose=launch_bot&ref={pending_id}"}


@app.post("/api/launch/{pending_id}/confirm")
def confirm(pending_id: str, claim: str):
    try:
        bot = get_launcher().confirm_launch(pending_id, claim)
    except ApprovalPending as err:
        raise HTTPException(409, str(err))
    except ApprovalDenied as err:
        raise HTTPException(403, f"not approved: {err}")
    except LaunchError as err:
        raise HTTPException(404, str(err))
    return {"bot": bot.model_dump(), "owner_token": claim, "tx_url": tx_url(bot.born_tx)}


@app.get("/api/bots")
def list_bots(creator: str | None = None, status: str | None = None):
    lau = get_launcher()
    out = []
    for rec in lau.b.arkiv.bots(creator or None, status or None):
        try:
            equity = lau.b.vault.equity(rec.bot_id)
        except Exception:
            equity = None
        pnl = (equity - rec.rules.start_cash_usd) * 10000 // rec.rules.start_cash_usd if equity is not None else None
        out.append({**rec.model_dump(), "equity_usd": equity, "pnl_bps": pnl, "tx_url": tx_url(rec.born_tx)})
    return out


@app.get("/api/graveyard/{creator_id}")
def graveyard(creator_id: str):
    lau = get_launcher()
    names = {b.bot_id: b.ens_name for b in lau.b.arkiv.bots(creator_id, None)}
    return [{**d.model_dump(), "ens_name": names.get(d.bot_id, f"bot #{d.bot_id}"), "tx_url": tx_url(d.tx_hash)}
            for d in lau.b.arkiv.graveyard(creator_id)]


@app.get("/api/report")
def report(creator: str | None = None, strategy: str | None = None):
    return get_launcher().report(creator or None, strategy or None)


@app.post("/api/bots/{bot_id}/{action}")
def end_bot(bot_id: int, action: str, token: str = ""):
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
    alive = [b for b in lau.live.values() if not b.dead]
    if not alive:
        raise HTTPException(409, "launch a bot first")
    old = alive[0]
    other_wallet, bot = Account.create().address, Account.create().address
    return blocked("same person, new wallet", lau.b.vault.register_bot,
                   bot_address=bot, creator_id=old.record.creator_id, creator_wallet=other_wallet,
                   badge_node=to_bytes32("cheat"), expires_at=old.expires_at, start_cash_usd=1_000_000,
                   max_trade_usd=1_000_000, max_loss_bps=1000, strategy_id=to_bytes32("cheat"))


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
