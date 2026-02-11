# Task 4.2: RED - Write Unit Test for Answer Formatting

**BDD Reference**: Feature "answer_question MCP Tool" - Scenario "Submit answer with code blocks"

## Verification Command

```bash
uv run pytest tests/unit/test_mcp_formatters.py::test_format_answer_response -v
```

**Expected Result**: Test fails with "ModuleNotFoundError" (formatting function not implemented yet)

## Implementation Details

Create unit tests in `tests/unit/test_mcp_formatters.py` for the answer response formatting function.

### Test Requirements

Create tests that verify the `_format_answer_response()` function handles:

1. **Solution answer (is_solution=True)**
   - Input: Comment with is_solution=True
   - Expected output: "Answer submitted successfully!" with pending status

2. **Regular comment (is_solution=False)**
   - Input: Comment with is_solution=False
   - Expected output: "Answer submitted successfully!" with status

3. **Different review statuses**
   - Input: Comments with "pending", "approved" statuses
   - Expected output: Appropriate messages for each status

### Formatting Requirements

The formatted output should include:
- "Answer submitted successfully!" header
- Comment ID
- Question/thread ID
- Status (defaults to "pending")
- Status-appropriate follow-up message:
  - Pending: Review message + token earning encouragement
  - Approved: Live message

### BDD Scenario Mapping

- **Given**: Answer submitted successfully via MCP
- **When**: Formatter processes comment response
- **Then**: Output contains confirmation message
- **Then**: Comment ID and thread ID included
- **Then**: Appropriate message based on review status

## Success Criteria

- Unit test file created or updated
- Test fails as expected (function not yet implemented)
- Test covers solution flag, non-solution comment, and different statuses
- Test verifies Markdown formatting correctness