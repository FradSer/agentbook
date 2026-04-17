# Task 012a: MCP tool aliasing and deprecation metadata — Red

**depends-on**: (none)

## Description

Red tests for the MCP tool renaming. New tools `recall`, `remember`, `trace` exposed alongside legacy `search`, `contribute`, `inspect`. Both names return byte-identical payloads apart from `_meta`. `tools/list` advertises both. Anonymous `remember` is forbidden like `contribute` today.

## Execution Context

**Task Number**: 012a of 41
**Phase**: MCP rename
**Prerequisites**: none (pure presentation layer).

## BDD Scenario

```gherkin
Scenario: New tool recall is served
  Given an unauthenticated MCP client
  When the client calls "recall" with {"query": "pgvector missing"}
  Then the server returns the same payload shape as legacy "search"
  And the response _meta.deprecated is False

Scenario: Legacy search returns deprecation metadata
  Given any MCP client
  When the client calls "search" with {"query": "pgvector missing"}
  Then the response body equals the response body from calling "recall" with the same args
  And the response _meta contains {deprecated: true, replacement: "recall", sunset: "2026-10-18"}

Scenario: tools/list advertises both names
  When a client calls tools/list
  Then the result includes a tool named "recall" with deprecated=false
  And the result includes a tool named "search" whose description starts with "[DEPRECATED - use recall]"
  And both tools share identical inputSchema

Scenario: Anonymous contribute remains forbidden under the new name
  Given an anonymous MCP client
  When the client calls "remember" with a valid description
  Then the server returns {"error": "unauthorized", "tool": "remember"}
  And no Problem or Solution is persisted
```

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md`

## Files to Modify/Create

- Create: `backend/tests/unit/test_mcp_tool_aliasing.py`

## Steps

### Step 1: Tests
- `test_recall_served_anonymous` — simulate unauthenticated call; assert response structure parity with `search`, `_meta.deprecated == False`.
- `test_search_returns_deprecation_meta` — call legacy `search`; assert body equal to `recall` body (apart from `_meta`), `_meta = {"deprecated": true, "replacement": "recall", "sunset": "2026-10-18"}`.
- `test_tools_list_advertises_both` — call `tools/list`; assert both tools present; assert legacy descriptions prefixed with `[DEPRECATED - use recall]`; assert `inputSchema` equality (JSON deep-equal).
- `test_remember_anonymous_forbidden` — anonymous `remember` call returns `{"error": "unauthorized", "tool": "remember"}`; assert no `Problem` row created.
- `test_trace_aliased_to_inspect` — parity test for `trace` ↔ `inspect`.

### Step 2: Confirm Red
- All five tests fail because new names do not exist.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_mcp_tool_aliasing.py -v
```

## Success Criteria

- Five failing tests.
- Byte-identity assertion is strict (JSON deep-equal minus `_meta`).
