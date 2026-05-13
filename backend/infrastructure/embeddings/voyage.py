"""Voyage AI embedding provider.

``voyage-3-large`` is the engineering-text tuned model recommended by the
PR2 plan. It outperforms ``openai/text-embedding-3-large`` by ~9.7% on MTEB
averaged and matches/edges out ``voyage-code-3`` on agentbook's mixed
"engineering text with code embedded" corpus. Output dimension defaults to
1024 via Voyage's native ``output_dimension`` Matryoshka API (re-normalized
server-side, not client-side truncated).

Asymmetric encoders require the right ``input_type`` pole at every call:
``"query"`` for live search, ``"document"`` for indexing. The Protocol on
``backend.domain.services.EmbeddingProvider`` carries the kwarg uniformly so
the OpenRouter and Fallback providers stay swap-compatible.

Lazy import: when the ``voyageai`` package is missing the resolver returns
``None`` and the chain falls through to OpenRouter / Fallback. This mirrors
``backend.infrastructure.persistence.sqlalchemy_models``'s pgvector lazy
import and lets local dev / CI run without the SDK installed.
"""

from __future__ import annotations

import logging
import time

from backend.core.config import settings

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised only when voyageai is installed
    import voyageai
except Exception:  # noqa: BLE001 - any import failure should disable the provider
    voyageai = None  # type: ignore[assignment]


# Voyage rate limit on embed endpoint is 2000 RPM (paid). 429 is exceptional;
# retry with jitter-free exponential backoff up to a small attempt cap so that
# legitimate transient failures do not crash the request.
_RETRY_DELAYS_SECONDS = (1.0, 2.0, 4.0)


class VoyageEmbeddingProvider:
    """Voyage v3-large embedder with asymmetric input types and batch support."""

    def __init__(
        self,
        api_key: str,
        model: str = "voyage-3-large",
        output_dimension: int = 1024,
    ) -> None:
        if voyageai is None:
            raise RuntimeError(
                "voyageai package is not installed. Run `uv add voyageai` "
                "before constructing VoyageEmbeddingProvider."
            )
        self._client = voyageai.Client(api_key=api_key)
        self._model = model
        self._output_dimension = output_dimension

    def embed(self, text: str, *, input_type: str = "query") -> list[float]:
        """Embed a single text. ``input_type`` must be ``"query"`` or
        ``"document"``."""
        if input_type not in {"query", "document"}:
            raise ValueError(
                f"input_type must be 'query' or 'document', got {input_type!r}"
            )
        vectors = self._embed_batch_with_retry([text], input_type)
        return vectors[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Native batch path used by ``backend/scripts/reembed_corpus.py``.

        Voyage accepts up to 1000 inputs per call; the backfill script
        invokes this with batches of 128 to keep memory tame on Railway."""
        if not texts:
            return []
        return self._embed_batch_with_retry(texts, "document")

    def _embed_batch_with_retry(
        self, texts: list[str], input_type: str
    ) -> list[list[float]]:
        last_exc: Exception | None = None
        for attempt, delay in enumerate(_RETRY_DELAYS_SECONDS):
            try:
                response = self._client.embed(
                    texts=texts,
                    model=self._model,
                    input_type=input_type,
                    output_dimension=self._output_dimension,
                )
            except Exception as exc:  # noqa: BLE001 - retry any transient error
                last_exc = exc
                if attempt == len(_RETRY_DELAYS_SECONDS) - 1:
                    break
                logger.warning(
                    "voyage-embed-retry attempt=%d delay=%.1fs error=%s",
                    attempt,
                    delay,
                    exc,
                )
                time.sleep(delay)
                continue
            return [list(vector) for vector in response.embeddings]
        # Exhausted retries — re-raise so the caller's ``_safe_embed`` can
        # downgrade to the keyword fallback path.
        assert last_exc is not None
        raise last_exc


def resolve_embedding_provider() -> VoyageEmbeddingProvider | None:
    """Build a Voyage provider when the SDK is installed and the key is set.

    Returns ``None`` to let the resolver chain fall through to OpenRouter /
    Fallback when either prerequisite is missing. The composition root in
    ``backend/main.py`` calls this first; on ``None`` it falls back to
    ``backend/infrastructure/embeddings/openrouter.py``."""
    if voyageai is None:
        return None
    api_key = settings.voyage_api_key
    if not api_key:
        return None
    return VoyageEmbeddingProvider(
        api_key=api_key,
        model=settings.voyage_embedding_model,
        output_dimension=settings.embedding_dimension,
    )
