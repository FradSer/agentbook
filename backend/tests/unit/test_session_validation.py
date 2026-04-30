"""Unit tests for session ID validation functions.

BDD Scenarios:
- Session ID is cryptographically secure
- Session ID is at least 32 characters
- Session ID uses secrets module for generation
- Session ID contains only visible ASCII characters (0x21-0x7E)
"""

import pytest

from backend.presentation.mcp.session import (
    DEFAULT_SESSION_ID_LENGTH,
    MAX_SESSION_ID_LENGTH,
    MIN_SESSION_ID_LENGTH,
    generate_session_id,
    validate_session_id,
)


class TestValidateSessionId:
    """Tests for validate_session_id function."""

    def test_valid_session_id_format(self) -> None:
        """Test valid session ID with visible ASCII characters (0x21-0x7E)."""
        # Session ID with various visible ASCII characters
        session_id = "session-test_123!@#$%^&*()"
        assert validate_session_id(session_id) is True

    def test_valid_session_id_minimum_length(self) -> None:
        """Test valid session ID with minimum length."""
        session_id = "A" * MIN_SESSION_ID_LENGTH
        assert validate_session_id(session_id) is True

    def test_valid_session_id_maximum_length(self) -> None:
        """Test valid session ID with maximum length."""
        session_id = "Z" * MAX_SESSION_ID_LENGTH
        assert validate_session_id(session_id) is True

    def test_invalid_session_id_too_short(self) -> None:
        """Test invalid session ID with less than minimum characters."""
        session_id = "A" * (MIN_SESSION_ID_LENGTH - 1)
        assert validate_session_id(session_id) is False

    def test_invalid_session_id_too_long(self) -> None:
        """Test invalid session ID with more than maximum characters."""
        session_id = "A" * (MAX_SESSION_ID_LENGTH + 1)
        assert validate_session_id(session_id) is False

    @pytest.mark.parametrize(
        "session_id",
        [
            "session id with space",
            "session\tid",
            "session\x00id",
            "session\nid",
        ],
        ids=["space", "tab", "null-byte", "newline"],
    )
    def test_invalid_session_id_contains_invisible_character(
        self, session_id: str
    ) -> None:
        """Test invalid session ID with invisible/whitespace characters."""
        assert validate_session_id(session_id) is False

    def test_session_id_with_none_input(self) -> None:
        """Test that None is valid for new connections."""
        assert validate_session_id(None) is True


class TestGenerateSessionId:
    """Tests for generate_session_id function."""

    def test_default_length(self) -> None:
        """Test that generated session ID has default length."""
        session_id = generate_session_id()
        assert len(session_id) == DEFAULT_SESSION_ID_LENGTH

    def test_custom_length(self) -> None:
        """Test that generated session ID respects custom length."""
        session_id = generate_session_id(length=64)
        assert len(session_id) == 64

    def test_all_ids_unique(self) -> None:
        """Test that all generated session IDs are unique."""
        ids = {generate_session_id() for _ in range(100)}
        assert len(ids) == 100

    def test_all_ids_valid_format(self) -> None:
        """Test that all generated session IDs have valid format."""
        for _ in range(100):
            session_id = generate_session_id()
            assert validate_session_id(session_id) is True

    def test_all_ids_contain_only_visible_ascii(self) -> None:
        """Test that all generated session IDs contain only visible ASCII."""
        for _ in range(100):
            session_id = generate_session_id()
            for char in session_id:
                # Check character is in range 0x21-0x7E (visible ASCII)
                assert 0x21 <= ord(char) <= 0x7E, f"Invalid character: {char!r}"
