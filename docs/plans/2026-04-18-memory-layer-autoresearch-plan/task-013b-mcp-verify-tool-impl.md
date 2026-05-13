# Task 013b: MCP verify tool with auth enforcement — Green

**depends-on**: 013a

## Description

Implement the `verify` handler and the `AgentbookService.verify_solution(solution_id, agent_id) -> {"status", "run_id"}` method. Handler enforces Bearer auth via `_get_authenticated_agent`. The service method enqueues a sandbox run asynchronously (does NOT block the caller) and returns within 200ms.

## Execution Context

**Task Number**: 013b of 41
**Phase**: MCP rename
**Prerequisites**: Task 013a red tests committed.

## BDD Scenario

(Same two scenarios as task 013a — see `bdd-specs.md`.)

## Files to Modify/Create

- Modify: `backend/presentation/mcp/tools.py::dispatch_tool` — add `verify` branch that calls `_get_authenticated_agent` then `service.verify_solution`.
- Modify: `backend/application/service.py::AgentbookService` — add `verify_solution(solution_id, agent_id) -> dict`.

## Steps

### Step 1: Handler
- In the `verify` branch of `dispatch_tool`:
  ```python
  if name == "verify":
      agent = _get_authenticated_agent(server)
      solution_id = UUID(arguments["solution_id"])
      return _json_response(service.verify_solution(solution_id, agent.agent_id))
  ```

### Step 2: Service method signature
- Interface:
  ```python
  def verify_solution(self, solution_id: UUID, agent_id: UUID) -> dict:
      """Enqueue a sandbox run asynchronously and return {status, run_id}."""
  ```
- Semantics:
  - Look up the solution's problem; if no `error_signature`, return `{"error": "not_verifiable", "reason": "no error_signature"}`.
  - Run dedup + budget + circuit-breaker + concurrency gates from tasks 008/009/010.
  - If any gate rejects, return the corresponding error envelope.
  - Otherwise, spawn a background task (`asyncio.create_task` or `ThreadPoolExecutor.submit`) that calls `self.sandbox.run(...)`, awaits it, and persists the verified outcome via `_emit_verified_outcome`.
  - Return `{"status": "queued", "run_id": "<uuid>"}` immediately.

### Step 3: Rate-limit assertion
- The per-agent budget (task 009b) must key on the `verify` tool's `agent_id`. Ensure the budget is shared between `verify` and sandbox invocations from `improve_solution` so a single agent cannot bypass by using both paths.

### Step 4: Green
- Run 013a tests. Smoke broader MCP tests.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_mcp_verify_tool.py -v
uv run pytest backend/tests/unit/test_mcp_tool_handlers.py
uv run ruff check backend/presentation/mcp/tools.py backend/application/service.py
```

## Success Criteria

- Both 013a scenarios pass.
- Anonymous call returns exact error payload and does not invoke sandbox.
- Authenticated call returns within 200ms with `status="queued"`.
- Per-agent sandbox budget shared across `verify` and `improve_solution`.
