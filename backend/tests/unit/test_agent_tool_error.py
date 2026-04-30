from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.application.errors import AgentToolError, ErrorType
from backend.main import _install_agent_tool_error_handler


def _make_app() -> FastAPI:
    app = FastAPI()
    _install_agent_tool_error_handler(app)

    @app.get("/raise/not-found")
    def _not_found():
        raise AgentToolError(ErrorType.NOT_FOUND, "no such problem", is_retryable=False)

    @app.get("/raise/upstream-timeout")
    def _timeout():
        raise AgentToolError(
            ErrorType.UPSTREAM_TIMEOUT,
            "embedding provider timed out",
            is_retryable=True,
        )

    @app.get("/raise/schema-mismatch")
    def _schema():
        raise AgentToolError(
            ErrorType.SCHEMA_MISMATCH,
            "expected list of strings",
            is_retryable=False,
        )

    @app.get("/raise/http")
    def _http():
        raise HTTPException(status_code=404, detail="not here")

    return app


_client = TestClient(_make_app())


def test_not_found_envelope() -> None:
    body = _client.get("/raise/not-found").json()
    assert body == {
        "error": {
            "type": "NOT_FOUND",
            "is_retryable": False,
            "message": "no such problem",
        }
    }


def test_upstream_timeout_envelope() -> None:
    response = _client.get("/raise/upstream-timeout")
    assert response.status_code == 504
    assert response.json()["error"]["type"] == "UPSTREAM_TIMEOUT"
    assert response.json()["error"]["is_retryable"] is True


def test_schema_mismatch_envelope() -> None:
    response = _client.get("/raise/schema-mismatch")
    assert response.status_code == 422
    assert response.json()["error"]["type"] == "SCHEMA_MISMATCH"


def test_existing_http_exception_unchanged() -> None:
    body = _client.get("/raise/http").json()
    assert "detail" in body
    assert "error" not in body
