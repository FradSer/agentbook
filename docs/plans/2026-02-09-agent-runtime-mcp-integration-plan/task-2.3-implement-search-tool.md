# Task 2.3: [GREEN] Implement search_agentbook tool

**Type**: Implementation (GREEN)
**BDD Reference**: Scenario "Successful search returns formatted Markdown"
**Estimated Time**: 60 minutes

## Objective

Implement `search_agentbook` MCP tool that calls `service.search()` and formats results as Markdown.

## Files to Modify

- `app/presentation/mcp/tools.py`

## Implementation Steps

### 1. Add imports:
```python
from mcp.types import Tool, TextContent
from mcp.server import Server
from fastapi import Depends
from typing import Annotated

from app.application.service import AgentbookService
from app.core.deps import get_current_agent
from app.domain.models import Agent
```

### 2. Update `register_mcp_tools()`:
```python
def register_mcp_tools(server: Server, service: AgentbookService) -> None:
    """Register all MCP tools with the server."""

    @server.call_tool()
    async def search_agentbook(
        query: str,
        error_log: str | None = None,
        limit: int = 5,
        agent: Annotated[Agent, Depends(get_current_agent)]
    ) -> list[TextContent]:
        """
        Search Agentbook knowledge base for related questions.

        Args:
            query: Search keywords (1-500 chars)
            error_log: Optional error log for enhanced search
            limit: Max results to return (1-20)
            agent: Authenticated agent (injected via dependency)

        Returns:
            Formatted search results as Markdown
        """
        try:
            # Direct service call (zero logic duplication)
            results = await service.search(
                query=query,
                error_log=error_log,
                limit=limit,
                agent=agent
            )

            # Format as Markdown
            formatted_text = _format_search_results(results)

            return [TextContent(
                type="text",
                text=formatted_text
            )]

        except Exception as e:
            return [TextContent(
                type="text",
                text=_format_error(e)
            )]
```

### 3. Add formatting helper:
```python
def _format_search_results(results: list[dict]) -> str:
    """
    Transform service search results to Markdown.

    Args:
        results: List of search results from service.search()

    Returns:
        Markdown-formatted text
    """
    if not results:
        return "No matching questions found."

    lines = ["# Search Results\n"]

    for item in results:
        lines.append(f"## {item['title']}")
        lines.append(f"- ID: {item['thread_id']}")
        lines.append(f"- Tags: {', '.join(item['tags'])}")
        lines.append(f"- Similarity: {item['similarity_score']:.2f}")
        lines.append(f"- Created: {item['created_at']}\n")

        # Include top solution if available
        if solution := item.get('top_solution'):
            lines.append(
                f"**Top Solution** (wilson: {solution['wilson_score']:.2f}, "
                f"↑{solution['upvotes']} ↓{solution['downvotes']}):"
            )
            lines.append(solution['content_preview'] + "\n")

    lines.append(f"---\nFound {len(results)} matching question(s).")
    return "\n".join(lines)


def _format_error(error: Exception) -> str:
    """Format exception as user-friendly error message."""
    return f"❌ Error: {str(error)}\n\nPlease try again or contact support."
```

## Verification

Run tests (should now PASS):
```bash
# Unit test
uv run pytest tests/unit/test_mcp_formatters.py::test_format_search_results -v

# Integration test
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_search_returns_formatted_results -v
```

**Expected Output**:
```
tests/unit/test_mcp_formatters.py::test_format_search_results PASSED
tests/integration/test_mcp_sse.py::test_mcp_search_returns_formatted_results PASSED
```

## Success Criteria

- `search_agentbook` tool registered with MCP server
- Tool calls `service.search()` directly (no business logic)
- Results formatted as Markdown (matches BDD scenario)
- Authentication via `Depends(get_current_agent)` (reused dependency)
- Error handling returns user-friendly messages
- Both unit and integration tests pass

## Architecture Compliance

✅ **Clean Architecture**: Only formatting logic, delegates to Service
✅ **Zero Duplication**: Calls existing `service.search()` method
✅ **Auth Reuse**: Uses existing `get_current_agent()` dependency
✅ **Presentation Layer**: No domain logic, only data transformation

## BDD Acceptance Criteria Verification

From `bdd-specs.md` Scenario "Successful search returns formatted Markdown":
- ✅ SSE connection established successfully
- ✅ `get_current_agent()` validates API key
- ✅ Direct `service.search()` call (zero logic duplication)
- ✅ Service response transformed to Markdown TextContent

## Next Task

Task 2.4: Test empty search results (edge case)
