# Task 012b: MCP tool aliasing and deprecation metadata — Green

**depends-on**: 012a

## Description

Register four new `types.Tool` entries (`recall`, `remember`, `trace`, `verify`) alongside the legacy four. Add a `_wrap_with_meta` helper stamping `_meta.deprecated = bool(name in LEGACY_NAMES)` and, when deprecated, `_meta.replacement` and `_meta.sunset = "2026-10-18"`. Dispatcher routes both names to the same handler.

(Note: `verify` is *registered* here but its sandbox-enqueue semantics are added in task 013b. Here we only wire the name.)

## Execution Context

**Task Number**: 012b of 41
**Phase**: MCP rename
**Prerequisites**: Task 012a red tests committed.

## BDD Scenario

(Same four scenarios as task 012a — see `bdd-specs.md`.)

## Files to Modify/Create

- Modify: `backend/presentation/mcp/tools.py::TOOL_DEFINITIONS` — append recall, remember, trace, verify.
- Modify: `backend/presentation/mcp/tools.py::dispatch_tool` — add synonym branches.
- Modify: `backend/presentation/mcp/tools.py` — add `LEGACY_NAMES = {"search", "contribute", "report", "inspect"}`, `_SUNSET = "2026-10-18"`, `_wrap_with_meta(response, name)`.

## Steps

### Step 1: Add new tool definitions
- For each new tool name, copy the legacy `types.Tool` definition with identical `inputSchema`. Update the `description` to the memory-shaped language. The legacy tool descriptions mutate to prefix `"[DEPRECATED - use <new>] "`.

### Step 2: Update dispatcher
- Canonical mapping:
  ```python
  _CANONICAL = {
      "search": "recall", "recall": "recall",
      "contribute": "remember", "remember": "remember",
      "report": "report",  # no rename in this pass
      "inspect": "trace", "trace": "trace",
      "verify": "verify",  # new semantics in 013b
  }
  ```
- Dispatch on the canonical name. After the handler returns, call `_wrap_with_meta(response, requested_name)`.

### Step 3: `_wrap_with_meta`
- Helper:
  ```python
  def _wrap_with_meta(response: list[dict], requested_name: str) -> list[dict]:
      # Response is [{type: "text", text: json.dumps(...)}].
      body = json.loads(response[0]["text"])
      deprecated = requested_name in LEGACY_NAMES
      body.setdefault("_meta", {})
      body["_meta"]["deprecated"] = deprecated
      if deprecated:
          body["_meta"]["replacement"] = _CANONICAL[requested_name]
          body["_meta"]["sunset"] = _SUNSET
      response[0]["text"] = json.dumps(body, default=str)
      return response
  ```

### Step 4: Green
- Run 012a tests. Smoke existing `test_mcp_tool_handlers.py` and `test_mcp_sse_smoke.py`.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_mcp_tool_aliasing.py -v
uv run pytest backend/tests/unit/test_mcp_tool_handlers.py
uv run pytest backend/tests/unit/test_mcp_sse_smoke.py
```

## Success Criteria

- All 012a scenarios pass.
- Legacy MCP clients still receive correct payloads (byte-identical body + added `_meta`).
- `tools/list` response length grew by exactly 4 entries.
