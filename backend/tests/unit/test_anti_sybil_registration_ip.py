"""Verifies features/anti-sybil-registration-ip.feature.

Registration must stamp an ip_hash derived from the caller address so the
anti-Sybil cluster-merge has a live deterministic signal; without it the only
signal is registration timing (1, below the >=2 union threshold) and clustering
is inert.
"""

from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from backend.application.clustering import detect_clusters
from backend.application.service import AgentbookService
from backend.core.ip_hash import hash_remote_addr
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)


def _service() -> AgentbookService:
    return AgentbookService(
        agents=InMemoryAgentRepository(),
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )


def test_register_agent_persists_ip_hash() -> None:
    service = _service()
    agent, _ = service.register_agent(model_type="test", ip_hash="deadbeef")
    assert agent.ip_hash == "deadbeef"
    assert service._agents.get(agent.agent_id).ip_hash == "deadbeef"


def test_register_route_stamps_ip_hash_from_request() -> None:
    from backend.main import create_app
    from backend.presentation.api.deps import get_service

    service = _service()
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    client = TestClient(app, raise_server_exceptions=False)

    body = client.post("/v1/auth/register", json={"model_type": "test"}).json()
    agent = service._agents.get(UUID(body["agent_id"]))
    assert agent is not None
    assert agent.ip_hash is not None
    # TestClient stamps the ASGI scope client host as "testclient".
    assert agent.ip_hash == hash_remote_addr("testclient")


def test_same_address_registrations_collapse_into_one_cluster() -> None:
    service = _service()
    shared = hash_remote_addr("203.0.113.7")
    agents = [
        service.register_agent(model_type="test", ip_hash=shared)[0] for _ in range(3)
    ]
    clusters = detect_clusters(agents)
    assert len(clusters) == 1
    assert len(clusters[0]) == 3
