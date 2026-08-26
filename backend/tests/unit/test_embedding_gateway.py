"""Verifies features/embedding-gateway.feature.

Embedding providers route through the Cloudflare AI Gateway (agentbook-gw)
when EMBEDDING_GATEWAY_BASE_URL is configured: provider paths, gateway auth
header, BYOK key relaxation — while direct mode stays byte-compatible with
the previous behavior.
"""

from __future__ import annotations

import httpx

from backend.core.config import settings
from backend.infrastructure.embeddings.gemini import GeminiEmbeddingProvider
from backend.infrastructure.embeddings.openrouter import OpenRouterEmbeddingProvider
from backend.infrastructure.embeddings.voyage import VoyageEmbeddingProvider

_GATEWAY = "https://gateway.ai.cloudflare.com/v1/acct/agentbook-gw"


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


# --- Voyage -------------------------------------------------------------------


def test_voyage_gateway_mode_posts_to_gateway_path_with_auth() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("cf-aig-authorization")
        seen["voyage_auth"] = request.headers.get("Authorization")
        return httpx.Response(
            200, json={"data": [{"embedding": [0.1, 0.2], "index": 0}]}
        )

    provider = VoyageEmbeddingProvider(
        api_key=None,
        model="voyage-3-large",
        base_url=f"{_GATEWAY}/custom-voyage",
        auth_token="cf-token-1",
        http_client=_mock_client(handler),
    )
    vector = provider.embed("probe")
    assert vector == [0.1, 0.2]
    assert seen["url"] == f"{_GATEWAY}/custom-voyage/v1/embeddings"
    assert seen["auth"] == "Bearer cf-token-1"
    assert seen["voyage_auth"] is None, "BYOK mode must not send a bare key"


# --- OpenRouter ---------------------------------------------------------------


def test_openrouter_gateway_mode_posts_to_gateway_path() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("cf-aig-authorization")
        return httpx.Response(200, json={"data": [{"embedding": [0.5]}]})

    provider = OpenRouterEmbeddingProvider(
        api_key=None,
        model="openai/text-embedding-3-small",
        base_url=f"{_GATEWAY}/custom-openrouter",
        auth_token="cf-token-1",
        http_client=_mock_client(handler),
    )
    assert provider.embed("probe") == [0.5]
    assert seen["url"] == f"{_GATEWAY}/custom-openrouter/api/v1/embeddings"
    assert seen["auth"] == "Bearer cf-token-1"
    assert "Authorization" not in provider._headers


# --- Gemini -------------------------------------------------------------------


def test_gemini_gateway_mode_sets_base_url_and_gateway_header(monkeypatch) -> None:
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"embeddings": [{"values": [0.3, 0.4]}]}

    def post(url, *, headers, json):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse()

    provider = GeminiEmbeddingProvider(
        api_keys=["gateway-byok"],
        gateway_base_url=_GATEWAY,
        gateway_auth_token="cf-token-1",
        gateway_http_client=type("Client", (), {"post": staticmethod(post)})(),
    )
    provider.embed("probe")

    assert captured["url"] == (
        f"{_GATEWAY}/google-ai-studio/v1beta/models/"
        "gemini-embedding-001:batchEmbedContents"
    )
    assert captured["headers"]["cf-aig-authorization"] == "Bearer cf-token-1"
    assert "Authorization" not in captured["headers"]
    assert "x-goog-api-key" not in captured["headers"]


def test_gemini_direct_mode_has_no_gateway_base(monkeypatch) -> None:
    captured: dict = {}

    class FakeHttpOptions:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        class models:  # noqa: N801
            @staticmethod
            def embed_content(model, contents, config):
                class Emb:
                    values = [1.0]

                class Result:
                    embeddings = [Emb()]

                return Result()

    import backend.infrastructure.embeddings.gemini as gemini_module

    monkeypatch.setattr(gemini_module.genai, "Client", FakeClient)
    monkeypatch.setattr(gemini_module.types, "HttpOptions", FakeHttpOptions)

    provider = GeminiEmbeddingProvider(api_keys=["real-key"])
    provider.embed("probe")
    assert "base_url" not in captured


# --- Resolver relaxation (BYOK without per-provider keys) ----------------------


def test_resolvers_relax_key_requirement_in_gateway_mode(monkeypatch) -> None:
    monkeypatch.setattr(
        settings,
        "ai_gateway_base_url",
        _GATEWAY,
    )
    monkeypatch.setattr(settings, "ai_gateway_auth_token", "cf-token-1")
    monkeypatch.setattr(settings, "voyage_api_key", None)
    monkeypatch.setattr(settings, "gemini_api_key", None)

    from backend.infrastructure.embeddings.gemini import (
        resolve_embedding_provider as resolve_gemini,
    )
    from backend.infrastructure.embeddings.openrouter import (
        resolve_embedding_provider as resolve_openrouter,
    )
    from backend.infrastructure.embeddings.voyage import (
        resolve_embedding_provider as resolve_voyage,
    )

    voyage = resolve_voyage()
    assert isinstance(voyage, VoyageEmbeddingProvider)

    gemini = resolve_gemini()
    assert isinstance(gemini, GeminiEmbeddingProvider)

    openrouter = resolve_openrouter()
    assert isinstance(openrouter, OpenRouterEmbeddingProvider)


def test_default_settings_keep_direct_mode() -> None:
    assert settings.ai_gateway_base_url is None
