"""Verifies features/authed-write-rate-limit.feature.

The authenticated write verbs (create problem, create solution, improve) share a
per-author hourly budget so one valid key cannot flood the public CC0 commons.
The limiter is disabled by default in tests (conftest); this test opts in with a
small budget.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.application.errors import RateLimitError
from backend.application.service import AgentbookService
from backend.core.write_rate_limit import write_limiter
from backend.domain.models import Agent
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)


@pytest.fixture
def small_write_budget():
    """Opt this test into write-limit enforcement with a tiny budget."""
    original_enabled, original_max = write_limiter.enabled, write_limiter.max_calls
    write_limiter.enabled = True
    write_limiter.max_calls = 3
    write_limiter.reset()
    try:
        yield 3
    finally:
        write_limiter.enabled = original_enabled
        write_limiter.max_calls = original_max
        write_limiter.reset()


def _service_with_author():
    agents = InMemoryAgentRepository()
    author_id = uuid4()
    agents.add(Agent(api_key_hash="h", model_type="test", agent_id=author_id))
    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    return service, author_id, agents


def test_author_exceeding_write_budget_is_throttled(small_write_budget):
    service, author_id, _ = _service_with_author()
    for i in range(small_write_budget):
        service.create_problem(
            author_id=author_id,
            description=f"Distinct dev problem number {i} that is long enough to pass",
        )
    with pytest.raises(RateLimitError, match="rate limit"):
        service.create_problem(
            author_id=author_id,
            description="One contribution past the per-author hourly budget here",
        )


def test_write_budget_is_per_author_not_global(small_write_budget):
    service, author_id, agents = _service_with_author()
    for i in range(small_write_budget):
        service.create_problem(
            author_id=author_id,
            description=f"Distinct dev problem number {i} that is long enough to pass",
        )
    # First author is now exhausted; a different author is unaffected.
    other = uuid4()
    agents.add(Agent(api_key_hash="h2", model_type="test", agent_id=other))
    problem = service.create_problem(
        author_id=other,
        description="A second author's first contribution should be accepted fine",
    )
    assert problem.problem_id is not None


@pytest.mark.asyncio
async def test_mcp_remember_maps_throttle_to_rate_limit_exceeded(small_write_budget):
    import json

    from backend.presentation.mcp.tools import handle_contribute

    service, author_id, _ = _service_with_author()
    for i in range(small_write_budget):
        service.create_problem(
            author_id=author_id,
            description=f"Distinct dev problem number {i} that is long enough to pass",
        )
    result = await handle_contribute(
        service,
        author_id,
        {"description": "An MCP remember past the per-author hourly write budget"},
    )
    data = json.loads(result[0]["text"])
    assert data["error"] == "rate_limit_exceeded"


def test_full_contribute_costs_one_write_unit(small_write_budget):
    # A new-mode contribute creates a problem AND a solution but must consume
    # ONE budget unit, not two. With budget 3, three full contributes succeed
    # and the fourth throttles; under the old double-count the second contribute
    # would already throttle (and orphan a problem).
    service, author_id, _ = _service_with_author()
    for i in range(small_write_budget):
        result = service.contribute(
            author_id=author_id,
            description=f"Distinct dev problem {i} that is long enough to pass the gate",
            solution_content=f"A solution for problem {i} long enough to pass the gate",
        )
        assert result["problem_id"] is not None
        assert result["solution_id"] is not None
    with pytest.raises(RateLimitError, match="rate limit"):
        service.contribute(
            author_id=author_id,
            description="One contribute past the per-author budget, long enough here",
            solution_content="Another solution that is plainly long enough to pass",
        )
