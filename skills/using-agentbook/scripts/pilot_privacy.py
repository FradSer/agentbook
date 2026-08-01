"""Conservative public-query sanitization for the Agentbook pilot."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

MAX_PUBLIC_QUERY_CHARS = 500

_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_ERROR_LINE_RE = re.compile(
    r"(?:error|exception|failure|failed|fatal|panic|assertion)", re.IGNORECASE
)
_DEPENDENCY_RE = re.compile(r"[A-Za-z0-9_.-]+=[A-Za-z0-9_.+:-]+")
_CODE_LIKE_RE = re.compile(
    r"(?:\{.*\}|\bSELECT\b.+\bFROM\b|\bINSERT\s+INTO\b|\bUPDATE\b.+\bSET\b)",
    re.IGNORECASE,
)
_QUOTED_VALUE_RE = re.compile(r"(?P<quote>['\"`])(?P<value>[^'\"`]+)(?P=quote)")
_PUBLIC_QUOTED_LITERALS = {
    "bool",
    "bytes",
    "dict",
    "float",
    "int",
    "list",
    "nonetype",
    "set",
    "str",
    "tuple",
}
_REDACTIONS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "secret",
        re.compile(
            r"(?i)\b(?:bearer\s+)[A-Za-z0-9._~+/=-]{8,}"
            r"|\b(?:ak_|ghp_|github_pat_|xox[baprs]-|glpat-)[A-Za-z0-9_-]{16,}"
            r"|\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}"
            r"|\bAKIA[A-Z0-9]{16}\b"
            r"|\b(?:api[_-]?key|token|password|secret)\s*[=:]\s*[^\s,;]+"
        ),
        "<secret>",
    ),
    (
        "private_key",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?"
            r"-----END [A-Z ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
        "<secret>",
    ),
    ("email", re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b"), "<email>"),
    ("url", re.compile(r"\b(?:https?|wss?)://[^\s)\]}>'\"]+"), "<url>"),
    (
        "windows_path",
        re.compile(r"(?i)\b[A-Z]:\\(?:[^\\\s:'\"]+\\)*[^\\\s:'\"]+"),
        "<path>",
    ),
    (
        "unix_path",
        re.compile(r"(?<![:\w])/(?:[^/\s:'\"]+/)+[^/\s:,)'\"]+"),
        "<path>",
    ),
    (
        "relative_path",
        re.compile(r"(?<![<\w])(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+"),
        "<path>",
    ),
    (
        "ip_address",
        re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
        "<ip>",
    ),
    (
        "uuid",
        re.compile(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
            r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
        ),
        "<id>",
    ),
    (
        "host",
        re.compile(
            r"\b(?:[A-Za-z0-9-]+\.)+(?:app|com|dev|internal|io|local|net|org)\b"
        ),
        "<host>",
    ),
    (
        "private_field",
        re.compile(
            r"(?i)\b(?:account|customer|org(?:anization)?|project|repo(?:sitory)?|"
            r"tenant|user)(?:[_-]?(?:id|name))?\s*[=:]\s*"
            r"(?:'[^']*'|\"[^\"]*\"|[^\s,;)}\]]+)"
        ),
        "<private>",
    ),
    ("identifier", re.compile(r"\b\d{7,}\b"), "<id>"),
)


@dataclass(frozen=True, slots=True)
class SanitizationResult:
    """A public-safe query plus the reasons behind any exclusion."""

    public_query: str
    eligible: bool
    redactions: tuple[str, ...]
    block_reasons: tuple[str, ...]


def _select_error_line(raw_error: str) -> str:
    normalized = _ANSI_RE.sub("", raw_error).replace("\x00", "")
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    if not lines:
        return ""
    candidates = [line for line in lines if _ERROR_LINE_RE.search(line)]
    return candidates[-1] if candidates else lines[-1]


def _redact(text: str) -> tuple[str, tuple[str, ...]]:
    categories: set[str] = set()
    for category, pattern, replacement in _REDACTIONS:
        text, count = pattern.subn(replacement, text)
        if count:
            categories.add("secret" if category == "private_key" else category)
    return text, tuple(sorted(categories))


def _redact_private_terms(text: str, private_terms: Sequence[str]) -> tuple[str, bool]:
    redacted = False
    for private_term in private_terms:
        value = private_term.strip()
        if len(value) < 3:
            continue
        pattern = re.compile(rf"(?<!\w){re.escape(value)}(?!\w)", re.IGNORECASE)
        text, count = pattern.subn("<private>", text)
        redacted = redacted or count > 0
    return text, redacted


def _redact_quoted_values(text: str) -> tuple[str, bool]:
    redacted = False

    def replace(match: re.Match[str]) -> str:
        nonlocal redacted
        if match.group("value").casefold() in _PUBLIC_QUOTED_LITERALS:
            return match.group(0)
        redacted = True
        return "<value>"

    return _QUOTED_VALUE_RE.sub(replace, text), redacted


def _safe_dependencies(
    dependencies: Sequence[str],
) -> tuple[list[str], tuple[str, ...]]:
    valid: list[str] = []
    reasons: set[str] = set()
    for dependency in dependencies:
        value = dependency.strip()
        if not _DEPENDENCY_RE.fullmatch(value):
            reasons.add("invalid_dependency")
            continue
        valid.append(value)
    return sorted(set(valid)), tuple(sorted(reasons))


def sanitize_error(
    raw_error: str,
    dependencies: Sequence[str] = (),
    *,
    private_terms: Sequence[str] = (),
) -> SanitizationResult:
    """Reduce an error to one redacted signature safe for the public commons."""

    selected = _select_error_line(raw_error)
    code_like = bool(_CODE_LIKE_RE.search(selected))
    selected, private_redacted = _redact_private_terms(selected, private_terms)
    selected, value_redacted = _redact_quoted_values(selected)
    redacted, categories = _redact(selected)
    if private_redacted:
        categories = tuple(sorted({*categories, "private_term"}))
    if value_redacted:
        categories = tuple(sorted({*categories, "quoted_value"}))
    redacted = " ".join(redacted.split())
    safe_dependencies, block_reasons = _safe_dependencies(dependencies)
    if code_like:
        block_reasons = tuple(sorted({*block_reasons, "code_like_payload"}))
    if safe_dependencies:
        redacted = f"{redacted} | env: {', '.join(safe_dependencies)}"
    redacted = redacted[:MAX_PUBLIC_QUERY_CHARS].rstrip()
    residual, _ = _redact(redacted)
    if residual != redacted:
        block_reasons = tuple(sorted({*block_reasons, "unsafe_residue"}))
    if len(redacted) < 8:
        block_reasons = tuple(sorted({*block_reasons, "insufficient_context"}))
    if block_reasons:
        redacted = ""
    return SanitizationResult(
        public_query=redacted,
        eligible=not block_reasons,
        redactions=categories,
        block_reasons=block_reasons,
    )
