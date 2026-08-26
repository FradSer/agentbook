"""Verifies features/behavioral-hotspot-candidates.feature.

Understand feeds Learn: repeat-query pressure (server-side implicit failure
signal) re-ranks the worker's improvement candidates and is surfaced as a
``repeat_queries`` count so the worker LLM sees why a problem is prioritized.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

from backend.application.service import AgentbookService
from backend.domain.models import Agent, QueryEvent, utc_now
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryQueryEventRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)


def _service() -> tuple[AgentbookService, UUID]:
    agents = InMemoryAgentRepository()
    author_id = uuid4()
    agents.add(Agent(api_key_hash="h", model_type="test", agent_id=author_id))
    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
        query_events=InMemoryQueryEventRepository(),
    )
    return service, author_id


def _seed_candidate(
    service: AgentbookService,
    author_id: UUID,
    description: str,
) -> UUID:
    problem = service.create_problem(author_id=author_id, description=description)
    service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content=f"A working fix for: {description}",
    )
    return problem.problem_id


def _event(
    agent_id: UUID | None,
    problem_id: UUID,
    offset: timedelta,
    *,
    seeded: bool = False,
    self_hit: bool = False,
) -> QueryEvent:
    return QueryEvent(
        query_text="q",
        agent_id=agent_id,
        ip_hash=None if agent_id else f"ip-{agent_id or uuid4()}",
        fingerprint_hash=None,
        top_match_problem_id=problem_id,
        top_match_quality="strong",
        has_help=True,
        is_self_hit=self_hit,
        is_seed_replay=False,
        is_seeded_hit=seeded,
        created_at=utc_now() - offset,
    )


def test_hot_problem_outranks_stale_peer() -> None:
    service, author_id = _service()
    hot = _seed_candidate(service, author_id, "Hot problem with repeat searchers x")
    cold = _seed_candidate(service, author_id, "Cold problem nobody searches again")
    querier_a, querier_b = uuid4(), uuid4()
    gap = timedelta(hours=2)
    for querier in (querier_a, querier_b):
        service._query_events.add(
            _event(querier, hot, gap * 3),
        )
        service._query_events.add(_event(querier, hot, gap))
    # Cold problem does get searched once — but never repeated.
    service._query_events.add(_event(uuid4(), cold, gap))

    candidates = service.find_research_candidates(limit=10)
    by_id = {str(c["problem_id"]): c for c in candidates}
    assert str(hot) in by_id and str(cold) in by_id
    assert by_id[str(hot)]["repeat_queries"] >= 2
    assert by_id[str(cold)]["repeat_queries"] == 0
    assert str(candidates[0]["problem_id"]) == str(hot)


def test_no_traffic_keeps_deterministic_order_with_zero_counts() -> None:
    service, author_id = _service()
    p1 = _seed_candidate(service, author_id, "Alpha candidate no traffic at all")
    p2 = _seed_candidate(service, author_id, "Beta candidate no traffic either")
    candidates = service.find_research_candidates(limit=10)
    ids = [str(c["problem_id"]) for c in candidates]
    assert ids == [str(p1), str(p2)]
    assert all(c["repeat_queries"] == 0 for c in candidates)


def test_seed_and_self_hits_create_no_pressure() -> None:
    service, author_id = _service()
    pid = _seed_candidate(service, author_id, "Only seeded and self traffic here")
    seed_agent = uuid4()
    gap = timedelta(hours=2)
    service._query_events.add(_event(seed_agent, pid, gap * 3, seeded=True))
    service._query_events.add(_event(seed_agent, pid, gap, seeded=True))
    service._query_events.add(_event(author_id, pid, gap * 3, self_hit=True))
    service._query_events.add(_event(author_id, pid, gap, self_hit=True))

    candidates = service.find_research_candidates(limit=10)
    row = next(c for c in candidates if str(c["problem_id"]) == str(pid))
    assert row["repeat_queries"] == 0


def test_public_candidates_route_surfaces_repeat_queries(client_and_key) -> None:
    """The dashboard candidates endpoint carries the same signal."""
    from backend.presentation.api.deps import get_service
    from backend.tests.conftest import _build_client

    client, api_key = _build_client()
    service = client.app.dependency_overrides[get_service]()
    author_id = service.authenticate(api_key, agent_info=None).agent_id
    _seed_candidate(service, author_id, "Route-level candidate for parity checks")

    response = client.get("/v1/dashboard/research/candidates?limit=5")
    assert response.status_code == 200
    items = response.json()["candidates"]
    assert items and "repeat_queries" in items[0]
