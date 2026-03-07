# Task 006: V2 Tools Over Streamable HTTP Test

**Type**: test
**Depends-on**: task-005-backward-compat-impl

## Objective

Write tests for v2 tool execution over Streamable HTTP transport.

## BDD Scenarios

```gherkin
Scenario: resolve tool returns solutions
  Given knowledge base has solution S001 for "ImportError: pydantic.v1"
  When agent calls resolve tool with:
    | parameter    | value                                      |
    | description  | ImportError: cannot import 'pydantic.v1'   |
    | error_signature | ImportError                            |
    | environment  | {"python": "3.12", "pydantic": "2.5.0"}    |
    | auto_post    | true                                       |
  Then service.resolve() is called with agent_id from authenticated agent
  And response contains solutions with confidence scores
  And response is formatted as JSON in SSE event data

Scenario: contribute tool creates knowledge
  When agent calls contribute tool with:
    | parameter        | value                                        |
    | description      | FastAPI lifespan context manager memory leak |
    | error_signature  | MemoryError                                  |
    | tags             | ["fastapi", "memory-leak"]                   |
    | solution_content | Use context manager properly...              |
    | solution_steps   | ["Step 1: ...", "Step 2: ..."]              |
  Then service.contribute() is called with author_id from authenticated agent
  And response confirms knowledge creation with ID

Scenario: report_outcome tool updates confidence
  Given solution S100 exists with confidence 0.70
  When agent calls report_outcome tool with:
    | parameter          | value                      |
    | solution_id        | S100                       |
    | success            | true                       |
    | notes              | "Fixed the issue immediately" |
    | time_saved_seconds | 300                        |
  Then service.report_outcome() is called with reporter_id from authenticated agent
  And solution confidence is updated
  And response confirms outcome recorded

Scenario: get_context tool retrieves entity details
  Given problem P200 exists with related solutions
  When agent calls get_context tool with:
    | parameter | value                  |
    | id        | P200                   |
    | include   | ["solutions", "outcomes"] |
  Then service.get_context() is called
  And response includes requested context data

Scenario: Multiple tool calls in single session
  Given session "session-v2" is established
  When agent calls resolve tool
  And agent calls contribute tool
  And agent calls get_context tool
  Then all calls use same session
  And all calls use same authenticated agent
  And responses are correlated to requests via JSON-RPC id
```

## Files to Modify

- `tests/integration/test_mcp_streamable_http.py`

## Test Cases

1. **test_resolve_tool_returns_solutions** - Happy path for resolve
2. **test_contribute_tool_creates_knowledge** - Happy path for contribute
3. **test_report_outcome_updates_confidence** - Happy path for report_outcome
4. **test_get_context_retrieves_details** - Happy path for get_context
5. **test_multiple_tool_calls_same_session** - Session persistence

## Test Fixtures Required

- Mock `AgentbookServiceV2` with test data
- Sample problem/solution fixtures

## Verification

```bash
uv run pytest tests/integration/test_mcp_streamable_http.py -k "tool" -v
# Expected: 5 failed (RED phase)
```

## Commit

```
test(mcp): add v2 tools integration tests for streamable http

Test resolve, contribute, report_outcome, and get_context tools.
```