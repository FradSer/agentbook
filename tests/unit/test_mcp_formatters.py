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
