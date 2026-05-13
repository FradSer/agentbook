"""Unit tests for AgentbookService.get_live_research_snapshot()."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from backend.application.service import RESEARCH_TIMEOUT_SECONDS, AgentbookService
from backend.domain.models import Agent, Problem, ResearchCycle
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)


def _make_service():
    agents = InMemoryAgentRepository()
    author_id = uuid4()
    agents.add(
        Agent(api_key_hash="test-hash", model_type="test", agent_id=author_id),
    )
    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    return service, author_id


def _add_active_problem(
    service,
    author_id,
    *,
    description: str = "Active research problem description with enough length",
    started_seconds_ago: int = 30,
    solution_count: int = 2,
    best_confidence: float = 0.7,
) -> Problem:
    started_at = datetime.now(tz=UTC) - timedelta(seconds=started_seconds_ago)
    problem = Problem(
        author_id=author_id,
        description=description,
        review_status="approved",
        research_started_at=started_at,
        solution_count=solution_count,
        best_confidence=best_confidence,
    )
    service._problems.add(problem)
    return problem


def test_snapshot_empty_state_returns_empty_active_and_null_last_cycle():
    service, _ = _make_service()
    snapshot = service.get_live_research_snapshot()
    assert snapshot["active"] == []
    assert snapshot["last_cycle_at"] is None
    assert isinstance(snapshot["now"], str)


def test_snapshot_includes_single_active_problem():
    service, author_id = _make_service()
    problem = _add_active_problem(service, author_id)
    snapshot = service.get_live_research_snapshot()
    assert len(snapshot["active"]) == 1
    item = snapshot["active"][0]
    assert item["problem_id"] == str(problem.problem_id)
    assert item["solution_count"] == 2
    assert item["best_confidence"] == 0.7
    assert item["elapsed_seconds"] >= 0
    assert isinstance(item["research_started_at"], str)


def test_snapshot_orders_active_by_research_started_at_desc():
    service, author_id = _make_service()
    older = _add_active_problem(
        service, author_id, description="older active problem", started_seconds_ago=120
    )
    middle = _add_active_problem(
        service, author_id, description="middle active problem", started_seconds_ago=60
    )
    newer = _add_active_problem(
        service, author_id, description="newer active problem", started_seconds_ago=10
    )
    snapshot = service.get_live_research_snapshot()
    ids = [item["problem_id"] for item in snapshot["active"]]
    assert ids == [str(newer.problem_id), str(middle.problem_id), str(older.problem_id)]


def test_snapshot_excludes_stale_row_at_361_seconds():
    service, author_id = _make_service()
    _add_active_problem(service, author_id, started_seconds_ago=361)
    snapshot = service.get_live_research_snapshot()
    assert snapshot["active"] == []


def test_snapshot_includes_row_at_359_seconds():
    service, author_id = _make_service()
    problem = _add_active_problem(service, author_id, started_seconds_ago=359)
    snapshot = service.get_live_research_snapshot()
    assert len(snapshot["active"]) == 1
    assert snapshot["active"][0]["problem_id"] == str(problem.problem_id)


def test_snapshot_returns_global_max_last_cycle_at():
    service, author_id = _make_service()
    p1 = _add_active_problem(service, author_id, description="problem one cycles")
    p2 = _add_active_problem(service, author_id, description="problem two cycles")
    older_at = datetime.now(tz=UTC) - timedelta(minutes=10)
    newer_at = datetime.now(tz=UTC) - timedelta(minutes=2)
    service._research_cycles.add(
        ResearchCycle(
            problem_id=p1.problem_id,
            researcher_id=author_id,
            status="no_improvement",
            created_at=older_at,
        )
    )
    service._research_cycles.add(
        ResearchCycle(
            problem_id=p2.problem_id,
            researcher_id=author_id,
            status="no_improvement",
            created_at=newer_at,
        )
    )
    snapshot = service.get_live_research_snapshot()
    assert snapshot["last_cycle_at"] == newer_at.isoformat()


def test_snapshot_active_item_payload_allowlist():
    service, author_id = _make_service()
    _add_active_problem(service, author_id)
    snapshot = service.get_live_research_snapshot()
    item = snapshot["active"][0]
    expected_keys = {
        "problem_id",
        "description",
        "solution_count",
        "best_confidence",
        "research_started_at",
        "elapsed_seconds",
    }
    assert set(item.keys()) == expected_keys


def test_snapshot_truncates_description_to_300_chars():
    service, author_id = _make_service()
    long_description = "x" * 500
    _add_active_problem(service, author_id, description=long_description)
    snapshot = service.get_live_research_snapshot()
    assert len(snapshot["active"][0]["description"]) == 300
    assert snapshot["active"][0]["description"] == "x" * 300


def test_snapshot_research_started_at_serialised_as_iso8601():
    service, author_id = _make_service()
    _add_active_problem(service, author_id)
    snapshot = service.get_live_research_snapshot()
    item = snapshot["active"][0]
    assert isinstance(item["research_started_at"], str)
    assert isinstance(snapshot["now"], str)
    # round-trip through fromisoformat to confirm well-formed ISO 8601
    datetime.fromisoformat(item["research_started_at"])
    datetime.fromisoformat(snapshot["now"])


def test_snapshot_uses_research_timeout_seconds_constant():
    """Window must respect RESEARCH_TIMEOUT_SECONDS exactly: 1s under = in, 1s over = out."""
    service, author_id = _make_service()
    inside = _add_active_problem(
        service,
        author_id,
        description="inside window problem",
        started_seconds_ago=RESEARCH_TIMEOUT_SECONDS - 1,
    )
    _add_active_problem(
        service,
        author_id,
        description="outside window problem",
        started_seconds_ago=RESEARCH_TIMEOUT_SECONDS + 1,
    )
    snapshot = service.get_live_research_snapshot()
    ids = [item["problem_id"] for item in snapshot["active"]]
    assert ids == [str(inside.problem_id)]
