"""Settings loaded from the repo-root .env (never committed) and the process environment."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    sepolia_rpc_url: str = "https://ethereum-sepolia-rpc.publicnode.com"
    operator_private_key: str = ""
    vault_address: str = ""
    chainlink_eth_usd: str = "0x694AA1769357215DE4FAC081bf1f309aDC325306"
    ens_parent_name: str = ""
    arkiv_rpc_url: str = "https://rpc.rabdi.db-chain.testnet.arkiv.network"
    arkiv_private_key: str = ""
    # Optional: free key from hub.arkiv.network/access-keys, appended to the RPC URL (higher rate limits).
    arkiv_access_key: str = ""
    # Optional, read-only deployments: the writer wallet whose records we trust.
    # Derived from arkiv_private_key when that is set.
    arkiv_writer_address: str = ""
    world_client_id: str = ""
    world_client_secret: str = ""
    world_mock: bool = False
    anthropic_api_key: str = ""
    bot_model: str = "claude-haiku-5-5"


@lru_cache
def get_settings() -> Settings:
    return Settings()
