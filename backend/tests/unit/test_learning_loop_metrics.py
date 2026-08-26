"""Verifies features/learning-loop-metrics.feature.

The meta-metric: instrumentation for the learning loop itself. get_metrics
measured content-side health while the improvement loop starved silently;
learning_loop adds proposal throughput windows and an explicit starvation
flag (eligible base exists but nothing survives filtering).
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

from backend.application.service import AgentbookService
from backend.domain.models import Agent, ResearchCycle, utc_now
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


def _seed_candidate(service: AgentbookService, author_id: UUID) -> UUID:
    problem = service.create_problem(
        author_id=author_id,
        description="A candidate problem below the confidence ceiling",
    )
    service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="A working fix body with sufficient characters.",
    )
    return problem.problem_id


def _cycle(
    service: AgentbookService,
    author_id: UUID,
    problem_id: UUID,
    status: str,
    age: timedelta,
) -> None:
    service._research_cycles.add(
        ResearchCycle(
            problem_id=problem_id,
            researcher_id=author_id,
            status=status,  # type: ignore[arg-type]
            reasoning="eval sweep",
            created_at=utc_now() - age,
        )
    )


def test_empty_corpus_yields_zeroed_learning_loop() -> None:
    service, _ = _service()
    section = service.get_metrics()["learning_loop"]
    assert section["proposals_last_7d"] == 0
    assert section["proposals_last_30d"] == 0
    assert section["eligible_base"] == 0
    assert section["starved"] is False


def test_cycle_windows_feed_proposal_throughput() -> None:
    service, author_id = _service()
    pid = _seed_candidate(service, author_id)
    _cycle(service, author_id, pid, "improved", timedelta(days=2))
    _cycle(service, author_id, pid, "no_improvement", timedelta(days=40))
    _cycle(service, author_id, pid, "improved", timedelta(days=40))

    section = service.get_metrics()["learning_loop"]
    assert section["proposals_last_7d"] == 1
    assert section["proposals_last_30d"] == 1
    assert section["accepted_last_30d"] == 1


def test_starvation_flagged_when_nothing_survives_filtering() -> None:
    service, author_id = _service()
    pid = _seed_candidate(service, author_id)
    # Stall the only eligible problem beyond the threshold.
    for i in range(3):
        _cycle(service, author_id, pid, "no_improvement", timedelta(days=i + 1))

    section = service.get_metrics()["learning_loop"]
    assert section["eligible_base"] >= 1
    assert section["surfaced_candidates"] == 0
    assert section["starved"] is True


def test_healthy_loop_not_flagged() -> None:
    service, author_id = _service()
    _seed_candidate(service, author_id)

    section = service.get_metrics()["learning_loop"]
    assert section["eligible_base"] >= 1
    assert section["surfaced_candidates"] >= 1
    assert section["starved"] is False


def test_metrics_http_surface_carries_learning_loop(client_and_key) -> None:
    """response_model regression guard: the typed MetricsApiResponse must
    declare learning_loop or FastAPI strips it (prod lesson 2026-08-26)."""
    from backend.presentation.api.deps import get_service

    client, _ = client_and_key
    body = client.get("/v1/dashboard/metrics").json()
    assert "learning_loop" in body
    section = body["learning_loop"]
    assert set(section) >= {
        "proposals_last_7d",
        "proposals_last_30d",
        "eligible_base",
        "surfaced_candidates",
        "starved",
    }
    assert get_service is not None
