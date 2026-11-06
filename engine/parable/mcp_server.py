"""MCP (Model Context Protocol) server for Parable: lets an AI assistant (Claude Code, Codex, Cursor) use
Parable by talking to the SAME running Parable server as the website, so everything it starts shows up on
the dashboard and World ID approval works. Money is shown in dollars and percents, never raw units.

Run:  cd engine && PARABLE_URL=http://127.0.0.1:8000 uv run python -m parable.mcp_server
Add to Claude Code:  claude mcp add parable -- uv --directory <repo>/engine run python -m parable.mcp_server
"""

import os

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Parable")
_client: httpx.Client | None = None


def base_url() -> str:
    return os.environ.get("PARABLE_URL", "http://127.0.0.1:8000").rstrip("/")


def client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(base_url=base_url(), timeout=60)
    return _client


def set_client(c: httpx.Client | None) -> None:
    """Tests plug in the web app's TestClient here."""
    global _client
    _client = c


def call(method: str, path: str, **kw) -> dict | list:
    r = client().request(method, path, **kw)
    try:
        body = r.json()
    except ValueError:
        body = {"detail": f"server error ({r.status_code})"}
    if r.status_code >= 400:
        return {"error": body.get("detail", "error") if isinstance(body, dict) else "error", "status": r.status_code}
    return body


def usd(n) -> str | None:
    return None if n is None else f"${n / 1e6:,.2f}"


def pct(bps) -> str | None:
    return None if bps is None else f"{bps / 100:+.2f}%"


@mcp.tool()
def status() -> dict:
    """Parable at a glance: bots born and dead (counted by the vault and Arkiv), running now, ETH price, links to check."""
    info, card, live = call("GET", "/api/info"), call("GET", "/api/report"), call("GET", "/api/bots", params={"status": "alive"})
    return {"bots_ever": card.get("launched"), "dead": card.get("dead"), "running": len(live) if isinstance(live, list) else None,
            "eth_price_usd": info.get("eth_price_usd"), "vault": info.get("vault_address"), "ens_names": f"*.{info.get('ens_parent')}",
            "arkiv_writer": info.get("arkiv_writer"), "dashboard": base_url()}


@mcp.tool()
def list_brains() -> list[dict]:
    """Which AI brains a bot can use on this server (available = set up and usable now)."""
    return call("GET", "/api/brains")


@mcp.tool()
def launch_bot(brain: str = "jev:deepseek-v4.1-flash", strategy: str = "yolo", cash_dollars: float = 100,
               max_trade_dollars: float = 20, max_loss_percent: float = 10, minutes: int = 10) -> dict:
    """Start a bot launch. Returns an approve_url: a human must open it and approve with World ID.
    Then call confirm_launch(pending_id, claim) until the bot is born (about a minute)."""
    r = call("POST", "/api/launch", json={"brain": brain, "strategy": strategy, "start_cash_usd": int(cash_dollars * 1e6),
                                         "max_trade_usd": int(max_trade_dollars * 1e6), "max_loss_bps": int(max_loss_percent * 100),
                                         "lease_seconds": minutes * 60})
    if "error" in r:
        return r
    return {**r, "approve_url": base_url() + r["approve_url"], "next": "Open approve_url, approve in World App, then call confirm_launch."}


@mcp.tool()
def confirm_launch(pending_id: str, claim: str) -> dict:
    """Check a launch: 'waiting' (approve in World ID first), 'being born' (step N of 6), or the born bot."""
    r = call("POST", f"/api/launch/{pending_id}/confirm", headers={"x-claim": claim})
    if r.get("status") == 409:
        return {"state": "being born" if str(r["error"]).startswith("approved") else "waiting for World ID", "detail": r["error"]}
    if "error" in r:
        return r
    b = r["bot"]
    return {"state": "born", "bot_id": b["bot_id"], "ens_name": b["ens_name"], "owner_token": r["owner_token"], "birth_tx": r.get("tx_url")}


@mcp.tool()
def running_bots() -> list[dict]:
    """Bots running now with their value, return, brain and time left."""
    bots = call("GET", "/api/bots", params={"status": "alive"})
    if not isinstance(bots, list):
        return [bots]
    return [{"bot_id": b["bot_id"], "ens_name": b["ens_name"], "brain": b["rules"]["brain"], "strategy": b["strategy"],
             "value": usd(b.get("equity_usd")), "return": pct(b.get("pnl_bps")), "birth_tx": b.get("tx_url")} for b in bots]


@mcp.tool()
def bot_history(bot_id: int) -> list[dict]:
    """One bot's public history from Arkiv, newest first: birth, trades (with the AI's reason), refusals, death."""
    return call("GET", f"/api/bots/{bot_id}/events")


@mcp.tool()
def graveyard() -> list[dict]:
    """Every bot that ever died on this vault: how it ended, trades, return, and links to Arkiv and Etherscan."""
    graves = call("GET", "/api/graveyard/all")
    if not isinstance(graves, list):
        return [graves]
    return [{"bot_id": g["bot_id"], "ens_name": g["ens_name"], "brain": g["brain"], "ended": g["cause"], "trades": g.get("trades"),
             "return": pct(g["pnl_bps"]), "arkiv": g.get("arkiv_url"), "tx": g.get("tx_url")} for g in graves]


@mcp.tool()
def compare_brains() -> list[dict]:
    """Every brain's full record (bots launched, dead, made money, average and worst return), dead bots included."""
    rows = call("GET", "/api/report/brains")
    return [r for r in rows if r.get("launched")] if isinstance(rows, list) else [rows]


@mcp.tool()
def try_to_cheat(kind: str = "unregistered") -> dict:
    """Ask the real vault to dry-run a cheat: 'unregistered' (stranger trades), 'over_limit' (10x size; needs a
    running bot) or 'second_identity' (same person, new wallet). Returns the vault's refusal and a cast command."""
    if kind == "over_limit":
        live = call("GET", "/api/bots", params={"status": "alive"})
        if not isinstance(live, list) or not live:
            return {"error": "launch a bot first: over_limit needs a running bot"}
        return call("POST", f"/api/cheat/over-limit/{live[0]['bot_id']}")
    path = {"unregistered": "/api/cheat/unregistered-trade", "second_identity": "/api/cheat/second-identity"}.get(kind)
    return call("POST", path) if path else {"error": "kind must be unregistered, over_limit or second_identity"}


@mcp.tool()
def stop_bot(bot_id: int, owner_token: str) -> dict:
    """Stop a running bot (creator only: needs the owner_token from confirm_launch). It goes to the graveyard."""
    return call("POST", f"/api/bots/{bot_id}/kill", headers={"x-owner-token": owner_token})


@mcp.tool()
def start_swarm(mind: str = "gemini:gemini-3.5-flash-lite", workers: list[str] | None = None, minutes: int = 15) -> dict:
    """Start a swarm: one mind model checks the workers every minute. workers is a list like
    ["jev:deepseek-v4.1-flash", "gemini:gemini-3.5-flash-lite", "rule"]. Returns an approve_url for World ID."""
    workers = workers or ["jev:deepseek-v4.1-flash", "gemini:gemini-3.5-flash-lite", "rule"]
    r = call("POST", "/api/swarm/start", json={"mind": mind, "workers": workers, "bots": len(workers), "minutes": minutes})
    return r if "error" in r else {**r, "approve_url": base_url() + r["approve_url"], "next": "Approve, then call confirm_swarm."}


@mcp.tool()
def confirm_swarm(pending_id: str, claim: str) -> dict:
    """After World ID approval, starts the swarm's workers. Then watch it with swarm_status."""
    return call("POST", f"/api/swarm/{pending_id}/confirm", headers={"x-claim": claim})


@mcp.tool()
def swarm_status() -> dict:
    """The swarm live: phase, each worker's numbers, and every keep/stop decision with who made it."""
    return call("GET", "/api/swarm")


@mcp.tool()
def telemetry() -> dict:
    """Live numbers: ETH market vs Chainlink price, and each running bot's return at the market price."""
    s = call("GET", "/api/series")
    if "error" in s:
        return s
    last = s["prices"][-1] if s["prices"] else [None, None, None]
    return {"eth_market_usd": last[1], "eth_chainlink_usd": last[2],
            "bots": [{"ens_name": b["ens_name"], "brain": b["brain"], "swarm": b["swarm"], "status": b["status"],
                      "return_at_market": pct(b["points"][-1][2]) if b["points"] else None} for b in s["bots"]]}


if __name__ == "__main__":
    mcp.run()
