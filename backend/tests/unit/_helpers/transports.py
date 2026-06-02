"""Thin REST + MCP JSON-RPC callers reused by cross-transport feature tests.

Both callers are driven by the *same* in-memory ``AgentbookService`` instance so
a parity test compares two serializations of one logical read, not two
independent fixtures. The REST caller wraps the service in a FastAPI
``TestClient``; the MCP caller invokes the dispatcher directly (the same code
path the Streamable HTTP transport reaches after JSON-RPC envelope parsing).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi.testclient import TestClient
from mcp.server import Server

from backend.application.service import AgentbookService
from backend.main import create_app
from backend.presentation.api.deps import get_service
from backend.presentation.mcp.tools import dispatch_tool


def rest_search(
    service: AgentbookService,
    query: str,
    *,
    error_log: str | None = None,
    limit: int = 10,
    include: str | None = None,
    format: str = "concise",
    pattern_class: str | None = None,
) -> dict[str, Any]:
    """Call REST ``GET /v1/search`` against *service* and return the JSON body."""
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app, raise_server_exceptions=False)

    params: dict[str, Any] = {"q": query, "limit": limit, "format": format}
    if error_log is not None:
        params["error_log"] = error_log
    if include is not None:
        params["include"] = include
    if pattern_class is not None:
        params["pattern_class"] = pattern_class

    response = client.get("/v1/search", params=params)
    response.raise_for_status()
    return response.json()


def mcp_recall(
    service: AgentbookService,
    query: str,
    *,
    error_log: str | None = None,
    limit: int = 5,
    pattern_class: str | None = None,
) -> dict[str, Any]:
    """Call the MCP ``recall`` tool against *service* and return the JSON payload.

    Mirrors the dispatcher path used by the Streamable HTTP transport. The
    dispatcher's ``recall`` branch performs no ``await`` of its own, but it is an
    ``async`` function, so it is driven through a fresh event loop here to keep
    the caller synchronous for feature tests.
    """
    server = Server("agentbook-transport-test")
    server._service = service

    arguments: dict[str, Any] = {"query": query, "limit": limit}
    if error_log is not None:
        arguments["error_log"] = error_log
    if pattern_class is not None:
        arguments["pattern_class"] = pattern_class

    result = asyncio.run(dispatch_tool(server, "recall", arguments))
    return json.loads(result[0]["text"])


def best_solution_for(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Extract the first result's ``best_solution`` from either transport body.

    Both ``rest_search`` and ``mcp_recall`` return the same envelope shape
    (``{"results": [...], "total": int, ...}``), so a single extractor serves
    both transports.
    """
    results = payload.get("results") or []
    if not results:
        return None
    return results[0].get("best_solution")
