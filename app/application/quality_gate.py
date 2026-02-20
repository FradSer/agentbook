import re

_URL_ONLY = re.compile(r"^https?://\S+$", re.IGNORECASE)
_SPAM_PHRASES = re.compile(r"\b(buy cheap|click here|buy now)\b", re.IGNORECASE)
_BUY_URL = re.compile(r"\bbuy\b.+https?://", re.IGNORECASE)


def check_problem_quality(
    description: str | None, error_signature: str | None
) -> tuple[bool, str | None]:
    if not description:
        return (False, "Problem description too short (minimum 20 characters)")

    stripped = description.strip()

    if len(stripped) < 20:
        return (False, "Problem description too short (minimum 20 characters)")

    no_spaces = stripped.replace(" ", "")
    if no_spaces and len(set(no_spaces)) / len(no_spaces) < 0.2:
        return (False, "quality_check_failed")

    if (
        _URL_ONLY.match(stripped)
        or _SPAM_PHRASES.search(stripped)
        or _BUY_URL.search(stripped)
    ):
        return (False, "spam_detected")

    return (True, None)


def check_solution_quality(
    content: str, steps: list[str] | None
) -> tuple[bool, str | None]:
    if not content or not content.strip():
        return (False, "Solution content cannot be empty")

    stripped = content.strip()

    if len(stripped) < 10 and not steps:
        return (False, "Solution too short")

    if _URL_ONLY.match(stripped):
        return (False, "spam_detected")

    if _SPAM_PHRASES.search(stripped) or _BUY_URL.search(stripped):
        return (False, "spam_detected")

    return (True, None)
