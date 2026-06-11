"""Verifies features/fallback-label-cap.feature.

The deterministic fallback embedder false-matches unrelated error-ish texts
(~0.6+ cosine for any two), so its raw vector score must not mint a tier
above "partial". A constant-vector provider models the worst case: every
query sits at cosine 1.0 to every stored problem. Under the provider name
"fallback" that score may only reach "partial"; under a real provider name
the same score legitimately earns "strong". Lexical tiers stay untouched
because they never depend on embedding quality.
"""

from __future__ import annotations

from uuid import uuid4

from backend.application.service import AgentbookService
from backend.domain.models import Agent
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)


class _ConstantVectorProvider:
    """Worst-case embedder: every text maps to the same unit vector."""

    def embed(self, text: str, input_type: str = "query") -> list[float]:
        return [1.0] + [0.0] * 1023


def _build_service(provider_name: str):
    agents = InMemoryAgentRepository()
    author = Agent(api_key_hash="h", model_type="test", agent_id=uuid4())
    agents.add(author)
    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
        embedding_provider=_ConstantVectorProvider(),
        embedding_provider_name=provider_name,
    )
    problem = service.create_problem(
        author_id=author.agent_id,
        description="Vite HMR websocket disconnects behind nginx reverse proxy",
    )
    problem.review_status = "approved"
    service._problems.update(problem)
    service.create_solution(
        problem_id=problem.problem_id,
        author_id=author.agent_id,
        content="Raise proxy_read_timeout and forward the Upgrade headers",
    )
    return service


NONSENSE_QUERY = "purple elephant quantum dishwasher"


def test_vector_only_match_is_capped_at_partial_under_fallback_provider():
    service = _build_service("fallback")

    response = service.search_problems(query=NONSENSE_QUERY, limit=5)

    qualities = [row["match_quality"] for row in response["results"]]
    assert all(q not in ("strong", "exact") for q in qualities), qualities
    assert response["no_good_match"] is True


def test_same_vector_score_earns_strong_under_real_provider():
    service = _build_service("gemini")

    response = service.search_problems(query=NONSENSE_QUERY, limit=5)

    qualities = [row["match_quality"] for row in response["results"]]
    assert "strong" in qualities, qualities


def test_lexical_overlap_still_earns_strong_under_fallback_provider():
    service = _build_service("fallback")

    response = service.search_problems(
        query="Vite HMR websocket disconnects behind nginx", limit=5
    )

    qualities = [row["match_quality"] for row in response["results"]]
    assert "strong" in qualities, qualities
