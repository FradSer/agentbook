# Task 012: Tool Parameter Validation Test

**Type**: test
**Depends-on**: task-006-v2-tools-impl

## Objective

Write tests for tool parameter validation and error responses.

## BDD Scenarios

```gherkin
Scenario: resolve tool rejects empty description
  When agent calls resolve tool with description: ""
  Then response contains JSON-RPC error
  And error type is "invalid_input"
  And error detail indicates "description is required and cannot be empty"

Scenario: resolve tool rejects missing description
  When agent calls resolve tool without description parameter
  Then response contains JSON-RPC error
  And error type is "invalid_input"
  And error detail indicates "description is required"

Scenario: report_outcome tool validates solution_id format
  When agent calls report_outcome tool with solution_id: "invalid-uuid"
  Then response contains JSON-RPC error
  And error type is "invalid_input"
  And error detail indicates "solution_id must be a valid UUID"

Scenario: contribute tool validates steps format
  When agent calls contribute tool with solution_steps: "not-an-array"
  Then response contains JSON-RPC error
  And error type is "invalid_input"
  And error detail indicates "steps must be an array"

Scenario: Unauthenticated tool call is rejected
  When agent calls resolve tool without Authorization header
  Then response returns HTTP 401 Unauthorized
  And tool is not executed
  And error message indicates "Authentication required"
```

## Files to Modify

- `tests/integration/test_mcp_streamable_http.py`

## Test Cases

1. **test_resolve_rejects_empty_description** - Empty string validation
2. **test_resolve_rejects_missing_description** - Required field validation
3. **test_report_outcome_validates_solution_id** - UUID format validation
4. **test_contribute_validates_steps_format** - Array type validation
5. **test_unauthenticated_tool_call_rejected** - Auth enforcement

## Verification

```bash
uv run pytest tests/integration/test_mcp_streamable_http.py -k "validation" -v
# Expected: 5 failed (RED phase)
```

## Commit

```
test(mcp): add tool parameter validation tests

Test required fields, format validation, and authentication enforcement.
```