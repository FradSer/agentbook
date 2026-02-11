# Task 5.2: RED - Write Unit Test for Vote Response Formatting

**BDD Reference**: Feature "vote_answer MCP Tool" - Scenario "Upvote triggers reward transaction"

## Verification Command

```bash
uv run pytest tests/unit/test_mcp_formatters.py::test_format_vote_response -v
```

**Expected Result**: Test fails with "ModuleNotFoundError" (formatting function not implemented yet)

## Implementation Details

Create unit tests in `tests/unit/test_mcp_formatters.py` for the vote response formatting function.

### Test Requirements

Create tests that verify the `_format_vote_response()` function handles:

1. **Upvote with reward**
   - Input: Comment, vote_type="upvote", reward_issued=5
   - Expected output: Confirmation with reward info and community message

2. **Downvote (no reward)**
   - Input: Comment, vote_type="downvote", reward_issued=0
   - Expected output: Confirmation without reward info

3. **No reward scenario (e.g., self-vote)**
   - Input: Comment, vote_type="upvote", reward_issued=0
   - Expected output: Confirmation without reward info

### Formatting Requirements

The formatted output should include:
- "Vote recorded successfully!" header
- "Vote Type: {upvote|downvote}"
- "Updated Wilson Score: {score:.2f}"
- For upvote with reward: "Reward Issued: X tokens (to answer author)"
- Status-appropriate closing message:
  - Upvote: Community appreciation message
  - Downvote: Quality improvement feedback message

### BDD Scenario Mapping

- **Given**: Vote recorded successfully
- **When**: Formatter processes vote response
- **Then**: Output contains confirmation message
- **Then**: Vote type and Wilson score included
- **Then**: Reward info included when applicable
- **Then**: Appropriate closing message based on vote type

## Success Criteria

- Unit test file created or updated
- Test fails as expected (function not yet implemented)
- Test covers upvote with reward, downvote no reward, and no reward scenario
- Test verifies Markdown formatting correctness