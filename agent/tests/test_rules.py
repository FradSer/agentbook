"""Tests for ContentRules class"""

from agent.src.rules import ContentRules


class TestContentRules:
    """Test ContentRules validation logic"""

    def test_empty_title_rejected(self):
        """Empty title should be rejected with reason containing 'empty'"""
        result, reason = ContentRules.check_thread(
            "", "Valid body content that is long enough"
        )

        assert result == "reject"
        assert reason is not None
        assert "empty" in reason.lower()

    def test_empty_body_rejected(self):
        """Empty body should be rejected with reason containing 'empty'"""
        result, reason = ContentRules.check_thread("Valid title", "")

        assert result == "reject"
        assert reason is not None
        assert "empty" in reason.lower()

    def test_whitespace_only_content_rejected(self):
        """Content with only whitespace should be rejected as empty"""
        result, reason = ContentRules.check_thread("   ", "   ")

        assert result == "reject"
        assert reason is not None
        assert "empty" in reason.lower()

    def test_short_title_rejected(self):
        """Title shorter than MIN_TITLE_LENGTH should be rejected"""
        result, reason = ContentRules.check_thread("Hi", "This is a valid body content")

        assert result == "reject"
        assert reason is not None
        assert "short" in reason.lower()

    def test_short_body_rejected(self):
        """Body shorter than MIN_CONTENT_LENGTH should be rejected"""
        result, reason = ContentRules.check_thread("Valid title", "Short")

        assert result == "reject"
        assert reason is not None
        assert "short" in reason.lower()

    def test_valid_content_passes(self):
        """Valid content should pass"""
        result, reason = ContentRules.check_thread(
            "This is a valid title",
            "This is a valid body content that meets the minimum length requirement",
        )

        assert result == "pass"
        assert reason is None

    def test_minimum_boundary_passes(self):
        """Content at exact minimum boundary should pass"""
        result, reason = ContentRules.check_thread("12345", "1234567890")

        assert result == "pass"
        assert reason is None

    def test_empty_comment_rejected(self):
        """Empty comment should be rejected with reason containing 'empty'"""
        result, reason = ContentRules.check_comment("")

        assert result == "reject"
        assert reason is not None
        assert "empty" in reason.lower()

    def test_short_comment_rejected(self):
        """Comment shorter than MIN_CONTENT_LENGTH should be rejected"""
        result, reason = ContentRules.check_comment("Short")

        assert result == "reject"
        assert reason is not None
        assert "short" in reason.lower()

    def test_valid_comment_passes(self):
        """Valid comment should pass"""
        result, reason = ContentRules.check_comment("This is a valid comment")

        assert result == "pass"
        assert reason is None

    def test_whitespace_only_comment_rejected(self):
        """Comment with only whitespace should be rejected as empty"""
        result, reason = ContentRules.check_comment("   ")

        assert result == "reject"
        assert reason is not None
        assert "empty" in reason.lower()
