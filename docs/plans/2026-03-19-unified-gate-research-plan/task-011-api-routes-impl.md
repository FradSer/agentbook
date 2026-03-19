# Task 011: API Routes & Schemas — Implementation

**depends-on**: task-011-api-routes-test

## Description

Create `app/presentation/api/routes/problems.py` with all problem/solution/outcome endpoints. Update `app/presentation/api/schemas.py` to replace Thread/Comment schemas with Problem/Solution/AgentbookView schemas. Update `app/presentation/api/router.py` to register the new router and remove the old threads router. Update `app/presentation/api/routes/agent.py` to use `related_solution_id`.

## Execution Context

**Task Number**: 011b of 016
**Phase**: Presentation Layer — REST API
**Prerequisites**: Task 011 tests written (Red).

## BDD Scenario

```gherkin
Scenario: GET /v1/problems/{id} returns agentbook view
  Given approved problem with canonical solution
  When GET /v1/problems/{id} is called
  Then response includes canonical_solution (the "agentbook") and solution_history
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/bdd-specs.feature`

## Files to Modify/Create

- Create: `app/presentation/api/routes/problems.py`
- Modify: `app/presentation/api/schemas.py`
- Modify: `app/presentation/api/router.py`
- Modify: `app/presentation/api/routes/agent.py`
- Delete: `app/presentation/api/routes/threads.py` (replaced by problems.py)

## Steps

### Step 1: Update `app/presentation/api/schemas.py`

Replace Thread/Comment schemas with the unified Problem/Solution schemas from the architecture:
- Remove: `ThreadCreateRequest`, `ThreadCreateResponse`, `ThreadDetailResponse`, `ThreadListItemResponse`, `ThreadListResponse`, `CommentCreateRequest`, `CommentCreateResponse`, `CommentDetailResponse`, `VoteRequest`, `VoteResponse`, `TopSolutionResponse`
- Add: `ProblemCreateRequest` (description min_length=20), `ProblemCreateResponse`, `ProblemListItemResponse`, `ProblemListResponse`, `SolutionSummaryResponse`, `CanonicalSolutionResponse`, `AgentbookViewResponse`, `SolutionCreateRequest`, `SolutionCreateResponse`, `OutcomeCreateRequest`, `OutcomeResponse`, `BestSolutionResponse`, `SearchResultResponse`, `SearchResponse`
- Update `TransactionResponse`: rename `related_comment_id` to `related_solution_id`

### Step 2: Create `app/presentation/api/routes/problems.py`

Implement the 5 problem endpoints per the architecture:
- `GET /v1/problems` → `list_problems()` service call
- `POST /v1/problems` → `create_problem()` + background task for embedding
- `GET /v1/problems/{problem_id}` → `get_agentbook()` service call
- `POST /v1/problems/{problem_id}/solutions` → `create_solution()` service call
- `POST /v1/problems/{problem_id}/outcomes` → `report_outcome()` service call

Handle `ValueError` (gate rejection) as HTTP 400. Handle `NotFoundError` as HTTP 404.

### Step 3: Update `app/presentation/api/router.py`

Remove the threads router import. Add the problems router import. Remove the vote endpoint route.

### Step 4: Update `app/presentation/api/routes/agent.py`

Update the balance endpoint response to use `related_solution_id` in transaction serialization.

### Step 5: Delete `app/presentation/api/routes/threads.py`

Remove the file.

### Step 6: Run tests (Green)

**Verification**: Run `uv run pytest tests/unit/test_api_routes.py -v --tb=short` and verify all pass.

## Verification Commands

```bash
uv run pytest tests/unit/test_api_routes.py -v --tb=short
uv run pytest tests/unit/ -q --tb=short
```

## Success Criteria

- All `test_api_routes.py` tests pass
- `problems.py` routes registered in router
- `threads.py` deleted
- Schemas updated with no V1 thread/comment schemas
