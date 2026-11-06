"""Shared Pydantic models. Mirrors INTERFACES.md exactly.

Money: USD values are integers with 6 decimals, ETH values have 18.
"""

from typing import Literal

from pydantic import BaseModel


class BotRules(BaseModel):
    strategy: str
    start_cash_usd: int
    max_trade_usd: int
    max_loss_bps: int
    lease_seconds: int
    brain: str = "rule"  # "rule", "claude:<model>", "jev:<model>", "gemini:<model>" or "gemma:<model>"; old records count as the free rule
    approval: str = "world"  # "world" = a person approved with World ID; "demo" = approved without it (marked on the register)


class TradeDecision(BaseModel):
    """LLM output, validated."""

    action: Literal["buy", "sell", "hold"]
    amount_usd: int = 0
    reason: str


class BotRecord(BaseModel):
    bot_id: int
    bot_address: str
    creator_id: str
    ens_name: str
    strategy: str
    rules: BotRules
    status: Literal["alive", "dead"]
    born_at: int
    born_tx: str


class BotEvent(BaseModel):
    bot_id: int
    kind: Literal["birth", "trade", "rejected", "death"]
    at: int
    tx_hash: str | None = None
    data: dict = {}


class DeathRecord(BaseModel):
    bot_id: int
    cause: Literal["expired", "killed", "loss_limit"]
    final_equity_usd: int
    start_cash_usd: int
    pnl_bps: int
    lifetime_s: int
    tx_hash: str


class ReportCard(BaseModel):
    subject: str
    launched: int
    alive: int
    dead: int
    profitable: int
    worst_pnl_bps: int
    avg_pnl_bps: float
    vault_count_matches: bool
