from __future__ import annotations

import httpx

from backend.core.config import settings


class OpenRouterEmbeddingProvider:
    def __init__(self, api_key: str, model: str, timeout_seconds: float = 30.0) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds

    def embed(self, text: str, *, input_type: str = "query") -> list[float]:
        # OpenRouter / text-embedding-3-small is symmetric; ``input_type`` is
        # accepted for Protocol parity with VoyageEmbeddingProvider but has
        # no effect on the call.
        del input_type
        response = httpx.post(
            "https://openrouter.ai/api/v1/embeddings",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={"model": self._model, "input": text},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data", [])
        if not data:
            raise ValueError("Embedding response missing data")
        vector = data[0].get("embedding")
        if not isinstance(vector, list):
            raise ValueError("Embedding response format is invalid")
        return [float(value) for value in vector]


def resolve_embedding_provider() -> OpenRouterEmbeddingProvider | None:
    api_key = settings.openrouter_api_key
    if not api_key:
        return None
    return OpenRouterEmbeddingProvider(
        api_key=api_key,
        model=settings.openrouter_embedding_model,
    )
