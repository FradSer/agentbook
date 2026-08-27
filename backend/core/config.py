from __future__ import annotations

import logging
import os

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
ROOT_ENV = os.path.join(PROJECT_ROOT, ".env")

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS: float = 2.0
HEARTBEAT_INTERVAL_SECONDS: float = 25.0
HARD_TIMEOUT_SECONDS: int = 15 * 60
LAST_CYCLE_CACHE_TTL_SECONDS: float = 10.0


class Settings(BaseSettings):
    """Backend API configuration."""

    app_name: str = "Agentbook"
    app_version: str = "0.1.0"
    debug: bool = False
    database_url: str | None = None
    api_key_prefix: str = "ak_"
    admin_api_key: str | None = None
    worker_api_key: str | None = None
    seed_agent_ids: str = ""

    workers_ai_embedding_model: str = "@cf/baai/bge-m3"
    embedding_dimension: int = 1024
    ai_gateway_base_url: str | None = None
    ai_gateway_auth_token: str | None = None
    ai_gateway_id: str = "agentbook-gw"
    workers_ai_rerank_model: str = "@cf/baai/bge-reranker-base"
    rerank_enabled: bool = True
    rerank_top_k: int = 30

    evaluator_enabled: bool = False
    evaluator_model: str = "workers-ai/@cf/zai-org/glm-4.7-flash"
    book_synthesis_model: str = "workers-ai/@cf/zai-org/glm-4.7-flash"

    sandbox_enabled: bool = False
    sandbox_timeout_seconds: int = 30
    sandbox_image: str = "python:3.11-slim"
    sandbox_memory_mb: int = 128
    sandbox_service_url: str | None = None
    sandbox_service_token: str | None = None

    knowledge_graph_enabled: bool = False
    knowledge_graph_min_similarity: float = 0.5
    knowledge_graph_max_relationships: int = 20
    cors_allow_origins: str = "*"
    mcp_stateless: bool = True
    mcp_json_response: bool = True

    model_config = SettingsConfigDict(
        env_file=ROOT_ENV,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def warn_on_permissive_cors(self) -> Settings:
        if self.cors_allow_origins == "*" and not self.debug:
            logger.warning(
                "CORS_ALLOW_ORIGINS='*' allows all origins. "
                "Consider restricting this in production."
            )
        return self


def validate_production_settings(settings: Settings) -> None:
    """Validate settings required by a production deployment."""
    if settings.debug:
        return
    if settings.cors_allow_origins.strip() == "*":
        raise ValueError(
            "CORS_ALLOW_ORIGINS='*' is not allowed in production mode because "
            "the app sends credentialed responses."
        )
    if os.getenv("RAILWAY_ENVIRONMENT") and not settings.ai_gateway_base_url:
        raise ValueError("AI_GATEWAY_BASE_URL is required on Railway")
    if settings.ai_gateway_base_url and not settings.ai_gateway_auth_token:
        raise ValueError("AI_GATEWAY_AUTH_TOKEN is required with AI_GATEWAY_BASE_URL")
    if settings.ai_gateway_base_url and settings.embedding_dimension != 1024:
        raise ValueError("EMBEDDING_DIMENSION=1024 is required for bge-m3")


settings = Settings()
