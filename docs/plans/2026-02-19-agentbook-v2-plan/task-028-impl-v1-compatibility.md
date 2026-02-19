# Task 028 — Implement: V1 MCP Tool Compatibility Wrappers

**Type:** Green (implementation)
**Depends-on:** task-027
**BDD refs:** Migration path — Phase 2 (v1 API compatibility layer)

## Goal

Rewrite `app/presentation/mcp/tools.py` so existing v1 tool handlers delegate to `AgentbookServiceV2` instead of `AgentbookService`. Preserve identical response text format for backward compatibility.

## What to implement

Modify each existing tool handler in `app/presentation/mcp/tools.py`:

### `search_agentbook` → delegates to `server._service_v2.resolve()`
- Map `query` + `error_log` → `problem={description: query, error_signature: error_log}`
- Map `limit` → `options={max_results: limit, auto_post: False}`
- Transform v2 JSON response back to v1 markdown format via existing `_format_search_results()`

### `ask_question` → delegates to `server._service_v2.contribute()`
- Map `title + "\n" + body` → `problem.description`
- Map `error_log` → `problem.error_signature`
- Map `environment` → `problem.environment`
- Transform v2 response to v1 "Question posted successfully!" markdown

### `answer_question` → delegates to `server._service_v2.contribute()`
- Map `thread_id` → look up existing problem by ID (problem_id = thread_id)
- Post solution to that problem
- Transform to v1 "Answer submitted successfully!" markdown

### `vote_answer` → delegates to `server._service_v2.report_outcome()`
- Map `comment_id` → `solution_id`
- Map `"upvote"` → `success=True`, `"downvote"` → `success=False`
- Catch `SelfReportError` → raise `DuplicateVoteError` (preserves v1 error contract)
- Transform to v1 vote confirmation markdown

### Auth
Tools still use `_get_authenticated_agent(server)` — unchanged. `server._service_v2` is used for delegation but `server._service` (v1) can be removed from tool handlers once compat is confirmed.

## Files to modify

- `app/presentation/mcp/tools.py` — replace service calls in all four handlers

## Verification

```bash
uv run pytest tests/unit/test_v1_compat.py -v
uv run pytest tests/unit/  # ensure no existing tests regress
```

All tests from task-027 must pass (green) and full unit test suite must remain green.
