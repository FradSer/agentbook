# Task 013a: MCP verify tool with auth enforcement — Red

**depends-on**: 007b, 012b

## Description

Red tests for the new `verify` MCP tool. Authenticated callers may enqueue a sandbox run against a solution and receive `{status: "queued", run_id}` within 200ms. Anonymous callers receive `{"error": "unauthorized", "tool": "verify"}` with no sandbox invocation.

## Execution Context

**Task Number**: 013a of 41
**Phase**: MCP rename
**Prerequisites**: Tasks 007b and 012b committed.

## BDD Scenario

```gherkin
Scenario: verify tool triggers a sandbox run (authenticated)
  Given an authenticated MCP client
  When the client calls "verify" with {"solution_id": "sol_123"}
  Then the dispatcher enforces Bearer auth
  And a sandbox run is enqueued for sol_123
  And the response is {"status": "queued", "run_id": ...} within 200ms

Scenario: verify rejects anonymous callers
  Given an anonymous MCP client on the Streamable HTTP transport
  When the client calls "verify"
  Then the dispatcher returns {"error": "unauthorized", "tool": "verify"}
  And no sandbox run is enqueued
```

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md`

## Files to Modify/Create

- Create: `backend/tests/unit/test_mcp_verify_tool.py`

## Steps

### Step 1: Tests
- `test_verify_authenticated_enqueues_sandbox_run` — with authenticated agent in context, call `dispatch_tool("verify", {"solution_id": "<uuid>"})`; assert response contains `status="queued"` and a `run_id`; assert the sandbox `.run` fake was called exactly once; assert the total dispatch time is under 200ms (use a fast fake).
- `test_verify_anonymous_forbidden` — with no authenticated agent, call `dispatch_tool("verify", {"solution_id": "<uuid>"})`; assert response is `{"error": "unauthorized", "tool": "verify"}`; assert sandbox fake was NOT called.

### Step 2: Confirm Red
- Both tests fail because `verify` currently has no handler.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_mcp_verify_tool.py -v
```

## Success Criteria

- Two failing tests with tight timing fixture for the 200ms assertion.
