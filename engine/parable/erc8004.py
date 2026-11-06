"""ERC-8004 (Trustless Agents) export and terminal TUI table.
Unlike standard ERC-8004 directories that list only living agents, Parable exports both living and dead
agents from the Sepolia vault + Arkiv graveyard so survivorship bias cannot hide failed agents.
Run `uv run python -m parable.erc8004` for a terminal scoreboard of all on-chain bots.
"""

from parable.bot_runner import code_fingerprint
from parable.config import get_settings


def build_erc8004_feed(launcher) -> dict:
    """Build an ERC-8004 compatible agent registration + reputation feed (including graveyard deaths)."""
    s = get_settings()
    try:
        bots = {b.bot_id: b for b in launcher.b.arkiv.bots()}
    except Exception:
        bots = {}
    for bot_id, live in list(launcher.live.items()):
        bots.setdefault(bot_id, live.record)
    try:
        deaths = {d.bot_id: d for d in launcher.b.arkiv.all_graves()}
    except Exception:
        deaths = {}

    agents = []
    for bot_id, rec in sorted(bots.items()):
        death = deaths.get(bot_id)
        status = "dead" if death or rec.status == "dead" else "alive"
        pnl_bps = death.pnl_bps if death else 0
        final_eq = death.final_equity_usd if death else rec.rules.start_cash_usd
        agents.append({
            "type": "https://eips.ethereum.org/EIPS/eip-8004#registration-v1",
            "agentId": bot_id,
            "name": rec.ens_name,
            "agentAddress": f"eip155:11155111:{rec.bot_address}",
            "creatorId": rec.creator_id,
            "codeHash": code_fingerprint(rec.rules),
            "status": status,
            "strategy": rec.strategy,
            "brain": rec.rules.brain,
            "reputation": {
                "authority": f"eip155:11155111:{s.vault_address}",
                "pnlBps": pnl_bps,
                "startCashUsd": round(rec.rules.start_cash_usd / 1e6, 2),
                "finalEquityUsd": round(final_eq / 1e6, 2),
                "causeOfDeath": death.cause if death else None,
                "birthTx": rec.born_tx,
                "deathTx": death.tx_hash if death else None,
            },
        })
    return {
        "standard": "ERC-8004",
        "chain": "eip155:11155111",
        "vault": s.vault_address,
        "ensNamespace": s.ens_parent_name,
        "totalAgents": len(agents),
        "aliveAgents": sum(1 for a in agents if a["status"] == "alive"),
        "deadAgents": sum(1 for a in agents if a["status"] == "dead"),
        "agents": agents,
    }


def render_tui(feed: dict) -> str:
    """Render a clean ASCII terminal scoreboard of living and dead Parable agents."""
    lines = [
        f"PARABLE · ERC-8004 AGENT & GRAVEYARD REGISTRY ({feed['ensNamespace']})",
        f"Vault: {feed['vault']} · Total: {feed['totalAgents']} (Alive: {feed['aliveAgents']}, Dead: {feed['deadAgents']})",
        "-" * 92,
        f"{'ID':<4} {'STATUS':<7} {'ENS BADGE':<24} {'STRATEGY':<11} {'BRAIN':<24} {'CODE HASH':<12} {'PNL':<7}",
        "-" * 92,
    ]
    for a in feed["agents"]:
        rep = a["reputation"]
        pnl = f"{rep['pnlBps'] / 100:+.1f}%"
        lines.append(
            f"#{a['agentId']:<3} {a['status'].upper():<7} {a['name'][:23]:<24} "
            f"{a['strategy']:<11} {a['brain'][:23]:<24} {a['codeHash'][:10]:<12} {pnl:<7}"
        )
    lines.append("-" * 92)
    return "\n".join(lines)


if __name__ == "__main__":
    from parable.api import get_launcher

    print(render_tui(build_erc8004_feed(get_launcher())))
