"""Identity enrichment of the MCP ``recall`` query-event recording.

The recurrence-density instrument records one ``QueryEvent`` per search on the
service's cache-miss path. For dedup and organic-recurrence to work on real MCP
traffic, the ``recall`` handler must hand the service a ``CallerContext`` built
from the MCP request identity: the authenticated agent's hashes when present, or
an ``ip_hash`` derived from the remote address for anonymous callers. Recording
is side-channel — the ``recall`` JSON response must be byte-for-byte unchanged.

These tests drive ``dispatch_tool`` directly with the MCP context vars set,
mirroring ``test_mcp_rate_limit.py``, but against a real in-memory service so the
recorded event is observable.
"""

from __future__ import annotations

import json

import pytest
from mcp.server import Server

from backend.presentation.mcp.context import (
    current_agent as _current_agent_ctx,
    current_remote_addr as _current_remote_addr_ctx,
)
from backend.presentation.mcp.tools import dispatch_tool, hash_remote_addr
from backend.tests.conftest import _build_service

_STRONG_DESC = "Docker daemon socket permission denied; fix via docker group membership"
_STRONG_SIG = (
    "permission denied while trying to connect to the Docker daemon socket "
    "at unix:///var/run/docker.sock"
)
_STRONG_QUERY = _STRONG_SIG
_STRONG_SOLUTION = (
    "Add the user to the docker group and restart the shell session "
    "so the socket becomes group-accessible."
)


@pytest.fixture(autouse=True)
def _reset_mcp_context():
    """Reset both ContextVars between tests so identity does not leak."""
    agent_token = _current_agent_ctx.set(None)
    addr_token = _current_remote_addr_ctx.set(None)
    try:
        yield
    finally:
        _current_remote_addr_ctx.reset(addr_token)
        _current_agent_ctx.reset(agent_token)


def _seed_answered_problem(service, author_id):
    """Approved problem with one active solution, matchable by ``_STRONG_QUERY``."""
    problem = service.create_problem(
        author_id=author_id,
        description=_STRONG_DESC,
        error_signature=_STRONG_SIG,
    )
    service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content=_STRONG_SOLUTION,
        steps=["add user to docker group", "re-login"],
    )
    return problem


def _make_server(service) -> Server:
    server = Server("agentbook-recall-recurrence-test")
    server._service = service
    return server


async def _recall(server: Server) -> dict:
    result = await dispatch_tool(server, "recall", {"query": _STRONG_QUERY})
    return json.loads(result[0]["text"])


@pytest.mark.asyncio
async def test_authenticated_recall_records_identity_enriched_event():
    """An authenticated recall stamps the event with the agent's id and ip_hash."""
    service, author_id = _build_service()
    problem = _seed_answered_problem(service, author_id)
    agent = service.register_agent("claude-sonnet-4-5")[0]
    # Give the authenticated agent identity hashes so the handler forwards them.
    agent.ip_hash = "agent-ip-hash"
    agent.fingerprint_hash = "agent-fp-hash"
    server = _make_server(service)
    _current_agent_ctx.set(agent)

    response = await _recall(server)
    assert response["no_good_match"] is False

    events = service._query_events.list_all()
    assert len(events) == 1
    event = events[0]
    assert event.agent_id == agent.agent_id
    assert event.ip_hash == "agent-ip-hash"
    assert event.fingerprint_hash == "agent-fp-hash"
    assert event.top_match_problem_id == problem.problem_id

    # The response is the unchanged search payload — recording is side-channel.
    assert response == service.search_problems(query=_STRONG_QUERY, limit=5)


@pytest.mark.asyncio
async def test_anonymous_recall_records_dedup_capable_event():
    """An anonymous recall records agent_id=None with ip_hash from the address."""
    service, author_id = _build_service()
    _seed_answered_problem(service, author_id)
    server = _make_server(service)
    _current_remote_addr_ctx.set("203.0.113.7")

    response = await _recall(server)
    assert response["no_good_match"] is False

    events = service._query_events.list_all()
    assert len(events) == 1
    event = events[0]
    assert event.agent_id is None
    assert event.ip_hash == hash_remote_addr("203.0.113.7")
    assert event.ip_hash is not None


@pytest.mark.asyncio
async def test_repeated_anonymous_recall_from_one_address_dedups():
    """Recurrence dedup collapses repeated anonymous queries from one address."""
    service, author_id = _build_service()
    _seed_answered_problem(service, author_id)
    server = _make_server(service)
    _current_remote_addr_ctx.set("203.0.113.7")

    # First miss records; the second is served from cache, so to exercise dedup
    # we clear the search cache between calls — both still share one ip_hash.
    await _recall(server)
    service._search_cache.clear()
    await _recall(server)

    events = service._query_events.list_all()
    assert len(events) == 1, "two queries from one address must collapse to one event"
