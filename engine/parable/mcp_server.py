"""MCP (Model Context Protocol) server for Parable.

Lets any AI assistant (Claude Code, OpenAI Codex, Cursor) inspect a creator's full trading history,
query the Arkiv graveyard, compare AI brains, start a World-approved bot launch, or stop a bot.
Run with: `cd engine && uv run python -m parable.mcp_server`
"""

from mcp.server.fastmcp import FastMCP

from parable import api
from parable.models import BotRules

mcp = FastMCP("Parable")


@mcp.tool()
def launch_bot(
    strategy: str = "momentum",
    brain: str = "rule",
    start_cash_usd: int = 100_000_000,
    max_trade_usd: int = 20_000_000,
    max_loss_bps: int = 1000,
    lease_seconds: int = 600,
) -> dict:
    """Start a Parable bot launch. Returns pending_id, claim token, and the World ID approval URL."""
    req = api.LaunchRequest(
        strategy=strategy, brain=brain, start_cash_usd=start_cash_usd,
        max_trade_usd=max_trade_usd, max_loss_bps=max_loss_bps, lease_seconds=lease_seconds,
    )
    return api.launch(req)


@mcp.tool()
def list_bots(creator_id: str = "", status: str = "") -> list[dict]:
    """List bots from the public Arkiv record (and in-memory live bots), with live Sepolia equity and code hash."""
    return api.list_bots(creator=creator_id or None, status=status or None)


@mcp.tool()
def graveyard(creator_id: str = "all") -> list[dict]:
    """Read the permanent Arkiv graveyard of dead bots (causes: expired, killed, loss_limit)."""
    return api.graveyard(creator_id or "all")


@mcp.tool()
def report_card(creator_id: str = "", strategy: str = "", brain: str = "") -> dict:
    """Get the honest report card (launched, alive, dead, profitable, worst loss, vault_count_matches)."""
    card = api.report(creator=creator_id or None, strategy=strategy or None, brain=brain or None)
    return card.model_dump() if hasattr(card, "model_dump") else dict(card)


@mcp.tool()
def compare_brains() -> list[dict]:
    """Compare every AI brain and rule across all bots, dead or alive."""
    return api.report_brains()


@mcp.tool()
def bot_events(bot_id: int) -> list[dict]:
    """Read one bot's full timeline from Arkiv: birth, trades, vault-blocked trades, and death."""
    return api.bot_events(bot_id)


@mcp.tool()
def kill_bot(bot_id: int, owner_token: str) -> dict:
    """Stop a live bot (creator only, requires the claim/owner token from launch)."""
    return api.end_bot(bot_id, "kill", token=owner_token)


if __name__ == "__main__":
    mcp.run()
