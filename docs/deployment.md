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

## Compatibility Notes

- MCP HTTP authentication now accepts only `Authorization: Bearer <api_key>`.
- `X-API-Key` is no longer supported on MCP endpoints.
- Outcome persistence now requires a non-null `kind`; invalid rows should fail fast instead of being silently coerced.

### Rollback Guidance

- If external MCP clients still send `X-API-Key`, either update those clients to Bearer auth or temporarily reintroduce `X-API-Key` parsing in `backend/presentation/mcp/auth.py` and `backend/presentation/mcp/streamable_router.py`.
- If legacy outcome rows with null `kind` exist, backfill `outcomes.kind` before rollback/roll-forward cycles:
  `UPDATE outcomes SET kind = 'observed' WHERE kind IS NULL;`

## China Access

See @docs/deployment-china.md for Cloudflare Workers reverse proxy setup.
