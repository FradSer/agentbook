"""Unit tests for the operator dashboard at GET /v1/dashboard/recurrence-density.

The endpoint surfaces the recurrence-density rollup (recurrence_density,
organic_recurrence, total_independent_queries, and a per-problem list) so an
operator can apply the bootstrap proceed/abandon/green-light gates from the
numbers. It is a public read, consistent with the other ``/v1/dashboard/*``
endpoints. Events are seeded through ``search_problems`` (the real recording
path) so the test exercises end-to-end on the in-memory path.

Feature file: backend/tests/features/recurrence-density.feature.
"""

from __future__ import annotations

from backend.application.service import AgentbookService, CallerContext
from backend.presentation.api.schemas import RecurrenceDensityResponse
from backend.tests.conftest import _build_service

_STRONG_DESC = "Docker daemon socket permission denied; fix via docker group membership"
_STRONG_SIG = (
    "permission denied while trying to connect to the Docker daemon socket "
    "at unix:///var/run/docker.sock"
)
_STRONG_QUERY = _STRONG_SIG
_STRONG_SOLUTION = (
    "Add the user to the docker group and restart the shell session "
    "so the socket becomes group-accessible."
)


def _seed_answered_problem(service: AgentbookService, author_id):
    """Approved problem authored by ``author_id`` with one active solution,
    matchable at the strong/exact tier by ``_STRONG_QUERY``."""
    problem = service.create_problem(
        author_id=author_id,
        description=_STRONG_DESC,
        error_signature=_STRONG_SIG,
    )
    service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content=_STRONG_SOLUTION,
        steps=["add user to docker group", "re-login"],
    )
    return problem


def _client(service: AgentbookService):
    from fastapi.testclient import TestClient

    from backend.main import create_app
    from backend.presentation.api.deps import get_service

    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


def test_recurrence_density_endpoint_surfaces_rollup_shape() -> None:
    """Recorded events surface as a 200 rollup validating against the schema."""
    service, author_id = _build_service()
    problem = _seed_answered_problem(service, author_id)
    querier = service.register_agent("claude-sonnet-4-5")[0].agent_id
    service.search_problems(
        query=_STRONG_QUERY,
        limit=10,
        caller=CallerContext(agent_id=querier),
    )

    client = _client(service)
    response = client.get("/v1/dashboard/recurrence-density")

    assert response.status_code == 200
    body = response.json()
    # The body must conform to the typed response contract.
    model = RecurrenceDensityResponse.model_validate(body)
    assert isinstance(model.recurrence_density, float)
    assert isinstance(model.organic_recurrence, float)
    assert isinstance(model.total_independent_queries, int)
    assert model.total_independent_queries == 1
    assert model.recurrence_density > 0.0

    assert len(model.problems) == 1
    row = model.problems[0]
    assert row.problem_id == str(problem.problem_id)
    assert row.query_count == 1
    assert isinstance(row.organic_recurrence, float)


def test_recurrence_density_endpoint_empty_returns_zero_rollup() -> None:
    """An instrument with no recorded events returns a 200 zero rollup."""
    service, _ = _build_service()

    client = _client(service)
    response = client.get("/v1/dashboard/recurrence-density")

    assert response.status_code == 200
    model = RecurrenceDensityResponse.model_validate(response.json())
    assert model.recurrence_density == 0.0
    assert model.organic_recurrence == 0.0
    assert model.total_independent_queries == 0
    assert model.problems == []


def test_recurrence_density_endpoint_is_public_no_auth() -> None:
    """The endpoint is reachable without an Authorization header (public read)."""
    service, author_id = _build_service()
    _seed_answered_problem(service, author_id)
    querier = service.register_agent("claude-sonnet-4-5")[0].agent_id
    service.search_problems(
        query=_STRONG_QUERY,
        limit=10,
        caller=CallerContext(agent_id=querier),
    )

    client = _client(service)
    # No Authorization header attached -- mirrors /radar, /metrics, /usage.
    response = client.get("/v1/dashboard/recurrence-density")
    assert response.status_code == 200
    assert "Authorization" not in client.headers
