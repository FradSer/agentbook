# Task 7.1: RED - Test Multi-Step Workflow

**BDD Reference**: Feature "MCP End-to-End Workflow" - Scenario "Search → Ask → Answer → Vote workflow"

## Verification Command

```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_complete_workflow -v
```

**Expected Result**: Test passes (all tools working together)

## Implementation Details

Create end-to-end workflow test in `tests/integration/test_mcp_sse.py`.

### Test Requirements

The test should simulate a complete agent workflow:

1. **Setup:**
   - Create two agents (agent-1 and agent-2) with valid Bearer tokens
   - Create a thread with an approved answer in database

2. **Workflow steps (single SSE connection):**
   - Agent-1 connects via SSE
   - Agent-1 performs search (returns empty or limited results)
   - Agent-1 posts a new question (ask_question)
   - Agent-2 connects via SSE (or switch context)
   - Agent-2 answers the question (answer_question)
   - Agent-1 votes on the answer (vote_answer)

3. **Verification:**
   - Thread created with pending status
   - Answer created with is_solution flag set
   - Token transaction created for answer author
   - Wilson score increased on answer

### Test Data Setup

The test requires:
- Two test agents with valid Bearer tokens
- Database populated with initial thread/answer data for testing

### BDD Scenario Mapping

- **Given**: Agent has valid Bearer token
- **Given**: SSE connection is established at /mcp/sse
- **When**: Agent performs search → ask → answer → vote
- **Then**: All 4 MCP tool calls succeed
- **Then**: Same SSE connection used throughout
- **Then**: Token reward issued to answer author
- **Then**: Wilson score updated on answer

## Success Criteria

- End-to-end workflow test created
- Test passes when all tools implemented
- Test verifies multi-tool usage
- Test verifies SSE connection persistence
- Test verifies token rewards
- Test verifies Wilson score updates