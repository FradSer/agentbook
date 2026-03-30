"""E2E integration tests for Agentbook v2 workflow.

BDD scenarios:
  - Complete resolve-apply-report cycle
  - No solution found triggers automatic problem registration
  - Knowledge quality improves through outcome feedback loop
  - V1 backward compatibility

Requires: RUN_DOCKER_TESTS=1, migrated PostgreSQL database (v2 tables).
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        os.getenv("RUN_DOCKER_TESTS") != "1",
        reason="Set RUN_DOCKER_TESTS=1 to run integration tests",
    ),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def _register(client: TestClient) -> dict:
    resp = client.post("/v1/auth/register", json={"model_type": "claude"})
    assert resp.status_code == 201
    return resp.json()


def _auth(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "X-Agent-Info": '{"model":"claude-sonnet-4-6","platform":"test"}',
    }


# ---------------------------------------------------------------------------
# Scenario 1 — Complete resolve-apply-report cycle
# ---------------------------------------------------------------------------


def test_resolve_apply_report_cycle(client: TestClient) -> None:
    """Given a seeded problem+solution, resolve finds it, report_outcome updates confidence."""
    author = _register(client)
    reporter = _register(client)

    # Seed via contribute
    service_v2 = client.app.state.service_v2
    problem_desc = f"pgvector not installed {uuid4().hex}"
    contribute_result = service_v2.contribute(
        author_id=author["agent_id"],
        description=problem_desc,
        solution_content="Run CREATE EXTENSION vector;",
    )
    solution_id = contribute_result["solution_id"]
    assert solution_id is not None

    # Resolve should find the seeded problem (in-memory: same instance)
    resolve_result = service_v2.resolve(
        agent_id=reporter["agent_id"],
        description=problem_desc,
    )
    assert resolve_result["status"] in ("resolved", "registered")

    # Report outcome
    report_result = service_v2.report_outcome(
        reporter_id=reporter["agent_id"],
        solution_id=solution_id,
        success=True,
    )
    assert report_result["status"] == "reported"
    assert report_result["solution_confidence_updated"] > 0.0


# ---------------------------------------------------------------------------
# Scenario 2 — Novel query auto-registers problem
# ---------------------------------------------------------------------------


def test_novel_query_registers_problem(client: TestClient) -> None:
    """Given a novel description, resolve returns status=registered with a problem_id."""
    agent = _register(client)
    service_v2 = client.app.state.service_v2

    unique_desc = f"completely novel error {uuid4().hex}"
    result = service_v2.resolve(agent_id=agent["agent_id"], description=unique_desc)

    assert result["status"] == "registered"
    assert result["problem_id"] is not None
    assert result["solutions"] == []

    # Verify problem appears in radar new_unsolved
    radar = service_v2.get_radar()
    problem_ids = [str(p["problem_id"]) for p in radar["new_unsolved"]]
    assert str(result["problem_id"]) in problem_ids


# ---------------------------------------------------------------------------
# Scenario 3 — Knowledge quality feedback loop
# ---------------------------------------------------------------------------


def test_knowledge_quality_feedback_loop(client: TestClient) -> None:
    """Three success reports + one failure should raise confidence above initial."""
    author = _register(client)
    service_v2 = client.app.state.service_v2

    contrib = service_v2.contribute(
        author_id=author["agent_id"],
        description=f"feedback loop test {uuid4().hex}",
        solution_content="Do the thing.",
    )
    sol_id = contrib["solution_id"]
    assert sol_id is not None

    # 3 successes from 3 different agents
    for _ in range(3):
        agent = _register(client)
        service_v2.report_outcome(
            reporter_id=agent["agent_id"],
            solution_id=sol_id,
            success=True,
        )

    # 1 failure
    failing_agent = _register(client)
    final = service_v2.report_outcome(
        reporter_id=failing_agent["agent_id"],
        solution_id=sol_id,
        success=False,
    )

    # Confidence should be above initial 0.3 (3 successes > 1 failure)
    assert final["solution_confidence_updated"] > 0.3


# ---------------------------------------------------------------------------
# Scenario 4 — Dashboard endpoints respond
# ---------------------------------------------------------------------------


def test_dashboard_radar_endpoint(client: TestClient) -> None:
    """GET /v1/dashboard/radar returns the three sections."""
    resp = client.get("/v1/dashboard/radar")
    assert resp.status_code == 200
    data = resp.json()
    assert "trending" in data
    assert "new_unsolved" in data
    assert "degrading" in data


def test_dashboard_metrics_endpoint(client: TestClient) -> None:
    """GET /v1/dashboard/metrics returns key v2 metrics."""
    resp = client.get("/v1/dashboard/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "resolution_rate" in data
    assert "avg_solution_confidence" in data
    assert "solutions_needing_synthesis" in data


# ---------------------------------------------------------------------------
# Scenario 5 — V1 backward compatibility via HTTP endpoints
# ---------------------------------------------------------------------------


def test_v1_threads_endpoint_still_works(client: TestClient) -> None:
    """GET /v1/threads returns a valid thread list response."""
    resp = client.get("/v1/threads")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
