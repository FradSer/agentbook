# Task 018 — Implement: MCP Tools V2

**Type:** Green (implementation)
**Depends-on:** task-017
**BDD refs:** Feature 1, Feature 2, Feature 3, Cross-Feature E2E scenarios

## Goal

Create `app/presentation/mcp/tools_v2.py` with `register_tools_v2(server)` function containing all four v2 MCP tools. Tools must return structured JSON (not markdown text like v1 tools).

## What to implement

### `register_tools_v2(server: Server) -> None`

Register four tools:

**`resolve` tool handler:**
- Parse `problem` dict from arguments — require `description` (min 1 char), validate other fields are optional
- Call `service.resolve(requester_id=agent.agent_id, problem=problem, options=options)`
- On `ValueError` → return `[{"type": "text", "text": json.dumps({"error": "invalid_input", "detail": str(e)})}]`
- On success → return `[{"type": "text", "text": json.dumps(result)}]`

**`contribute` tool handler:**
- Parse `problem` and optional `solution` dicts
- Call `service.contribute(...)`
- On `ValueError` → return error JSON

**`report_outcome` tool handler:**
- Parse `solution_id`, `outcome` dict
- Call `service.report_outcome(...)`
- On `SelfReportError` → `{"error": "self_reporting_not_allowed"}`
- On `RateLimitError` → `{"error": "rate_limit_exceeded"}`
- On `NotFoundError` → `{"error": "not_found"}`

**`get_context` tool handler:**
- Parse `id` and optional `include` list
- Call `service.get_context(...)`
- On `NotFoundError` → `{"error": "not_found"}`

### Service injection
Tools access `server._service_v2` (new attribute, set during `app/main.py` startup alongside existing `server._service`).

## Files to create

- `app/presentation/mcp/tools_v2.py`

## Files to modify

- `app/presentation/mcp/router.py` — call `register_tools_v2(server)` alongside existing `register_tools(server)` during MCP server setup
- `app/main.py` — inject `AgentbookServiceV2` instance as `server._service_v2` during startup

## Verification

```bash
uv run pytest tests/unit/test_mcp_tools_v2.py -v
```

All tests from task-017 must pass (green).
