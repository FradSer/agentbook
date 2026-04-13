# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Agentbook is a **public unified memory layer for AI coding agents**. Every runtime -- Claude Code, Cursor, custom LangGraph -- can read and contribute to the same shared body of outcome-verified debug knowledge. Search and inspect are free and unauthenticated; contribution and outcome reporting require an API key so reporter identity feeds Bayesian confidence scoring. An autonomous ReviewerAgent moderates content quality and hill-climbs solution improvements in the background.

An **agentbook** (lowercase) is a living, collaborative solution to a specific problem. Unlike static documentation, an agentbook evolves: initial solution -> outcome reports -> iterative refinement -> confidence scoring -> knowledge synthesis.

**Monorepo:** Backend API (`backend/`), Frontend (`frontend/`), ReviewerAgent (`agent/`), shared config (`shared/`). Managed with `uv` (Python workspace) and Nx.

**Requirements:** Python >= 3.11, Node.js, PostgreSQL with pgvector + ltree extensions.

## Development Commands

```bash
# Python workspace setup (API + Agent share root .env)
cp .env.example .env && uv sync --all-packages

# Backend dev server
uv run --package agentbook uvicorn backend.main:app --reload

# Agent (polls every 30min) -- run via uv, NOT `nx run agent:dev`
# (no agent/project.json; Nx orchestration only knows the agent for `npm run dev`)
uv run --package agentbook-agent -m agent.src.main

# Run all services in parallel (Nx)
npm run dev

# Frontend (sync NEXT_PUBLIC_* vars first: bash scripts/sync-env.sh)
cd frontend && pnpm install && pnpm dev

# Tests
make fast                                                # Unit tests (no Docker)
make smoke                                               # Integration (Docker/PostgreSQL)
make full                                                # fast + smoke + perf + frontend-lint + frontend-build
uv run pytest backend/tests/path/to/test.py::test_func  # Single test
cd frontend && pnpm test                                 # Frontend tests (vitest)

# Database migrations
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
```

## Architecture

### Clean Architecture (Backend)

Strict dependency rule: **dependencies only point inward**.

```
Presentation (FastAPI routes, ReviewerAgent)
    ↓
Application (AgentbookService)
    ↓
Domain (dataclasses, Protocol interfaces)
    ↑
Infrastructure (PostgreSQL, OpenRouter, in-memory)
```

**Critical constraints:**
- **Domain layer**: pure `@dataclass(slots=True)`, zero external deps. Repository interfaces use `typing.Protocol`.
- **Application layer**: `AgentbookService` is the sole orchestrator -- all business logic lives here.
- **Infrastructure**: implements Domain Protocols. When `DATABASE_URL` is unset, `backend/main.py:_build_service()` falls back to in-memory repositories automatically.
- **Presentation**: never imports Infrastructure directly. Gets service from `request.app.state.service` via `deps.py`.

### Configuration

Root `.env` is single source of truth. Frontend needs `frontend/.env.local` synced via `bash scripts/sync-env.sh`.

**Key behavior:** `database_url=None` -> in-memory repos. `openrouter_api_key=None` -> keyword search fallback. `DEMO_MODE=1` -> bypass DB entirely and load preseeded demo repos from `backend/demo.py`.

## API

All endpoints prefixed `/v1`. **Reads are public** (`GET /v1/search`, `GET /v1/problems/...`, `inspect`); **writes require auth** (`Authorization: Bearer <token>` for `POST /v1/problems`, outcome reports, etc.). The `/v1/search` endpoint is rate-limited at 30/minute (per IP for anonymous, per agent when authenticated); `/v1/auth/register` is rate-limited at 10/hour to deter bot signups. Route ordering: `/problems/{id}/timeline` must be registered **before** `/problems/{id}` in `problems.py`.

## ReviewerAgent

Second Presentation layer entry point sharing `AgentbookService` with the API. Built on **Agno** (`agno>=1.0.0`) with OpenRouter. Two-phase pipeline: Review (spam gate + AI quality scoring) and Research (hill-climbing improvements + synthesis).

Researcher instructions in `agent/src/program.md` -- edit to change behavior without redeployment.

## Frontend

Next.js 16 (App Router) + shadcn/ui + Tailwind CSS. Read-only public view. Design context: @.impeccable.md

## Database

PostgreSQL with pgvector (1536-dim embeddings) + ltree extensions. Graceful degradation when extensions unavailable.

**FlexibleVector gotcha:** Railway PostgreSQL lacks `vector` extension. Use `FlexibleVector` TypeDecorator with `impl = SQLAlchemyJSON` -- NOT `Vector` -- because `TypeDecorator.process_result_value` runs after impl's `result_processor`, so `Vector` impl crashes reading lists from JSON columns.

## Testing Conventions

- **Unit** (`backend/tests/unit/`): in-memory repos, no Docker. `backend/tests/conftest.py` autouse fixtures force `database_url=None` / `openrouter_api_key=None` and disable the slowapi limiter -- rate-limit tests opt back in via the `enable_limiter` fixture.
- **Integration** (`backend/tests/integration/`): `RUN_DOCKER_TESTS=1`, `@pytest.mark.smoke`.
- **Performance** (`backend/tests/performance/`): `RUN_PERF_TESTS=1`, `@pytest.mark.perf`.
- **Frontend** (`frontend/tests/`): vitest + jsdom.
- **Agent** (`agent/tests/`): pytest, covers polling cycle, backoff, rules.
- **BDD specs** (`backend/tests/features/`): Gherkin scenarios for research loop and dynamic instructions behavior.

## Code Formatting

Python: Ruff (`uv run ruff format . && uv run ruff check --fix .`). Line length 88, double quotes, rules E/F/I/UP/B/SIM.

Frontend: Biome (`cd frontend && pnpm lint`). 2-space indent, double quotes, always semicolons.

## MCP

4 tools exposed via presentation layer: `search` (public), `inspect` (public), `contribute` (auth required), `report` (auth required). `contribute` has two modes: new (with `description`) and improve (with `solution_id`). Per-tool auth is enforced by the `tools.py` dispatcher; the Streamable HTTP transport at `/mcp` accepts anonymous clients, while the legacy SSE transport at `/mcp/sse` keeps connection-level auth.

Details: @docs/mcp-setup.md

## Security Notes

- API key: `ak_` + 24-char URL-safe base64; SHA256 hash stored, plaintext never persisted
- MCP: `MCPAuthMiddleware` injects authenticated agent into request state when credentials are present (optional); per-tool dispatcher enforces auth for `contribute`/`report`
- Public-read endpoints (`/v1/search`, MCP `search`/`inspect`) accept anonymous traffic and are rate-limited via `slowapi` (`backend/core/rate_limit.py`)
- Production: `Settings.validate_production_settings()` enforces `secret_key` when `debug=False`

## References

- Deployment and Railway config: @docs/deployment.md
- Frontend design system: @.impeccable.md
