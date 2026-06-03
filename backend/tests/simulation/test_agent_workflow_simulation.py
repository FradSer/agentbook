"""Simulate coding agents exercising Agentbook end-to-end.

In-memory tests cover MCP ``recall`` plus the full contribute/report/improve
loop. Postgres tests mirror production persistence using MCP write tools and
``resolve`` (semantic recall is skipped when pgvector cosine ops are unavailable
on JSON embedding columns — the same constraint documented for E2E search).
"""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest

from backend.tests.simulation.agentbook_workflow import AgentbookWorkflowSimulator

pytestmark = pytest.mark.simulation


def test_in_memory_agent_mcp_workflow(service_and_author) -> None:
    """One agent: recall → remember → report → improve → resolve (in-memory)."""
    service, _author_id = service_and_author
    sim = AgentbookWorkflowSimulator(service, model_type="sim/in-memory")

    result = asyncio.run(sim.run_full_mcp_workflow(uuid4().hex[:8]))

    assert result.ok, _format_failures(result)
    assert any(step.name == "report_outcome" and step.ok for step in result.steps)


@pytest.mark.smoke
@pytest.mark.skipif(
    os.getenv("RUN_DOCKER_TESTS") != "1",
    reason="Set RUN_DOCKER_TESTS=1 for Postgres simulation",
)
def test_postgres_agent_mcp_workflow(postgres_service_client) -> None:
    """One agent against Postgres: resolve → remember → report → trace."""
    _client, service = postgres_service_client
    sim = AgentbookWorkflowSimulator(service, model_type="sim/postgres")

    result = asyncio.run(sim.run_postgres_safe_workflow(uuid4().hex[:8]))

    assert result.ok, _format_failures(result)


@pytest.mark.smoke
@pytest.mark.skipif(
    os.getenv("RUN_DOCKER_TESTS") != "1",
    reason="Set RUN_DOCKER_TESTS=1 for Postgres simulation",
)
def test_postgres_concurrent_simulated_agents(postgres_service_client) -> None:
    """Ten agents run the postgres-safe workflow concurrently (shared txn)."""
    _client, service = postgres_service_client

    async def _one(agent_idx: int) -> bool:
        sim = AgentbookWorkflowSimulator(
            service,
            model_type=f"sim/concurrent-{agent_idx}",
        )
        suffix = f"{agent_idx}-{uuid4().hex[:6]}"
        outcome = await sim.run_postgres_safe_workflow(suffix)
        return outcome.ok

    async def _run_batch() -> list[bool]:
        return list(await asyncio.gather(*[_one(i) for i in range(10)]))

    results = asyncio.run(_run_batch())
    assert all(results), f"concurrent agents failed: {results.count(False)}/10"


@pytest.mark.smoke
@pytest.mark.skipif(
    os.getenv("RUN_DOCKER_TESTS") != "1",
    reason="Set RUN_DOCKER_TESTS=1 for Postgres simulation",
)
def test_cross_agent_resolve_and_report(postgres_service_client) -> None:
    """Author contributes via MCP; a second agent resolves and reports."""
    _client, service = postgres_service_client
    token = uuid4().hex[:8]
    description = f"Cross-agent simulation OOMKilled pod {token}"
    error_signature = f"simulation-only: OOMKilled container memory [{token}]"

    author = AgentbookWorkflowSimulator(service, model_type="sim/author")
    author.register()
    assert author.agent is not None

    created = asyncio.run(
        author.mcp(
            "remember",
            {
                "description": description,
                "error_signature": error_signature,
                "solution_content": "Raise memory limits and enable HPA.",
            },
            authenticated=True,
        )
    )
    assert created.get("solution_id")
    solution_id = created["solution_id"]

    peer = AgentbookWorkflowSimulator(service, model_type="sim/peer")
    peer.register()
    assert peer.agent is not None

    resolved = service.resolve(
        agent_id=peer.agent.agent_id,
        description=description,
        error_signature=error_signature,
    )
    assert resolved["status"] == "resolved"
    assert resolved["solutions"]

    report = asyncio.run(
        peer.mcp(
            "report",
            {"solution_id": str(solution_id), "success": True},
            authenticated=True,
        )
    )
    assert report.get("status") == "reported"


def _format_failures(result) -> str:
    failed = [s for s in result.steps if not s.ok]
    lines = [f"{step.name}: {step.error or step.payload}" for step in failed]
    return "workflow failures:\n" + "\n".join(lines)
