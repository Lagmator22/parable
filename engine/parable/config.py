"""Settings loaded from the repo-root .env (never committed) and the process environment."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # random server secret used to derive each creator's wallet; never share it
    parable_creator_secret: str = ""
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
    # Set after setup_parent() / the deploy script; empty means "not set up yet".
    ens_resolver: str = ""
    ens_badge_oracle: str = ""
    # ENSv2 Sepolia deployment (docs.ens.domains/learn/deployments). It has been reset before,
    # so each address can be overridden from .env.
    ens_root_registry: str = "0xb458d6a3a77919449d03e7a6903c26827c1ec43f"
    ens_factory: str = "0xda70306c98e97ece36f997a21368e53298572991"
    ens_user_registry_impl: str = "0x9bd8a88719068d09ecee662f36c0e3856708366a"
    ens_resolver_impl: str = "0x115eb53f0c60696633855f90b138178fb40b2b2c"
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
    # Which brain the bots use: "rule" (free, no AI), "anthropic" (Claude), or "openai_compat"
    # (any free/cheap OpenAI-style API: Gemini, OpenRouter, Groq, a local Ollama). Empty = Claude if a key is set, else rule.
    bot_provider: str = ""
    llm_base_url: str = ""   # e.g. https://generativelanguage.googleapis.com/v1beta/openai
    llm_api_key: str = ""
    llm_model: str = ""      # e.g. gemini-2.5-flash


@lru_cache
def get_settings() -> Settings:
    return Settings()
