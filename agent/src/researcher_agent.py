from __future__ import annotations

from pathlib import Path

import httpx
from agno.agent import Agent
from agno.models.openai.like import OpenAILike

from agent.src.config import settings


class _StripAuthAsyncTransport(httpx.AsyncHTTPTransport):
    """Remove Authorization header so CF Gateway doesn't forward it to the upstream provider."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        request.headers.pop("authorization", None)
        return await super().handle_async_request(request)


def _researcher_model_id() -> str:
    return settings.agent_researcher_model_name or settings.agent_model_name


def _build_model() -> OpenAILike:
    model_id = _researcher_model_id()
    if settings.cf_aig_url and settings.cf_aig_token:
        async_client = httpx.AsyncClient(transport=_StripAuthAsyncTransport())
        return OpenAILike(
            id=model_id,
            base_url=settings.cf_aig_url,
            api_key="not-needed",
            default_headers={"cf-aig-authorization": f"Bearer {settings.cf_aig_token}"},
            http_client=async_client,
        )
    from agno.models.openrouter import OpenRouter

    return OpenRouter(id=model_id, api_key=settings.openrouter_api_key)


# Fallback constant used when program.md is missing
_RESEARCHER_INSTRUCTIONS_FALLBACK = """
You are the ResearcherAgent for Agentbook — an autonomous hill-climbing loop that improves solutions.

## Loop semantics (karpathy/autoresearch pattern)
Each call is one iteration: read context → propose modification → measure → keep or discard.
The metric is `confidence` (outcome-driven Bayesian score, 0.0–1.0).
You ONLY keep a proposal when it strictly increases confidence.

## Your two tools

1. `propose_improvement(solution_id, improved_content, reasoning, steps)` — submit a candidate.
   The system will run hill-climbing: accepted only if confidence strictly improves.

2. `skip_improvement(problem_id, reason)` — declare no improvement possible for this cycle.

Always call exactly ONE of these two tools. Never respond with plain text only.

## Simplicity criterion (Karpathy rule)
Reject proposals that are MORE THAN 2x the length of the current solution unless you have strong
evidence (from the outcome data below) that the extra complexity is necessary.
Tiny improvement + ugly complexity = skip.

## Decision process
1. Read the outcome data (success/failure counts, failure notes, environments).
2. Identify the most impactful weakness in the current best solution.
3. Propose the MINIMAL change that addresses that weakness.
4. If no weakness is identifiable or no improvement is possible, call skip_improvement.

## Quality rules
- Prefer concrete, actionable steps over vague descriptions.
- Simpler solutions beat complex ones when confidence is equal.
- A solution that works in more environments is better.
"""


def _load_instructions() -> str:
    """Load researcher instructions from program.md (autoresearch pattern), with fallback."""
    custom_path = settings.agent_researcher_instructions_path
    path = Path(custom_path) if custom_path else Path(__file__).parent / "program.md"
    if path.exists():
        return path.read_text()
    return _RESEARCHER_INSTRUCTIONS_FALLBACK


def create_researcher_agent(tools: list) -> Agent:
    return Agent(
        model=_build_model(),
        instructions=_load_instructions(),
        tools=tools,
    )
