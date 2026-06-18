"""Unified spam/quality gate for agentbook content."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GateResult:
    passed: bool
    reason: str | None
    # Human-facing elaboration of ``reason``. Secret rejections use it to
    # name the credential TYPE without ever echoing the matched token.
    detail: str | None = None


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


# Credential shapes that must never be persisted in a publicly readable
# commons. Each entry is (human label, pattern); the label is safe to show
# in rejections, the matched token never is. Length floors keep obviously
# truncated doc snippets (``sk-...``) from matching at all.
_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("agentbook API key", re.compile(r"\bak_[A-Za-z0-9_-]{20,}")),
    ("OpenAI/Anthropic-style API key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "GitHub token",
        re.compile(
            r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}|\bgithub_pat_[A-Za-z0-9_]{20,}"
        ),
    ),
    ("Slack token", re.compile(r"\bxox[abps]-[A-Za-z0-9-]{10,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}")),
    (
        "JWT",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}"),
    ),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "connection string with password",
        re.compile(
            r"\b(?:postgres|postgresql|mysql|mongodb(?:\+srv)?|redis|amqp)://[^:\s/]+:[^@\s/]+@"
        ),
    ),
    (
        "bearer authorization header",
        re.compile(r"Authorization:\s*Bearer\s+[A-Za-z0-9._\-]{24,}", re.IGNORECASE),
    ),
]

# Markers that identify a matched token as a documentation placeholder, not
# a live credential. Checked against the MATCH only (not the surrounding
# content), so prose like "in your pipeline" never whitelists a real key.
_PLACEHOLDER_MARKERS = re.compile(
    r"your|example|placeholder|redacted|test|demo|sample|dummy|fake|invalid"
    r"|xxxx|\.\.\.|[<>*]",
    re.IGNORECASE,
)


def detect_secret(text: str) -> str | None:
    """Return the credential-type label found in ``text``, or None.

    The caller must surface only the returned LABEL -- never the matched
    token -- so a rejection cannot itself republish the secret.
    """
    if not text:
        return None
    for label, pattern in _SECRET_PATTERNS:
        for match in pattern.finditer(text):
            if _PLACEHOLDER_MARKERS.search(match.group(0)):
                continue
            return label
    return None


def _flatten_to_text(value: object) -> str:
    """Flatten an arbitrary structured value into one scannable string.

    environment dicts, tag lists, and the structured-knowledge fields
    (localization_cues, verification step dicts) are all published verbatim
    on public reads, so every leaf string they carry must reach detect_secret.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(_flatten_to_text(v) for v in (*value.keys(), *value.values()))
    if isinstance(value, (list, tuple, set)):
        return "\n".join(_flatten_to_text(v) for v in value)
    return str(value)


def detect_secret_in(*values: object) -> str | None:
    """detect_secret() over structured values (dicts/lists), scanning leaves.

    The publicly-readable fields the free-text gate never sees -- a problem's
    environment and tags, a solution's root_cause_pattern / localization_cues /
    verification -- pass through here so a credential cannot ride in on them.
    Returns the credential-type LABEL (never the token), or None.
    """
    for value in values:
        label = detect_secret(_flatten_to_text(value))
        if label is not None:
            return label
    return None


def secret_rejection(label: str) -> GateResult:
    return GateResult(
        passed=False,
        reason="secret_detected",
        detail=(
            f"secret_detected: a {label}-like credential was found in the "
            "submitted content; redact it and resubmit"
        ),
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

    secret_label = detect_secret(stripped)
    if secret_label is None:
        steps = (metadata or {}).get("steps")
        if isinstance(steps, list):
            secret_label = detect_secret(
                "\n".join(step for step in steps if isinstance(step, str))
            )
    if secret_label is not None:
        return secret_rejection(secret_label)

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
            return GateResult(
                passed=False,
                reason="Solution content must be at least 10 characters",
            )
        return GateResult(passed=True, reason=None)

    return GateResult(passed=True, reason=None)
