"""Identity enrichment of the REST ``/v1/search`` query-event recording.

Sibling to ``test_mcp_recall_recurrence.py``. The recurrence-density instrument
records one ``QueryEvent`` per recall on the service's cache-miss path. For
dedup and organic-recurrence to work on real REST traffic, the ``/v1/search``
route must hand the service a ``CallerContext`` built from the request identity:
the authenticated agent's hashes when present, or an ``ip_hash`` derived from the
remote address for anonymous callers. Recording is side-channel — the search
JSON response must be byte-for-byte unchanged.

Covers backend/tests/features/transport-read-parity.feature (the two recurrence
side-channel scenarios).
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from backend.core.ip_hash import hash_remote_addr
from backend.main import create_app
from backend.presentation.api.deps import get_service
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


def _client(service, *, host: str = "testclient") -> TestClient:
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False, client=(host, 1234))


def _search(client: TestClient, *, token: str | None = None) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = client.get(
        "/v1/search",
        params={"q": _STRONG_QUERY, "format": "full"},
        headers=headers,
    )
    response.raise_for_status()
    return response.json()


def test_authenticated_rest_search_records_identity_enriched_event():
    """An authenticated REST search stamps the event with the agent's hashes."""
    service, author_id = _build_service()
    problem = _seed_answered_problem(service, author_id)
    agent, api_key = service.register_agent("claude-sonnet-4-5")
    # Give the authenticated agent identity hashes so the route forwards them.
    agent.ip_hash = "agent-ip-hash"
    agent.fingerprint_hash = "agent-fp-hash"

    client = _client(service, host="198.51.100.4")
    body = _search(client, token=api_key)
    assert body["results"], "seeded problem must be recalled"

    events = service._query_events.list_all()
    assert len(events) == 1
    event = events[0]
    assert event.agent_id == agent.agent_id
    assert event.ip_hash == "agent-ip-hash"
    assert event.fingerprint_hash == "agent-fp-hash"
    assert event.top_match_problem_id == problem.problem_id

    # Recording is side-channel: caller threading must not leak identity or
    # recording internals into the response payload, and an identical anonymous
    # request returns the same body (the recorded event aside).
    leak_keys = {"caller", "ip_hash", "fingerprint_hash", "agent_id", "query_event"}
    assert not (leak_keys & body.keys())
    assert not (leak_keys & body["results"][0].keys())
    service._search_cache.clear()
    anon_body = _search(_client(service, host="198.51.100.4"))
    assert anon_body == body


def test_anonymous_rest_search_records_dedup_capable_event():
    """An anonymous REST search records agent_id=None with ip_hash from the address."""
    service, author_id = _build_service()
    _seed_answered_problem(service, author_id)

    client = _client(service, host="203.0.113.7")
    body = _search(client)
    assert body["results"]

    events = service._query_events.list_all()
    assert len(events) == 1
    event = events[0]
    assert event.agent_id is None
    assert event.ip_hash == hash_remote_addr("203.0.113.7")
    assert event.ip_hash is not None


def test_repeated_anonymous_rest_search_from_one_address_dedups():
    """Recurrence dedup collapses repeated anonymous REST queries from one address."""
    service, author_id = _build_service()
    _seed_answered_problem(service, author_id)

    client = _client(service, host="203.0.113.7")
    _search(client)
    # The second identical query is served from the search cache, so clear it to
    # exercise dedup proper — both calls still share one ip_hash.
    service._search_cache.clear()
    _search(client)

    events = service._query_events.list_all()
    assert len(events) == 1, "two queries from one address must collapse to one event"
