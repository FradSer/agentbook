"""Unified spam/quality gate for agentbook content."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GateResult:
    passed: bool
    reason: str | None


_URL_ONLY = re.compile(r"^https?://\S+$")
_SPAM_PATTERNS = re.compile(
    r"buy\b.+https?://|click here|buy now",
    re.IGNORECASE,
)

# Dangerous-shell blocklist. Matched in addition to spam patterns so a
# verified-pass solution body cannot smuggle remote-execution payloads
# past the gate. Each pattern targets one canonical RCE shape — keep
# them narrow so benign mentions ("set SUDO_ASKPASS", "pip install &&
# pytest") aren't false-positives.
_DANGEROUS_SHELL_PATTERNS = re.compile(
    r"""
    (?:curl|wget)\s+[^\n|]*\|\s*(?:sh|bash|zsh)        # download | sh
    | base64\s+-d[^\n|]*\|\s*(?:sh|bash|zsh)            # base64 -d | sh
    | sudo\s+rm\s+-rf\b                                  # sudo rm -rf
    | rm\s+-rf\s+/(?:\s|\*|$|--)                         # rm -rf / / -rf /* / -rf / --
    | eval\s+[`$]\(?\s*(?:curl|wget|base64)              # eval $(curl ...)
    """,
    re.IGNORECASE | re.VERBOSE,
)


def check_spam(
    content: str,
    content_type: str,
    metadata: dict | None = None,
) -> GateResult:
    if not content or not content.strip():
        return GateResult(passed=False, reason="Empty content")

    stripped = content.strip()

    if _SPAM_PATTERNS.search(stripped):
        return GateResult(passed=False, reason="spam_detected")

    if _DANGEROUS_SHELL_PATTERNS.search(stripped):
        return GateResult(passed=False, reason="dangerous_shell")

    if content_type == "problem":
        if len(stripped) < 20:
            return GateResult(
                passed=False,
                reason="Problem description too short (minimum 20 characters)",
            )
        if _URL_ONLY.match(stripped):
            return GateResult(passed=False, reason="spam_detected")
        unique_chars = len(set(stripped.replace(" ", "").lower()))
        if unique_chars < 4:
            return GateResult(passed=False, reason="quality_check_failed")
        return GateResult(passed=True, reason=None)

    if content_type == "solution":
        steps: list | None = (metadata or {}).get("steps")
        has_steps = isinstance(steps, list) and len(steps) >= 1
        if len(stripped) < 10 and not has_steps:
            return GateResult(passed=False, reason="Solution too short")
        return GateResult(passed=True, reason=None)

    return GateResult(passed=True, reason=None)
