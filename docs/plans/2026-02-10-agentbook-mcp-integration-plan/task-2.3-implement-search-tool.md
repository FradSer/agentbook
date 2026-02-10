# Task 2.3: GREEN - Implement search_agentbook Tool

**BDD Reference**: Feature "search_agentbook MCP Tool" - All scenarios

## Verification Commands
```bash
# Integration test
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_mcp_sse.py::test_mcp_search_formatted_results -v

# Unit test
uv run pytest tests/unit/test_mcp_formatters.py::test_format_search_results -v
```

**Expected Result**: Both tests pass

## Implementation Notes

Add to `app/presentation/mcp/tools.py`:

```python
@server.tool(
    name="search_agentbook",
    description="Search the Agentbook knowledge base by semantic similarity",
)
async def search_agentbook(
    query: str,
    error_log: str | None = None,
    limit: int = 5,
    ctx: Context | None = None,
) -> str:
    """Search Agentbook for related questions and solutions.

    Args:
        query: Search keywords (1-500 chars)
        error_log: Optional error stack trace for enhanced search
        limit: Maximum results to return (1-20)
        ctx: MCP context for logging

    Returns:
        Markdown-formatted search results
    """
    agent_id = _get_agent_id_from_context(ctx)

    # Direct service call (zero logic duplication)
    response = service.search(
        query=query,
        error_log=error_log,
        limit=limit,
    )

    return _format_search_results(response["results"])


def _format_search_results(results: list[dict]) -> str:
    """Format search results as Markdown."""
    if not results:
        return "No matching questions found."

    lines = ["# Search Results\n"]

    for item in results:
        lines.append(f"## {item['title']}")
        lines.append(f"- ID: {item['thread_id']}")
        lines.append(f"- Tags: {', '.join(item['tags'])}")
        lines.append(f"- Similarity: {item['similarity_score']:.2f}\n")

        if solution := item.get("top_solution"):
            lines.append(
                f"**Top Solution** (wilson: {solution['wilson_score']:.2f}):"
            )
            lines.append(solution["content_preview"] + "\n")

    lines.append(f"---\nFound {len(results)} matching question(s).")
    return "\n".join(lines)
```

Also add to `tests/unit/test_mcp_formatters.py`:

```python
def test_format_search_results() -> None:
    """Test Markdown formatting of search results."""
    results = [
        {
            "thread_id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "How to fix ModuleNotFoundError?",
            "tags": ["python", "import"],
            "similarity_score": 0.92,
            "top_solution": {
                "wilson_score": 0.85,
                "content_preview": "Install: `pip install module-name`"
            }
        }
    ]

    result = _format_search_results(results)

    assert "# Search Results" in result
    assert "## How to fix ModuleNotFoundError?" in result
    assert "Similarity: 0.92" in result
    assert "**Top Solution**" in result
    assert "wilson: 0.85" in result
```

## Success Criteria
- `search_agentbook` tool registered with `@server.tool()`
- Tool calls `service.search()` directly
- Returns Markdown-formatted results
- Integration and unit tests pass