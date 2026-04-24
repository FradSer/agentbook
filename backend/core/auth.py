"""Shared authentication helpers for API and MCP presentation layers."""

from __future__ import annotations

_BEARER_PREFIX = "Bearer "


def extract_bearer_token(
    authorization: str | None, required_prefix: str | None = None
) -> str | None:
    """Return the Bearer token payload, optionally validating an API-key prefix."""
    if not authorization or not authorization.startswith(_BEARER_PREFIX):
        return None
    token = authorization[len(_BEARER_PREFIX) :].strip()
    if required_prefix and not token.startswith(required_prefix):
        return None
    return token or None
