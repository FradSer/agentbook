# Repository Guidelines

## Project Structure & Module Organization

Agentbook is a `pnpm`/`uv` monorepo. The FastAPI backend follows Clean Architecture: `backend/domain/` defines dependency-free models and repository protocols; `backend/application/` owns use cases through `AgentbookService`; `backend/infrastructure/` provides persistence, search, and sandbox adapters; and `backend/presentation/` exposes REST and MCP. Dependencies must point inward—inject the service instead of importing infrastructure from presentation.

Autonomous workers live in `agent/src/`. The Next.js UI uses `frontend/app/`, `frontend/components/`, `frontend/lib/`, and `frontend/public/`; `cloudflare/api-proxy/` contains the edge worker. Keep database revisions in `alembic/`, shared configuration in `shared/`, and design or operations material in `docs/`. Tests stay with their service: `backend/tests/{unit,features,integration,eval,simulation}`, `agent/tests/`, `frontend/tests/`, and `cloudflare/api-proxy/tests/`.

## Build, Test, and Development Commands

Initialize with `cp .env.example .env`, `uv sync --all-packages`, and `pnpm install`.

- `pnpm dev` starts backend, agent, and frontend through Nx.
- `make fast` runs offline backend unit and feature tests.
- `uv run pytest backend/tests/unit/test_file.py::test_name` runs one Python test; `pnpm --filter frontend test` runs Vitest.
- `make full` runs the release suite, including Docker-backed checks, evaluations, linting, and the frontend build.
- `pnpm --filter frontend build` verifies a production UI build.

## Coding Style & Naming Conventions

Python targets 3.11: use four-space indentation, type annotations, `snake_case` functions/modules, and `PascalCase` classes. Ruff enforces 88-character lines, sorted imports, and double quotes; run `uv run ruff format . && uv run ruff check --fix .`. TypeScript uses two spaces, double quotes, semicolons, PascalCase components, and `useX` hooks. Run `pnpm --filter frontend lint` for Biome and TypeScript checks.

## Testing Guidelines

Use mandatory RED-GREEN-REFACTOR TDD: add a failing test, implement the smallest fix, then refactor with all tests green. Name Python tests `test_*.py` and Vitest files `*.test.ts` or `*.test.tsx`. No global coverage threshold is configured; every behavior change still requires regression and error-path coverage. Mark external suites with the existing `smoke`, `perf`, `eval`, `e2e`, or `simulation` markers. Confidence-policy changes must bump the frozen version and update `docs/confidence-changelog.md`.

## Commit & Pull Request Guidelines

Use atomic Conventional Commits such as `fix: prevent proxy ssrf`; keep the entire title lowercase and under 50 characters. Push only after relevant lint, build, and test commands pass. PRs must explain the problem, architecture impact, verification, and linked issue; include screenshots for UI work and migration or configuration notes when applicable. CI must pass secret scanning, the frozen-policy guard, backend and agent tests, frontend lint/typecheck, and build. Merge approved PRs with a merge commit.
