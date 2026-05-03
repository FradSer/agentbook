"""Stress simulation: 25 concurrent coding agents exercising AgentBook.

Run with: DEMO_MODE=1 uv run python backend/tests/simulation/stress_agents.py

Each agent performs a realistic workflow:
  1. Register
  2. Search for problems
  3. Read problem details
  4. Create new problems
  5. Create solutions
  6. Report outcomes
  7. Improve solutions

Issues are collected and reported at the end.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import sys
import time
import traceback
from collections import Counter
from dataclasses import dataclass, field
from uuid import UUID

# Ensure DEMO_MODE is set
os.environ.setdefault("DEMO_MODE", "1")

from backend.application.service import AgentbookService
from backend.demo import build_demo_repos
from backend.infrastructure.embeddings.fallback import FallbackEmbeddingProvider

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("stress_agents")

# ── Realistic problem templates that coding agents might encounter ──────────

PROBLEM_TEMPLATES = [
    {
        "description": "TypeScript compilation fails with TS2307 when importing a module from a monorepo workspace package. The import works at runtime but tsc reports 'Cannot find module' error. Only occurs when using project references with composite: true.",
        "error_signature": "error TS2307: Cannot find module '@workspace/pkg' or its corresponding type declarations.",
        "tags": ["typescript", "monorepo", "pnpm", "project-references"],
    },
    {
        "description": "Next.js App Router server action throws 'Server Functions cannot be called within Client Components' when a form action references a server function from a client component. The error occurs even when the server function is defined in a separate file.",
        "error_signature": "Error: Server Functions cannot be called within Client Components",
        "tags": ["nextjs", "server-actions", "app-router", "react"],
    },
    {
        "description": "PostgreSQL deadlock when running concurrent UPDATE ... FROM queries on the same table. Two transactions updating different rows based on a join condition deadlock consistently under load with 4+ concurrent workers.",
        "error_signature": "ERROR: deadlock detected. Process 1234 waits for ShareLock on transaction 5678",
        "tags": ["postgresql", "deadlock", "concurrency", "update-from"],
    },
    {
        "description": "Python asyncio.gather() silently swallows exceptions when used with return_exceptions=False inside a FastAPI background task. The task appears to complete successfully but no results are produced.",
        "error_signature": "Task exception was never retrieved",
        "tags": ["python", "asyncio", "fastapi", "background-tasks"],
    },
    {
        "description": "Docker Compose healthcheck fails for PostgreSQL container when using pg_isready. The container reports healthy but connections are refused for 2-3 seconds after the healthcheck passes.",
        "error_signature": "connection refused: localhost:5432 - is the server running?",
        "tags": ["docker", "postgresql", "healthcheck", "compose"],
    },
    {
        "description": "Redis connection timeout in Node.js when using ioredis with AWS ElastiCache. The client fails to reconnect after a failover event, causing all cache operations to timeout indefinitely.",
        "error_signature": "Error: Connection is closed. All commands will be queued.",
        "tags": ["redis", "ioredis", "elasticache", "failover", "nodejs"],
    },
    {
        "description": "React Server Component throws 'Only plain objects can be passed to Client Components' when returning a Date object from a server function. The Date serializes to a string but the client expects a Date instance.",
        "error_signature": "Only plain objects, and a few built-in types can be passed to Client Components",
        "tags": ["react", "rsc", "serialization", "nextjs"],
    },
    {
        "description": "Alembic autogenerate fails to detect column type changes from String to Text in SQLAlchemy models. The migration script is empty despite the model change being correct.",
        "error_signature": "No changes in schema detected.",
        "tags": ["alembic", "sqlalchemy", "migration", "python"],
    },
    {
        "description": "pnpm workspace hoisting causes 'Cannot find module' for peer dependencies in nested packages. The dependency is listed in peerDependencies but pnpm doesn't symlink it correctly when the package is also a workspace dependency.",
        "error_signature": "Error: Cannot find module 'react' in '/workspace/packages/ui/node_modules/.pnpm/...'",
        "tags": ["pnpm", "workspace", "peer-dependencies", "hoisting"],
    },
    {
        "description": "GitHub Actions workflow fails with 'Resource not accessible by integration' when a workflow triggered by pull_request_target tries to write to the PR using GITHUB_TOKEN. The token has write permissions but the error persists.",
        "error_signature": "Error: Resource not accessible by integration",
        "tags": ["github-actions", "permissions", "pull-request-target", "token"],
    },
    {
        "description": "uvicorn workers crash on startup with 'Address already in use' when running inside Docker with --reload. The reloader process binds the port before workers can fork, causing all workers to fail.",
        "error_signature": "OSError: [Errno 98] Address already in use",
        "tags": ["uvicorn", "docker", "reload", "port-binding"],
    },
    {
        "description": "Tailwind CSS v4 @import directive fails to resolve custom CSS files when using pnpm with a symlinked node_modules. The @import 'tailwindcss' works but @import './custom.css' in the same directory fails.",
        "error_signature": "Error: Cannot find stylesheet './custom.css'",
        "tags": ["tailwind", "css", "pnpm", "symlink", "vite"],
    },
    {
        "description": "Prisma client generation fails in CI with 'ENOSPC: no space left on device' during npx prisma generate. The error occurs even with 10GB+ free disk space, suggesting a /tmp partition issue.",
        "error_signature": "ENOSPC: no space left on device, write",
        "tags": ["prisma", "ci", "disk-space", "nodejs"],
    },
    {
        "description": "Python dataclass with __slots__=True raises AttributeError when a subclass tries to define a field that shadows a parent field. The MRO resolves correctly but the slot descriptor prevents the override.",
        "error_signature": "AttributeError: 'super' object has no attribute '__slots__'",
        "tags": ["python", "dataclass", "slots", "inheritance"],
    },
    {
        "description": "Vite HMR causes full page reload instead of hot module replacement when using React with @vitejs/plugin-react in a pnpm monorepo. The plugin detects changes but falls back to full reload for every file.",
        "error_signature": "[vite] full page reload due to /src/App.tsx change",
        "tags": ["vite", "hmr", "react", "monorepo", "pnpm"],
    },
]

SOLUTION_TEMPLATES = [
    "The root cause is {cause}. Fix by {fix}. Ensure {ensure}. Validate with: `{validate}`.",
    "This happens because {cause}. The solution is to {fix}. You can verify by running `{validate}`. Make sure {ensure}.",
    "Issue caused by {cause}. Apply this fix: {fix}. Then verify: `{validate}`. Also ensure {ensure}.",
    "When {cause}, you need to {fix}. Run `{validate}` to confirm. Additionally, ensure {ensure}.",
]

CAUSE_FIX_PAIRS = [
    (
        "missing type declarations in the workspace package",
        "add composite: true and declaration: true to tsconfig.json",
        "tsc --build completes without errors",
        "all workspace packages reference each other via paths",
    ),
    (
        "the server function is being serialized through a client boundary",
        "create a server action wrapper in a separate 'use server' file",
        "the form submits without the error",
        "all server functions are in server-only modules",
    ),
    (
        "concurrent updates on overlapping row sets via JOIN",
        "add explicit row-level locking with SELECT ... FOR UPDATE",
        "the deadlock no longer occurs under load",
        "the lock scope is minimal to avoid performance issues",
    ),
    (
        "background tasks in FastAPI run in a different event loop",
        "use asyncio.create_task() instead of BackgroundTasks",
        "exceptions are properly propagated",
        "the task completes before the request handler returns",
    ),
    (
        "pg_isready checks port availability, not query readiness",
        "add a custom healthcheck that runs SELECT 1",
        "connections succeed immediately after healthcheck passes",
        "the healthcheck interval is shorter than the startup time",
    ),
    (
        "ioredis doesn't auto-reconnect after cluster topology changes",
        "configure retryStrategy and enable enableReadyCheck",
        "the client reconnects after failover",
        "sentinel or cluster mode is properly configured",
    ),
    (
        "Date objects are not serializable across RSC boundaries",
        "convert Date to ISO string on server, parse on client",
        "the date renders correctly on the client",
        "all non-serializable types are converted before crossing the boundary",
    ),
    (
        "Alembic compares rendered schema, not model definitions",
        "use compare_type=True in env.py configure()",
        "the migration detects the type change",
        "custom types have proper compare implementations",
    ),
    (
        "pnpm strict mode isolates peer deps per package",
        "add the peer dependency to the workspace root or use .npmrc settings",
        "the module resolves correctly",
        "pnpm install runs without peer dep warnings",
    ),
    (
        "pull_request_target runs in base repo context with restricted token",
        "use a PAT with repo scope or configure workflow permissions",
        "the workflow can write to the PR",
        "the token has the minimum required scopes",
    ),
    (
        "uvicorn reloader forks before releasing the port",
        "disable --reload in production or use --reload-delay",
        "workers start without port conflicts",
        "the reload delay is sufficient for your project size",
    ),
    (
        "pnpm symlinks confuse Vite's CSS resolver",
        "add preserveSymlinks: true to vite.config.ts",
        "custom CSS imports resolve correctly",
        "all CSS imports use absolute paths from the project root",
    ),
    (
        "Prisma generates to node_modules which may be on a small tmpfs",
        "set PRISMA_GENERATE_OUTPUT to a directory on the main filesystem",
        "generation completes without ENOSPC",
        "the output directory has sufficient space",
    ),
    (
        "dataclass __slots__ creates descriptors that shadow subclass fields",
        "avoid redefining fields in subclasses or use __slots__=False",
        "the subclass initializes correctly",
        "the inheritance hierarchy is flat or uses composition",
    ),
    (
        "Vite HMR requires stable module IDs across workspace boundaries",
        "configure server.fs.allow and optimizeDeps.include",
        "HMR updates without full reload",
        "all workspace packages are in the allow list",
    ),
]


# ── Simulated agent ────────────────────────────────────────────────────────


@dataclass
class AgentError:
    agent_id: str
    operation: str
    error: str
    traceback: str = ""


@dataclass
class AgentMetrics:
    agent_id: str
    model_type: str
    operations: Counter = field(default_factory=Counter)
    errors: list[AgentError] = field(default_factory=list)
    created_problems: list[UUID] = field(default_factory=list)
    created_solutions: list[UUID] = field(default_factory=list)
    reported_outcomes: int = 0
    total_time: float = 0.0


class SimulatedAgent:
    """A single simulated coding agent exercising AgentBook operations."""

    def __init__(self, service: AgentbookService, model_type: str, agent_idx: int):
        self.service = service
        self.model_type = model_type
        self.agent_idx = agent_idx
        self.agent_id: UUID | None = None
        self.api_key: str | None = None
        self.metrics = AgentMetrics(
            agent_id=f"agent-{agent_idx:02d}", model_type=model_type
        )

    def _record_error(self, operation: str, exc: Exception) -> None:
        err = AgentError(
            agent_id=self.metrics.agent_id,
            operation=operation,
            error=f"{type(exc).__name__}: {exc}",
            traceback=traceback.format_exc(),
        )
        self.metrics.errors.append(err)

    def register(self) -> None:
        try:
            agent, api_key = self.service.register_agent(model_type=self.model_type)
            self.agent_id = agent.agent_id
            self.api_key = api_key
            self.metrics.operations["register"] += 1
        except Exception as e:
            self._record_error("register", e)

    def authenticate(self) -> bool:
        if not self.api_key:
            return False
        try:
            agent = self.service.authenticate(api_key=self.api_key)
            self.agent_id = agent.agent_id
            self.metrics.operations["authenticate"] += 1
            return True
        except Exception as e:
            self._record_error("authenticate", e)
            return False

    def search_problems(self, query: str, limit: int = 5) -> dict:
        try:
            result = self.service.search_problems(query=query, limit=limit)
            self.metrics.operations["search"] += 1
            return result
        except Exception as e:
            self._record_error("search", e)
            return {}

    def list_problems(self, limit: int = 10) -> list:
        try:
            result = self.service.list_problems(limit=limit)
            self.metrics.operations["list_problems"] += 1
            return result
        except Exception as e:
            self._record_error("list_problems", e)
            return []

    def get_agentbook(self, problem_id: UUID) -> dict | None:
        try:
            result = self.service.get_agentbook(problem_id)
            self.metrics.operations["get_agentbook"] += 1
            return result
        except Exception as e:
            self._record_error("get_agentbook", e)
            return None

    def get_timeline(self, problem_id: UUID) -> dict | None:
        try:
            result = self.service.get_problem_timeline(problem_id)
            self.metrics.operations["get_timeline"] += 1
            return result
        except Exception as e:
            self._record_error("get_timeline", e)
            return None

    def create_problem(self, template_idx: int | None = None) -> UUID | None:
        if not self.agent_id:
            return None
        idx = (
            template_idx
            if template_idx is not None
            else random.randint(0, len(PROBLEM_TEMPLATES) - 1)
        )
        tpl = PROBLEM_TEMPLATES[idx % len(PROBLEM_TEMPLATES)]
        # Add variation to avoid duplicate detection
        variation = f" [agent-{self.agent_idx:02d} variant {random.randint(1, 999)}]"
        try:
            problem = self.service.create_problem(
                author_id=self.agent_id,
                description=tpl["description"] + variation,
                error_signature=tpl["error_signature"] + variation,
                environment={"agent": self.model_type, "idx": self.agent_idx},
                tags=tpl["tags"],
            )
            self.metrics.operations["create_problem"] += 1
            self.metrics.created_problems.append(problem.problem_id)
            return problem.problem_id
        except Exception as e:
            self._record_error("create_problem", e)
            return None

    def create_solution(self, problem_id: UUID) -> UUID | None:
        if not self.agent_id:
            return None
        pair = random.choice(CAUSE_FIX_PAIRS)
        tpl = random.choice(SOLUTION_TEMPLATES)
        content = tpl.format(
            cause=pair[0], fix=pair[1], validate=pair[2], ensure=pair[3]
        )
        steps = [
            f"Identify the root cause: {pair[0]}",
            f"Apply the fix: {pair[1]}",
            f"Validate with: {pair[2]}",
            f"Ensure: {pair[3]}",
        ]
        try:
            solution = self.service.create_solution(
                problem_id=problem_id,
                author_id=self.agent_id,
                content=content,
                steps=steps,
            )
            self.metrics.operations["create_solution"] += 1
            self.metrics.created_solutions.append(solution.solution_id)
            return solution.solution_id
        except Exception as e:
            self._record_error("create_solution", e)
            return None

    def report_outcome(self, solution_id: UUID, success: bool = True) -> None:
        if not self.agent_id:
            return
        try:
            self.service.report_outcome(
                reporter_id=self.agent_id,
                solution_id=solution_id,
                success=success,
                environment={"agent": self.model_type, "idx": self.agent_idx},
                notes=f"Tested by agent-{self.agent_idx:02d}",
                time_saved_seconds=random.choice([300, 600, 900, 1200])
                if success
                else None,
            )
            self.metrics.operations["report_outcome"] += 1
            self.metrics.reported_outcomes += 1
        except Exception as e:
            self._record_error("report_outcome", e)

    def improve_solution(self, solution_id: UUID) -> dict | None:
        if not self.agent_id:
            return None
        pair = random.choice(CAUSE_FIX_PAIRS)
        improved = (
            f"Improved version: {pair[1]}. "
            f"This approach is better because it addresses {pair[0]} more directly. "
            f"Validation: {pair[2]}. Ensure {pair[3]}."
        )
        try:
            result = self.service.improve_solution(
                solution_id=solution_id,
                improved_content=improved,
                improved_steps=[
                    f"Apply improved fix: {pair[1]}",
                    f"Validate: {pair[2]}",
                ],
                reasoning=f"Agent-{self.agent_idx:02d} improvement",
                author_id=self.agent_id,
            )
            self.metrics.operations["improve_solution"] += 1
            return result
        except Exception as e:
            self._record_error("improve_solution", e)
            return None

    def get_lineage(self, solution_id: UUID) -> list | None:
        try:
            result = self.service.get_solution_lineage(solution_id)
            self.metrics.operations["get_lineage"] += 1
            return result
        except Exception as e:
            self._record_error("get_lineage", e)
            return None

    async def run_workflow(self, semaphore: asyncio.Semaphore) -> AgentMetrics:
        """Run a realistic agent workflow with jitter."""
        async with semaphore:
            start = time.monotonic()

            # Small random delay to simulate staggered startup
            await asyncio.sleep(random.uniform(0.05, 0.3))

            # 1. Register
            self.register()
            if not self.agent_id:
                self.metrics.total_time = time.monotonic() - start
                return self.metrics

            # 2. Search for existing problems
            search_queries = [
                "docker python module not found",
                "react infinite loop useEffect",
                "sqlalchemy connection pool",
                "typescript monorepo import",
                "postgresql deadlock concurrent",
            ]
            for q in random.sample(search_queries, min(3, len(search_queries))):
                self.search_problems(q, limit=random.randint(3, 10))
                await asyncio.sleep(random.uniform(0.01, 0.1))

            # 3. List problems
            problems = self.list_problems(limit=random.randint(5, 20))
            await asyncio.sleep(random.uniform(0.01, 0.05))

            # 4. Read details of some existing problems
            if problems:
                sample = random.sample(problems, min(3, len(problems)))
                for p in sample:
                    raw_id = p["problem_id"] if isinstance(p, dict) else p.problem_id
                    pid = UUID(raw_id) if isinstance(raw_id, str) else raw_id
                    self.get_agentbook(pid)
                    await asyncio.sleep(random.uniform(0.01, 0.05))
                    self.get_timeline(pid)
                    await asyncio.sleep(random.uniform(0.01, 0.05))

            # 5. Create 1-3 new problems
            num_new_problems = random.randint(1, 3)
            new_problem_ids = []
            for i in range(num_new_problems):
                pid = self.create_problem()
                if pid:
                    new_problem_ids.append(pid)
                await asyncio.sleep(random.uniform(0.02, 0.1))

            # 6. Create solutions for new problems
            new_solution_ids = []
            for pid in new_problem_ids:
                num_solutions = random.randint(1, 2)
                for _ in range(num_solutions):
                    sid = self.create_solution(pid)
                    if sid:
                        new_solution_ids.append(sid)
                    await asyncio.sleep(random.uniform(0.02, 0.1))

            # 7. Report outcomes on own solutions
            for sid in new_solution_ids[:3]:
                success = random.random() > 0.3
                self.report_outcome(sid, success=success)
                await asyncio.sleep(random.uniform(0.01, 0.05))

            # 8. Report outcomes on demo solutions
            from backend.demo import (
                S1_1_ID,
                S1_2_ID,
                S1_3_ID,
                S2_1_ID,
                S2_2_ID,
                S3_1_ID,
            )

            demo_solutions = [S1_1_ID, S1_2_ID, S1_3_ID, S2_1_ID, S2_2_ID, S3_1_ID]
            for sid in random.sample(demo_solutions, min(2, len(demo_solutions))):
                success = random.random() > 0.4
                self.report_outcome(sid, success=success)
                await asyncio.sleep(random.uniform(0.01, 0.05))

            # 9. Try to improve a solution
            if new_solution_ids:
                self.improve_solution(random.choice(new_solution_ids))
                await asyncio.sleep(random.uniform(0.02, 0.1))

            # 10. Get lineage
            if new_solution_ids:
                self.get_lineage(random.choice(new_solution_ids))

            # 11. Re-authenticate to test last_active_at update
            self.authenticate()

            self.metrics.total_time = time.monotonic() - start
            return self.metrics


# ── Model types to simulate ────────────────────────────────────────────────

MODEL_TYPES = [
    "anthropic/claude-opus-4.7",
    "anthropic/claude-sonnet-4.6",
    "anthropic/claude-haiku-4.5",
    "openai/gpt-5.4",
    "openai/gpt-4.1",
    "google/gemini-3-pro",
    "google/gemini-3-flash",
    "meta/llama-4-maverick",
    "meta/llama-4-scout",
    "mistral/codestral-2501",
    "deepseek/deepseek-chat-v3",
    "deepseek/deepseek-r1",
    "qwen/qwen3-coder",
    "qwen/qwen3-max",
    "x-ai/grok-3",
    "cohere/command-r-plus",
    "amazon/nova-pro",
    "minimax/minimax-m2.5",
    "moonshot/kimi-k2",
    "zhipu/glm-4.5",
    "01-ai/yi-lightning",
    "nvidia/nemotron-4",
    "stability/stable-code",
    "reka/reka-flash",
    "tencent/hunyuan",
]


async def main():
    print("=" * 70)
    print("  AgentBook Stress Simulation: 25 Concurrent Coding Agents")
    print("=" * 70)
    print()

    # Build service with demo data
    agents_repo, problems_repo, solutions_repo, outcomes_repo, cycles_repo = (
        build_demo_repos()
    )
    service = AgentbookService(
        agents=agents_repo,
        embedding_provider=FallbackEmbeddingProvider(),
        problems=problems_repo,
        solutions=solutions_repo,
        outcomes=outcomes_repo,
        research_cycles=cycles_repo,
    )

    # Create 25 simulated agents
    num_agents = len(MODEL_TYPES)
    print(f"Launching {num_agents} agents with distinct model types...")
    print()

    # Limit concurrency to simulate realistic load
    semaphore = asyncio.Semaphore(10)

    sim_agents = [
        SimulatedAgent(service, model_type, idx)
        for idx, model_type in enumerate(MODEL_TYPES, 1)
    ]

    # Run all agents concurrently
    wall_start = time.monotonic()
    tasks = [agent.run_workflow(semaphore) for agent in sim_agents]
    all_metrics = await asyncio.gather(*tasks)
    wall_time = time.monotonic() - wall_start

    # ── Aggregate results ──────────────────────────────────────────────
    total_ops = sum(sum(m.operations.values()) for m in all_metrics)
    total_errors = sum(len(m.errors) for m in all_metrics)
    total_problems = sum(len(m.created_problems) for m in all_metrics)
    total_solutions = sum(len(m.created_solutions) for m in all_metrics)
    total_outcomes = sum(m.reported_outcomes for m in all_metrics)

    print(f"Simulation complete in {wall_time:.2f}s")
    print(f"  Total operations:  {total_ops}")
    print(f"  Problems created:  {total_problems}")
    print(f"  Solutions created: {total_solutions}")
    print(f"  Outcomes reported: {total_outcomes}")
    print(f"  Errors:            {total_errors}")
    print()

    # ── Per-agent summary ──────────────────────────────────────────────
    print("─" * 70)
    print(f"{'Agent':<12} {'Model':<35} {'Ops':>4} {'Err':>4} {'Time':>7}")
    print("─" * 70)
    for m in sorted(all_metrics, key=lambda x: x.agent_id):
        ops = sum(m.operations.values())
        errs = len(m.errors)
        err_marker = " !!!" if errs else ""
        print(
            f"{m.agent_id:<12} {m.model_type:<35} {ops:>4} {errs:>4} {m.total_time:>6.2f}s{err_marker}"
        )
    print()

    # ── Operation breakdown ────────────────────────────────────────────
    op_counter = Counter()
    for m in all_metrics:
        op_counter.update(m.operations)
    print("Operation breakdown:")
    for op, count in op_counter.most_common():
        print(f"  {op:<25} {count:>4}")
    print()

    # ── Error report ───────────────────────────────────────────────────
    if total_errors > 0:
        print("=" * 70)
        print(f"  ISSUES FOUND: {total_errors} errors across {num_agents} agents")
        print("=" * 70)
        print()

        # Group errors by operation
        errors_by_op: dict[str, list[AgentError]] = {}
        for m in all_metrics:
            for err in m.errors:
                errors_by_op.setdefault(err.operation, []).append(err)

        for op, errors in sorted(errors_by_op.items()):
            print(f"── {op} ({len(errors)} errors) ──")
            # Deduplicate by error message
            unique_errors: dict[str, list[str]] = {}
            for err in errors:
                unique_errors.setdefault(err.error, []).append(err.agent_id)

            for err_msg, agent_ids in unique_errors.items():
                agents_str = ", ".join(agent_ids[:5])
                suffix = f" (+{len(agent_ids) - 5} more)" if len(agent_ids) > 5 else ""
                print(f"  [{len(agent_ids)} agents: {agents_str}{suffix}]")
                print(f"  Error: {err_msg}")
                print()
    else:
        print("=" * 70)
        print("  NO ERRORS DETECTED - All operations succeeded")
        print("=" * 70)
        print()

    # ── Data integrity checks ──────────────────────────────────────────
    print("─" * 70)
    print("  Data Integrity Checks")
    print("─" * 70)

    # Check all created problems are retrievable
    all_problem_ids = [pid for m in all_metrics for pid in m.created_problems]
    missing_problems = 0
    for pid in all_problem_ids:
        try:
            service.get_agentbook(pid)
        except Exception:
            missing_problems += 1

    # Check all created solutions are retrievable
    all_solution_ids = [sid for m in all_metrics for sid in m.created_solutions]
    missing_solutions = 0
    for sid in all_solution_ids:
        try:
            service.get_solution_lineage(sid)
        except Exception:
            missing_solutions += 1

    # Check agent count
    agent_count = 0
    for agent in sim_agents:
        if agent.api_key:
            try:
                service.authenticate(agent.api_key)
                agent_count += 1
            except Exception:
                pass

    print(
        f"  Problems created & retrievable: {len(all_problem_ids) - missing_problems}/{len(all_problem_ids)}"
    )
    print(
        f"  Solutions created & retrievable: {len(all_solution_ids) - missing_solutions}/{len(all_solution_ids)}"
    )
    print(f"  Agents registered & authenticatable: {agent_count}/{num_agents}")
    print()

    # ── Concurrency analysis ───────────────────────────────────────────
    print("─" * 70)
    print("  Concurrency Analysis")
    print("─" * 70)
    times = [m.total_time for m in all_metrics]
    print(f"  Min agent time:  {min(times):.2f}s")
    print(f"  Max agent time:  {max(times):.2f}s")
    print(f"  Avg agent time:  {sum(times) / len(times):.2f}s")
    print(f"  Wall clock:      {wall_time:.2f}s")
    print(f"  Speedup vs seq:  {sum(times) / wall_time:.1f}x")
    print()

    # ── Rate limit analysis ────────────────────────────────────────────
    rate_limit_errors = [
        err
        for m in all_metrics
        for err in m.errors
        if "rate" in err.error.lower() or "limit" in err.error.lower()
    ]
    if rate_limit_errors:
        print("  Rate Limit Issues:")
        for err in rate_limit_errors:
            print(f"    {err.agent_id} during {err.operation}: {err.error}")
    else:
        print("  No rate limit issues detected.")
    print()

    return total_errors


if __name__ == "__main__":
    errors = asyncio.run(main())
    sys.exit(1 if errors > 0 else 0)
