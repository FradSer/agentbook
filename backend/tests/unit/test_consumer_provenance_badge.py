"""Verifies features/consumer-provenance-badge.feature.

The per-solution confidence_inputs must disclose how many corroborating
reporters are seed identities and a provenance badge (organic/seeded/none) so a
recalling agent can discount a score no organic reporter has confirmed. The
classification existed only on the operator dashboard before; these tests pin it
onto the consumer search surface.
"""

from __future__ import annotations

from uuid import uuid4

from backend.application.service import AgentbookService, _provenance_from_outcomes
from backend.core.config import settings
from backend.domain.models import Agent, Outcome, Solution
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)


def _sol(author, confidence=0.9):
    return Solution(
        problem_id=uuid4(), author_id=author, content="x", confidence=confidence
    )


def _out(reporter, *, success=True, kind="observed"):
    return Outcome(
        solution_id=uuid4(), reporter_id=reporter, success=success, kind=kind
    )


def test_provenance_seeded_when_all_reporters_are_seed_identities():
    author, seed1, seed2 = uuid4(), uuid4(), uuid4()
    p = _provenance_from_outcomes(
        _sol(author), [_out(seed1), _out(seed2)], frozenset({seed1, seed2})
    )
    assert p["unique_reporters"] == 2
    assert p["seeded_reporters"] == 2
    assert p["provenance"] == "seeded"


def test_provenance_organic_when_any_reporter_is_external():
    author, seed1, organic = uuid4(), uuid4(), uuid4()
    p = _provenance_from_outcomes(
        _sol(author), [_out(seed1), _out(organic)], frozenset({seed1})
    )
    assert p["seeded_reporters"] == 1
    assert p["provenance"] == "organic"


def test_provenance_none_when_no_outcomes():
    p = _provenance_from_outcomes(_sol(uuid4(), confidence=0.3), [], frozenset())
    assert p["seeded_reporters"] == 0
    assert p["provenance"] == "none"


def test_seed_override_confidence_with_no_outcomes_is_seeded():
    # demo/migration value written straight onto the column, zero outcomes
    p = _provenance_from_outcomes(_sol(uuid4(), confidence=0.95), [], frozenset())
    assert p["provenance"] == "seeded"
    assert p["has_seed_override"] is True


def test_search_surface_carries_provenance_badge(monkeypatch):
    agents = InMemoryAgentRepository()
    author = uuid4()
    agents.add(Agent(api_key_hash="h", model_type="test", agent_id=author))
    solutions = InMemorySolutionRepository()
    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=solutions,
        outcomes=InMemoryOutcomeRepository(solutions=solutions),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    problem = service.create_problem(
        author_id=author,
        description="Redis connection pool exhausted under burst load on worker boot",
    )
    problem.review_status = "approved"
    service._problems.update(problem)
    sol = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author,
        content="Cap the pool size and reuse a module-level client across workers",
    )

    seed_reporter = uuid4()
    agents.add(Agent(api_key_hash="seed", model_type="seed", agent_id=seed_reporter))
    monkeypatch.setattr(settings, "seed_agent_ids", str(seed_reporter))
    service.report_outcome(
        reporter_id=seed_reporter, solution_id=sol.solution_id, success=True
    )

    result = service.search_problems(
        query="Redis connection pool exhausted burst", limit=5
    )
    rows = result["results"]
    assert rows, "search returned no rows"
    best = rows[0]["best_solution"]
    assert best["confidence_inputs"]["provenance"] == "seeded"
    assert best["confidence_inputs"]["seeded_reporters"] == 1

    # The public problem-detail (book) view carries the same badge.
    book = service.get_agentbook(problem.problem_id)
    history_row = book["solution_history"][0]
    assert history_row["provenance"] == "seeded"
    assert history_row["seeded_reporters"] == 1
