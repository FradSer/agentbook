from __future__ import annotations

import logging

from pydantic import model_validator

from shared.config import SharedSettings

logger = logging.getLogger(__name__)

# SSE stream timing knobs (live-research banner). Module-level so operators
# can tune via reload without re-deploying every worker; matches the pattern
# used by `backend.core.sse_concurrency` for its concurrency caps.
POLL_INTERVAL_SECONDS: float = 2.0
HEARTBEAT_INTERVAL_SECONDS: float = 25.0
HARD_TIMEOUT_SECONDS: int = 15 * 60
LAST_CYCLE_CACHE_TTL_SECONDS: float = 10.0


class Settings(SharedSettings):
    """Backend API configuration extending shared settings."""

    # Application metadata
    app_name: str = "Agentbook"
    app_version: str = "0.1.0"
    debug: bool = False

    # Security
    api_key_prefix: str = "ak_"
    secret_key: str = "change-me"

    # OpenRouter embeddings (api_key inherited from SharedSettings).
    # Kept as a fallback after Voyage in the resolver chain.
    openrouter_embedding_model: str = "openai/text-embedding-3-small"
    # Vector dimension shared by both embedding providers (Voyage v3-large at
    # output_dimension=1024 and the Fallback / OpenRouter paths). Lowered from
    # 1536 (text-embedding-3-small native) so that Voyage's Matryoshka
    # truncation lines up with the IVFFlat / HNSW column type.
    embedding_dimension: int = 1024

    # Voyage AI commercial models. ``voyage-3-large`` is the engineering-text
    # tuned embedder; ``rerank-2.5-lite`` is the latency-optimised cross
    # encoder (full ``rerank-2.5`` is reserved for the offline Reviewer pass
    # in a future Phase 4). Voyage rerank caps at 100 requests/minute per
    # account so the in-process token bucket in
    # ``backend/infrastructure/reranking/voyage.py`` mirrors that limit.
    voyage_embedding_model: str = "voyage-3-large"
    voyage_rerank_model: str = "rerank-2.5-lite"

    # Search reranking configuration. ``rerank_top_k`` is the candidate pool
    # size handed to the reranker before final truncation to ``limit``.
    # ``rerank_enabled`` lets operators kill-switch the reranker without
    # redeploy if Voyage has an outage.
    rerank_enabled: bool = True
    rerank_top_k: int = 30

    # Embedding column cutover flag. ``v1`` reads/writes the legacy
    # ``problems.embedding`` column (1536-dim). ``v2`` switches to
    # ``problems.embedding_v2`` (1024-dim, populated by
    # ``backend/scripts/reembed_corpus.py``). Operators flip this only after
    # the backfill reports >99% coverage on the new column.
    embedding_version: str = "v1"

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
        if not settings.secret_key or settings.secret_key == "change-me":
            raise ValueError(
                "SECRET_KEY must be set to a non-default value in production mode."
            )


settings = Settings()
