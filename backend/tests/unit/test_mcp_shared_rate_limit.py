"""Red tests for the shared MCP rate-limit bucket across legacy + new names.

search and recall MUST share the 30/minute bucket so callers cannot bypass
the limit by alternating tool names.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

from backend.application.service import AgentbookService
from backend.core.mcp_rate_limit import (
    mcp_search_limiter,
    mcp_search_limiter_auth,
)
from backend.domain.models import Agent
from backend.presentation.mcp.context import current_remote_addr
from backend.presentation.mcp.tools import dispatch_tool


def _make_service() -> AgentbookService:
    from backend.infrastructure.persistence.in_memory import (
        InMemoryAgentRepository,
        InMemoryOutcomeRepository,
        InMemoryProblemRepository,
        InMemoryResearchCycleRepository,
        InMemorySolutionRepository,
    )

    agents = InMemoryAgentRepository()
    author_id = uuid4()
    agents.add(Agent(api_key_hash="h", model_type="t", agent_id=author_id))
    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    return service


def _reset_limiters() -> None:
    # Tests opt back in: conftest autouse disables limiters by default.
    mcp_search_limiter.enabled = True
    mcp_search_limiter_auth.enabled = True
    mcp_search_limiter.reset()
    mcp_search_limiter_auth.reset()


def _payload(result) -> dict:
    return json.loads(result[0]["text"])


def test_search_then_recall_shares_bucket() -> None:
    _reset_limiters()
    service = _make_service()
    server = SimpleNamespace(_service=service, _agent=None)

    # Anonymous path: 30/min bucket per IP.
    token = current_remote_addr.set("10.0.0.1")
    try:
        # Exhaust the bucket with legacy name.
        for _ in range(30):
            asyncio.run(dispatch_tool(server, "search", {"query": "q"}))
        # The 31st call on the new name MUST be rate-limited.
        result = asyncio.run(dispatch_tool(server, "recall", {"query": "q"}))
    finally:
        current_remote_addr.reset(token)

    body = _payload(result)
    assert body.get("error") == "rate_limit_exceeded"


def test_recall_then_search_shares_bucket() -> None:
    _reset_limiters()
    service = _make_service()
    server = SimpleNamespace(_service=service, _agent=None)

    token = current_remote_addr.set("10.0.0.2")
    try:
        for _ in range(30):
            asyncio.run(dispatch_tool(server, "recall", {"query": "q"}))
        result = asyncio.run(dispatch_tool(server, "search", {"query": "q"}))
    finally:
        current_remote_addr.reset(token)

    body = _payload(result)
    assert body.get("error") == "rate_limit_exceeded"
