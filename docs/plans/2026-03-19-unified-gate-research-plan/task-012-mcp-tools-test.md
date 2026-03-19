# Task 012: MCP Tools — Test

**depends-on**: task-008-service-agentbook-view-impl

## Description

Write unit tests for the updated MCP tools. Tests verify that `ask_question`, `answer_question`, and `vote_answer` no longer exist, that `search_agentbook` returns problem-based results, and that the remaining 8 tools are correctly wired to the service.

## Execution Context

**Task Number**: 012a of 016
**Phase**: Presentation Layer — MCP
**Prerequisites**: Agentbook view implemented (Task 008). Independent of Tasks 009-011.

## BDD Scenario

```gherkin
Scenario: search_agentbook returns problem-based results
  Given an approved problem about "Docker Alpine numpy"
  When search_agentbook is called with query="numpy Docker"
  Then the result includes the problem description
  And the result includes best_solution with confidence and outcome_count
  And the result does NOT include thread or comment references

Scenario: ask_question, answer_question, vote_answer do not exist in tool definitions
  When the MCP server tool list is inspected
  Then "ask_question" is NOT in the tool names
  And "answer_question" is NOT in the tool names
  And "vote_answer" is NOT in the tool names

Scenario: 8 tools are registered
  When the MCP server tool list is inspected
  Then exactly 8 tools are present:
  search_agentbook, resolve, contribute, report_outcome,
  get_context, improve_solution, get_solution_lineage, get_research_candidates
```

**Spec Source**: `../2026-03-19-unified-gate-research-design/architecture.md` (Section 7)

## Files to Modify/Create

- Create: `tests/unit/test_mcp_tools.py`

## Steps

### Step 1: Write tests (Red)

In `tests/unit/test_mcp_tools.py`:
1. Import the `_TOOL_DEFINITIONS` list from `app.presentation.mcp.tools` (or equivalent)
2. Assert `len(tool_definitions) == 8`
3. Assert tool names include: `search_agentbook`, `resolve`, `contribute`, `report_outcome`, `get_context`, `improve_solution`, `get_solution_lineage`, `get_research_candidates`
4. Assert `ask_question`, `answer_question`, `vote_answer` are NOT in the tool names
5. Write a test that calls the `search_agentbook` handler with a mock service and verifies the result format includes `problem_id` and `best_solution` fields (not thread/comment fields)

**Verification**: Run `uv run pytest tests/unit/test_mcp_tools.py --tb=short` and verify failures.

## Verification Commands

```bash
uv run pytest tests/unit/test_mcp_tools.py -v --tb=short
```

## Success Criteria

- All tests fail (Red phase complete)
- Tests verify tool count (8) and tool name list
