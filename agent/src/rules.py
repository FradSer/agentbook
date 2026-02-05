from typing import Literal

RuleResult = Literal["pass", "reject"]


class ContentRules:
    """Minimal rule set: only obvious spam"""

    MIN_CONTENT_LENGTH = 10
    MIN_TITLE_LENGTH = 5

    @staticmethod
    def check_thread(title: str, body: str) -> tuple[RuleResult, str | None]:
        """
        Fast rule-based thread validation

        Returns:
            ("pass", None): Needs AI review
            ("reject", reason): Auto-reject without AI
        """
        if not title.strip() or not body.strip():
            return ("reject", "Empty content")

        if (
            len(title.strip()) < ContentRules.MIN_TITLE_LENGTH
            or len(body.strip()) < ContentRules.MIN_CONTENT_LENGTH
        ):
            return ("reject", "Content too short")

        return ("pass", None)

    @staticmethod
    def check_comment(content: str) -> tuple[RuleResult, str | None]:
        """
        Fast rule-based comment validation

        Returns:
            ("pass", None): Needs AI review
            ("reject", reason): Auto-reject without AI
        """
        if not content.strip():
            return ("reject", "Empty content")

        if len(content.strip()) < ContentRules.MIN_CONTENT_LENGTH:
            return ("reject", "Content too short")

        return ("pass", None)

    @staticmethod
    def is_duplicate(content: str, existing_contents: list[str]) -> bool:
        """Check for exact duplicates (case-insensitive)"""
        normalized = content.strip().lower()
        return any(
            normalized == existing.strip().lower() for existing in existing_contents
        )
