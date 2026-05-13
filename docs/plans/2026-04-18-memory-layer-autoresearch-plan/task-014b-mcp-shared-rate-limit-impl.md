# Task 014b: MCP shared rate-limit bucket across legacy and new names — Green

**depends-on**: 014a

## Description

Key the MCP rate-limit bucket on the canonical name (`recall`), not the requested name. `search` and `recall` share one bucket; similarly for future rename pairs if their rate limits ever differ.

## Execution Context

**Task Number**: 014b of 41
**Phase**: MCP rename
**Prerequisites**: Task 014a red tests committed.

## BDD Scenario

(Same as task 014a — see `bdd-specs.md`.)

## Files to Modify/Create

- Modify: `backend/presentation/mcp/tools.py::dispatch_tool` — rate-limit key uses `_CANONICAL[name]` not `name`.
- Modify: `backend/core/mcp_rate_limit.py::mcp_rate_key` if it currently includes the tool name.

## Steps

### Step 1: Canonicalise rate-limit key
- Where the existing code calls `search_limiter.hit(mcp_rate_key(agent, remote_addr))`, prepend the canonical tool name so the bucket is shared: `mcp_rate_key(agent, remote_addr, tool=_CANONICAL[name])`.
- Update `mcp_rate_key` to accept a `tool` parameter that defaults to the canonical name.

### Step 2: Green
- Run 014a tests + broader MCP suite.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_mcp_shared_rate_limit.py -v
uv run pytest backend/tests/unit/test_mcp_tool_handlers.py
```

## Success Criteria

- Both 014a scenarios pass.
- No regression in existing rate-limit tests.
