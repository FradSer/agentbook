"""Cross-runtime tool manifest route."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_manifest_default_is_openai_shape() -> None:
    response = _client().get("/v1/tools/manifest")
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


def test_manifest_openai_format_contains_all_mcp_tools() -> None:
    response = _client().get("/v1/tools/manifest", params={"format": "openai"})
    assert response.status_code == 200
    names = {entry["function"]["name"] for entry in response.json()["tools"]}
    assert {"search", "contribute", "report", "inspect"}.issubset(names)


def test_manifest_gemini_returns_function_declarations() -> None:
    response = _client().get("/v1/tools/manifest", params={"format": "gemini"})
    assert response.status_code == 200
    body = response.json()
    assert "function_declarations" in body
    assert body["function_declarations"], "expected at least one declaration"
    first = body["function_declarations"][0]
    assert "name" in first
    assert "description" in first
    assert "parameters" in first


def test_manifest_langchain_matches_openai_shape() -> None:
    client = _client()
    openai = client.get("/v1/tools/manifest", params={"format": "openai"}).json()
    langchain = client.get("/v1/tools/manifest", params={"format": "langchain"}).json()
    assert openai == langchain


def test_manifest_unknown_format_returns_422() -> None:
    response = _client().get("/v1/tools/manifest", params={"format": "xml"})
    assert response.status_code == 422
