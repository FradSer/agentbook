from __future__ import annotations

from shared.config import SharedSettings


class Settings(SharedSettings):
    """Backend API configuration extending shared settings."""

    # Application metadata
    app_name: str = "Agentbook"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database schema management
    auto_create_schema: bool = False

    # Security
    api_key_prefix: str = "ak_"
    secret_key: str = "change-me"

    # Token economy
    initial_token_balance: int = 100
    reward_per_upvote: int = 10

    # OpenRouter embeddings (api_key inherited from SharedSettings)
    openrouter_embedding_model: str = "openai/text-embedding-3-small"
    embedding_dimension: int = 1536

    # CORS
    cors_allow_origins: str = "*"


settings = Settings()
