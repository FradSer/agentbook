"""Parametrized E2E matrix: >=100 full-stack workflows against PostgreSQL.

Each case exercises register → contribute → resolve → dashboard → report on a
unique problem derived from the simulation corpus templates.

Requires: RUN_DOCKER_TESTS=1 and DATABASE_URL with migrations applied.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.tests.simulation.stress_agents import PROBLEM_TEMPLATES

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.e2e,
    pytest.mark.skipif(
        os.getenv("RUN_DOCKER_TESTS") != "1",
        reason="Set RUN_DOCKER_TESTS=1 to run integration tests",
    ),
]

E2E_CASE_COUNT = 100


def _register(client: TestClient) -> dict:
    resp = client.post("/v1/auth/register", json={"model_type": "claude"})
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.parametrize("case_index", range(E2E_CASE_COUNT))
def test_e2e_contribute_search_report_workflow(
    client: TestClient, case_index: int
) -> None:
    """Full agent workflow: seed knowledge, recall via search, report outcome."""
    template = PROBLEM_TEMPLATES[case_index % len(PROBLEM_TEMPLATES)]
    run_id = uuid4().hex[:8]
    description = f"{template['description']} [e2e-{case_index}-{run_id}]"

    author = _register(client)
    reporter = _register(client)
    service = client.app.state.service

    contrib = service.contribute(
        author_id=author["agent_id"],
        description=description,
        error_signature=template.get("error_signature"),
        tags=list(template.get("tags") or []),
        solution_content=f"E2E fix for case {case_index}: apply documented remediation.",
    )
    solution_id = contrib["solution_id"]
    assert solution_id is not None
    assert contrib["status"] in (
        "knowledge_created",
        "problem_created",
        "similar_exists",
    )

    resolve = service.resolve(
        agent_id=reporter["agent_id"],
        description=description,
    )
    assert resolve["status"] in ("resolved", "registered", "no_solutions")

    metrics_resp = client.get("/v1/dashboard/metrics")
    assert metrics_resp.status_code == 200
    assert "resolution_rate" in metrics_resp.json()

    report = service.report_outcome(
        reporter_id=reporter["agent_id"],
        solution_id=solution_id,
        success=case_index % 5 != 0,
        notes=f"e2e matrix case {case_index}",
    )
    assert report["status"] == "reported"
    assert report["solution_confidence_updated"] >= 0.0
