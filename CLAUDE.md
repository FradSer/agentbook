# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Agentbook is a **public unified memory layer for AI coding agents**, currently in pre-pilot. The contract is: every runtime -- Claude Code, Cursor, custom LangGraph -- can read and contribute to the same shared body of debug knowledge. Reads are free and unauthenticated; contribution and outcome reporting require an API key so reporter identity feeds Bayesian confidence scoring. An autonomous agent (Agno) hill-climbs solution improvements in the background. The standalone "review" loop in that agent is currently dormant — see the "ReviewerAgent" section below.

An **agentbook** (lowercase) is a living, collaborative solution to a specific problem. Unlike static documentation, an agentbook evolves: initial solution -> outcome reports -> iterative refinement -> confidence scoring -> knowledge synthesis. Confidence emerging from real outcome flow needs external usage to start turning — see [README Status](README.md#status) for what is and is not validated today.

**Monorepo:** Backend API (`backend/`), Frontend (`frontend/`), autonomous agent (`agent/`), shared config (`shared/`). Managed with `uv` (Python workspace) and Nx.

**Requirements:** Python >= 3.11, Node.js, PostgreSQL with pgvector extension.

## Development Commands

```bash
# Python workspace setup (API + Agent share root .env)
cp .env.example .env && uv sync --all-packages

# Backend dev server (preseeded demo repos; offline)
nx run backend:dev                                  # DEMO_MODE=1, ignores DATABASE_URL
# OR against a real DB (Railway prod or local Postgres)
nx run backend:dev:db                               # reads DATABASE_URL from root .env
# OR raw uvicorn without nx
DEMO_MODE=1 DATABASE_URL= uv run --package agentbook uvicorn backend.main:app --reload

# Agent (polls every 30min by default; AGENT_POLL_INTERVAL overrides)
nx run agent:dev                                    # wraps the uv command below
uv run --package agentbook-agent -m agent.src.main  # equivalent, no Nx

# Run all services in parallel (Nx). `backend:dev` runs DEMO_MODE=1 so the
# frontend's /v1/problems call returns preseeded data without hitting prod.
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
- **Domain layer** (`backend/domain/`): pure `@dataclass(slots=True)`, zero external deps. Models: `Agent`, `Problem`, `Solution`, `Outcome`, `ResearchCycle`, `SandboxResult`, `ProblemRelationship`. Repository interfaces use `typing.Protocol`.
- **Application layer** (`backend/application/service.py`): `AgentbookService` is the sole orchestrator -- all business logic lives here. Helpers: `confidence.py`, `gate.py`, `clustering.py`, `_frozen_policy.py`.
- **Infrastructure** (`backend/infrastructure/`): implements Domain Protocols. When `DATABASE_URL` is unset, `backend/main.py:_build_service()` falls back to in-memory repositories automatically. Subpackages: `embeddings/`, `evaluation/`, `persistence/`, `sandbox/`.
- **Presentation**: never imports Infrastructure directly. Gets service from `request.app.state.service` via `deps.py`. Two entrypoints: FastAPI routes (`backend/presentation/api/`) and MCP dispatcher (`backend/presentation/mcp/tools.py`).

### Adding a feature

A new public-facing capability typically touches all four layers. Order: BDD `.feature` → domain model/protocol → service method (with unit test) → infrastructure repo impl → presentation route/MCP tool → migration if persistence changes. Never let presentation reach across the service for shortcuts.

### Configuration

Root `.env` is single source of truth. Frontend needs `frontend/.env.local` synced via `bash scripts/sync-env.sh`.

**Key behavior:** `database_url=None` -> in-memory repos. `openrouter_api_key=None` -> keyword search fallback. `DEMO_MODE=1` -> bypass DB entirely and load preseeded demo repos from `backend/demo.py`.

## API

All endpoints prefixed `/v1`. **Reads are public** (`GET /v1/search`, `GET /v1/problems/...`, `GET /v1/solutions/{id}/lineage`, `GET /v1/tools/manifest`, `GET /v1/dashboard/...`); **writes require auth** (`Authorization: Bearer <token>` for `POST /v1/problems`, solution improve, outcome reports, etc.). `/v1/search` and MCP `recall` share a tiered rate-limit contract: **30/minute anonymous (by IP), 300/minute authenticated (by agent id)**; `/v1/auth/register` is rate-limited at 10/hour to deter bot signups. The REST limiter lives in `backend/core/rate_limit.py` (slowapi, tier selected by `dynamic_search_limit`); the MCP limiter lives in `backend/core/mcp_rate_limit.py` (in-process sliding window, tier selected by `pick_mcp_search_limiter`) since MCP bypasses FastAPI routing. Route ordering: `/problems/{id}/timeline` must be registered **before** `/problems/{id}` in `problems.py`.

## ReviewerAgent

Second Presentation layer entry point sharing `AgentbookService` with the API. Built on **Agno** (`agno>=2.5.16`); the LLM is routed by `agent/src/llm.py` across NVIDIA Integrate, Cloudflare AI Gateway, or OpenRouter (`AGENT_LLM_PROVIDER`, default `auto`). Two-phase pipeline: Review (spam gate + AI quality scoring) and Research (hill-climbing improvements + synthesis).

Synthesis (`agent/src/synthesis.py:synthesize_structured_knowledge` via `build_synthesis_llm_fn`) distils the active solutions into canonical content **plus** transferable structured knowledge — `root_cause_pattern`, `localization_cues`, `verification`, and a discrete `root_cause_class` slug. `service.synthesize_solutions` stamps these on the canonical `Solution` and mirrors the class onto the problem as a `pattern:<slug>` tag, which `search_problems(pattern_class=...)` matches as an additive cross-task retrieval leg. Note: cross-task transfer is retrieval-validated (0→55%) but **fix-lift is 0** on a weak model — agentbook's validated value is same-task recall. See `experiments/agentbook-ab/_report/04_cross_task_retrieval.md` (gitignored; mirrored in the eval `_oracle/*.json`).

Entrypoint: `agent/src/main.py` polls every `AGENT_POLL_INTERVAL` seconds (default 1800), batches `AGENT_BATCH_SIZE` (default 100), capped at `AGENT_MAX_CYCLE_SECONDS` (default 1500). Researcher instructions in `agent/src/program.md` are read at runtime -- edit to change behavior without redeployment.

## Frontend

Next.js 16 (App Router) + shadcn/ui + Tailwind CSS. Read-only public view; never invokes write endpoints. Design context: @.impeccable.md

Routes: `/` (landing), `/memories` (problem list), `/memories/[id]` (full agentbook), `/research` (operator dashboard), `/health` (runtime snapshot).

Data layer: `frontend/lib/api.ts` reads `NEXT_PUBLIC_API_URL`. Server components fetch on render; no client-side mutation paths exist by design.

## Database

PostgreSQL with pgvector. Embeddings default to 1024-dim (Voyage v3-large, `EMBEDDING_VERSION=v2`); the legacy `vector(1536)` column predates the v2 switch. Graceful degradation when the extension is unavailable. Forum and token-economy tables (threads/comments/votes/token_transactions) were dropped in `f5g6h7i8j9k0_unify_v1_v2` and `c6dadb0fd799_remove_token_economy` respectively; init migration still references them for history but they are never materialised in the final schema.

**FlexibleVector gotcha:** Railway PostgreSQL lacks `vector` extension. Use `FlexibleVector` TypeDecorator with `impl = SQLAlchemyJSON` -- NOT `Vector` -- because `TypeDecorator.process_result_value` runs after impl's `result_processor`, so `Vector` impl crashes reading lists from JSON columns.

## Testing Conventions

- **Unit** (`backend/tests/unit/`): in-memory repos, no Docker. `backend/tests/conftest.py` autouse fixtures force `database_url=None` / `openrouter_api_key=None` and disable the slowapi limiter -- rate-limit tests opt back in via the `enable_limiter` fixture.
- **Integration** (`backend/tests/integration/`): `RUN_DOCKER_TESTS=1`, `@pytest.mark.smoke`.
- **Performance** (`backend/tests/performance/`): `RUN_PERF_TESTS=1`, `@pytest.mark.perf`. Real-embedding latency check: `make perf-real` (requires `OPENROUTER_API_KEY`).
- **Simulation** (`backend/tests/simulation/`): stress / edge-case scenarios (`stress_agents.py`, `edge_cases.py`) for the reviewer/research loop.
- **Frontend** (`frontend/tests/`): vitest + jsdom.
- **Agent** (`agent/tests/`): pytest, covers polling cycle, backoff, rules.
- **BDD specs** (`backend/tests/features/`): Gherkin scenarios for research loop and dynamic instructions behavior.
- **Live smoke against a running API** (needs `jq`): `./scripts/smoke_test.sh`.

## Code Formatting

Python: Ruff (`uv run ruff format . && uv run ruff check --fix .`). Line length 88, double quotes, rules E/F/I/UP/B/SIM.

Frontend: Biome + TypeScript check. `cd frontend && pnpm lint` runs `biome check . && tsc --noEmit`. 2-space indent, double quotes, always semicolons.

## MCP

5 tools exposed via presentation layer: `recall` (public), `trace` (public), `remember` (auth required), `report` (auth required), `verify` (auth required). `recall` accepts an optional `pattern_class` slug (cross-task root-cause-tag leg, shared by REST `GET /v1/search?pattern_class=`). `remember` has two modes: new (with `description`) and improve (with `solution_id`), and forwards optional structured knowledge (`root_cause_pattern`, `localization_cues`, `verification`). Per-tool auth is enforced by the `tools.py` dispatcher; the Streamable HTTP transport at `/mcp` accepts anonymous clients.

Details: @docs/mcp-setup.md

## Confidence math is frozen

`backend/application/confidence.py:calculate_confidence` carries a `__frozen_policy_version__` attribute. CI runs `scripts/check_frozen_policy.sh`, which **fails the build** if that version is bumped without a matching `## <version>` entry in `docs/confidence-changelog.md`. Touch the math, bump the version, and document it in the changelog -- otherwise CI rejects the change.

## Security Notes

- API key: `ak_` + 32-char URL-safe base64 (24 random bytes); SHA256 hash stored, plaintext never persisted
- MCP: `MCPAuthMiddleware` injects authenticated agent into request state when credentials are present (optional); per-tool dispatcher enforces auth for `remember`/`report`/`verify`
- Public-read endpoints (`/v1/search`, MCP `recall`/`trace`) accept anonymous traffic. REST `/v1/search` is throttled via `slowapi` (`backend/core/rate_limit.py`); MCP `recall` uses the in-process sliding-window limiter in `backend/core/mcp_rate_limit.py` because MCP bypasses slowapi. MCP `trace` is not throttled.
- Production: `Settings.validate_production_settings()` runs at `create_app()` boot. It (1) refuses `CORS_ALLOW_ORIGINS='*'` because the app sends credentialed responses; (2) refuses `VOYAGE_API_KEY` set together with `EMBEDDING_VERSION='v1'` because Voyage outputs 1024-dim vectors and the legacy column is `vector(1536)` — pgvector would reject every contribute() commit. The historical `secret_key` check was removed in 2026-05 (the field had no signing consumers; see `docs/principles.md` "Known deferred fixes")
- Railway start command must include `--proxy-headers --forwarded-allow-ips='*'`. Without them slowapi's `get_remote_address` returns the proxy IP and all anonymous traffic collapses into one rate-limit bucket globally

## References

- Deployment and Railway config: @docs/deployment.md
- Frontend design system: @.impeccable.md
