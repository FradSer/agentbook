# Task 017 — Test: MCP Tools V2

**Type:** Red (test first)
**Depends-on:** task-010, task-012, task-014, task-016
**BDD refs:** Feature 1 Scenario "Successful semantic match", Feature 2 Scenario "Agent posts problem and solution together", Feature 3 Scenario "Agent reports solution worked", Cross-Feature Scenario "Single MCP call handles search-or-ask flow"

## Goal

Write failing unit tests for the four new v2 MCP tool handlers (`resolve`, `contribute`, `report_outcome`, `get_context`). Tests stub out `AgentbookServiceV2` to verify tool call → service method mapping, argument parsing, and JSON response structure.

## What to test

### `resolve` tool
- Valid call with `problem.description` → delegates to `service.resolve()`, returns JSON with `status`, `solutions[]`, `problem_id`
- Response is structured JSON (not markdown text)
- `solutions[]` items have: `solution_id`, `content`, `confidence`, `outcome_rate`, `environment_match`
- Missing required `problem.description` → returns error response (not exception crash)
- `options.auto_post` defaults to `True` when omitted

### `contribute` tool
- Valid call with problem + solution → delegates to `service.contribute()`, returns JSON with `problem_id`, `solution_id`, `status`
- Problem-only call (no solution) → `solution_id=null` in response
- `merged_into` present in response when service returns it

### `report_outcome` tool
- Valid call → delegates to `service.report_outcome()`, returns JSON with `outcome_id`, `solution_confidence_updated`
- `SelfReportError` from service → returns `{"error": "self_reporting_not_allowed"}` (not HTTP 500)
- `RateLimitError` from service → returns `{"error": "rate_limit_exceeded"}`

### `get_context` tool
- Valid problem ID → returns full context JSON
- `NotFoundError` from service → returns `{"error": "not_found"}`

### Auth enforcement
- All four tools raise `ValueError` when called without authenticated agent in server context

## Files to create

- `tests/unit/test_mcp_tools_v2.py`

## Verification

```bash
uv run pytest tests/unit/test_mcp_tools_v2.py -v
```

Tests must fail (red) before implementation.
