from __future__ import annotations

from uuid import uuid4

from backend.core.config import settings
from backend.domain.models import Agent, Problem, Solution
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


def test_worker_review_rejects_secret_in_pending_problem_metadata(client_and_key):
    """Legacy pending records must not publish a secret after model approval."""
    client, _ = client_and_key
    service = client.app.dependency_overrides[get_service]()
    author = uuid4()
    service._agents.add(
        Agent(agent_id=author, api_key_hash="worker-test", model_type="test")
    )
    problem = Problem(
        author_id=author,
        description="A legacy pending problem with otherwise valid details",
        environment={"token": "ghp_abcdefghijklmnopqrstuvwxyz1234567890"},
    )
    problem.review_status = None
    service._problems.add(problem)
    settings.worker_api_key = "worker-secret"
    try:
        reviewed = client.post(
            f"/v1/internal/worker/content/{problem.problem_id}/review",
            headers={"Authorization": "Bearer worker-secret"},
            json={"status": "approved", "reason": "genuine report"},
        )
        assert reviewed.status_code == 200
        assert reviewed.json()["status"] == "rejected"
        assert reviewed.json()["reason"] == "secret_detected"
        assert service._problems.get(problem.problem_id).review_status == "rejected"
    finally:
        settings.worker_api_key = None


def test_worker_review_rejects_secret_in_pending_solution_metadata(client_and_key):
    """Legacy solution metadata must receive the same secret gate as inserts."""
    client, _ = client_and_key
    service = client.app.dependency_overrides[get_service]()
    author = uuid4()
    service._agents.add(
        Agent(agent_id=author, api_key_hash="worker-test", model_type="test")
    )
    problem = Problem(author_id=author, description="A parent problem for review")
    service._problems.add(problem)
    solution = Solution(
        problem_id=problem.problem_id,
        author_id=author,
        content="A valid pending solution body with sufficient detail.",
        verification=[{"token": "ghp_abcdefghijklmnopqrstuvwxyz1234567890"}],
    )
    solution.review_status = None
    service._solutions.add(solution)
    settings.worker_api_key = "worker-secret"
    try:
        reviewed = client.post(
            f"/v1/internal/worker/content/{solution.solution_id}/review",
            headers={"Authorization": "Bearer worker-secret"},
            json={"status": "approved", "reason": "genuine solution"},
        )
        assert reviewed.status_code == 200
        assert reviewed.json()["status"] == "rejected"
        assert reviewed.json()["reason"] == "secret_detected"
        assert service._solutions.get(solution.solution_id).review_status == "rejected"
    finally:
        settings.worker_api_key = None


def test_worker_review_cannot_restore_removed_problem(client_and_key):
    """A worker verdict must never undo an operator takedown."""
    client, _ = client_and_key
    service = client.app.dependency_overrides[get_service]()
    author = uuid4()
    service._agents.add(
        Agent(agent_id=author, api_key_hash="worker-test", model_type="test")
    )
    problem = Problem(author_id=author, description="A removed problem must stay removed")
    problem.review_status = "removed"
    service._problems.add(problem)
    settings.worker_api_key = "worker-secret"
    try:
        reviewed = client.post(
            f"/v1/internal/worker/content/{problem.problem_id}/review",
            headers={"Authorization": "Bearer worker-secret"},
            json={"status": "approved", "reason": "genuine report"},
        )
        assert reviewed.status_code == 404
        assert service._problems.get(problem.problem_id).review_status == "removed"
    finally:
        settings.worker_api_key = None


def test_worker_queue_rejects_secret_metadata_before_model_receives_it(client_and_key):
    """The gateway/model must never receive a queued legacy credential."""
    client, _ = client_and_key
    service = client.app.dependency_overrides[get_service]()
    author = uuid4()
    service._agents.add(
        Agent(agent_id=author, api_key_hash="worker-test", model_type="test")
    )
    problem = Problem(
        author_id=author,
        description="A legacy pending problem with otherwise valid details",
        environment={"token": "ghp_abcdefghijklmnopqrstuvwxyz1234567890"},
    )
    problem.review_status = None
    service._problems.add(problem)
    settings.worker_api_key = "worker-secret"
    try:
        queued = client.get(
            "/v1/internal/worker/review-queue",
            headers={"Authorization": "Bearer worker-secret"},
        )
        assert queued.status_code == 200
        assert queued.json()["problems"] == []
        assert service._problems.get(problem.problem_id).review_status == "rejected"
    finally:
        settings.worker_api_key = None


def test_worker_review_cannot_restore_removed_solution(client_and_key):
    """A queued solution must remain removed after an operator takedown."""
    client, _ = client_and_key
    service = client.app.dependency_overrides[get_service]()
    author = uuid4()
    service._agents.add(
        Agent(agent_id=author, api_key_hash="worker-test", model_type="test")
    )
    problem = Problem(author_id=author, description="A parent problem for review")
    service._problems.add(problem)
    solution = Solution(
        problem_id=problem.problem_id,
        author_id=author,
        content="[removed by operator]",
    )
    solution.review_status = "removed"
    service._solutions.add(solution)
    settings.worker_api_key = "worker-secret"
    try:
        reviewed = client.post(
            f"/v1/internal/worker/content/{solution.solution_id}/review",
            headers={"Authorization": "Bearer worker-secret"},
            json={"status": "approved", "reason": "genuine solution"},
        )
        assert reviewed.status_code == 404
        assert service._solutions.get(solution.solution_id).review_status == "removed"
    finally:
        settings.worker_api_key = None
