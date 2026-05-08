"""Unit tests for the use-side dashboard at GET /v1/dashboard/usage.

Aggregates from outcomes + problems tables. No new write hot path is added —
the tests assert correct windowing, deduplication, kind-splitting, ordering,
and truncation.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

import pytest

from backend.application.service import AgentbookService
from backend.domain.models import Outcome, utc_now


def _register_reporter(service: AgentbookService) -> UUID:
    """Register a fresh agent and return its UUID."""
    agent, _ = service.register_agent(model_type="test")
    return agent.agent_id


def _seed_problem_with_solution(
    service: AgentbookService, author_id: UUID
) -> tuple[UUID, UUID]:
    """Create one approved problem with one solution; return their IDs."""
    problem = service.create_problem(
        author_id=author_id,
        description="Test problem with sufficient description length to clear the gate.",
    )
    solution = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="A solution to the test problem with enough characters.",
    )
    return problem.problem_id, solution.solution_id


def _seed_outcome(
    service: AgentbookService,
    *,
    solution_id: UUID,
    reporter_id: UUID,
    created_at,
    success: bool = True,
    kind: str = "observed",
) -> None:
    """Add an outcome directly to the in-memory repo so created_at is controllable.

    Bypassing service.report_outcome is intentional — that path stamps
    ``created_at = utc_now()`` and runs confidence math we don't need here.
    """
    service._outcomes.add(
        Outcome(
            solution_id=solution_id,
            reporter_id=reporter_id,
            success=success,
            kind=kind,
            created_at=created_at,
        )
    )


# ---------------------------------------------------------------------------
# Service-level tests (most coverage)
# ---------------------------------------------------------------------------


def test_usage_dashboard_empty_corpus_returns_zeros(service_and_author) -> None:
    service, _ = service_and_author
    result = service.get_usage_dashboard()
    assert result["outcomes"] == {
        "total": 0,
        "last_7_days": 0,
        "last_30_days": 0,
        "verified_total": 0,
        "observed_total": 0,
    }
    assert result["reporters"] == {
        "unique_total": 0,
        "unique_last_7_days": 0,
        "unique_last_30_days": 0,
    }
    assert result["problems"] == {
        "total_approved": 0,
        "with_outcomes": 0,
        "with_zero_outcomes": 0,
    }
    assert result["top_problems_by_outcomes"] == []


def test_usage_dashboard_outcomes_split_by_window(service_and_author) -> None:
    service, author_id = service_and_author
    _, sid = _seed_problem_with_solution(service, author_id)
    reporter_id = _register_reporter(service)
    now = utc_now()

    _seed_outcome(
        service,
        solution_id=sid,
        reporter_id=reporter_id,
        created_at=now - timedelta(days=1),
    )
    _seed_outcome(
        service,
        solution_id=sid,
        reporter_id=reporter_id,
        created_at=now - timedelta(days=8),
    )
    _seed_outcome(
        service,
        solution_id=sid,
        reporter_id=reporter_id,
        created_at=now - timedelta(days=35),
    )

    result = service.get_usage_dashboard()
    assert result["outcomes"]["total"] == 3
    assert result["outcomes"]["last_7_days"] == 1
    assert result["outcomes"]["last_30_days"] == 2


def test_usage_dashboard_unique_reporters_per_window(service_and_author) -> None:
    service, author_id = service_and_author
    _, sid = _seed_problem_with_solution(service, author_id)
    now = utc_now()

    # 3 reporters within last 7 days
    for _ in range(3):
        rid = _register_reporter(service)
        _seed_outcome(
            service,
            solution_id=sid,
            reporter_id=rid,
            created_at=now - timedelta(days=2),
        )
    # 2 reporters at 15 days ago (within 30d, outside 7d)
    for _ in range(2):
        rid = _register_reporter(service)
        _seed_outcome(
            service,
            solution_id=sid,
            reporter_id=rid,
            created_at=now - timedelta(days=15),
        )

    result = service.get_usage_dashboard()
    assert result["reporters"]["unique_total"] == 5
    assert result["reporters"]["unique_last_7_days"] == 3
    assert result["reporters"]["unique_last_30_days"] == 5


def test_usage_dashboard_verified_vs_observed_split(service_and_author) -> None:
    service, author_id = service_and_author
    _, sid = _seed_problem_with_solution(service, author_id)
    reporter_id = _register_reporter(service)
    now = utc_now()

    for _ in range(2):
        _seed_outcome(
            service,
            solution_id=sid,
            reporter_id=reporter_id,
            created_at=now - timedelta(hours=1),
            kind="verified",
        )
    for _ in range(3):
        _seed_outcome(
            service,
            solution_id=sid,
            reporter_id=reporter_id,
            created_at=now - timedelta(hours=1),
            kind="observed",
        )

    result = service.get_usage_dashboard()
    assert result["outcomes"]["verified_total"] == 2
    assert result["outcomes"]["observed_total"] == 3
    assert result["outcomes"]["total"] == 5


def test_usage_dashboard_top_problems_ordered_by_outcome_count(
    service_and_author,
) -> None:
    service, author_id = service_and_author
    reporter_id = _register_reporter(service)
    now = utc_now()

    expected_counts = (5, 2, 1)
    for outcome_count in expected_counts:
        _, sid = _seed_problem_with_solution(service, author_id)
        for _ in range(outcome_count):
            _seed_outcome(
                service,
                solution_id=sid,
                reporter_id=reporter_id,
                created_at=now - timedelta(hours=1),
            )

    result = service.get_usage_dashboard()
    top = result["top_problems_by_outcomes"]
    assert len(top) == 3
    assert tuple(t["outcome_count"] for t in top) == expected_counts


def test_usage_dashboard_top_problems_limit_is_10(service_and_author) -> None:
    service, author_id = service_and_author
    reporter_id = _register_reporter(service)
    now = utc_now()

    for _ in range(12):
        _, sid = _seed_problem_with_solution(service, author_id)
        _seed_outcome(
            service,
            solution_id=sid,
            reporter_id=reporter_id,
            created_at=now - timedelta(hours=1),
        )

    result = service.get_usage_dashboard()
    assert len(result["top_problems_by_outcomes"]) == 10


def test_usage_dashboard_problems_with_zero_outcomes(service_and_author) -> None:
    service, author_id = service_and_author
    reporter_id = _register_reporter(service)
    now = utc_now()

    # 2 problems with outcomes
    for _ in range(2):
        _, sid = _seed_problem_with_solution(service, author_id)
        _seed_outcome(
            service,
            solution_id=sid,
            reporter_id=reporter_id,
            created_at=now - timedelta(hours=1),
        )
    # 3 problems without outcomes
    for _ in range(3):
        _seed_problem_with_solution(service, author_id)

    result = service.get_usage_dashboard()
    assert result["problems"] == {
        "total_approved": 5,
        "with_outcomes": 2,
        "with_zero_outcomes": 3,
    }
    # Only the 2 problems with outcomes appear in the top list — ranked
    # output is bounded by "having at least one outcome", not "fits in 10".
    assert len(result["top_problems_by_outcomes"]) == 2


def test_usage_dashboard_truncates_long_descriptions(service_and_author) -> None:
    service, author_id = service_and_author
    reporter_id = _register_reporter(service)
    now = utc_now()

    # Realistic-ish description >80 chars; must clear the spam gate's
    # 4-unique-char threshold (a flat "x" * 200 would not).
    base = "Long descriptive problem statement with enough variety to clear gate. "
    long_desc = (base * 4)[:200]
    assert len(long_desc) == 200
    problem = service.create_problem(
        author_id=author_id,
        description=long_desc,
    )
    solution = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="A solution to the test problem with enough characters.",
    )
    _seed_outcome(
        service,
        solution_id=solution.solution_id,
        reporter_id=reporter_id,
        created_at=now - timedelta(hours=1),
    )

    result = service.get_usage_dashboard()
    top = result["top_problems_by_outcomes"]
    assert len(top) == 1
    desc = top[0]["description"]
    assert len(desc) == 80
    # Single Unicode horizontal-ellipsis character; not three ASCII dots.
    assert desc.endswith("…")


def test_usage_dashboard_short_descriptions_unchanged(service_and_author) -> None:
    """A description that fits in 80 chars must be returned verbatim."""
    service, author_id = service_and_author
    reporter_id = _register_reporter(service)
    now = utc_now()

    short = "Eighty-char problem description that fits within the truncation limit."
    short = short.ljust(80, ".")
    assert len(short) == 80
    problem = service.create_problem(author_id=author_id, description=short)
    solution = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="A solution to the test problem with enough characters.",
    )
    _seed_outcome(
        service,
        solution_id=solution.solution_id,
        reporter_id=reporter_id,
        created_at=now - timedelta(hours=1),
    )

    result = service.get_usage_dashboard()
    top = result["top_problems_by_outcomes"]
    assert top[0]["description"] == short
    assert "…" not in top[0]["description"]


# ---------------------------------------------------------------------------
# Endpoint integration test (one round-trip through FastAPI)
# ---------------------------------------------------------------------------


def test_usage_dashboard_endpoint_returns_valid_json(service_and_author) -> None:
    """End-to-end: route is wired, schema validates, body matches expected shape."""
    service, author_id = service_and_author
    reporter_id = _register_reporter(service)
    now = utc_now()
    _, sid = _seed_problem_with_solution(service, author_id)
    _seed_outcome(
        service,
        solution_id=sid,
        reporter_id=reporter_id,
        created_at=now - timedelta(hours=1),
        kind="verified",
    )

    from fastapi.testclient import TestClient

    from backend.main import create_app
    from backend.presentation.api.deps import get_service

    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/v1/dashboard/usage")
    assert response.status_code == 200
    body = response.json()

    assert body["outcomes"]["total"] == 1
    assert body["outcomes"]["verified_total"] == 1
    assert body["outcomes"]["observed_total"] == 0
    assert body["reporters"]["unique_total"] == 1
    assert body["problems"]["total_approved"] == 1
    assert body["problems"]["with_outcomes"] == 1
    assert body["problems"]["with_zero_outcomes"] == 0
    assert len(body["top_problems_by_outcomes"]) == 1
    assert body["top_problems_by_outcomes"][0]["outcome_count"] == 1


@pytest.mark.parametrize("solution_ids", [[], None])
def test_outcome_counts_by_solution_ids_handles_empty(
    service_and_author, solution_ids
) -> None:
    """Empty / falsy input must short-circuit to {} without iterating."""
    service, _ = service_and_author
    if solution_ids is None:
        # Sanity: passing None would TypeError, so this branch documents that
        # the contract requires a list.
        pytest.skip("None is not a valid input — list required")
    assert service._outcomes.outcome_counts_by_solution_ids(solution_ids) == {}
