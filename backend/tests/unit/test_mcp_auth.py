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
    assert "Bearer token" in exc_info.value.detail
