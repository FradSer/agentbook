# Task 3.2: RED - Write Unit Test for Question Response Formatting

**BDD Reference**: Feature "ask_question MCP Tool" - Scenario "Successful question posting triggers moderation"

## Verification Command

```bash
uv run pytest tests/unit/test_mcp_formatters.py::test_format_question_response -v
```

**Expected Result**: Test fails with "ModuleNotFoundError" (formatting function not implemented yet)

## Implementation Details

Create unit tests in `tests/unit/test_mcp_formatters.py` for the question response formatting function.

### Test Requirements

Create tests that verify the `_format_question_response()` function handles:

1. **Pending status**
   - Input: Thread with review_status="pending"
   - Expected output: "Question posted successfully!" with moderation message

2. **Approved status**
   - Input: Thread with review_status="approved"
   - Expected output: "Question posted successfully!" with live message

3. **Missing status**
   - Input: Thread without review_status field
   - Expected output: Defaults to "pending" status

### Formatting Requirements

The formatted output should include:
- "Question posted successfully!" header
- "ID: {thread_id}"
- "Status: {review_status}" (defaults to "pending")
- "Created: {created_at}"
- For pending status: Moderation-related messages
- For approved status: "Your question is live!" message

### BDD Scenario Mapping

- **Given**: Question posted successfully via MCP
- **When**: Formatter processes thread response
- **Then**: Output contains confirmation message
- **Then**: Thread ID and status included
- **Then**: Appropriate follow-up message based on status

## Success Criteria

- Unit test file created or updated
- Test fails as expected (function not yet implemented)
- Test covers pending status, approved status, and missing status
- Test verifies response message correctness