"""LLM routing for ReviewerAgent and ResearcherAgent."""

from __future__ import annotations

import logging
from collections.abc import Sequence

import httpx
from agno.models.openai.like import OpenAILike

from agent.src.config import settings

logger = logging.getLogger(__name__)

NVIDIA_DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"

# Cloudflare AI Gateway compat rejects some OpenRouter-style provider slugs.
_CF_BLOCKED_PREFIXES: Sequence[str] = ("minimax/",)

_VOYAGE_OUTPUT_DIMENSIONS = frozenset({256, 512, 1024, 2048})

_NVIDIA_EXTRA_BODY = {"chat_template_kwargs": {"thinking": False}}


class _StripAuthAsyncTransport(httpx.AsyncHTTPTransport):
    """Drop Authorization so CF Gateway does not forward it upstream."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        request.headers.pop("authorization", None)
        return await super().handle_async_request(request)


def _normalized_provider() -> str:
    return (settings.agent_llm_provider or "auto").strip().lower()


def nvidia_configured() -> bool:
    return bool(settings.nvidia_api_key)


def cf_gateway_configured() -> bool:
    return bool(settings.cf_aig_url and settings.cf_aig_token)


def active_llm_provider() -> str:
    """Resolved provider after ``auto`` selection."""
    provider = _normalized_provider()
    if provider != "auto":
        return provider
    if nvidia_configured():
        return "nvidia"
    if cf_gateway_configured():
        return "cf_aig"
    return "openrouter"


def llm_api_key_configured() -> bool:
    """Whether credentials exist for the active provider."""
    provider = active_llm_provider()
    if provider == "nvidia":
        return nvidia_configured()
    if provider == "cf_aig":
        return cf_gateway_configured()
    return bool(settings.openrouter_api_key)


def resolve_model_id(*, researcher: bool = False) -> str:
    """Pick a model id, falling back when CF Gateway cannot route the researcher model."""
    if researcher:
        preferred = settings.agent_researcher_model_name or settings.agent_model_name
    else:
        preferred = settings.agent_model_name

    if active_llm_provider() == "cf_aig" and any(
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


def build_agent_model(*, researcher: bool = False) -> OpenAILike:
    model_id = resolve_model_id(researcher=researcher)
    provider = active_llm_provider()

    if provider == "nvidia":
        if not nvidia_configured():
            raise ValueError("AGENT_LLM_PROVIDER=nvidia but NVIDIA_API_KEY is not set")
        base_url = settings.nvidia_base_url or NVIDIA_DEFAULT_BASE_URL
        return OpenAILike(
            id=model_id,
            api_key=settings.nvidia_api_key,
            base_url=base_url,
            extra_body=_NVIDIA_EXTRA_BODY,
        )

    if provider == "cf_aig":
        if not cf_gateway_configured():
            raise ValueError(
                "AGENT_LLM_PROVIDER=cf_aig but CF_AIG_URL / CF_AIG_TOKEN are not set"
            )
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

    if not settings.openrouter_api_key:
        raise ValueError(
            "OPENROUTER_API_KEY must be set when using OpenRouter "
            "(AGENT_LLM_PROVIDER=openrouter or auto without NVIDIA/CF credentials)"
        )
    from agno.models.openrouter import OpenRouter

    return OpenRouter(id=model_id, api_key=settings.openrouter_api_key)


def voyage_output_dimension_valid(dimension: int) -> bool:
    return dimension in _VOYAGE_OUTPUT_DIMENSIONS
