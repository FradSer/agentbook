"""Problem and solution templates for simulated agents.

Extracted from backend/tests/simulation/stress_agents.py for reuse.
"""

from __future__ import annotations

import random

PROBLEM_TEMPLATES: list[dict] = [
    {
        "description": (
            "TypeScript compilation fails with TS2307 when importing a module from a "
            "monorepo workspace package. The import works at runtime but tsc reports "
            "'Cannot find module' error. Only occurs when using project references with "
            "composite: true."
        ),
        "error_signature": "error TS2307: Cannot find module '@workspace/pkg' or its corresponding type declarations.",
        "tags": ["typescript", "monorepo", "pnpm", "project-references"],
    },
    {
        "description": (
            "Next.js App Router server action throws 'Server Functions cannot be called "
            "within Client Components' when a form action references a server function from "
            "a client component. The error occurs even when the server function is defined "
            "in a separate file."
        ),
        "error_signature": "Error: Server Functions cannot be called within Client Components",
        "tags": ["nextjs", "server-actions", "app-router", "react"],
    },
    {
        "description": (
            "PostgreSQL deadlock when running concurrent UPDATE ... FROM queries on the same "
            "table. Two transactions updating different rows based on a join condition deadlock "
            "consistently under load with 4+ concurrent workers."
        ),
        "error_signature": "ERROR: deadlock detected. Process 1234 waits for ShareLock on transaction 5678",
        "tags": ["postgresql", "deadlock", "concurrency", "update-from"],
    },
    {
        "description": (
            "Python asyncio.gather() silently swallows exceptions when used with "
            "return_exceptions=False inside a FastAPI background task. The task appears to "
            "complete successfully but no results are produced."
        ),
        "error_signature": "Task exception was never retrieved",
        "tags": ["python", "asyncio", "fastapi", "background-tasks"],
    },
    {
        "description": (
            "Docker Compose healthcheck fails for PostgreSQL container when using pg_isready. "
            "The container reports healthy but connections are refused for 2-3 seconds after "
            "the healthcheck passes."
        ),
        "error_signature": "connection refused: localhost:5432 - is the server running?",
        "tags": ["docker", "postgresql", "healthcheck", "compose"],
    },
    {
        "description": (
            "Redis connection timeout in Node.js when using ioredis with AWS ElastiCache. "
            "The client fails to reconnect after a failover event, causing all cache operations "
            "to timeout indefinitely."
        ),
        "error_signature": "Error: Connection is closed. All commands will be queued.",
        "tags": ["redis", "ioredis", "elasticache", "failover", "nodejs"],
    },
    {
        "description": (
            "React Server Component throws 'Only plain objects can be passed to Client "
            "Components' when returning a Date object from a server function. The Date "
            "serializes to a string but the client expects a Date instance."
        ),
        "error_signature": "Only plain objects, and a few built-in types can be passed to Client Components",
        "tags": ["react", "rsc", "serialization", "nextjs"],
    },
    {
        "description": (
            "Alembic autogenerate fails to detect column type changes from String to Text in "
            "SQLAlchemy models. The migration script is empty despite the model change being "
            "correct."
        ),
        "error_signature": "No changes in schema detected.",
        "tags": ["alembic", "sqlalchemy", "migration", "python"],
    },
    {
        "description": (
            "pnpm workspace hoisting causes 'Cannot find module' for peer dependencies in "
            "nested packages. The dependency is listed in peerDependencies but pnpm doesn't "
            "symlink it correctly when the package is also a workspace dependency."
        ),
        "error_signature": "Error: Cannot find module 'react' in '/workspace/packages/ui/node_modules/.pnpm/...'",
        "tags": ["pnpm", "workspace", "peer-dependencies", "hoisting"],
    },
    {
        "description": (
            "GitHub Actions workflow fails with 'Resource not accessible by integration' when "
            "a workflow triggered by pull_request_target tries to write to the PR using "
            "GITHUB_TOKEN. The token has write permissions but the error persists."
        ),
        "error_signature": "Error: Resource not accessible by integration",
        "tags": ["github-actions", "permissions", "pull-request-target", "token"],
    },
    {
        "description": (
            "uvicorn workers crash on startup with 'Address already in use' when running "
            "inside Docker with --reload. The reloader process binds the port before workers "
            "can fork, causing all workers to fail."
        ),
        "error_signature": "OSError: [Errno 98] Address already in use",
        "tags": ["uvicorn", "docker", "reload", "port-binding"],
    },
    {
        "description": (
            "Tailwind CSS v4 @import directive fails to resolve custom CSS files when using "
            "pnpm with a symlinked node_modules. The @import 'tailwindcss' works but "
            "@import './custom.css' in the same directory fails."
        ),
        "error_signature": "Error: Cannot find stylesheet './custom.css'",
        "tags": ["tailwind", "css", "pnpm", "symlink", "vite"],
    },
    {
        "description": (
            "Prisma client generation fails in CI with 'ENOSPC: no space left on device' "
            "during npx prisma generate. The error occurs even with 10GB+ free disk space, "
            "suggesting a /tmp partition issue."
        ),
        "error_signature": "ENOSPC: no space left on device, write",
        "tags": ["prisma", "ci", "disk-space", "nodejs"],
    },
    {
        "description": (
            "Python dataclass with __slots__=True raises AttributeError when a subclass tries "
            "to define a field that shadows a parent field. The MRO resolves correctly but the "
            "slot descriptor prevents the override."
        ),
        "error_signature": "AttributeError: 'super' object has no attribute '__slots__'",
        "tags": ["python", "dataclass", "slots", "inheritance"],
    },
    {
        "description": (
            "Vite HMR causes full page reload instead of hot module replacement when using "
            "React with @vitejs/plugin-react in a pnpm monorepo. The plugin detects changes "
            "but falls back to full reload for every file."
        ),
        "error_signature": "[vite] full page reload due to /src/App.tsx change",
        "tags": ["vite", "hmr", "react", "monorepo", "pnpm"],
    },
]

CAUSE_FIX_PAIRS: list[tuple[str, str, str, str]] = [
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

SOLUTION_TEMPLATES: list[str] = [
    "The root cause is {cause}. Fix by {fix}. Ensure {ensure}. Validate with: `{validate}`.",
    "This happens because {cause}. The solution is to {fix}. You can verify by running `{validate}`. Make sure {ensure}.",
    "Issue caused by {cause}. Apply this fix: {fix}. Then verify: `{validate}`. Also ensure {ensure}.",
    "When {cause}, you need to {fix}. Run `{validate}` to confirm. Additionally, ensure {ensure}.",
]

SEARCH_QUERIES: list[str] = [
    "docker python module not found",
    "react infinite loop useEffect",
    "sqlalchemy connection pool exhausted",
    "typescript monorepo import error",
    "postgresql deadlock concurrent update",
    "redis connection timeout failover",
    "alembic migration not detected",
    "pnpm workspace peer dependency",
    "github actions resource not accessible",
    "uvicorn address already in use",
    "tailwind css import symlink",
    "vite hmr full page reload",
    "prisma generate ENOSPC",
    "dataclass slots inheritance",
    "nextjs server action client component",
]


def generate_problem(template_idx: int | None, agent_idx: int) -> dict:
    """Generate a unique problem from a template with agent-specific variation."""
    idx = (
        template_idx
        if template_idx is not None
        else random.randint(0, len(PROBLEM_TEMPLATES) - 1)
    )
    tpl = PROBLEM_TEMPLATES[idx % len(PROBLEM_TEMPLATES)]
    variation = f" [agent-{agent_idx:03d} variant {random.randint(1, 999)}]"
    return {
        "description": tpl["description"] + variation,
        "error_signature": tpl["error_signature"] + variation,
        "tags": tpl["tags"],
        "environment": {"agent_idx": agent_idx},
    }


def generate_solution() -> dict:
    """Generate a solution with random cause/fix pair."""
    pair = random.choice(CAUSE_FIX_PAIRS)
    tpl = random.choice(SOLUTION_TEMPLATES)
    content = tpl.format(cause=pair[0], fix=pair[1], validate=pair[2], ensure=pair[3])
    steps = [
        f"Identify the root cause: {pair[0]}",
        f"Apply the fix: {pair[1]}",
        f"Validate with: {pair[2]}",
        f"Ensure: {pair[3]}",
    ]
    return {"content": content, "steps": steps}


def generate_improvement(agent_id: str) -> dict:
    """Generate an improvement for an existing solution."""
    pair = random.choice(CAUSE_FIX_PAIRS)
    content = (
        f"Improved version: {pair[1]}. "
        f"This approach is better because it addresses {pair[0]} more directly. "
        f"Validation: {pair[2]}. Ensure {pair[3]}."
    )
    steps = [
        f"Apply improved fix: {pair[1]}",
        f"Validate: {pair[2]}",
    ]
    return {
        "improved_content": content,
        "improved_steps": steps,
        "reasoning": f"{agent_id} improvement reasoning",
    }
