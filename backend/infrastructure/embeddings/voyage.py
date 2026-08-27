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

Transport: Gateway-only in production. Local direct SDK compatibility is
retained for development tests; production resolution never uses a provider
key.

Retry policy mirrors the original SDK behavior: the offline backfill path
(``embed_documents``) keeps a small exponential budget; the live request path
carries none — a hung provider aborts fast and the caller's ``_safe_embed``
degrades to keyword fallback.
"""

from __future__ import annotations

import logging
import time

import httpx

from backend.core.config import settings

try:  # pragma: no cover - exercised only when voyageai is installed
    import voyageai
except Exception:  # noqa: BLE001 - any import failure should disable the SDK path
    voyageai = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_DIRECT_BASE_URL = "https://api.voyageai.com"

# Voyage rate limit on embed endpoint is 2000 RPM (paid). 429 is exceptional;
# retry with jitter-free exponential backoff up to a small attempt cap so that
# legitimate transient failures do not crash the request. This budget is used
# only on the offline ``embed_documents`` backfill path, never on a live
# request.
_RETRY_DELAYS_SECONDS = (1.0, 2.0, 4.0)
# Live request path (``embed``): no blocking retry sleeps. Recall is an agent's
# near-free first move, so an unresponsive provider must abort fast and let the
# caller's ``_safe_embed`` degrade to keyword fallback rather than block the
# request thread through a 1s + 2s + 4s storm.
_LIVE_RETRY_DELAYS_SECONDS: tuple[float, ...] = ()
# Tight per-request client timeout so a hung connection aborts here instead of
# hanging the recall.
_LIVE_QUERY_TIMEOUT_SECONDS = 2.0
_BATCH_TIMEOUT_SECONDS = 30.0


class VoyageEmbeddingProvider:
    """Voyage v3-large embedder with asymmetric input types and batch support."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "voyage-3-large",
        output_dimension: int = 1024,
        *,
        base_url: str | None = None,
        auth_token: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._gateway_mode = base_url is not None
        self._url = (base_url or _DIRECT_BASE_URL).rstrip("/") + "/v1/embeddings"
        headers: dict[str, str] = {}
        if self._gateway_mode:
            if not auth_token:
                raise ValueError("gateway auth token is required in gateway mode")
            headers["cf-aig-authorization"] = f"Bearer {auth_token}"
        elif api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._headers = headers
        self._model = model
        self._output_dimension = output_dimension
        self._http = (
            (http_client or httpx.Client(timeout=_LIVE_QUERY_TIMEOUT_SECONDS))
            if self._gateway_mode
            else None
        )
        self._batch_http: httpx.Client | None = None
        if not self._gateway_mode:
            if voyageai is None:
                raise RuntimeError(
                    "voyageai package is not installed. Run `uv add voyageai` "
                    "before constructing VoyageEmbeddingProvider."
                )
            if not api_key:
                raise ValueError("VoyageEmbeddingProvider requires an API key")
            self._client = voyageai.Client(
                api_key=api_key,
                timeout=_LIVE_QUERY_TIMEOUT_SECONDS,
                max_retries=0,
            )

    def embed(self, text: str, *, input_type: str = "query") -> list[float]:
        """Embed a single text on the live request path.

        ``input_type`` must be ``"query"`` or ``"document"``. This path carries
        an empty retry budget (``_LIVE_RETRY_DELAYS_SECONDS``): the bounded
        client timeout aborts a hung call and the caller's ``_safe_embed``
        degrades to keyword fallback, so recall never blocks on a synchronous
        retry storm."""
        if input_type not in {"query", "document"}:
            raise ValueError(
                f"input_type must be 'query' or 'document', got {input_type!r}"
            )
        vectors = self._embed_batch_with_retry(
            [text], input_type, retry_delays=_LIVE_RETRY_DELAYS_SECONDS
        )
        return vectors[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Native batch path used by ``backend/scripts/reembed_corpus.py``.

        Voyage accepts up to 1000 inputs per call; the backfill script
        invokes this with batches of 128 to keep memory tame on Railway. This
        offline path retains the full ``_RETRY_DELAYS_SECONDS`` budget — it is
        not on a live request thread, so a transient 429 is worth waiting out."""
        if not texts:
            return []
        return self._embed_batch_with_retry(
            texts, "document", retry_delays=_RETRY_DELAYS_SECONDS
        )

    def _post(
        self, payload: dict, *, client: httpx.Client | None = None
    ) -> list[list[float]]:
        response = (client or self._http).post(
            self._url, json=payload, headers=self._headers
        )
        response.raise_for_status()
        data = response.json().get("data") or []
        if not data:
            raise ValueError("Voyage embedding response missing data")
        vectors = []
        for item in data:
            embedding = item.get("embedding")
            if not isinstance(embedding, list):
                raise ValueError("Voyage embedding response format is invalid")
            vectors.append([float(value) for value in embedding])
        return vectors

    def _embed_batch_with_retry(
        self,
        texts: list[str],
        input_type: str,
        *,
        retry_delays: tuple[float, ...] = _RETRY_DELAYS_SECONDS,
    ) -> list[list[float]]:
        # ``retry_delays`` is the blocking sleep *before each retry*; the final
        # attempt breaks without sleeping (matching the prior backfill cost of
        # 3 attempts / 2 sleeps). An empty tuple means a single attempt with no
        # sleep — the live request path.
        if retry_delays and self._batch_http is None:
            self._batch_http = httpx.Client(timeout=_BATCH_TIMEOUT_SECONDS)
        client = self._batch_http or self._http
        attempts = max(len(retry_delays), 1)
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                if not self._gateway_mode:
                    response = self._client.embed(
                        texts=texts,
                        model=self._model,
                        input_type=input_type,
                        output_dimension=self._output_dimension,
                    )
                    vectors = [list(vector) for vector in response.embeddings]
                else:
                    vectors = self._post(
                        {
                            "model": self._model,
                            "input": texts,
                            "input_type": input_type,
                            "output_dimension": self._output_dimension,
                        },
                        client=client,
                    )
            except Exception as exc:  # noqa: BLE001 - retry any transient error
                last_exc = exc
                if attempt >= attempts - 1:
                    break
                delay = retry_delays[attempt]
                logger.warning(
                    "voyage-embed-retry attempt=%d delay=%.1fs error=%s",
                    attempt,
                    delay,
                    exc,
                )
                time.sleep(delay)
                continue
            return vectors
        # Exhausted retries — re-raise so the caller's ``_safe_embed`` can
        # downgrade to the keyword fallback path.
        assert last_exc is not None
        raise last_exc


def resolve_embedding_provider() -> VoyageEmbeddingProvider | None:
    """Build a Gateway Voyage embedder or a local direct provider."""
    if settings.ai_gateway_base_url:
        if not settings.ai_gateway_auth_token:
            return None
        provider_base = (
            settings.ai_gateway_base_url.rstrip("/")
            + "/"
            + settings.ai_gateway_voyage_slug
        )
        return VoyageEmbeddingProvider(
            api_key=None,
            model=settings.voyage_embedding_model,
            output_dimension=settings.embedding_dimension,
            base_url=provider_base,
            auth_token=settings.ai_gateway_auth_token,
        )
    api_key = settings.voyage_api_key
    if voyageai is None or not api_key:
        return None
    return VoyageEmbeddingProvider(
        api_key=api_key,
        model=settings.voyage_embedding_model,
        output_dimension=settings.embedding_dimension,
    )
