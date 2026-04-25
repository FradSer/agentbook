from __future__ import annotations

import logging

from pydantic import model_validator

from shared.config import SharedSettings

logger = logging.getLogger(__name__)


class Settings(SharedSettings):
    """Backend API configuration extending shared settings."""

    # Application metadata
    app_name: str = "Agentbook"
    app_version: str = "0.1.0"
    debug: bool = False

    # Security
    api_key_prefix: str = "ak_"
    secret_key: str = "change-me"

    # OpenRouter embeddings (api_key inherited from SharedSettings)
    openrouter_embedding_model: str = "openai/text-embedding-3-small"
    embedding_dimension: int = 1536

    # LLM Evaluator (optional — A/B comparison for cold-start signal)
    evaluator_enabled: bool = False
    evaluator_model: str = "anthropic/claude-sonnet-4-5"

    # Sandbox execution
    sandbox_enabled: bool = False
    sandbox_timeout_seconds: int = 30
    sandbox_image: str = "python:3.11-slim"
    sandbox_memory_mb: int = 128

    # Cross-problem knowledge graph
    knowledge_graph_enabled: bool = False
    knowledge_graph_min_similarity: float = 0.5
    knowledge_graph_max_relationships: int = 20

    # CORS
    cors_allow_origins: str = "*"

    # MCP Transport Configuration (Streamable HTTP)
    mcp_stateless: bool = True
    mcp_json_response: bool = True

    @model_validator(mode="after")
    def warn_on_permissive_cors(self) -> Settings:
        """Emit warning for permissive CORS configuration in production.

        Logs a warning if CORS_ALLOW_ORIGINS='*' and debug mode is disabled.
        """
        if self.cors_allow_origins == "*" and not self.debug:
            logger.warning(
                "CORS_ALLOW_ORIGINS='*' allows all origins. "
                "Consider restricting this in production."
            )
        return self


def validate_production_settings(settings: Settings) -> None:
    """Validate production settings before starting application.

    Args:
        settings: Settings instance to validate

    Raises:
        ValueError: If production settings are invalid
    """
    if not settings.debug:
        if not settings.secret_key:
            raise ValueError("SECRET_KEY must be set in production mode.")


settings = Settings()
