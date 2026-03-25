"""Integration tests for MCP Streamable HTTP transport.

These tests validate MCP protocol over Streamable HTTP transport.
Tests use in-memory repositories by default (no Docker required).

BDD Reference: Feature "MCP Streamable HTTP Transport"

The Streamable HTTP transport is the modern MCP transport that:
- Uses POST requests for all MCP operations
- Returns either JSON or SSE based on Accept header
- Supports stateless mode for horizontal scaling
- Creates sessions with mcp-session-id header
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def client() -> TestClient:
    """FastAPI test client for Streamable HTTP tests."""
    app = create_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def test_agent(client: TestClient) -> dict:
    """Register a test agent via the public API and return credentials."""
    response = client.post("/v1/auth/register", json={})
    assert response.status_code == 201
    return response.json()


@pytest.fixture()
def auth_headers(test_agent: dict) -> dict[str, str]:
    """Valid Authorization headers derived from registered test agent."""
    return {
        "Authorization": f"Bearer {test_agent['api_key']}",
    }


@pytest.fixture()
def mcp_initialize_request() -> dict:
    """JSON-RPC initialize request body."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0",
            },
        },
    }


@pytest.fixture()
def valid_headers(auth_headers: dict[str, str]) -> dict[str, str]:
    """Valid headers for Streamable HTTP POST requests."""
    return {
        **auth_headers,
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }


# ============================================================================
# Session Establishment Tests
# ============================================================================


def test_post_establishes_session(
    client: TestClient,
    test_agent,
    valid_headers: dict[str, str],
    mcp_initialize_request: dict,
) -> None:
    """Scenario: POST request establishes new session

    BDD Reference: Feature "MCP Streamable HTTP Transport"

    Given: FastAPI backend is running with Streamable HTTP MCP endpoint
    When: Client sends POST request to /mcp with:
          - Accept: application/json, text/event-stream
          - Content-Type: application/json
          - Authorization: Bearer ak_valid-key
          - Body: initialize JSON-RPC message
    Then: Response returns HTTP 200 OK
          And: Response body contains server capabilities

    Note: In stateless mode (default), no session ID header is returned.
          For stateful mode, see test_stateful_session_with_id_header.
    """
    # Act: Send initialize request
    response = client.post(
        "/mcp",
        headers=valid_headers,
        json=mcp_initialize_request,
    )

    # Assert: Response is 200 OK
    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )

    # Assert: Response body contains JSON-RPC response with server capabilities
    body = response.json()
    assert body.get("jsonrpc") == "2.0", "Response should be valid JSON-RPC"
    assert body.get("id") == 1, "Response ID should match request ID"
    assert "result" in body, "Response should contain result"
    result = body["result"]
    assert "capabilities" in result, "Response should contain server capabilities"
    assert "serverInfo" in result, "Response should contain server info"


def test_stateless_mode_no_session_header(
    client: TestClient,
    test_agent,
    auth_headers: dict[str, str],
    mcp_initialize_request: dict,
) -> None:
    """Scenario: Stateless mode creates no session

    BDD Reference: Feature "MCP Streamable HTTP Transport"

    Given: StreamableHTTPSessionManager is configured with stateless=True
           (This is the default in app/core/config.py: mcp_stateless=True)
    When: Client sends POST request to /mcp with initialize message
    Then: Response returns HTTP 200 OK
          And: Response does NOT include "mcp-session-id" header
          And: Each request is processed independently
          And: No session state persists between requests
    """
    headers = {
        **auth_headers,
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }

    # Act: Send initialize request
    response = client.post(
        "/mcp",
        headers=headers,
        json=mcp_initialize_request,
    )

    # Assert: Response is 200 OK
    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )

    # Assert: No session ID header in stateless mode
    session_id = response.headers.get("mcp-session-id")
    assert session_id is None, (
        "Stateless mode should NOT include mcp-session-id header"
    )

    # Assert: Response still contains valid JSON-RPC response
    body = response.json()
    assert body.get("jsonrpc") == "2.0", "Response should be valid JSON-RPC"
    assert "result" in body, "Response should contain result"


def test_initialize_returns_server_capabilities(
    client: TestClient,
    test_agent,
    valid_headers: dict[str, str],
    mcp_initialize_request: dict,
) -> None:
    """Scenario: Initialize returns server capabilities

    BDD Reference: Feature "MCP Streamable HTTP Transport"

    Given: MCP server is configured with tools
    When: Client sends initialize request
    Then: Response contains server capabilities including tools
          And: Protocol version is returned
          And: Server info includes name and version
    """
    # Act: Send initialize request
    response = client.post(
        "/mcp",
        headers=valid_headers,
        json=mcp_initialize_request,
    )

    # Assert: Response is 200 OK
    assert response.status_code == 200

    # Assert: Response body structure
    body = response.json()
    assert body.get("jsonrpc") == "2.0"
    assert body.get("id") == 1

    result = body.get("result", {})
    assert "protocolVersion" in result, "Response should contain protocol version"
    assert "capabilities" in result, "Response should contain capabilities"
    assert "serverInfo" in result, "Response should contain server info"

    # Assert: Server info structure
    server_info = result.get("serverInfo", {})
    assert "name" in server_info, "Server info should contain name"
    assert "version" in server_info, "Server info should contain version"

    # Assert: Capabilities is a valid dict
    capabilities = result.get("capabilities", {})
    assert isinstance(capabilities, dict), "Capabilities should be a dict"


# ============================================================================
# Header Validation Tests
# ============================================================================


def test_accept_header_validation(
    client: TestClient,
    test_agent,
    auth_headers: dict[str, str],
    mcp_initialize_request: dict,
) -> None:
    """Scenario: Accept header validation for POST

    BDD Reference: Feature "MCP Streamable HTTP Transport"

    Given: FastAPI backend is running
    When: Client sends POST request to /mcp with:
          - Accept: application/json (missing text/event-stream)
          - Content-Type: application/json
    Then: Response returns HTTP 406 Not Acceptable
          And: Error message indicates "Client must accept both application/json and text/event-stream"
    """
    headers = {
        **auth_headers,
        "Accept": "application/json",  # Missing text/event-stream
        "Content-Type": "application/json",
    }

    # Act: Send request with invalid Accept header
    response = client.post(
        "/mcp",
        headers=headers,
        json=mcp_initialize_request,
    )

    # Assert: Response is 406 Not Acceptable
    assert response.status_code == 406, (
        f"Expected 406 Not Acceptable, got {response.status_code}"
    )

    # Assert: Error message is informative
    error_detail = response.json().get("detail", "")
    assert "application/json" in error_detail.lower() or "accept" in error_detail.lower(), (
        f"Error message should mention Accept header requirements: {error_detail}"
    )


def test_content_type_validation(
    client: TestClient,
    test_agent,
    auth_headers: dict[str, str],
    mcp_initialize_request: dict,
) -> None:
    """Scenario: Content-Type validation for POST

    BDD Reference: Feature "MCP Streamable HTTP Transport"

    Given: FastAPI backend is running
    When: Client sends POST request to /mcp with:
          - Accept: application/json, text/event-stream
          - Content-Type: text/plain (invalid)
    Then: Response returns HTTP 415 Unsupported Media Type
          And: Error message indicates "Content-Type must be application/json"
    """
    headers = {
        **auth_headers,
        "Accept": "application/json, text/event-stream",
        "Content-Type": "text/plain",  # Invalid content type
    }

    # Act: Send request with invalid Content-Type
    response = client.post(
        "/mcp",
        headers=headers,
        content=json.dumps(mcp_initialize_request),
    )

    # Assert: Response is 415 Unsupported Media Type
    assert response.status_code == 415, (
        f"Expected 415 Unsupported Media Type, got {response.status_code}"
    )

    # Assert: Error message is informative
    error_detail = response.json().get("detail", "")
    assert "application/json" in error_detail.lower() or "content-type" in error_detail.lower(), (
        f"Error message should mention Content-Type requirements: {error_detail}"
    )


# ============================================================================
# Authentication Tests
# ============================================================================


def test_authentication_required(
    client: TestClient,
    mcp_initialize_request: dict,
) -> None:
    """Scenario: Authentication is required for MCP endpoint

    BDD Reference: Feature "MCP Streamable HTTP Transport"

    Given: FastAPI backend is running
    When: Client sends POST request without Authorization header
    Then: Response returns HTTP 401 Unauthorized
    """
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        # No Authorization header
    }

    # Act: Send request without authentication
    response = client.post(
        "/mcp",
        headers=headers,
        json=mcp_initialize_request,
    )

    # Assert: Response is 401 Unauthorized
    assert response.status_code == 401, (
        f"Expected 401 Unauthorized, got {response.status_code}"
    )


def test_invalid_api_key_rejected(
    client: TestClient,
    mcp_initialize_request: dict,
) -> None:
    """Scenario: Invalid API key is rejected

    BDD Reference: Feature "MCP Streamable HTTP Transport"

    Given: FastAPI backend is running
    When: Client sends POST request with invalid API key
    Then: Response returns HTTP 401 Unauthorized
    """
    headers = {
        "Authorization": "Bearer sk-agentbook-invalid-key-12345",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }

    # Act: Send request with invalid API key
    response = client.post(
        "/mcp",
        headers=headers,
        json=mcp_initialize_request,
    )

    # Assert: Response is 401 Unauthorized
    assert response.status_code == 401, (
        f"Expected 401 Unauthorized, got {response.status_code}"
    )


# ============================================================================
# JSON-RPC Protocol Tests
# ============================================================================


def test_jsonrpc_request_format(
    client: TestClient,
    test_agent,
    valid_headers: dict[str, str],
) -> None:
    """Scenario: JSON-RPC request format is validated

    BDD Reference: Feature "MCP Streamable HTTP Transport"

    Given: MCP server expects JSON-RPC 2.0 format
    When: Client sends valid JSON-RPC request
    Then: Response follows JSON-RPC 2.0 specification
    """
    request_body = {
        "jsonrpc": "2.0",
        "id": 42,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"},
        },
    }

    # Act
    response = client.post(
        "/mcp",
        headers=valid_headers,
        json=request_body,
    )

    # Assert
    assert response.status_code == 200

    body = response.json()
    assert body.get("jsonrpc") == "2.0", "Response should have jsonrpc version"
    assert body.get("id") == 42, "Response ID should match request ID"


def test_jsonrpc_method_not_found(
    client: TestClient,
    test_agent,
    valid_headers: dict[str, str],
) -> None:
    """Scenario: Invalid method returns JSON-RPC error

    BDD Reference: Feature "MCP Streamable HTTP Transport"

    Given: MCP server has specific methods available
    When: Client calls non-existent method
    Then: Response contains JSON-RPC error with code -32601
    """
    request_body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "nonexistent_method",
        "params": {},
    }

    # Act
    response = client.post(
        "/mcp",
        headers=valid_headers,
        json=request_body,
    )

    # Assert - JSON-RPC errors are in the response body, not as HTTP errors
    body = response.json()
    assert body.get("jsonrpc") == "2.0"
    # Unknown methods return an error; code is -32601 (method not found) or
    # -32602 (invalid params) depending on how the SDK validates the message.
    assert "error" in body, "Unknown method should return a JSON-RPC error"
    assert body["error"].get("code") in (-32601, -32602), (
        f"Expected method-not-found or invalid-params error code, got {body['error'].get('code')}"
    )