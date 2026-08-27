"""Gateway routing contracts for production embedding providers."""

from __future__ import annotations

import httpx

from backend.core.config import settings
from backend.infrastructure.embeddings.workers_ai import WorkersAIEmbeddingProvider

_GATEWAY = "https://gateway.ai.cloudflare.com/v1/acct/agentbook-gw"


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_workers_ai_gateway_mode_returns_embedding() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["gateway_id"] = request.headers.get("cf-aig-gateway-id")
        seen["provider_auth"] = request.headers.get("x-provider-key")
        return httpx.Response(
            200,
            json={"result": {"data": [[0.1, 0.2]]}},
        )

    provider = WorkersAIEmbeddingProvider(
        base_url=_GATEWAY,
        account_id="acct",
        gateway_id="agentbook-gw",
        auth_token="cf-token-1",
        http_client=_mock_client(handler),
    )
    assert provider.embed("probe") == [0.1, 0.2]
    assert seen["url"] == "https://api.cloudflare.com/client/v4/accounts/acct/ai/run"
    assert seen["auth"] == "Bearer cf-token-1"
    assert seen["gateway_id"] == "agentbook-gw"
    assert seen["provider_auth"] is None


def test_workers_ai_gateway_mode_posts_to_rest_embeddings() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["gateway_id"] = request.headers.get("cf-aig-gateway-id")
        seen["provider_auth"] = request.headers.get("x-provider-key")
        seen["body"] = request.read()
        return httpx.Response(200, json={"result": {"data": [[0.5]]}})

    provider = WorkersAIEmbeddingProvider(
        base_url=_GATEWAY,
        auth_token="cf-token-1",
        http_client=_mock_client(handler),
    )
    assert provider.embed("probe") == [0.5]
    assert seen["url"] == "https://api.cloudflare.com/client/v4/accounts/acct/ai/run"
    assert seen["auth"] == "Bearer cf-token-1"
    assert seen["gateway_id"] == "agentbook-gw"
    assert seen["provider_auth"] is None
    assert b"@cf/baai/bge-large-en-v1.5" in seen["body"]


def test_workers_ai_resolver_uses_gateway_without_provider_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_gateway_base_url", _GATEWAY)
    monkeypatch.setattr(settings, "ai_gateway_auth_token", "cf-token-1")
    monkeypatch.setattr(
        settings, "workers_ai_embedding_model", "@cf/baai/bge-large-en-v1.5"
    )

    from backend.infrastructure.embeddings.workers_ai import (
        resolve_embedding_provider,
    )

    provider = resolve_embedding_provider()
    assert isinstance(provider, WorkersAIEmbeddingProvider)


def test_default_settings_keep_direct_mode() -> None:
    assert settings.ai_gateway_base_url is None
