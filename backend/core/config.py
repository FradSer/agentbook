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
    # Operator-only takedown credential (env ADMIN_API_KEY). When unset the
    # DELETE /v1/problems|solutions/{id} redaction endpoints are disabled.
    admin_api_key: str | None = None
    # Comma-separated agent UUIDs whose traffic counts as seeded, not organic
    # (env SEED_AGENT_IDS). Lets the operator tag historical seed-corpus
    # identities so the G3/G4 organic-share reads exclude them.
    seed_agent_ids: str = ""
    # ``secret_key`` was deleted in 2026-05 — the field had no consumers
    # (no cookie/JWT/CSRF signing) and the production-validate check on
    # it was decorative security. If a future feature needs a signing
    # secret, re-introduce it alongside the actual signing path so the
    # validation has bite. ``conftest.py``'s historical save/restore was
    # removed in the same change.

    # Gemini embeddings (api_key inherited from SharedSettings as
    # ``gemini_api_key``). Default embedder, ahead of Voyage / OpenRouter in
    # the resolver chain. ``gemini-embedding-001`` emits ``embedding_dimension``
    # via Matryoshka truncation (normalized client-side for non-3072 sizes).
    gemini_embedding_model: str = "gemini-embedding-001"

    # OpenRouter embeddings (api_key inherited from SharedSettings).
    # Kept as a fallback after Gemini / Voyage in the resolver chain.
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
    # Remote sandbox microservice: when set, code is POSTed to this URL
    # (a separate service that is itself a Docker host) instead of shelling
    # out to a local ``docker`` daemon. This is the path that works on hosts
    # with no Docker daemon (e.g. a Railway app container) — the API never
    # runs untrusted code in-process, the sandbox service owns isolation.
    sandbox_service_url: str | None = None
    sandbox_service_token: str | None = None

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

    @model_validator(mode="after")
    def warn_on_embedding_dimension_mismatch(self) -> Settings:
        """Warn loudly in EVERY mode when Voyage is wired to the v1 column.

        Voyage v3-large outputs 1024-dim vectors; the legacy
        ``problems.embedding`` column read/written under ``v1`` is
        vector(1536). In production ``validate_production_settings`` turns
        this into a hard boot refusal, but in debug / DEMO mode that check is
        skipped — so the same misconfiguration would silently degrade every
        recall to keyword search while the response still advertised a dense
        provider. Surface it at construction so it is visible regardless of
        mode.
        """
        if self.voyage_api_key and self.embedding_version == "v1":
            logger.warning(
                "VOYAGE_API_KEY is set with EMBEDDING_VERSION='v1': Voyage "
                "outputs 1024-dim vectors but the legacy column is "
                "vector(1536). Recall will silently degrade to keyword "
                "search. Backfill embedding_v2 and set EMBEDDING_VERSION=v2."
            )
        if self.voyage_api_key and self.embedding_dimension not in {
            256,
            512,
            1024,
            2048,
        }:
            logger.warning(
                "EMBEDDING_DIMENSION=%s is invalid for Voyage v3-large "
                "(use 256, 512, 1024, or 2048). Embeddings will fall back until "
                "fixed.",
                self.embedding_dimension,
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
        # CORS '*' + allow_credentials=True is a CSRF surface waiting to be
        # mis-configured. Browsers reject the literal '*' + credentials combo
        # by spec, but `CORS_ALLOW_ORIGINS=https://attacker.com,...` lets
        # any listed origin through with credentials. Refuse to boot.
        if settings.cors_allow_origins.strip() == "*":
            raise ValueError(
                "CORS_ALLOW_ORIGINS='*' is not allowed in production mode "
                "because the app sends credentialed responses. Set "
                "CORS_ALLOW_ORIGINS to an explicit comma-separated origin list."
            )
        # No embedding credential resolves to the deterministic Fallback
        # embedder, so production silently serves keyword-only recall — the
        # opposite of the semantic-recall contract. This is a degradation, not
        # a data-corruption misconfig (recall still functions), so warn loudly
        # rather than refuse boot: the existing warn-on-degraded-stack path only
        # fires for a set-but-rejected key, never for all-keys-absent.
        if not (
            settings.gemini_api_key
            or settings.voyage_api_key
            or settings.openrouter_api_key
        ):
            logger.warning(
                "No embedding credential is configured in production "
                "(GEMINI_API_KEY / VOYAGE_API_KEY / OPENROUTER_API_KEY all "
                "unset): recall is degraded to keyword-only search. Set an "
                "embedding key to restore semantic recall."
            )
        # Embedding dimension must match the active column. The legacy
        # ``problems.embedding`` column is vector(1536) (per the init
        # migration) while ``problems.embedding_v2`` is vector(1024). When
        # ``EMBEDDING_VERSION=v1`` writes target the 1536-dim column;
        # Voyage v3-large outputs 1024 and pgvector rejects the dim
        # mismatch on commit. Refuse to boot in this exact configuration —
        # the operator must run ``backend/scripts/reembed_corpus.py`` and
        # flip ``EMBEDDING_VERSION=v2`` before going live with Voyage.
        if settings.voyage_api_key and settings.embedding_version == "v1":
            raise ValueError(
                "VOYAGE_API_KEY is set but EMBEDDING_VERSION='v1' (legacy "
                "1536-dim column). Voyage outputs 1024-dim vectors and "
                "writes will fail on commit. Run backend/scripts/"
                "reembed_corpus.py to backfill embedding_v2 then set "
                "EMBEDDING_VERSION=v2."
            )
        if settings.voyage_api_key and settings.embedding_dimension not in {
            256,
            512,
            1024,
            2048,
        }:
            raise ValueError(
                f"EMBEDDING_DIMENSION={settings.embedding_dimension} is invalid "
                "for Voyage v3-large (accepted: 256, 512, 1024, 2048). Set "
                "EMBEDDING_DIMENSION=1024 to match embedding_v2."
            )
        # Gemini emits ``output_dimensionality`` to whatever value we ask, so
        # the only hard constraint is that it equals the active column width
        # (v1=1536, v2=1024). A mismatch makes pgvector reject every commit;
        # refuse to boot rather than fail on the first write.
        if settings.gemini_api_key:
            expected_dim = 1024 if settings.embedding_version == "v2" else 1536
            if settings.embedding_dimension != expected_dim:
                raise ValueError(
                    "GEMINI_API_KEY is set but EMBEDDING_DIMENSION="
                    f"{settings.embedding_dimension} does not match the active "
                    f"EMBEDDING_VERSION={settings.embedding_version!r} column "
                    f"({expected_dim}-dim). Set EMBEDDING_DIMENSION={expected_dim} "
                    "(or flip EMBEDDING_VERSION) so Gemini output lines up with "
                    "the pgvector column."
                )


settings = Settings()
