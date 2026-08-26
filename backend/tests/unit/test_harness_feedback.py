"""Verifies features/harness-feedback.feature.

The worker's harness-feedback channel: systemic, cross-cutting observations
computed from behavioral telemetry (reporting gaps) plus hot-problem
evidence, so framework-level amendments (skill guidance / tool descriptions)
can be proposed and confirmed by humans — the Learn surface extended to the
harness.
"""

from __future__ import annotations

from datetime import timedelta

from backend.core.config import settings
from backend.domain.models import QueryEvent, utc_now


def _client_with_traffic(pairs: int, with_followup: bool):
    from uuid import uuid4 as _uuid4

    from fastapi.testclient import TestClient

    from backend.application.service import AgentbookService
    from backend.domain.models import Agent as AgentModel, Outcome
    from backend.infrastructure.persistence.database import Base
    from backend.infrastructure.persistence.in_memory import (
        InMemoryAgentRepository,
        InMemoryOutcomeRepository,
        InMemoryProblemRepository,
        InMemoryQueryEventRepository,
        InMemoryResearchCycleRepository,
        InMemorySolutionRepository,
    )
    from backend.main import create_app
    from backend.presentation.api.deps import get_service

    agents = InMemoryAgentRepository()
    author = AgentModel(api_key_hash="h", model_type="t", agent_id=_uuid4())
    agents.add(author)
    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
        query_events=InMemoryQueryEventRepository(),
    )

    problem = service.create_problem(
        author_id=author.agent_id,
        description="Hot problem that keeps being re-searched",
    )
    solution = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author.author_id if hasattr(author, "author_id") else author.agent_id,
        content="A fix body with enough characters to pass gates.",
    )
    del Base  # imported for parity with other suites; unused here

    now = utc_now()
    gap = timedelta(hours=2)
    reporters = []
    for i in range(pairs):
        reporter = _uuid4()
        reporters.append(reporter)
        service._query_events.add(
            QueryEvent(
                query_text="q",
                agent_id=reporter,
                ip_hash=None,
                fingerprint_hash=None,
                top_match_problem_id=problem.problem_id,
                top_match_quality="strong",
                has_help=True,
                is_self_hit=False,
                is_seed_replay=False,
                created_at=now - gap * (i + 2),
            )
        )
        service._query_events.add(
            QueryEvent(
                query_text="q again",
                agent_id=reporter,
                ip_hash=None,
                fingerprint_hash=None,
                top_match_problem_id=problem.problem_id,
                top_match_quality="strong",
                has_help=True,
                is_self_hit=False,
                is_seed_replay=False,
                created_at=now - gap,
            )
        )
        if with_followup:
            service._outcomes.add(
                Outcome(
                    solution_id=solution.solution_id,
                    reporter_id=reporter,
                    success=True,
                    created_at=now - timedelta(minutes=30),
                )
            )

    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


def test_reporting_gap_detected_when_followups_are_rare() -> None:
    client = _client_with_traffic(pairs=6, with_followup=False)
    settings.worker_api_key = "worker-secret"
    try:
        response = client.get(
            "/v1/internal/worker/harness-feedback",
            headers={"Authorization": "Bearer worker-secret"},
        )
    finally:
        settings.worker_api_key = None
    assert response.status_code == 200
    body = response.json()
    kinds = [o["kind"] for o in body["observations"]]
    assert "reporting_gap" in kinds
    gap = next(o for o in body["observations"] if o["kind"] == "reporting_gap")
    assert gap["metrics"]["recall_pairs"] >= 5
    assert gap["metrics"]["outcome_followup_share"] < 0.3
    hot = body["hot_problems"]
    assert hot and hot[0]["repeat_queries"] >= 1


def test_healthy_reporting_produces_no_gap_observation() -> None:
    client = _client_with_traffic(pairs=6, with_followup=True)
    settings.worker_api_key = "worker-secret"
    try:
        response = client.get(
            "/v1/internal/worker/harness-feedback",
            headers={"Authorization": "Bearer worker-secret"},
        )
    finally:
        settings.worker_api_key = None
    kinds = [o["kind"] for o in response.json()["observations"]]
    assert "reporting_gap" not in kinds


def test_harness_feedback_is_worker_only() -> None:
    client = _client_with_traffic(pairs=1, with_followup=False)
    settings.worker_api_key = "worker-secret"
    try:
        anonymous = client.get("/v1/internal/worker/harness-feedback")
        assert anonymous.status_code in (401, 403)
        agent_keyed = client.get(
            "/v1/internal/worker/harness-feedback",
            headers={"Authorization": "Bearer ak_someagentkey0000000000000"},
        )
        assert agent_keyed.status_code in (401, 403)
    finally:
        settings.worker_api_key = None
