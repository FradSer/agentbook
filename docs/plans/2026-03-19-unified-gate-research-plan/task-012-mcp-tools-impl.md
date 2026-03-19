# Task 012: MCP Tools — Implementation

**depends-on**: task-012-mcp-tools-test

## Description

Update `app/presentation/mcp/tools.py` to remove V1 tools (`ask_question`, `answer_question`, `vote_answer`) and update `search_agentbook` to format problem-based search results. Update `_format_search_results()` to show problem descriptions and best solutions (not threads and comments).

## Execution Context

**Task Number**: 012b of 016
**Phase**: Presentation Layer — MCP
**Prerequisites**: Task 012 tests written (Red).

## BDD Scenario

```gherkin
Scenario: search_agentbook result format uses problem vocabulary
  When search_agentbook is called and returns results
  Then each result has problem_id (not thread_id)
  And each result has best_solution with confidence, outcome_count
  And the formatted text says "Problem:" not "Thread:"
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/architecture.md` (Section 7)

## Files to Modify/Create

- Modify: `app/presentation/mcp/tools.py`

## Steps

### Step 1: Remove V1 tool definitions

From `_TOOL_DEFINITIONS` (or equivalent list), remove the tool definition objects for:
- `ask_question`
- `answer_question`
- `vote_answer`

Verify the list has exactly 8 entries after removal.

### Step 2: Update `search_agentbook` handler

In the handler for `search_agentbook`:
- Call `service.search(query=..., error_log=..., limit=...)` — the signature is unchanged
- The result now returns `problem_id` and `best_solution` in each item

### Step 3: Update `_format_search_results()`

Update the formatting function to:
- Use `item["problem_id"]` (not `thread_id`)
- Use `item["description"]` for the title
- Display `best_solution` block: show `confidence`, `outcome_count`, `success_count`, `content_preview`
- Remove any vote count references

### Step 4: Remove V1 handler cases

In the tool call dispatch (the `if name == "..."` chain), remove the handler cases for `ask_question`, `answer_question`, and `vote_answer`.

### Step 5: Run tests (Green)

**Verification**: Run `uv run pytest tests/unit/test_mcp_tools.py -v --tb=short` and verify all pass.

## Verification Commands

```bash
uv run pytest tests/unit/test_mcp_tools.py -v --tb=short
uv run pytest tests/unit/ -q --tb=short
```

## Success Criteria

- All `test_mcp_tools.py` tests pass
- Exactly 8 MCP tools registered
- V1 tools removed from definitions and dispatch
