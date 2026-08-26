"""Google Gemini embedding provider.

``gemini-embedding-001`` is the default embedder for the search stack. Its
native dimension is 3072 but Matryoshka Representation Learning lets it emit
reduced sizes; agentbook uses ``output_dimensionality=1024`` to line up with
the ``problems.embedding_v2`` column. Gemini only L2-normalizes the *full*
3072-dim output — reduced dims come back un-normalized, so this provider
normalizes client-side, otherwise cosine similarity against the indexed
corpus would be skewed.

Asymmetric like Voyage: ``"query"`` -> ``RETRIEVAL_QUERY`` for live search,
``"document"`` -> ``RETRIEVAL_DOCUMENT`` for indexing. Multiple API keys
(comma-separated ``GEMINI_API_KEY``) rotate round-robin per call.

Lazy import: when ``google-genai`` is missing the resolver returns ``None`` and
the search stack falls through to Voyage / OpenRouter / Fallback — mirroring
``backend.infrastructure.embeddings.voyage``.
"""

from __future__ import annotations

import logging
import math

import httpx

from backend.core.config import settings
from shared.provider_keys import RoundRobin, parse_keys

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised only when google-genai is installed
    from google import genai
    from google.genai import types
except Exception:  # noqa: BLE001 - any import failure disables the provider
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]

# gemini-embedding-001 only normalizes its native 3072-dim output; any reduced
# Matryoshka size must be L2-normalized client-side for cosine search.
_FULL_DIMENSION = 3072
# Live request timeout mirrors Voyage's 2s fast-fail: a hung provider aborts
# here and the caller's ``_safe_embed`` degrades to keyword fallback rather
# than blocking the recall thread.
_LIVE_TIMEOUT_MS = 2000
# Offline backfill (``reembed_corpus.py``) tolerates a longer wait.
_BATCH_TIMEOUT_MS = 30000
# gemini-embedding-001 accepts up to 100 inputs per request.
_MAX_BATCH = 100
_TASK_TYPES = {"query": "RETRIEVAL_QUERY", "document": "RETRIEVAL_DOCUMENT"}


def _l2_normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in values))
    if norm == 0.0:
        return values
    return [v / norm for v in values]


class GeminiEmbeddingProvider:
    """gemini-embedding-001 embedder with asymmetric input types and key rotation."""

    def __init__(
        self,
        api_keys: list[str],
        model: str = "gemini-embedding-001",
        output_dimension: int = 1024,
        *,
        gateway_base_url: str | None = None,
        gateway_auth_token: str | None = None,
        gateway_http_client: httpx.Client | None = None,
    ) -> None:
        if gateway_base_url and not gateway_auth_token:
            raise ValueError("gateway auth token is required in gateway mode")
        if genai is None and not gateway_base_url:
            raise RuntimeError(
                "google-genai package is not installed. Run `uv add google-genai` "
                "before constructing GeminiEmbeddingProvider."
            )
        if not api_keys:
            raise ValueError("GeminiEmbeddingProvider requires at least one API key")
        self._rotator = RoundRobin(api_keys)
        self._model = model
        self._output_dimension = output_dimension
        # AI Gateway routing: base_url points the SDK at agentbook-gw's
        # google-ai-studio passthrough; the gateway auth header travels with
        # every call. In BYOK mode the api_key itself is a placeholder.
        self._gateway_base_url = gateway_base_url
        self._gateway_auth_token = gateway_auth_token
        self._gateway_http = gateway_http_client
        self._gateway_headers: dict[str, str] = (
            {"cf-aig-authorization": f"Bearer {gateway_auth_token}"}
            if gateway_auth_token
            else {}
        )
        self._clients: dict[str, genai.Client] = {}

    def _client(self, api_key: str) -> genai.Client:
        client = self._clients.get(api_key)
        if client is None:
            client = genai.Client(api_key=api_key)
            self._clients[api_key] = client
        return client

    def _normalize(self, values: list[float]) -> list[float]:
        if self._output_dimension != _FULL_DIMENSION:
            return _l2_normalize(list(values))
        return list(values)

    def _embed_gateway(
        self, contents: list[str], task_type: str, timeout_ms: int
    ) -> list[list[float]]:
        """Call Google AI Studio through Gateway's native REST endpoint.

        The SDK is intentionally bypassed in Gateway mode: it would attach
        ``x-goog-api-key`` from its constructor. BYOK requires the application
        to send only ``cf-aig-authorization`` and let Gateway inject the
        provider credential from Secrets Store.
        """
        url = (
            self._gateway_base_url.rstrip("/")
            + f"/google-ai-studio/v1beta/models/{self._model}:batchEmbedContents"
        )
        body = {
            "requests": [
                {
                    "model": f"models/{self._model}",
                    "content": {"parts": [{"text": content}]},
                    "taskType": task_type,
                    "outputDimensionality": self._output_dimension,
                }
                for content in contents
            ]
        }
        headers = self._gateway_headers | {"Content-Type": "application/json"}
        if self._gateway_http is not None:
            response = self._gateway_http.post(url, headers=headers, json=body)
        else:
            response = httpx.post(
                url, headers=headers, json=body, timeout=timeout_ms / 1000
            )
        response.raise_for_status()
        payload = response.json()
        embeddings = payload.get("embeddings") or []
        if len(embeddings) != len(contents):
            raise ValueError("Gemini gateway response missing embeddings")
        vectors = []
        for embedding in embeddings:
            values = embedding.get("values") if isinstance(embedding, dict) else None
            if not isinstance(values, list):
                raise ValueError("Gemini gateway response format is invalid")
            vectors.append(self._normalize(values))
        return vectors

    def _embed(
        self, contents: list[str], task_type: str, timeout_ms: int
    ) -> list[list[float]]:
        if self._gateway_base_url:
            return self._embed_gateway(contents, task_type, timeout_ms)
        client = self._client(self._rotator.next())
        result = client.models.embed_content(
            model=self._model,
            contents=contents,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=self._output_dimension,
                http_options=types.HttpOptions(timeout=timeout_ms),
            ),
        )
        return [self._normalize(emb.values) for emb in result.embeddings]

    def embed(self, text: str, *, input_type: str = "query") -> list[float]:
        task_type = _TASK_TYPES.get(input_type)
        if task_type is None:
            raise ValueError(
                f"input_type must be 'query' or 'document', got {input_type!r}"
            )
        return self._embed([text], task_type, _LIVE_TIMEOUT_MS)[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Batch path used by ``backend/scripts/reembed_corpus.py``."""
        if not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _MAX_BATCH):
            chunk = texts[start : start + _MAX_BATCH]
            vectors.extend(self._embed(chunk, "RETRIEVAL_DOCUMENT", _BATCH_TIMEOUT_MS))
        return vectors


def resolve_embedding_provider() -> GeminiEmbeddingProvider | None:
    """Build a Gemini provider when the SDK is installed and a key is set.

    Returns ``None`` to let the resolver chain fall through to Voyage /
    OpenRouter / Fallback when either prerequisite is missing.
    """
    gateway_base = settings.ai_gateway_base_url
    if gateway_base:
        if not settings.ai_gateway_auth_token:
            raise ValueError("embedding gateway auth token is required")
        # Gateway BYOK mode uses the native REST path and does not require the
        # google-genai SDK or a raw Gemini key in this process.
        keys = ["gateway-byok"]
    else:
        if genai is None:
            return None
        keys = parse_keys(settings.gemini_api_key)
        if not keys:
            return None
    return GeminiEmbeddingProvider(
        api_keys=keys,
        model=settings.gemini_embedding_model,
        output_dimension=settings.embedding_dimension,
        gateway_base_url=gateway_base,
        gateway_auth_token=settings.ai_gateway_auth_token,
    )
