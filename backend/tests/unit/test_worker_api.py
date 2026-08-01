from __future__ import annotations

from uuid import uuid4

from backend.core.config import settings
from backend.domain.models import Agent, Problem
from backend.presentation.api.deps import get_service


def test_worker_queue_requires_dedicated_token(client_and_key):
    client, _ = client_and_key
    settings.worker_api_key = "worker-secret"
    try:
        assert client.get("/v1/internal/worker/review-queue").status_code == 401
        assert (
            client.get(
                "/v1/internal/worker/review-queue",
                headers={"Authorization": "Bearer worker-secret"},
            ).status_code
            == 200
        )
    finally:
        settings.worker_api_key = None


def test_worker_review_updates_pending_problem(client_and_key):
    client, _ = client_and_key
    service = client.app.dependency_overrides[get_service]()
    author = uuid4()
    service._agents.add(
        Agent(agent_id=author, api_key_hash="worker-test", model_type="test")
    )
    problem = Problem(author_id=author, description="A pending worker-review problem")
    problem.review_status = None
    service._problems.add(problem)
    settings.worker_api_key = "worker-secret"
    headers = {"Authorization": "Bearer worker-secret"}
    try:
        queued = client.get("/v1/internal/worker/review-queue", headers=headers)
        assert queued.status_code == 200
        assert queued.json()["problems"][0]["problem_id"] == str(problem.problem_id)

        reviewed = client.post(
            f"/v1/internal/worker/content/{problem.problem_id}/review",
            headers=headers,
            json={"status": "approved", "reason": "genuine report"},
        )
        assert reviewed.status_code == 200
        assert service._problems.get(problem.problem_id).review_status == "approved"
    finally:
        settings.worker_api_key = None
