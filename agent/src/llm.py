"""LLM routing for ReviewerAgent and ResearcherAgent."""

from __future__ import annotations

import logging
from collections.abc import Sequence

import httpx
from agno.models.openai.like import OpenAILike

from agent.src.config import settings

logger = logging.getLogger(__name__)

# Cloudflare AI Gateway compat rejects some OpenRouter-style provider slugs.
_CF_BLOCKED_PREFIXES: Sequence[str] = ("minimax/",)

_VOYAGE_OUTPUT_DIMENSIONS = frozenset({256, 512, 1024, 2048})


class _StripAuthAsyncTransport(httpx.AsyncHTTPTransport):
    """Drop Authorization so CF Gateway does not forward it upstream."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        request.headers.pop("authorization", None)
        return await super().handle_async_request(request)


def cf_gateway_configured() -> bool:
    return bool(settings.cf_aig_url and settings.cf_aig_token)


def resolve_model_id(*, researcher: bool = False) -> str:
    """Pick a model id, falling back when CF Gateway cannot route the researcher model."""
    if researcher:
        preferred = settings.agent_researcher_model_name or settings.agent_model_name
    else:
        preferred = settings.agent_model_name

    if _use_cf_gateway() and any(
        preferred.startswith(prefix) for prefix in _CF_BLOCKED_PREFIXES
    ):
        fallback = settings.agent_model_name
        if preferred != fallback:
            logger.warning(
                "Model %s is not routed via Cloudflare AI Gateway; using %s",
                preferred,
                fallback,
            )
        return fallback
    return preferred


def _use_cf_gateway() -> bool:
    provider = (settings.agent_llm_provider or "auto").strip().lower()
    if provider == "openrouter":
        return False
    if provider == "cf_aig":
        return cf_gateway_configured()
    return cf_gateway_configured()


def build_agent_model(*, researcher: bool = False) -> OpenAILike:
    model_id = resolve_model_id(researcher=researcher)
    if _use_cf_gateway():
        async_client = httpx.AsyncClient(transport=_StripAuthAsyncTransport())
        return OpenAILike(
            id=model_id,
            base_url=settings.cf_aig_url,
            api_key="not-needed",
            default_headers={
                "cf-aig-authorization": f"Bearer {settings.cf_aig_token}",
            },
            http_client=async_client,
        )
    from agno.models.openrouter import OpenRouter

    return OpenRouter(id=model_id, api_key=settings.openrouter_api_key)


def voyage_output_dimension_valid(dimension: int) -> bool:
    return dimension in _VOYAGE_OUTPUT_DIMENSIONS
