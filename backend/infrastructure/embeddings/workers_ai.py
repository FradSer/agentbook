"""Cloudflare Workers AI embedding provider through AI Gateway."""

from __future__ import annotations

import httpx

from backend.core.config import settings

_DEFAULT_MODEL = "@cf/baai/bge-large-en-v1.5"
_DEFAULT_TIMEOUT_SECONDS = 5.0


class WorkersAIEmbeddingProvider:
    """Use a Cloudflare-hosted embedding model via the Gateway compat API."""

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        *,
        base_url: str,
        auth_token: str,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not auth_token:
            raise ValueError("gateway auth token is required")
        self._model = model
        self._url = base_url.rstrip("/") + "/compat/embeddings"
        self._headers = {
            "cf-aig-authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }
        self._timeout_seconds = timeout_seconds
        self._http = http_client or httpx.Client(timeout=timeout_seconds)

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = self._http.post(
            self._url,
            headers=self._headers,
            json={"model": f"workers-ai/{self._model}", "input": texts},
        )
        response.raise_for_status()
        data = response.json().get("data") or []
        if len(data) != len(texts):
            raise ValueError("Workers AI Gateway response missing embeddings")
        vectors = [item.get("embedding") for item in data]
        if not all(isinstance(vector, list) for vector in vectors):
            raise ValueError("Workers AI Gateway response format is invalid")
        return [[float(value) for value in vector] for vector in vectors]

    def embed(self, text: str, *, input_type: str = "query") -> list[float]:
        del input_type
        return self._embed_batch([text])[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._embed_batch(texts)


def resolve_embedding_provider() -> WorkersAIEmbeddingProvider | None:
    if not settings.ai_gateway_base_url or not settings.ai_gateway_auth_token:
        return None
    return WorkersAIEmbeddingProvider(
        model=settings.workers_ai_embedding_model,
        base_url=settings.ai_gateway_base_url,
        auth_token=settings.ai_gateway_auth_token,
    )
