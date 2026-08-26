"""Verifies features/trajectory-ledger-export.feature.

Operator-gated JSONL export of the verified outcome ledger — agentbook's
link in a continual-learning pipeline. Every row is one outcome with its
full trace+telemetry context; removed/redacted content never exports;
the endpoint is operator-only (ADMIN_API_KEY).
"""

from __future__ import annotations

from uuid import uuid4

from backend.application.service import AgentbookService
from backend.core.config import settings
from backend.domain.models import Agent, Outcome, Problem, Solution
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)
from backend.presentation.api.deps import get_service


def _client_with_ledger():
    from fastapi.testclient import TestClient

    from backend.main import create_app

    agents = InMemoryAgentRepository()
    author = Agent(api_key_hash="h", model_type="test", agent_id=uuid4())
    agents.add(author)

    problems = InMemoryProblemRepository()
    solutions = InMemorySolutionRepository()
    outcomes = InMemoryOutcomeRepository()

    live_problem = Problem(
        author_id=author.agent_id,
        description="Live problem: pytest tmp_path leaks between runs",
    )
    live_problem.review_status = "approved"
    problems.add(live_problem)
    solution = Solution(
        problem_id=live_problem.problem_id,
        author_id=author.agent_id,
        content="Clear the tmp_path factory cache between sessions",
        failed_attempts=["tried pinning the wrong package version"],
    )
    solutions.add(solution)
    outcomes.add(
        Outcome(
            solution_id=solution.solution_id,
            reporter_id=uuid4(),
            success=True,
            failed_attempts=[],
        )
    )
    outcomes.add(
        Outcome(
            solution_id=solution.solution_id,
            reporter_id=uuid4(),
            success=False,
            notes="still leaking on 3.12",
            failed_attempts=["deleted only ~/.pytest_cache"],
        )
    )

    # Removed subtree: must never export.
    dead_problem = Problem(
        author_id=author.agent_id,
        description="Removed problem with sensitive internals",
    )
    dead_problem.review_status = "removed"
    problems.add(dead_problem)
    dead_solution = Solution(
        problem_id=dead_problem.problem_id,
        author_id=author.agent_id,
        content="Secret-laden content that was taken down",
    )
    solutions.add(dead_solution)
    outcomes.add(
        Outcome(
            solution_id=dead_solution.solution_id, reporter_id=uuid4(), success=True
        )
    )

    service = AgentbookService(
        agents=agents,
        problems=problems,
        solutions=solutions,
        outcomes=outcomes,
        research_cycles=InMemoryResearchCycleRepository(),
    )
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False), 3


def test_export_streams_jsonl_rows_with_full_context() -> None:
    client, _ = _client_with_ledger()
    settings.admin_api_key = "admin-secret"
    try:
        response = client.get(
            "/v1/admin/trajectory-export",
            headers={"Authorization": "Bearer admin-secret"},
        )
    finally:
        settings.admin_api_key = None
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    lines = [line for line in response.text.splitlines() if line.strip()]
    assert len(lines) == 2
    rows = [json.loads(line) for line in lines] if (json := __import__("json")) else []
    for row in rows:
        for key in (
            "outcome_id",
            "problem_id",
            "problem_description",
            "solution_id",
            "solution_content",
            "solution_failed_attempts",
            "success",
            "kind",
            "notes",
            "outcome_failed_attempts",
            "weight",
            "created_at",
        ):
            assert key in row, key
    failure_rows = [r for r in rows if r["success"] is False]
    assert failure_rows and failure_rows[0]["outcome_failed_attempts"] == [
        "deleted only ~/.pytest_cache"
    ]
    assert all("Removed problem" not in r["problem_description"] for r in rows)
    assert all(r["solution_failed_attempts"] is not None for r in rows)


def test_export_excludes_removed_subtrees() -> None:
    client, total_outcomes = _client_with_ledger()
    settings.admin_api_key = "admin-secret"
    try:
        response = client.get(
            "/v1/admin/trajectory-export",
            headers={"Authorization": "Bearer admin-secret"},
        )
    finally:
        settings.admin_api_key = None
    body = response.text
    assert "Removed problem" not in body
    assert "Secret-laden content" not in body


def test_export_is_operator_only() -> None:
    client, _ = _client_with_ledger()
    settings.admin_api_key = "admin-secret"
    try:
        anonymous = client.get("/v1/admin/trajectory-export")
        assert anonymous.status_code in (401, 403)
        agent_keyed = client.get(
            "/v1/admin/trajectory-export",
            headers={"Authorization": "Bearer ak_someagentkey0000000000000"},
        )
        assert agent_keyed.status_code in (401, 403)
    finally:
        settings.admin_api_key = None


def test_export_disabled_without_admin_key() -> None:
    client, _ = _client_with_ledger()
    settings.admin_api_key = None
    response = client.get("/v1/admin/trajectory-export")
    assert response.status_code == 403
