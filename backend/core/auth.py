"""Shared authentication helpers for API and MCP presentation layers.

The Bearer scheme is parsed case-insensitively per RFC 7235 §2.1
("The scheme name is case-insensitive"). ``parse_bearer_token``
returns a ``BearerParseResult`` so the presentation layer can emit a
401 detail that names the actual failure (missing header vs wrong
scheme vs wrong prefix) and the agent runtime can recover automatically
instead of retrying the same request that already failed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BearerErrorKind(StrEnum):
    """Why a Bearer parse failed. Stable string values for logging/JSON."""

    MISSING_HEADER = "missing_header"
    WRONG_SCHEME = "wrong_scheme"
    EMPTY_TOKEN = "empty_token"
    WRONG_PREFIX = "wrong_prefix"


@dataclass(frozen=True, slots=True)
class BearerParseResult:
    """Result of ``parse_bearer_token``.

    ``ok`` and ``token`` move together — both are populated on success,
    both are ``None``/``False`` on failure. ``error_kind`` and ``detail``
    are populated only on failure and describe what to tell the client.
    """

    ok: bool
    token: str | None
    error_kind: BearerErrorKind | None
    detail: str | None


def parse_bearer_token(
    authorization: str | None, required_prefix: str | None = None
) -> BearerParseResult:
    """Parse an Authorization header.

    Recognises any capitalisation of the ``Bearer`` scheme. When
    ``required_prefix`` is provided, the token payload is also checked
    against it (used for the ``ak_`` API-key prefix on agentbook).
    """
    if authorization is None or not authorization.strip():
        return BearerParseResult(
            ok=False,
            token=None,
            error_kind=BearerErrorKind.MISSING_HEADER,
            detail="Authorization header required",
        )

    parts = authorization.strip().split(None, 1)
    scheme = parts[0]
    if scheme.lower() != "bearer":
        return BearerParseResult(
            ok=False,
            token=None,
            error_kind=BearerErrorKind.WRONG_SCHEME,
            detail=(
                f"Bearer scheme required (got '{scheme}'). RFC 7235 §2.1: "
                "the scheme name is case-insensitive, so 'bearer' / 'BEARER' "
                "are also accepted."
            ),
        )

    token = parts[1].strip() if len(parts) == 2 else ""
    if not token:
        return BearerParseResult(
            ok=False,
            token=None,
            error_kind=BearerErrorKind.EMPTY_TOKEN,
            detail="Bearer token is empty",
        )

    if required_prefix and not token.startswith(required_prefix):
        return BearerParseResult(
            ok=False,
            token=None,
            error_kind=BearerErrorKind.WRONG_PREFIX,
            detail=f"API key must start with '{required_prefix}'",
        )

    return BearerParseResult(ok=True, token=token, error_kind=None, detail=None)
