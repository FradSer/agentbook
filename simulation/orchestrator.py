"""Simulation orchestrator.

Manages the lifecycle of N simulated agents running persona-driven
workflows against the AgentBook REST API concurrently.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field

from simulation.personas import AgentPersona
from simulation.problem_templates import (
    SEARCH_QUERIES,
    generate_improvement,
    generate_problem,
    generate_solution,
)
from simulation.rest_client import AgentbookRESTClient, OperationResult

# Demo solution IDs for cross-testing (from backend/demo.py)
DEMO_SOLUTION_IDS = [
    "33333333-0000-0000-1111-000000000001",
    "33333333-0000-0000-1111-000000000002",
    "33333333-0000-0000-1111-000000000003",
    "33333333-0000-0000-2222-000000000001",
    "33333333-0000-0000-2222-000000000002",
    "33333333-0000-0000-3333-000000000001",
]


@dataclass
class AgentSimulationResult:
    """Collected results from a single agent's simulation run."""

    agent_id: str
    persona_name: str
    model_type: str
    operations: list[OperationResult] = field(default_factory=list)
    created_problems: list[str] = field(default_factory=list)
    created_solutions: list[str] = field(default_factory=list)
    reported_outcomes: int = 0
    rate_limit_hits: int = 0
    total_time: float = 0.0
    latency_stats: dict = field(default_factory=dict)
    errors: list[dict] = field(default_factory=list)


class SimulationOrchestrator:
    """Manages the lifecycle of a multi-agent REST simulation."""

    def __init__(
        self,
        base_url: str,
        num_agents: int,
        personas: list[AgentPersona],
        max_concurrency: int = 10,
    ):
        self.base_url = base_url
        self.num_agents = num_agents
        self.personas = personas
        self.max_concurrency = max_concurrency
        self.results: list[AgentSimulationResult] = []

    async def run_simulation(self) -> list[AgentSimulationResult]:
        """Execute the full simulation with all agents concurrently."""
        semaphore = asyncio.Semaphore(self.max_concurrency)

        tasks = [
            self._run_agent_workflow(idx, persona, semaphore)
            for idx, persona in enumerate(self.personas)
        ]
        self.results = await asyncio.gather(*tasks)
        return self.results

    async def _run_agent_workflow(
        self,
        idx: int,
        persona: AgentPersona,
        semaphore: asyncio.Semaphore,
    ) -> AgentSimulationResult:
        """Execute a single agent's full workflow based on its persona."""
        agent_label = f"agent-{idx:03d}"
        # Each simulated agent stands in for a distinct external client, so
        # give it a stable synthetic source IP. Per-IP rate limits then behave
        # as they would for N agents on N machines.
        client_ip = f"10.0.{(idx // 254) % 256}.{(idx % 254) + 1}"
        result = AgentSimulationResult(
            agent_id=agent_label,
            persona_name=persona.name,
            model_type=persona.model_type,
        )
        start = time.monotonic()

        async with semaphore:
            async with AgentbookRESTClient(
                self.base_url, agent_label, client_ip
            ) as client:
                # Phase 1: Register
                reg = await client.register(persona.model_type)
                result.operations.append(reg)
                if reg.status_code == 429:
                    result.rate_limit_hits += 1
                await self._jitter(persona)

                # Without credentials, an agent can still use the public read
                # surface — exercise that, then finish.
                if not reg.success:
                    await self._read_only_workflow(client, persona, result)
                    result.total_time = time.monotonic() - start
                    result.latency_stats = client.get_latency_stats()
                    self._collect_errors(result)
                    return result

                # Phase 2: Verify auth
                verify = await client.verify()
                result.operations.append(verify)
                await self._jitter(persona)

                # Phase 3: Search (persona-driven)
                num_searches = self._persona_count(persona.search_intensity, 1, 10)
                queries = random.sample(
                    SEARCH_QUERIES, min(num_searches, len(SEARCH_QUERIES))
                )
                for q in queries:
                    sr = await client.search(q, limit=random.randint(3, 10))
                    result.operations.append(sr)
                    if sr.status_code == 429:
                        result.rate_limit_hits += 1
                    await self._jitter(persona)

                # Phase 4: List problems
                if random.random() < persona.read_prob:
                    lp = await client.list_problems(limit=random.randint(5, 20))
                    result.operations.append(lp)
                    await self._jitter(persona)

                # Phase 5: Read problem details and timelines
                existing_ids = self._extract_problem_ids(result.operations)
                to_read = self._persona_sample(
                    persona.read_prob, existing_ids, max_count=5
                )
                for pid in to_read:
                    detail = await client.get_problem(pid)
                    result.operations.append(detail)
                    await self._jitter(persona)
                    if random.random() < persona.read_prob:
                        tl = await client.get_timeline(pid)
                        result.operations.append(tl)
                        await self._jitter(persona)

                # Phase 6: Create problems (persona-driven)
                if random.random() < persona.create_problem_prob:
                    num_new = random.randint(*persona.num_problems_to_create)
                    for _ in range(num_new):
                        prob = generate_problem(None, idx)
                        cr = await client.create_problem(**prob)
                        result.operations.append(cr)
                        if cr.success and cr.response_data:
                            pid = cr.response_data.get("problem_id")
                            if pid:
                                result.created_problems.append(pid)
                        await self._jitter(persona)

                # Phase 7: Create solutions for new problems
                for pid in result.created_problems:
                    if random.random() < persona.create_solution_prob:
                        num_sols = random.randint(*persona.num_solutions_per_problem)
                        for _ in range(num_sols):
                            sol = generate_solution()
                            cs = await client.create_solution(pid, **sol)
                            result.operations.append(cs)
                            if cs.success and cs.response_data:
                                sid = cs.response_data.get("solution_id")
                                if sid:
                                    result.created_solutions.append(sid)
                            await self._jitter(persona)

                # Phase 8: Report outcomes on own solutions
                for sid in result.created_solutions[:5]:
                    if random.random() < persona.report_outcome_prob:
                        success = random.random() > 0.3
                        ro = await client.report_outcome(
                            sid,
                            success=success,
                            notes=f"Tested by {agent_label}",
                            time_saved_seconds=(
                                random.choice([300, 600, 900, 1200])
                                if success
                                else None
                            ),
                        )
                        result.operations.append(ro)
                        if ro.success:
                            result.reported_outcomes += 1
                        elif ro.status_code == 429:
                            result.rate_limit_hits += 1
                        await self._jitter(persona)

                # Phase 9: Report outcomes on demo solutions
                demo_sample = random.sample(
                    DEMO_SOLUTION_IDS,
                    min(3, len(DEMO_SOLUTION_IDS)),
                )
                for sid in demo_sample:
                    if random.random() < persona.report_outcome_prob:
                        success = random.random() > 0.4
                        ro = await client.report_outcome(
                            sid,
                            success=success,
                            notes=f"Cross-tested by {agent_label}",
                        )
                        result.operations.append(ro)
                        if ro.success:
                            result.reported_outcomes += 1
                        elif ro.status_code == 429:
                            result.rate_limit_hits += 1
                        await self._jitter(persona)

                # Phase 10: Improve solutions
                if result.created_solutions and random.random() < persona.improve_prob:
                    target = random.choice(result.created_solutions)
                    imp = generate_improvement(agent_label)
                    ir = await client.improve_solution(target, **imp)
                    result.operations.append(ir)
                    await self._jitter(persona)

                # Phase 11: Get lineage
                if result.created_solutions and random.random() < persona.lineage_prob:
                    target = random.choice(result.created_solutions)
                    ln = await client.get_lineage(target)
                    result.operations.append(ln)
                    await self._jitter(persona)

                # Phase 12: Dashboard reads
                if random.random() < persona.dashboard_prob:
                    for fn in (
                        client.get_radar,
                        client.get_metrics,
                        client.get_usage,
                    ):
                        dr = await fn()
                        result.operations.append(dr)
                        await self._jitter(persona)

                # Phase 13: Research activity
                if result.created_problems and random.random() < persona.dashboard_prob:
                    ra = await client.get_research_activity(result.created_problems[0])
                    result.operations.append(ra)
                    await self._jitter(persona)

                # Phase 14: Re-verify
                verify2 = await client.verify()
                result.operations.append(verify2)

            result.total_time = time.monotonic() - start
            result.latency_stats = client.get_latency_stats()
            self._collect_errors(result)

        return result

    # ── Helpers ──────────────────────────────────────────────────────

    async def _read_only_workflow(
        self,
        client: AgentbookRESTClient,
        persona: AgentPersona,
        result: AgentSimulationResult,
    ) -> None:
        """Public read surface for an agent that holds no credentials."""
        for q in random.sample(SEARCH_QUERIES, min(3, len(SEARCH_QUERIES))):
            sr = await client.search(q, limit=random.randint(3, 10))
            result.operations.append(sr)
            if sr.status_code == 429:
                result.rate_limit_hits += 1
            await self._jitter(persona)
        lp = await client.list_problems(limit=10)
        result.operations.append(lp)
        await self._jitter(persona)
        for pid in self._extract_problem_ids(result.operations)[:3]:
            detail = await client.get_problem(pid)
            result.operations.append(detail)
            await self._jitter(persona)

    @staticmethod
    def _collect_errors(result: AgentSimulationResult) -> None:
        """Record non-rate-limit failures as errors."""
        for op in result.operations:
            if not op.success and op.status_code != 429 and op.error:
                result.errors.append(
                    {
                        "phase": op.operation,
                        "error": op.error,
                        "status_code": op.status_code,
                    }
                )

    @staticmethod
    async def _jitter(persona: AgentPersona) -> None:
        await asyncio.sleep(random.uniform(persona.min_jitter, persona.max_jitter))

    @staticmethod
    def _persona_count(intensity: float, lo: int, hi: int) -> int:
        return lo + int(intensity * (hi - lo))

    @staticmethod
    def _persona_sample(prob: float, items: list[str], max_count: int) -> list[str]:
        if not items:
            return []
        count = min(max_count, max(0, int(prob * len(items))))
        return random.sample(items, count) if count > 0 else []

    @staticmethod
    def _extract_problem_ids(operations: list[OperationResult]) -> list[str]:
        """Extract problem IDs from previous operation results."""
        ids: list[str] = []
        for op in operations:
            if op.success and op.response_data:
                # From list_problems
                if isinstance(op.response_data, list):
                    for item in op.response_data:
                        if isinstance(item, dict) and "problem_id" in item:
                            ids.append(item["problem_id"])
                # From search results
                if isinstance(op.response_data, dict):
                    results = op.response_data.get("results", [])
                    for item in results:
                        if isinstance(item, dict) and "problem_id" in item:
                            ids.append(item["problem_id"])
        return list(set(ids))
