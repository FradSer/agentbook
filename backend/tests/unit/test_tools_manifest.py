"""Cross-runtime tool manifest route."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


@pytest.mark.parametrize("manifest_format", [None, "openai"])
def test_given_openai_compatible_request_when_fetching_manifest_then_function_shape_is_returned(
    manifest_format: str | None,
) -> None:
    params = {} if manifest_format is None else {"format": manifest_format}
    response = _client().get("/v1/tools/manifest", params=params)
    assert response.status_code == 200
    body = response.json()
    assert "tools" in body
    assert body["tools"], "expected at least one tool"
    first = body["tools"][0]
    assert first["type"] == "function"
    fn = first["function"]
    assert "name" in fn
    assert "description" in fn
    assert "parameters" in fn
    names = {entry["function"]["name"] for entry in body["tools"]}
    assert {"search", "contribute", "report", "inspect"}.issubset(names)


def test_given_gemini_request_when_fetching_manifest_then_function_declarations_are_returned() -> None:
    response = _client().get("/v1/tools/manifest", params={"format": "gemini"})
    assert response.status_code == 200
    body = response.json()
    assert "function_declarations" in body
    assert body["function_declarations"], "expected at least one declaration"
    first = body["function_declarations"][0]
    assert "name" in first
    assert "description" in first
    assert "parameters" in first


def test_given_langchain_request_when_fetching_manifest_then_payload_matches_openai() -> None:
    client = _client()
    openai = client.get("/v1/tools/manifest", params={"format": "openai"}).json()
    langchain = client.get("/v1/tools/manifest", params={"format": "langchain"}).json()
    assert openai == langchain


def test_given_unknown_manifest_format_when_fetching_then_validation_error_is_returned() -> None:
    response = _client().get("/v1/tools/manifest", params={"format": "xml"})
    assert response.status_code == 422
