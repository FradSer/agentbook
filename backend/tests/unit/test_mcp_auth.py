from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.presentation.mcp.auth import TokenVerifier


class _ServiceStub:
    def authenticate(self, api_key: str, agent_info=None):  # noqa: ANN001
        return {"api_key": api_key, "agent_info": agent_info}


def test_token_verifier_accepts_bearer_authorization_header() -> None:
    verifier = TokenVerifier(service=_ServiceStub())
    agent = verifier.verify(authorization="Bearer ak_test-token")
    assert agent["api_key"] == "ak_test-token"


def test_token_verifier_rejects_missing_bearer_authorization() -> None:
    verifier = TokenVerifier(service=_ServiceStub())
    with pytest.raises(HTTPException) as exc_info:
        verifier.verify()
    assert exc_info.value.status_code == 401
    # New detail names the failure mode (header missing) so callers can
    # distinguish "didn't send anything" from "sent wrong scheme".
    assert "Authorization header" in exc_info.value.detail


def test_token_verifier_accepts_lowercase_bearer_scheme() -> None:
    """RFC 7235 §2.1: Authorization scheme is case-insensitive."""
    verifier = TokenVerifier(service=_ServiceStub())
    agent = verifier.verify(authorization="bearer ak_lowercase")
    assert agent["api_key"] == "ak_lowercase"


def test_token_verifier_rejects_wrong_scheme_with_named_failure() -> None:
    verifier = TokenVerifier(service=_ServiceStub())
    with pytest.raises(HTTPException) as exc_info:
        verifier.verify(authorization="Basic dXNlcjpwYXNz")
    assert exc_info.value.status_code == 401
    assert "Bearer scheme required" in exc_info.value.detail


def test_token_verifier_rejects_wrong_prefix_with_named_failure() -> None:
    verifier = TokenVerifier(service=_ServiceStub())
    with pytest.raises(HTTPException) as exc_info:
        verifier.verify(authorization="Bearer sk_wrongprefix")
    assert exc_info.value.status_code == 401
    assert "must start with 'ak_'" in exc_info.value.detail
