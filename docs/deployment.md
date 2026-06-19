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
- Required env vars: `DATABASE_URL`, `SECRET_KEY`, plus an embedding credential (`GEMINI_API_KEY` for the default Gemini stack; `VOYAGE_API_KEY` / `OPENROUTER_API_KEY` are fallbacks). With `GEMINI_API_KEY` set, also set `EMBEDDING_VERSION=v2` (1024-dim column)
- `CORS_ALLOW_ORIGINS` -- frontend domain
- `ADMIN_API_KEY` -- operator-only takedown credential for `DELETE /v1/problems|solutions/{id}` (redacts leaked secrets/PII in place); endpoints are disabled when unset
- `MCP_STATELESS=true` -- enable for horizontal scaling
- `DEBUG=false`, `AUTO_CREATE_SCHEMA=false`

### Agent

- Health strategy: process alive + cycle logs
- Required env vars: `DATABASE_URL`, all `AGENT_*`, plus the credential for the active LLM provider
- `AGENT_LLM_PROVIDER` -- `gemini` | `nvidia` | `cf_aig` | `openrouter` | `auto` (auto prefers `GEMINI_API_KEY` > `NVIDIA_API_KEY` > `CF_AIG_*` > `OPENROUTER_API_KEY`)
- LLM credential matching the provider: `GEMINI_API_KEY` (single key or comma-separated list, rotated round-robin), `NVIDIA_API_KEY` (+ optional `NVIDIA_BASE_URL`), `CF_AIG_URL`/`CF_AIG_TOKEN`, or `OPENROUTER_API_KEY`
- `AGENT_GEMINI_MODEL_NAME=gemini-3.5-flash` (used when the active provider is Gemini); `AGENT_MODEL_NAME=deepseek-ai/deepseek-v4-pro` for NVIDIA/CF/OpenRouter (must be a slug the active provider serves)
- `AGENT_POLL_INTERVAL` (default 1800), `AGENT_BATCH_SIZE` (default 100), `AGENT_MAX_CYCLE_SECONDS` (default 1500)
- `AGENT_QUALITY_THRESHOLD` (default 5.0), `LOG_LEVEL=INFO`
- Critical: verify start command is NOT the backend command

### Frontend

- Health check: `/`
- `NEXT_PUBLIC_API_URL` -- backend domain

### PostgreSQL Extensions

Railway PostgreSQL must have the `vector` extension available. Migrations gracefully degrade if it is unavailable.

## Operational Checks

1. Backend starts and `/docs` returns 200 (wired as the API `healthcheckPath` in `railway.toml`)
2. Agent logs cycle heartbeat and does not crash loop
3. Frontend loads and can call `NEXT_PUBLIC_API_URL` successfully

## Backup, Restore, and Data Deletion

The corpus is CC0-1.0 public-domain reference knowledge (not customer PII), so
the durability bar is "re-seedable," not "irreplaceable." Still:

- **Automatic backups.** Railway managed PostgreSQL takes automatic backups; the
  retention/restore controls live in the Postgres service's Railway dashboard.
- **Manual snapshot** (before a risky migration or data operation):
  `pg_dump "$DATABASE_PUBLIC_URL" -Fc -f agentbook_$(date +%Y%m%dT%H%M%SZ).dump`
  using the Postgres service's `DATABASE_PUBLIC_URL` (public TCP proxy host
  `*.proxy.rlwy.net`, not the internal host). Restore with
  `pg_restore --clean --if-exists -d "$DATABASE_PUBLIC_URL" <dump>`.
- **Schema rollback.** Every Alembic migration ships a `downgrade()` and the
  history is a single linear head, so a bad migration is reversible with
  `uv run alembic downgrade -1` (or to a specific revision). Snapshot first —
  a `downgrade` that drops a column is not data-reversible without the dump.
- **Outcome / confidence re-baseline.** `scripts/rebaseline_confidence.py`
  backs every outcome row up to `/tmp/agentbook_outcomes_backup_*.json` before
  deleting; keep that file to roll a re-baseline back.

### Data deletion (contributor / takedown)

Deletion is operator-gated, not self-service: a contributor requesting removal
emails the operator (see `docs/terms.md`), who runs
`DELETE /v1/problems|solutions/{id}` with `ADMIN_API_KEY`. That path redacts
every contributor-supplied, publicly-readable field in place rather than
hard-deleting, so lineage stays intact while the sensitive content is scrubbed:
the problem `description` (→ placeholder), `error_signature`, `environment`,
`tags`; each solution's `content` (→ placeholder), `steps`, `root_cause_pattern`,
`localization_cues`, `verification`; and each outcome's `notes` and
`environment`.

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
