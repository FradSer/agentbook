"""Cloudflare Workers AI embedding provider through the AI Gateway REST API."""

from __future__ import annotations

import httpx

from backend.core.config import settings

_DEFAULT_MODEL = "@cf/baai/bge-m3"
_DEFAULT_TIMEOUT_SECONDS = 5.0


class WorkersAIEmbeddingProvider:
    """Generate 1024-dimensional embeddings with a Cloudflare-hosted model."""

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        *,
        account_id: str | None = None,
        auth_token: str,
        gateway_id: str = "agentbook-gw",
        base_url: str | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not auth_token or not gateway_id:
            raise ValueError("Cloudflare AI Gateway credentials are required")
        if base_url:
            parts = base_url.rstrip("/").split("/")
            account_id = account_id or (parts[-2] if len(parts) >= 2 else "")
        if not account_id:
            raise ValueError("Cloudflare account id is required")
        self._url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run"
        self._model = model
        self._headers = {
            "Authorization": f"Bearer {auth_token}",
            "cf-aig-gateway-id": gateway_id,
            "Content-Type": "application/json",
        }
        self._http = http_client or httpx.Client(timeout=timeout_seconds)

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = self._http.post(
            self._url,
            headers=self._headers,
            json={
                "model": self._model,
                "input": {"text": texts},
            },
        )
        response.raise_for_status()
        payload = response.json()
        result = payload.get("result") or {}
        data = result.get("data") or []
        if len(data) != len(texts):
            raise ValueError("Workers AI Gateway response missing embeddings")
        if not all(isinstance(vector, list) for vector in data):
            raise ValueError("Workers AI Gateway response format is invalid")
        return [[float(value) for value in vector] for vector in data]

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
    parts = settings.ai_gateway_base_url.rstrip("/").split("/")
    if len(parts) < 2:
        return None
    account_id = parts[-2]
    return WorkersAIEmbeddingProvider(
        model=settings.workers_ai_embedding_model,
        account_id=account_id,
        auth_token=settings.ai_gateway_auth_token,
        gateway_id=settings.ai_gateway_id,
        base_url=settings.ai_gateway_base_url,
    )
