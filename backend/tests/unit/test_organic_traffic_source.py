"""Verifies features/organic-traffic-source.feature.

The G3/G4 gates (organic < 5% kills the network thesis, >= 15% green-lights
multiplayer) are only readable when outcome traffic is classified by source.
These tests pin the bucket precedence (synthetic > seeded > author_self >
organic_external), the SEED_AGENT_IDS operator extension, the organic-share
math, and the fail-loud behavior on a malformed seed configuration.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.application.security import generate_api_key, hash_api_key
from backend.application.service import (
    EVALUATOR_AGENT_ID,
    SANDBOX_AGENT_ID,
    AgentbookService,
)
from backend.core.config import settings
from backend.domain.models import Agent, Outcome
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
        Agent(
            api_key_hash=hash_api_key(generate_api_key()),
            model_type="test",
            agent_id=author_id,
        )
    )
    solutions = InMemorySolutionRepository()
    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=solutions,
        outcomes=InMemoryOutcomeRepository(solutions=solutions),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    return service, author_id


def _seed_solution(service, author_id):
    problem = service.create_problem(
        author_id=author_id,
        description="ImportError numpy on Docker Alpine container after pip install",
    )
    problem.review_status = "approved"
    service._problems.update(problem)
    return service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Install build-base and python3-dev via apk before pip install",
    )


def _add_outcome(service, solution_id, reporter_id, success=True):
    service._outcomes.add(
        Outcome(
            solution_id=solution_id,
            reporter_id=reporter_id,
            success=success,
            kind="observed",
        )
    )


def test_outcomes_bucketed_by_source_with_first_match_precedence():
    service, author_id = _make_service()
    solution = _seed_solution(service, author_id)

    _add_outcome(service, solution.solution_id, EVALUATOR_AGENT_ID)
    _add_outcome(service, solution.solution_id, SANDBOX_AGENT_ID)
    _add_outcome(service, solution.solution_id, author_id)
    _add_outcome(service, solution.solution_id, uuid4())

    sources = service.get_usage_dashboard()["outcome_sources"]

    # SANDBOX_AGENT_ID is in both the synthetic and seed sets: synthetic wins.
    assert sources["synthetic"]["total"] == 2
    assert sources["seeded"]["total"] == 0
    assert sources["author_self"]["total"] == 1
    assert sources["organic_external"]["total"] == 1


def test_operator_configured_seed_identity_is_classified_seeded(monkeypatch):
    service, author_id = _make_service()
    solution = _seed_solution(service, author_id)
    seed_reporter = uuid4()
    monkeypatch.setattr(settings, "seed_agent_ids", str(seed_reporter))

    _add_outcome(service, solution.solution_id, seed_reporter)

    sources = service.get_usage_dashboard()["outcome_sources"]
    assert sources["seeded"]["total"] == 1
    assert sources["organic_external"]["total"] == 0


def test_organic_share_is_computed_over_the_30_day_window():
    service, author_id = _make_service()
    solution = _seed_solution(service, author_id)

    _add_outcome(service, solution.solution_id, uuid4())
    _add_outcome(service, solution.solution_id, EVALUATOR_AGENT_ID)
    _add_outcome(service, solution.solution_id, SANDBOX_AGENT_ID)
    _add_outcome(service, solution.solution_id, author_id)

    sources = service.get_usage_dashboard()["outcome_sources"]
    assert sources["organic_share_30d"] == pytest.approx(0.25)


def test_organic_share_is_zero_when_no_outcomes_exist():
    service, _ = _make_service()
    sources = service.get_usage_dashboard()["outcome_sources"]
    assert sources["organic_share_30d"] == 0.0
    assert sources["organic_external"] == {"total": 0, "last_30d": 0}


def test_malformed_seed_agent_ids_fails_loud(monkeypatch):
    service, _ = _make_service()
    monkeypatch.setattr(settings, "seed_agent_ids", "not-a-uuid")
    with pytest.raises(ValueError):
        service.get_usage_dashboard()


def test_usage_endpoint_exposes_outcome_sources():
    from backend.main import create_app
    from backend.presentation.api.deps import get_service

    service, author_id = _make_service()
    solution = _seed_solution(service, author_id)
    _add_outcome(service, solution.solution_id, uuid4())

    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app, raise_server_exceptions=False)

    body = client.get("/v1/dashboard/usage").json()
    assert body["outcome_sources"]["organic_external"]["total"] == 1
    assert body["outcome_sources"]["organic_share_30d"] == pytest.approx(1.0)
