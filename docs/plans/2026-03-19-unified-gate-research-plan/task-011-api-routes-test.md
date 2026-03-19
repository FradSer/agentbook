# Task 011: API Routes & Schemas — Test

**depends-on**: task-008-service-agentbook-view-impl

## Description

Write unit/integration tests for the new problems REST API. Tests cover the Pydantic schemas (request validation, response serialization) and the FastAPI route handlers. Uses the in-memory service (via TestClient with overridden dependencies).

## Execution Context

**Task Number**: 011a of 016
**Phase**: Presentation Layer — REST API
**Prerequisites**: Service agentbook view implemented (Task 008). Tasks 009 and 010 can be in parallel.

## BDD Scenario

```gherkin
Scenario: POST /v1/problems creates a problem
  Given a registered agent with valid API key
  When POST /v1/problems is called with valid description
  Then response status is 201
  And response body has problem_id and status="processing"

Scenario: GET /v1/problems returns only approved problems
  Given 2 approved problems and 1 pending problem
  When GET /v1/problems is called
  Then response has 2 results

Scenario: GET /v1/problems/{id} returns agentbook view
  Given approved problem "prob-1" with approved solution "sol-1"
  When GET /v1/problems/prob-1 is called
  Then response has canonical_solution or solution_history
  And response includes canonical_solution field

Scenario: POST /v1/problems/{id}/solutions creates a solution
  Given approved problem "prob-1" and authenticated agent
  When POST /v1/problems/prob-1/solutions is called
  Then response status is 201
  And response has solution_id

Scenario: POST /v1/problems requires authentication
  When POST /v1/problems is called without Authorization header
  Then response status is 401

Scenario: ProblemCreateRequest rejects description shorter than 20 chars
  When ProblemCreateRequest is constructed with description "short"
  Then Pydantic raises a ValidationError
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature` (Feature 1 + Feature 2 — endpoint scenarios)

## Files to Modify/Create

- Create: `tests/unit/test_api_routes.py`

## Steps

### Step 1: Write Pydantic schema tests (Red)

In `tests/unit/test_api_routes.py`, test the request/response schemas:
1. `ProblemCreateRequest(description="short")` raises `ValidationError` (min_length=20)
2. `ProblemCreateRequest(description="x" * 20)` succeeds
3. `AgentbookViewResponse` can be constructed from a dict with `canonical_solution=None`
4. `SolutionCreateRequest` validates `content` min_length=10
5. `OutcomeCreateRequest` validates `solution_id` as UUID

### Step 2: Write FastAPI route handler tests

Use `TestClient(app)` with overridden `get_service` dependency (inject an in-memory service):
1. `POST /v1/problems` → 201 with `problem_id`
2. `GET /v1/problems` → 200 with filtered list (only approved)
3. `GET /v1/problems/{id}` → 200 with agentbook view
4. `POST /v1/problems/{id}/solutions` → 201 with `solution_id`
5. `POST /v1/problems/{id}/outcomes` → 200 with outcome result
6. Unauthenticated POST → 401
7. Invalid problem_id in route → 404

**Verification**: Run `uv run pytest tests/unit/test_api_routes.py --tb=short` and verify failures (routes don't exist yet).

## Verification Commands

```bash
uv run pytest tests/unit/test_api_routes.py -v --tb=short
```

## Success Criteria

- All tests fail (Red phase complete)
- Tests cover all new endpoint scenarios and schema validation
