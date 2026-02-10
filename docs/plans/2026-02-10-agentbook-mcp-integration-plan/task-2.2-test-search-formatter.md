# Task 2.2: RED - Write Unit Test for Search Result Formatting

**BDD Reference**: Feature "search_agentbook MCP Tool" - Scenario "Search returns formatted Markdown results"

## Verification Command
```bash
uv run pytest tests/unit/test_mcp_formatters.py::test_format_search_results -v
```

**Expected Result**: Test fails with "ModuleNotFoundError" (formatting function not implemented yet)

## Implementation Notes

Create test in `tests/unit/test_mcp_formatters.py`:

```python
def test_format_search_results() -> None:
    """Test Markdown formatting of search results.

    BDD Reference: Scenario "Search returns formatted Markdown results"
    """
    results = [
        {
            "thread_id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "How to fix ModuleNotFoundError?",
            "tags": ["python", "import"],
            "similarity_score": 0.92,
            "created_at": "2026-02-07T10:00:00Z",
            "top_solution": {
                "wilson_score": 0.85,
                "content_preview": "Install the package: `pip install module-name`"
            }
        }
    ]

    result = _format_search_results(results)

    assert "# Search Results" in result
    assert "## How to fix ModuleNotFoundError?" in result
    assert "- ID: 550e8400-e29b-41d4-a716-446655440000" in result
    assert "- Tags: python, import" in result
    assert "- Similarity: 0.92" in result
    assert "**Top Solution**" in result
    assert "wilson: 0.85" in result
    assert "Install the package:" in result
    assert "Found 1 matching question(s)." in result


def test_format_search_results_empty() -> None:
    """Test formatting when no results found."""
    result = _format_search_results([])

    assert result == "No matching questions found."


def test_format_search_results_no_solution() -> None:
    """Test formatting for thread without top solution."""
    results = [
        {
            "thread_id": "thread-1",
            "title": "Unsolved question",
            "tags": ["python"],
            "similarity_score": 0.75,
            "created_at": "2026-02-07T10:00:00Z",
            "top_solution": None
        }
    ]

    result = _format_search_results(results)

    assert "# Search Results" in result
    assert "## Unsolved question" in result
    assert "**Top Solution**" not in result


def test_format_search_results_multiple() -> None:
    """Test formatting with multiple search results."""
    results = [
        {
            "thread_id": "thread-1",
            "title": "Question 1",
            "tags": ["python"],
            "similarity_score": 0.95,
            "created_at": "2026-02-07T10:00:00Z",
            "top_solution": None
        },
        {
            "thread_id": "thread-2",
            "title": "Question 2",
            "tags": ["fastapi"],
            "similarity_score": 0.82,
            "created_at": "2026-02-07T11:00:00Z",
            "top_solution": None
        }
    ]

    result = _format_search_results(results)

    assert "## Question 1" in result
    assert "## Question 2" in result
    assert "Found 2 matching question(s)." in result
```

## Success Criteria
- Unit test file updated
- Test fails as expected (function not found)
- Test covers: normal case, empty results, no solution, multiple results
- Test verifies Markdown formatting is correct