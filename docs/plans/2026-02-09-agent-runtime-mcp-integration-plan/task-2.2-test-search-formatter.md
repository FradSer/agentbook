# Task 2.2: [RED] Write unit test for search result formatting

**Type**: Test (RED)
**BDD Reference**: Scenario "Successful search returns formatted Markdown" - Markdown formatting
**Estimated Time**: 30 minutes

## Objective

Write unit tests for the `_format_search_results()` helper function to ensure correct Markdown formatting with mocked service responses.

## Files to Create

- `tests/unit/test_mcp_formatters.py` (new)

## Implementation Steps

Create test file with multiple test cases:

```python
"""Unit tests for MCP response formatters."""
import pytest
from app.presentation.mcp.tools import _format_search_results, _format_error


def test_format_search_results_with_data():
    """Test Markdown formatting of search results with top solution."""
    # Arrange: Mock service response
    service_response = [
        {
            "thread_id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "How to fix ModuleNotFoundError?",
            "tags": ["python", "import"],
            "similarity_score": 0.92,
            "created_at": "2026-02-07T10:00:00Z",
            "top_solution": {
                "comment_id": "660f9511-f3ac-52e5-b827-557766551111",
                "content_preview": "Install the package: `pip install module-name`",
                "wilson_score": 0.85,
                "upvotes": 10,
                "downvotes": 1
            }
        }
    ]

    # Act
    result = _format_search_results(service_response)

    # Assert
    assert "# Search Results" in result
    assert "## How to fix ModuleNotFoundError?" in result
    assert "- Tags: python, import" in result
    assert "- Similarity: 0.92" in result
    assert "**Top Solution**" in result
    assert "wilson: 0.85" in result
    assert "↑10 ↓1" in result
    assert "Install the package" in result
    assert "Found 1 matching question(s)" in result


def test_format_search_results_empty():
    """Test formatting when no results found."""
    # Arrange
    service_response = []

    # Act
    result = _format_search_results(service_response)

    # Assert
    assert result == "No matching questions found."


def test_format_search_results_no_solution():
    """Test formatting for thread without top solution."""
    # Arrange: Thread with no answers
    service_response = [
        {
            "thread_id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "Unsolved question",
            "tags": ["python"],
            "similarity_score": 0.75,
            "created_at": "2026-02-07T10:00:00Z",
            "top_solution": None
        }
    ]

    # Act
    result = _format_search_results(service_response)

    # Assert
    assert "# Search Results" in result
    assert "## Unsolved question" in result
    assert "**Top Solution**" not in result  # No solution section


def test_format_search_results_multiple_threads():
    """Test formatting with multiple search results."""
    # Arrange
    service_response = [
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

    # Act
    result = _format_search_results(service_response)

    # Assert
    assert "## Question 1" in result
    assert "## Question 2" in result
    assert "Found 2 matching question(s)" in result


def test_format_error():
    """Test error message formatting."""
    # Arrange
    error = ValueError("Invalid query parameter")

    # Act
    result = _format_error(error)

    # Assert
    assert "❌ Error:" in result
    assert "Invalid query parameter" in result
    assert "try again" in result.lower() or "contact" in result.lower()
```

## Verification

Run test (should FAIL with ModuleNotFoundError):
```bash
uv run pytest tests/unit/test_mcp_formatters.py::test_format_search_results_with_data -v
```

**Expected Output**:
```
FAILED tests/unit/test_mcp_formatters.py::test_format_search_results_with_data
ModuleNotFoundError: No module named 'app.presentation.mcp.tools'
```

## Success Criteria

- Test file created with 5+ test cases
- Tests cover:
  - ✅ Normal case with top solution
  - ✅ Empty results
  - ✅ Thread without solution
  - ✅ Multiple results
  - ✅ Error formatting
- Tests execute and fail with expected error
- No external dependencies (pure unit tests)

## Test Isolation

✅ **No Service Calls**: Uses mock data, no `AgentbookService` dependency
✅ **No Database**: Pure function testing
✅ **No Network**: No HTTP calls

## Next Task

Task 2.3: Implement search_agentbook tool (will make these tests pass)
