# Task 014a: MCP shared rate-limit bucket across legacy and new names — Red

**depends-on**: 012b

## Description

Red test: the 30/minute rate-limit bucket for `search` is shared with `recall`. An agent that has consumed its budget on `search` must see `rate_limit_exceeded` when it falls through to `recall`, and vice versa.

## Execution Context

**Task Number**: 014a of 41
**Phase**: MCP rename
**Prerequisites**: Task 012b committed.

## BDD Scenario

```gherkin
Scenario: Rate-limit bucket shared across new and legacy search
  Given search has rate limit 30/minute per agent
  And an agent calls "search" 30 times in 60s
  When the agent calls "recall" once more
  Then the server returns {"error": "rate_limit_exceeded"}
  And the shared bucket is the decision source
```

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md`

## Files to Modify/Create

- Modify: `backend/tests/unit/test_mcp_tool_aliasing.py` — add one scenario, OR create a dedicated file.
- Create: `backend/tests/unit/test_mcp_shared_rate_limit.py` (preferred to keep aliasing tests focused).

## Steps

### Step 1: Test
- `test_shared_bucket_across_search_and_recall` — with a controlled clock, call `dispatch_tool("search", {"query": "x"})` 30 times as the same agent; call `dispatch_tool("recall", {"query": "x"})` once; assert response body has `error == "rate_limit_exceeded"`.
- `test_shared_bucket_other_direction` — call `recall` 30 times; then `search` once; same rejection.

### Step 2: Confirm Red
- Tests fail because the current rate-limit logic in `dispatch_tool` keys on the tool name literally, not the canonical name.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_mcp_shared_rate_limit.py -v
```

## Success Criteria

- Two failing tests.
