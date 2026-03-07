# Task 012: Tool Parameter Validation Implementation

**Type**: impl
**Depends-on**: task-012-tool-validation-test

## Objective

Implement parameter validation in tool handlers with proper JSON-RPC error responses.

## BDD Scenario

```gherkin
Scenario: resolve tool rejects empty description
  When agent calls resolve tool with description: ""
  Then response contains JSON-RPC error
  And error type is "invalid_input"
  And error detail indicates "description is required and cannot be empty"
```

## Files to Modify

- `app/presentation/mcp/tools_v2.py`

## Implementation Steps

1. Create validation helper functions:
   - `validate_required_string(value, field_name)` - Check non-empty string
   - `validate_uuid(value, field_name)` - Check UUID format
   - `validate_array(value, field_name)` - Check list type

2. Add validation to each tool handler:
   - `handle_resolve`: validate description (required, non-empty)
   - `handle_contribute`: validate description, solution_content (required)
   - `handle_report_outcome`: validate solution_id (UUID format)
   - `handle_get_context`: validate id (required)

3. Return JSON-RPC error for validation failures:
   - Error type: "invalid_input"
   - Include descriptive detail message
   - Session remains valid for subsequent requests

## Error Response Format

```python
def create_validation_error(detail: str) -> list[dict]:
    return [{
        "type": "text",
        "text": json.dumps({
            "error": "invalid_input",
            "detail": detail
        })
    }]
```

## Verification

```bash
uv run pytest tests/integration/test_mcp_streamable_http.py -k "validation" -v
# Expected: 5 passed
```

## Commit

```
feat(mcp): implement tool parameter validation

Add required field, format, and type validation with JSON-RPC errors.
```