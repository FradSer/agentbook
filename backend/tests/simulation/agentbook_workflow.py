"""Simulated coding-agent workflows against Agentbook.

Exercises the same entry points real agents use: MCP ``recall`` / ``remember`` /
``report`` / ``trace`` plus ``AgentbookService.resolve`` for the autonomous
resolve-and-register path. Postgres environments without a working pgvector
``cosine_distance`` operator cannot run semantic ``recall``; the postgres-safe
workflow documents that gap and leans on ``resolve`` + exact ``error_signature``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from uuid import UUID

from mcp.server import Server

from backend.application.service import AgentbookService
from backend.domain.models import Agent
from backend.presentation.mcp.context import current_agent
from backend.presentation.mcp.tools import dispatch_tool


def parse_mcp_payload(result: list) -> dict:
    """Decode the JSON text frame returned by MCP tool handlers."""
    return json.loads(result[0]["text"])


@dataclass(slots=True)
class WorkflowStepResult:
    name: str
    ok: bool
    payload: dict | None = None
    error: str | None = None


@dataclass(slots=True)
class AgentWorkflowResult:
    steps: list[WorkflowStepResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(step.ok for step in self.steps)

    def step(
        self,
        name: str,
        *,
        ok: bool,
        payload: dict | None = None,
        error: str | None = None,
    ) -> None:
        self.steps.append(
            WorkflowStepResult(name=name, ok=ok, payload=payload, error=error)
        )


class AgentbookWorkflowSimulator:
    """Drive Agentbook the way an MCP-connected coding agent would."""

    def __init__(
        self,
        service: AgentbookService,
        *,
        model_type: str = "simulation/coding-agent",
    ) -> None:
        self.service = service
        self.model_type = model_type
        self.server = Server("agentbook-simulation")
        self.server._service = service
        self.agent: Agent | None = None
        self.api_key: str | None = None

    def register(self) -> Agent:
        agent, api_key = self.service.register_agent(model_type=self.model_type)
        self.agent = agent
        self.api_key = api_key
        return agent

    async def mcp(
        self,
        tool: str,
        arguments: dict,
        *,
        authenticated: bool = False,
    ) -> dict:
        if authenticated and self.agent is None:
            raise RuntimeError("call register() before authenticated MCP tools")

        token = current_agent.set(self.agent if authenticated else None)
        try:
            frames = await dispatch_tool(self.server, tool, arguments)
            return parse_mcp_payload(frames)
        finally:
            current_agent.reset(token)

    async def run_full_mcp_workflow(self, suffix: str) -> AgentWorkflowResult:
        """Full loop including semantic recall (in-memory / pgvector-ready DBs)."""
        result = AgentWorkflowResult()
        description = (
            f"Simulated agent hit ImportError for private package {suffix}: "
            "cannot import name 'Client' from partially initialized module"
        )
        error_signature = f"ImportError: cannot import name 'Client' [{suffix}]"
        solution_body = (
            "Break the circular import by moving shared types into a neutral "
            f"module. Validated under simulation id {suffix}."
        )

        try:
            self.register()
        except Exception as exc:
            result.step("register", ok=False, error=str(exc))
            return result
        result.step("register", ok=True)

        recall_before = await self.mcp(
            "recall", {"query": description, "limit": 5}, authenticated=False
        )
        recall_ok = "results" in recall_before and "error" not in recall_before
        result.step("recall_before", ok=recall_ok, payload=recall_before)

        remember = await self.mcp(
            "remember",
            {
                "description": description,
                "error_signature": error_signature,
                "solution_content": solution_body,
                "solution_steps": [
                    "Locate the circular edge in the import graph",
                    "Extract shared symbols to a leaf module",
                    "Re-run the failing import",
                ],
                "tags": ["python", "import-error", "simulation"],
            },
            authenticated=True,
        )
        remember_ok = remember.get("problem_id") and remember.get("solution_id")
        result.step("remember_new", ok=bool(remember_ok), payload=remember)

        if not remember_ok:
            return result

        problem_id = UUID(str(remember["problem_id"]))
        solution_id = UUID(str(remember["solution_id"]))

        recall_after = await self.mcp(
            "recall",
            {"query": error_signature, "limit": 5},
            authenticated=False,
        )
        recall_after_ok = (
            "results" in recall_after and recall_after.get("total", 0) >= 0
        )
        result.step("recall_after", ok=recall_after_ok, payload=recall_after)

        trace_problem = await self.mcp(
            "trace",
            {"id": str(problem_id), "include": ["solutions"]},
            authenticated=False,
        )
        trace_ok = trace_problem.get("type") == "problem"
        result.step("trace_problem", ok=trace_ok, payload=trace_problem)

        report = await self.mcp(
            "report",
            {
                "solution_id": str(solution_id),
                "success": True,
                "notes": f"Simulation agent confirmed fix for {suffix}",
                "time_saved_seconds": 600,
            },
            authenticated=True,
        )
        report_ok = report.get("status") == "reported"
        result.step("report_outcome", ok=report_ok, payload=report)

        improve = await self.mcp(
            "remember",
            {
                "solution_id": str(solution_id),
                "improved_content": solution_body + " Also add a lazy import guard.",
                "improved_steps": ["Apply lazy import in hot path"],
                "reasoning": f"Simulation refinement {suffix}",
            },
            authenticated=True,
        )
        improve_ok = "accepted" in improve or improve.get("solution_id")
        result.step("remember_improve", ok=bool(improve_ok), payload=improve)

        trace_lineage = await self.mcp(
            "trace",
            {"id": str(solution_id), "include": ["lineage", "outcomes"]},
            authenticated=False,
        )
        lineage_ok = trace_lineage.get("type") == "solution"
        result.step("trace_lineage", ok=lineage_ok, payload=trace_lineage)

        resolved = self.service.resolve(
            agent_id=self.agent.agent_id,
            description=description,
            error_signature=error_signature,
        )
        resolve_ok = resolved["status"] in {"resolved", "registered"}
        result.step("resolve", ok=resolve_ok, payload=resolved)

        return result

    async def run_postgres_safe_workflow(self, suffix: str) -> AgentWorkflowResult:
        """Persisted-DB workflow avoiding broken semantic recall on JSON embeddings."""
        result = AgentWorkflowResult()
        description = (
            f"Postgres simulation: kubectl rollout stuck {suffix} — "
            "Deployment exceeds progress deadline"
        )
        error_signature = (
            f"simulation-only: deployment progress deadline exceeded [{suffix}]"
        )
        solution_body = (
            "Inspect ReplicaSet events, fix failing readiness probes, then "
            f"roll forward. Simulation token {suffix}."
        )

        try:
            self.register()
        except Exception as exc:
            result.step("register", ok=False, error=str(exc))
            return result
        result.step("register", ok=True)

        # Read-only resolve: auto_post would register a duplicate problem before
        # ``remember`` contributes the canonical agentbook entry.
        resolved_before = self.service.resolve(
            agent_id=self.agent.agent_id,
            description=description,
            error_signature=error_signature,
            auto_post=False,
        )
        result.step(
            "resolve_before",
            ok=resolved_before["status"] in {"no_solutions", "resolved"},
            payload=resolved_before,
        )

        remember = await self.mcp(
            "remember",
            {
                "description": description,
                "error_signature": error_signature,
                "solution_content": solution_body,
                "solution_steps": [
                    "kubectl describe rs",
                    "Fix probe",
                    "kubectl rollout restart",
                ],
            },
            authenticated=True,
        )
        remember_ok = remember.get("problem_id") and remember.get("solution_id")
        result.step("remember_new", ok=bool(remember_ok), payload=remember)
        if not remember_ok:
            return result

        problem_id = UUID(str(remember["problem_id"]))
        solution_id = UUID(str(remember["solution_id"]))

        resolved_after = self.service.resolve(
            agent_id=self.agent.agent_id,
            description=description,
            error_signature=error_signature,
        )
        resolve_after_ok = resolved_after["status"] == "resolved" and bool(
            resolved_after.get("solutions")
        )
        result.step("resolve_after", ok=resolve_after_ok, payload=resolved_after)

        trace_problem = await self.mcp(
            "trace",
            {"id": str(problem_id), "include": ["solutions", "outcomes"]},
        )
        result.step(
            "trace_problem",
            ok=trace_problem.get("type") == "problem",
            payload=trace_problem,
        )

        report = await self.mcp(
            "report",
            {
                "solution_id": str(solution_id),
                "success": True,
                "notes": "rollout recovered",
            },
            authenticated=True,
        )
        result.step(
            "report_outcome",
            ok=report.get("status") == "reported",
            payload=report,
        )

        improve = await self.mcp(
            "remember",
            {
                "solution_id": str(solution_id),
                "improved_content": solution_body + " Document probe thresholds.",
                "reasoning": f"postgres simulation {suffix}",
            },
            authenticated=True,
        )
        result.step(
            "remember_improve",
            ok="accepted" in improve or bool(improve.get("solution_id")),
            payload=improve,
        )

        lineage = await self.mcp(
            "trace",
            {"id": str(solution_id), "include": ["lineage"]},
        )
        result.step(
            "trace_lineage",
            ok=lineage.get("type") == "solution",
            payload=lineage,
        )

        book = self.service.get_agentbook(problem_id)
        result.step(
            "get_agentbook",
            ok=book is not None and str(book.get("problem_id")) == str(problem_id),
            payload={"problem_id": str(problem_id)},
        )

        return result
