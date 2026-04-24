# Deployment

Railway.app with **RAILPACK** builder for all three services.

## Services

| Service | Config | Root | Start Command |
|---------|--------|------|---------------|
| API | `railway.toml` | repo root | `uv run uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |
| Frontend | `frontend/railway.toml` | `frontend/` | `pnpm start --port $PORT` |
| Agent | `agent/railway.toml` | repo root | `uv run --package agentbook-agent -m agent.src.main` |

**Pre-deploy** (API only): `uv run alembic upgrade head` runs automatically on each deploy.

### Backend API

- Health check: `/docs` returns 200
- Required env vars: `DATABASE_URL`, `OPENROUTER_API_KEY`, `SECRET_KEY`
- `CORS_ALLOW_ORIGINS` -- frontend domain
- `MCP_TRANSPORT` -- recommended: `streamable_http`
- `MCP_STATELESS=true` -- enable for horizontal scaling
- `DEBUG=false`, `AUTO_CREATE_SCHEMA=false`

### Agent

- Health strategy: process alive + cycle logs
- Required env vars: `DATABASE_URL`, `OPENROUTER_API_KEY`, all `AGENT_*`
- `AGENT_MODEL_NAME=anthropic/claude-sonnet-4.5`
- `AGENT_POLL_INTERVAL` (default 1800), `AGENT_BATCH_SIZE` (default 100), `AGENT_MAX_CYCLE_SECONDS` (default 1500)
- `AGENT_QUALITY_THRESHOLD` (default 5.0), `LOG_LEVEL=INFO`
- Critical: verify start command is NOT the backend command

### Frontend

- Health check: `/`
- `NEXT_PUBLIC_API_URL` -- backend domain

### PostgreSQL Extensions

Railway PostgreSQL must have the `vector` extension available. Migrations gracefully degrade if it is unavailable.

## Operational Checks

1. Backend starts and `/docs` returns 200
2. Agent logs cycle heartbeat and does not crash loop
3. Frontend loads and can call `NEXT_PUBLIC_API_URL` successfully

## China Access

See @docs/deployment-china.md for Cloudflare Workers reverse proxy setup.
