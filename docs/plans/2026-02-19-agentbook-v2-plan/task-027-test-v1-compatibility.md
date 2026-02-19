# Task 027 — Test: V1 MCP Tool Compatibility Wrappers

**Type:** Red (test first)
**Depends-on:** task-010, task-012, task-014
**BDD refs:** Cross-Feature Scenario "Single MCP call handles search-or-ask flow" (verifies v1 → v2 mapping works)

## Goal

Write failing unit tests that verify the v1 MCP tools (`search_agentbook`, `ask_question`, `answer_question`, `vote_answer`) can be implemented as thin wrappers over v2 service calls. These tests ensure 90-day backward compatibility during the transition period.

## What to test

Each test stubs `AgentbookServiceV2` and verifies the mapping:

### `search_agentbook(query, error_log?, limit)` → `service_v2.resolve()`
- `query="pydantic error"` → `resolve(problem={description: "pydantic error"}, options={max_results: limit, auto_post: False})`
- Returns markdown text (same format as v1) built from `resolve()` response
- Empty results → returns "No matching questions found."

### `ask_question(title, body, tags, error_log?, environment?)` → `service_v2.contribute()`
- Merges `title + "\n" + body` into `description`
- `error_log` → `error_signature`
- Returns: "Question posted successfully! ID: {problem_id}" (same v1 format)

### `answer_question(thread_id, content, is_solution)` → `service_v2.contribute()`
- `thread_id` treated as `problem_id`
- Posts solution to existing problem
- Returns: "Answer submitted successfully!" (same v1 format)

### `vote_answer(comment_id, vote_type)` → `service_v2.report_outcome()`
- `comment_id` treated as `solution_id`
- `"upvote"` → `report_outcome(success=True)`
- `"downvote"` → `report_outcome(success=False)`
- Returns: "Vote recorded successfully!" (same v1 format)

### Error passthrough
- `SelfReportError` from `report_outcome()` → v1 compat returns "You have already voted on this comment" (matches v1 `DuplicateVoteError` message)

## Files to create

- `tests/unit/test_v1_compat.py`

## Verification

```bash
uv run pytest tests/unit/test_v1_compat.py -v
```

Tests must fail (red) before implementation.
