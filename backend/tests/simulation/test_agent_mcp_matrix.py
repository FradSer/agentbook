"""Parametrized MCP agent workflows against PostgreSQL (simulation corpus).

Complements the service-layer E2E matrix: each case runs the postgres-safe
MCP path (remember → resolve → report → trace) using templates from
``stress_agents.PROBLEM_TEMPLATES``.
"""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest

from backend.tests.simulation.agentbook_workflow import AgentbookWorkflowSimulator
from backend.tests.simulation.stress_agents import PROBLEM_TEMPLATES

pytestmark = [
    pytest.mark.simulation,
    pytest.mark.smoke,
    pytest.mark.skipif(
        os.getenv("RUN_DOCKER_TESTS") != "1",
        reason="Set RUN_DOCKER_TESTS=1 for Postgres simulation",
    ),
]

MCP_MATRIX_CASE_COUNT = 25


@pytest.mark.parametrize("case_index", range(MCP_MATRIX_CASE_COUNT))
def test_mcp_agent_workflow_matrix(postgres_service_client, case_index: int) -> None:
    """Simulated agent contributes and reports using MCP tools on Postgres."""
    _client, service = postgres_service_client
    template = PROBLEM_TEMPLATES[case_index % len(PROBLEM_TEMPLATES)]
    suffix = f"mcp-{case_index}-{uuid4().hex[:6]}"

    sim = AgentbookWorkflowSimulator(
        service,
        model_type=f"sim/mcp-matrix-{case_index}",
    )

    async def _run() -> None:
        sim.register()
        assert sim.agent is not None
        description = f"{template['description']} [matrix-{suffix}]"
        error_signature = f"simulation-only: {template['error_signature']} [{suffix}]"
        remember = await sim.mcp(
            "remember",
            {
                "description": description,
                "error_signature": error_signature,
                "solution_content": f"MCP matrix fix for case {case_index}.",
                "tags": list(template.get("tags") or []),
            },
            authenticated=True,
        )
        assert remember.get("solution_id"), remember
        solution_id = remember["solution_id"]

        resolved = service.resolve(
            agent_id=sim.agent.agent_id,
            description=description,
            error_signature=error_signature,
        )
        assert resolved["status"] == "resolved"

        report = await sim.mcp(
            "report",
            {
                "solution_id": str(solution_id),
                "success": case_index % 4 != 0,
                "notes": f"mcp matrix {case_index}",
            },
            authenticated=True,
        )
        assert report.get("status") == "reported"

        trace = await sim.mcp(
            "trace",
            {"id": str(solution_id), "include": ["outcomes"]},
        )
        assert trace.get("type") == "solution"

    asyncio.run(_run())
