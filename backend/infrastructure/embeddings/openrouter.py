"""OpenRouter embedding provider.

Direct mode preserves the existing OpenRouter HTTP contract. Gateway mode
uses the account's ``custom-openrouter`` provider route and sends only the
Cloudflare Gateway authorization header; the upstream OpenRouter credential
is injected by AI Gateway BYOK.
"""

from __future__ import annotations

import httpx

from backend.core.config import settings

_DIRECT_BASE_URL = "https://openrouter.ai"


class OpenRouterEmbeddingProvider:
    def __init__(
        self,
        api_key: str | None,
        model: str,
        timeout_seconds: float = 30.0,
        *,
        base_url: str | None = None,
        auth_token: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._gateway_mode = base_url is not None
        if self._gateway_mode:
            if not auth_token:
                raise ValueError("gateway auth token is required in gateway mode")
            self._url = base_url.rstrip("/") + "/api/v1/embeddings"
            self._headers = {"cf-aig-authorization": f"Bearer {auth_token}"}
        else:
            if not api_key:
                raise ValueError("OpenRouterEmbeddingProvider requires an API key")
            self._url = _DIRECT_BASE_URL + "/api/v1/embeddings"
            self._headers = {"Authorization": f"Bearer {api_key}"}
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._http = http_client

    def embed(self, text: str, *, input_type: str = "query") -> list[float]:
        # OpenRouter / text-embedding-3-small is symmetric; ``input_type`` is
        # accepted for Protocol parity with VoyageEmbeddingProvider but has
        # no effect on the call.
        del input_type
        headers = self._headers | {"Content-Type": "application/json"}
        if self._gateway_mode:
            client = self._http or httpx.Client(timeout=self._timeout_seconds)
            response = client.post(
                self._url,
                headers=headers,
                json={"model": self._model, "input": text},
            )
        else:
            response = httpx.post(
                self._url,
                headers=headers,
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
    gateway_base = settings.ai_gateway_base_url
    if gateway_base:
        # BYOK: never copy a provider credential into the API process. The
        # gateway's custom-openrouter config injects it at request time.
        return OpenRouterEmbeddingProvider(
            api_key=None,
            model=settings.openrouter_embedding_model,
            base_url=gateway_base.rstrip("/")
            + "/"
            + settings.ai_gateway_openrouter_slug,
            auth_token=settings.ai_gateway_auth_token,
        )
    api_key = settings.openrouter_api_key
    if not api_key:
        return None
    return OpenRouterEmbeddingProvider(
        api_key=api_key,
        model=settings.openrouter_embedding_model,
    )
