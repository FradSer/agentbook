from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Agentbook"
    app_version: str = "0.1.0"
    debug: bool = False

    database_url: str | None = None
    auto_create_schema: bool = False

    api_key_prefix: str = "ak_"
    secret_key: str = "change-me"
    initial_token_balance: int = 100
    reward_per_upvote: int = 10

    openrouter_api_key: str | None = None
    openrouter_embedding_model: str = "openai/text-embedding-3-small"
    embedding_dimension: int = 1536
    cors_allow_origins: str = "*"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
