"""Outcome-report throttle: the write path that feeds confidence scoring.

Docs (``docs/mcp-setup.md``, the ``report`` tool description) advertise
"10 reports per hour per agent". The throttle lives in the application layer
(`AgentbookService.report_outcome`) so BOTH presentation surfaces — the REST
``POST /v1/problems/{id}/solutions/{solution_id}/outcomes`` route and the MCP
``report`` tool — inherit it from a single keyed-by-reporter check. This is
the exact unthrottled-write attack the confidence-inflation post-mortem warns
about, so it gets a dedicated regression test.

The cap is keyed by the *authenticated reporter id* (``count_by_reporter``),
counting all of a reporter's outcomes in the trailing hour regardless of which
solution they target. The realistic abuse path — and the one that actually
moves confidence across the corpus — is a single agent spraying reports across
*many distinct* solutions, so the tests below report once on each of many
solutions rather than re-reporting the same one (the in-memory repo upserts
by (solution_id, reporter_id), so repeated reports on one solution collapse to
a single stored outcome and never trip the cap).

The cap is enforced regardless of the slowapi / MCP in-process limiters (which
guard search, not writes), so this test does not need the ``enable_limiter``
opt-in fixture — that fixture toggles the slowapi limiter, which is irrelevant
to the application-layer report throttle.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from backend.application.errors import RateLimitError
from backend.domain.models import Agent


def _make_solutions(service, author_id: UUID, count: int) -> list[UUID]:
    """Create ``count`` distinct solutions under one fresh problem.

    Returns their solution ids. Each is a separate report target so a single
    reporter can accumulate ``count`` outcomes against the per-reporter cap.
    """
    problem = service.create_problem(
        author_id=author_id,
        description="Intermittent 503 from upstream during deploy",
    )
    solution_ids: list[UUID] = []
    for i in range(count):
        solution = service.create_solution(
            problem_id=problem.problem_id,
            author_id=author_id,
            content=f"Candidate fix #{i}: add a readiness probe with backoff.",
            steps=["Add readiness probe", "Back off on 503"],
        )
        solution_ids.append(solution.solution_id)
    return solution_ids


def _register_reporter(service) -> UUID:
    """Register and return a fresh reporter agent id distinct from the author.

    The cap applies per reporter; using a non-author reporter mirrors the real
    abuse path (an external agent spamming success reports to inflate scores).
    """
    reporter_id = uuid4()
    service._agents.add(
        Agent(
            api_key_hash=f"reporter-{reporter_id}",
            model_type="test",
            agent_id=reporter_id,
        )
    )
    return reporter_id


def test_eleventh_report_from_one_agent_is_rejected(service_and_author):
    service, author_id = service_and_author
    solution_ids = _make_solutions(service, author_id, 11)
    reporter_id = _register_reporter(service)

    # 10 reports inside the window are accepted (one per distinct solution).
    for solution_id in solution_ids[:10]:
        service.report_outcome(
            reporter_id=reporter_id,
            solution_id=solution_id,
            success=True,
        )

    # The 11th from the same agent within the hour is throttled.
    with pytest.raises(RateLimitError) as excinfo:
        service.report_outcome(
            reporter_id=reporter_id,
            solution_id=solution_ids[10],
            success=True,
        )

    # The window hint must be present so the MCP/REST handlers can surface a
    # Retry-After to the caller.
    assert excinfo.value.retry_after_seconds is not None
    assert excinfo.value.retry_after_seconds > 0


def test_rate_limit_is_per_reporter_not_global(service_and_author):
    """A second agent is unaffected by the first agent's exhausted budget."""
    service, author_id = service_and_author
    solution_ids = _make_solutions(service, author_id, 11)

    first = _register_reporter(service)
    second = _register_reporter(service)

    for solution_id in solution_ids[:10]:
        service.report_outcome(reporter_id=first, solution_id=solution_id, success=True)

    with pytest.raises(RateLimitError):
        service.report_outcome(
            reporter_id=first, solution_id=solution_ids[10], success=True
        )

    # Second agent still has its full budget against the same solutions.
    service.report_outcome(
        reporter_id=second, solution_id=solution_ids[0], success=True
    )
