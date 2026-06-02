"""Contract tests: POST /v1/problems must never silently drop a solution.

Feature file: backend/tests/features/contribute-no-silent-failure.feature

The write contract has exactly two acceptable outcomes for a request that
supplies solution content: attach the solution (201 + solution_count 1) or
reject with a 422 that names the offending field. A 201 with solution_count 0
for a request that supplied a solution is the silent-failure anti-pattern these
tests forbid.
"""

from __future__ import annotations

import json

from backend.tests.conftest import _build_client


def _create_problem(client, api_key, body):
    return client.post(
        "/v1/problems",
        json=body,
        headers={"Authorization": f"Bearer {api_key}"},
    )


def test_inline_solution_is_honored_not_dropped():
    client, api_key = _build_client()
    resp = _create_problem(
        client,
        api_key,
        {
            "description": "SQLAlchemy QueuePool limit reached under load on prod",
            "solution_content": "Increase pool_size and max_overflow on the engine",
        },
    )
    assert resp.status_code == 201, resp.text
    problem_id = resp.json()["problem_id"]

    get_resp = client.get(f"/v1/problems/{problem_id}")
    assert get_resp.status_code == 200
    book = get_resp.json()
    assert book["solution_count"] == 1
    contents = [s.get("content", "") for s in book["solution_history"]]
    assert any("Increase pool_size" in c for c in contents), contents


def test_unknown_solution_field_rejected_with_naming_422():
    client, api_key = _build_client()
    resp = _create_problem(
        client,
        api_key,
        {
            "description": "Redis connection pool exhausted during traffic spike",
            "solution": "raise the maxclients ceiling",
        },
    )
    assert resp.status_code == 422, resp.text
    body = json.dumps(resp.json())
    # Names the offending field.
    assert "solution" in body
    # Advises the two-step path.
    assert "/v1/problems/{id}/solutions" in body or "/solutions" in body


def test_unknown_solution_field_creates_no_problem_with_discarded_solution():
    client, api_key = _build_client()
    before = client.get("/v1/problems").json()
    _create_problem(
        client,
        api_key,
        {
            "description": "Postgres deadlock detected on concurrent upsert path",
            "solution": "retry the transaction with backoff",
        },
    )
    after = client.get("/v1/problems").json()
    # The rejected request must not have silently created a problem.
    assert len(after) == len(before)


def test_alias_solution_content_never_vanishes_silently():
    client, api_key = _build_client()
    resp = _create_problem(
        client,
        api_key,
        {
            "description": "asyncio task was destroyed but it is pending warning",
            "solution_content": "await the task or cancel it before loop close",
        },
    )
    if resp.status_code == 422:
        assert "solution_content" in json.dumps(resp.json())
        return
    assert resp.status_code == 201, resp.text
    problem_id = resp.json()["problem_id"]
    book = client.get(f"/v1/problems/{problem_id}").json()
    assert book["solution_count"] != 0, (
        "201 with solution_count 0 after supplying solution_content "
        "is the silent-failure anti-pattern"
    )


def test_alias_solution_steps_never_vanishes_silently():
    client, api_key = _build_client()
    resp = _create_problem(
        client,
        api_key,
        {
            "description": "Docker build cache invalidated on every COPY layer",
            "solution_content": "order COPY of lockfiles before source for cache reuse",
            "solution_steps": ["copy lockfiles", "install deps", "copy source"],
        },
    )
    if resp.status_code == 422:
        assert "solution_steps" in json.dumps(resp.json())
        return
    assert resp.status_code == 201, resp.text
    problem_id = resp.json()["problem_id"]
    book = client.get(f"/v1/problems/{problem_id}").json()
    assert book["solution_count"] != 0, (
        "201 with solution_count 0 after supplying solution_steps "
        "is the silent-failure anti-pattern"
    )


def test_problem_only_create_self_describes_next_step():
    client, api_key = _build_client()
    resp = _create_problem(
        client,
        api_key,
        {"description": "Webpack chunk hash changes on every deterministic build"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body.get("solution_count", 0) == 0
    affordance = json.dumps(body)
    assert "/v1/problems/{id}/solutions" in affordance or "/solutions" in affordance


def test_solution_create_schema_documents_structured_field_shapes():
    client, _ = _build_client()
    openapi = client.get("/openapi.json").json()
    schema = openapi["components"]["schemas"]["SolutionCreateRequest"]
    schema_text = json.dumps(schema)
    # The verification field documents its inner {command, expected, buggy} shape.
    assert "command" in schema_text
    assert "expected" in schema_text
    assert "buggy" in schema_text
    # environment is documented as an object on the problem-create request.
    problem_schema = json.dumps(
        openapi["components"]["schemas"]["ProblemCreateRequest"]
    )
    assert "os" in problem_schema or "language" in problem_schema


def test_too_short_solution_error_states_the_minimum():
    client, api_key = _build_client()
    # First create a problem to attach the solution to.
    prob = _create_problem(
        client,
        api_key,
        {"description": "Gunicorn worker timeout under slow upstream requests"},
    )
    problem_id = prob.json()["problem_id"]
    resp = client.post(
        f"/v1/problems/{problem_id}/solutions",
        json={"content": "too short"},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert resp.status_code in (400, 422), resp.text
    body = json.dumps(resp.json())
    # States the minimum, mirroring the description validator's wording.
    assert "at least 10 characters" in body
