"""Unit tests for MCP response formatters.

These tests validate Markdown formatting of MCP tool responses.
"""

from __future__ import annotations


def test_format_vote_response_upvote() -> None:
    """Test Markdown formatting of upvote response with reward."""
    from app.presentation.mcp.tools import _format_vote_response

    # Arrange: Mock vote response
    vote_data = {
        "vote_type": "upvote",
        "comment": {
            "comment_id": "660f9511-f3ac-52e5-b827-557766551111",
            "wilson_score": 0.78,
        },
        "reward_issued": 5,
    }

    # Act
    result = _format_vote_response(vote_data)

    # Assert
    assert "Vote recorded successfully!" in result
    assert "Vote Type: upvote" in result
    assert "Reward Issued: 5 tokens" in result
    assert "Wilson Score: 0.78" in result
    assert "community" in result.lower() or "thank" in result.lower()


def test_format_vote_response_downvote() -> None:
    """Test formatting of downvote (no reward)."""
    from app.presentation.mcp.tools import _format_vote_response

    # Arrange
    vote_data = {
        "vote_type": "downvote",
        "comment": {
            "comment_id": "770f9511-f3ac-52e5-b827-557766551222",
            "wilson_score": 0.45,
        },
        "reward_issued": 0,
    }

    # Act
    result = _format_vote_response(vote_data)

    # Assert
    assert "Vote recorded successfully!" in result
    assert "Vote Type: downvote" in result
    assert "Wilson Score: 0.45" in result
    assert "Reward Issued: 0" not in result or "no reward" in result.lower()


def test_format_vote_response_no_reward() -> None:
    """Test formatting when vote doesn't trigger reward (edge case)."""
    from app.presentation.mcp.tools import _format_vote_response

    # Arrange: Upvote but no reward (e.g., voting on own answer)
    vote_data = {
        "vote_type": "upvote",
        "comment": {
            "comment_id": "880f9511-f3ac-52e5-b827-557766551333",
            "wilson_score": 0.50,
        },
        "reward_issued": 0,
    }

    # Act
    result = _format_vote_response(vote_data)

    # Assert
    assert "Vote recorded successfully!" in result
    assert "Wilson Score: 0.50" in result


def test_format_search_results_with_data() -> None:
    """Test Markdown formatting of search results with top solution."""
    from app.presentation.mcp.tools import _format_search_results

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
                "downvotes": 1,
            },
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


def test_format_search_results_empty() -> None:
    """Test formatting when no results found."""
    from app.presentation.mcp.tools import _format_search_results

    # Arrange
    service_response = []

    # Act
    result = _format_search_results(service_response)

    # Assert
    assert result == "No matching questions found."


def test_format_search_results_no_solution() -> None:
    """Test formatting for thread without top solution."""
    from app.presentation.mcp.tools import _format_search_results

    # Arrange: Thread with no answers
    service_response = [
        {
            "thread_id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "Unsolved question",
            "tags": ["python"],
            "similarity_score": 0.75,
            "created_at": "2026-02-07T10:00:00Z",
            "top_solution": None,
        }
    ]

    # Act
    result = _format_search_results(service_response)

    # Assert
    assert "# Search Results" in result
    assert "## Unsolved question" in result
    assert "**Top Solution**" not in result  # No solution section


def test_format_search_results_multiple_threads() -> None:
    """Test formatting with multiple search results."""
    from app.presentation.mcp.tools import _format_search_results

    # Arrange
    service_response = [
        {
            "thread_id": "thread-1",
            "title": "Question 1",
            "tags": ["python"],
            "similarity_score": 0.95,
            "created_at": "2026-02-07T10:00:00Z",
            "top_solution": None,
        },
        {
            "thread_id": "thread-2",
            "title": "Question 2",
            "tags": ["fastapi"],
            "similarity_score": 0.82,
            "created_at": "2026-02-07T11:00:00Z",
            "top_solution": None,
        },
    ]

    # Act
    result = _format_search_results(service_response)

    # Assert
    assert "## Question 1" in result
    assert "## Question 2" in result
    assert "Found 2 matching question(s)" in result


def test_format_error() -> None:
    """Test error message formatting."""
    from app.presentation.mcp.tools import _format_error

    # Arrange
    error = ValueError("Invalid query parameter")

    # Act
    result = _format_error(error)

    # Assert
    assert "❌ Error:" in result
    assert "Invalid query parameter" in result
    assert "try again" in result.lower() or "contact" in result.lower()


def test_format_answer_response() -> None:
    """Test Markdown formatting of comment creation response."""
    from app.presentation.mcp.tools import _format_answer_response

    # Arrange: Mock comment object
    comment = {
        "comment_id": "660f9511-f3ac-52e5-b827-557766551111",
        "thread_id": "550e8400-e29b-41d4-a716-446655440000",
        "is_solution": True,
        "review_status": "pending",
        "created_at": "2026-02-07T15:00:00Z",
    }

    # Act
    result = _format_answer_response(comment)

    # Assert
    assert "Answer submitted successfully!" in result
    assert "Comment ID: 660f9511-f3ac-52e5-b827-557766551111" in result
    assert "Question ID: 550e8400-e29b-41d4-a716-446655440000" in result
    assert "Status: pending" in result
    assert "tokens" in result.lower() or "upvote" in result.lower()


def test_format_answer_response_not_solution() -> None:
    """Test formatting for regular comment (not marked as solution)."""
    from app.presentation.mcp.tools import _format_answer_response

    # Arrange
    comment = {
        "comment_id": "770f9511-f3ac-52e5-b827-557766551222",
        "thread_id": "880e8400-e29b-41d4-a716-446655440111",
        "is_solution": False,
        "review_status": "approved",
        "created_at": "2026-02-07T15:00:00Z",
    }

    # Act
    result = _format_answer_response(comment)

    # Assert
    assert "Answer submitted successfully!" in result
    assert "Comment ID:" in result


def test_format_question_response() -> None:
    """Test Markdown formatting of thread creation response."""
    from app.presentation.mcp.tools import _format_question_response

    # Arrange: Mock thread object
    thread = {
        "thread_id": "550e8400-e29b-41d4-a716-446655440000",
        "title": "How to configure Redis?",
        "review_status": "pending",
        "created_at": "2026-02-07T14:30:00Z",
    }

    # Act
    result = _format_question_response(thread)

    # Assert
    assert "Question posted successfully!" in result
    assert "ID: 550e8400-e29b-41d4-a716-446655440000" in result
    assert "Status: pending" in result
    assert "reviewed by" in result.lower() or "check back" in result.lower()


def test_format_question_response_approved() -> None:
    """Test formatting when question is immediately approved."""
    from app.presentation.mcp.tools import _format_question_response

    # Arrange: Mock approved thread
    thread = {
        "thread_id": "660f9511-f3ac-52e5-b827-557766551111",
        "title": "Approved question",
        "review_status": "approved",
        "created_at": "2026-02-07T14:30:00Z",
    }

    # Act
    result = _format_question_response(thread)

    # Assert
    assert "Question posted successfully!" in result
    assert "Status: approved" in result
