# Task 010: End-to-End Smoke Test

**Type**: test
**Depends-on**: task-007-error-handling-impl

## Objective

Write comprehensive end-to-end test validating complete MCP workflow.

## BDD Scenario

```gherkin
Scenario: Multiple tool calls in single session
  Given session "session-v2" is established
  When agent calls resolve tool
  And agent calls contribute tool
  And agent calls get_context tool
  Then all calls use same session
  And all calls use same authenticated agent
  And responses are correlated to requests via JSON-RPC id
```

## Files to Create

- `tests/integration/test_mcp_e2e.py`

## Test Cases

1. **test_complete_resolve_workflow**
   - Authenticate
   - Initialize session
   - Call resolve with auto_post=true
   - Verify response contains solutions or registered message
   - Session remains valid

2. **test_complete_contribute_workflow**
   - Authenticate
   - Call contribute with problem and solution
   - Verify response contains IDs
   - Verify knowledge is searchable

3. **test_complete_report_outcome_workflow**
   - Create solution
   - Report outcome (success)
   - Verify confidence score updated

4. **test_full_session_lifecycle**
   - Establish session via POST
   - Make multiple tool calls
   - Terminate via DELETE
   - Verify subsequent requests return 404

## Verification

```bash
uv run pytest tests/integration/test_mcp_e2e.py -v
# Expected: 4 passed
```

## Commit

```
test(mcp): add end-to-end smoke tests for complete workflow

Test resolve, contribute, report_outcome, and session lifecycle.
```