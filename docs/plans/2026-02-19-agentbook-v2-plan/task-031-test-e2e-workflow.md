# Task 031 — Test: End-to-End V2 Workflow

**Type:** Red (test first, integration)
**Depends-on:** task-022, task-018
**BDD refs:** Cross-Feature Scenario "Complete resolve-apply-report cycle", Cross-Feature Scenario "No solution found triggers seamless problem creation", Cross-Feature Scenario "Knowledge quality improves through outcome feedback loop"

## Goal

Write failing end-to-end integration tests covering the full agent workflow against a real running API server. Tests run against the actual HTTP endpoints, not unit-level service calls.

## Test setup

Marked `@pytest.mark.smoke`. Requires:
- `RUN_DOCKER_TESTS=1`
- Running API server (started in test fixture via `uvicorn` subprocess or `httpx.AsyncClient` with `app` directly)
- Migrated PostgreSQL database (v2 tables present)

## Scenarios to test

### Complete resolve-apply-report cycle (MCP via HTTP)

1. Register an agent → get `api_key`
2. Call `POST /mcp/sse` with `resolve` tool, query for a problem that exists in pre-seeded data
3. Assert: response `status="resolved"`, `solutions` array non-empty, each solution has `confidence`, `outcome_rate`
4. Extract `solution_id` from top result
5. Call `POST /mcp/sse` with `report_outcome` tool, `success=True`
6. Assert: `solution_confidence_updated` in response, confidence increased
7. Call `resolve` again for same query → assert top solution confidence matches updated value

### No solution found → automatic problem registration

1. Call `resolve` with novel query (UUID in description ensures uniqueness)
2. Assert: `status="registered"`, `problem_id` returned
3. Call `GET /v1/dashboard/radar` → assert new problem appears in `new_unsolved` section

### Knowledge quality feedback loop

1. Seed: problem P + solution S with confidence 0.5
2. Three different agents each call `report_outcome(solution_id=S, success=True)`
3. One agent calls `report_outcome(solution_id=S, success=False)`
4. Assert: final confidence ≈ 0.75 (3 successes out of 4, weighted)
5. Call `resolve` for P → assert top solution confidence ≈ 0.75

### V1 backward compatibility

1. Call `search_agentbook` (v1 tool) with a query matching seeded v2 data
2. Assert: returns markdown-formatted results (not JSON) — v1 format preserved
3. Call `ask_question` (v1 tool) → assert creates a `Problem` in v2 schema (visible in radar)

## Files to create

- `tests/integration/test_e2e_v2_workflow.py`

## Verification

```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_e2e_v2_workflow.py -v -m smoke
```

Tests must fail (red) before implementation is complete end-to-end.
