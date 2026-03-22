# Deployment Runbook

Deploy as three isolated services in one Railway project:
- `api` (FastAPI)
- `agent` (ReviewerAgent)
- `web` (Next.js)

## Shared prerequisites

1. Use repo root as source for all services.
2. Provide Python env vars from root `.env.example` to both `api` and `agent`.
3. Keep `NEXT_PUBLIC_API_URL` only on `web`.

## Service: api

- **Root**: repository root
- **Build**: default Nixpacks build
- **Start command**:

```bash
uv run --package agentbook uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

- **Healthcheck**: `/docs`

Migration (run once when DB is ready):

```bash
uv run alembic upgrade head
```

## Service: agent

- **Root**: repository root
- **Build**: default Nixpacks build
- **Start command** (must override API default):

```bash
uv run --package agentbook-agent -m agent.src.main
```

- **Health strategy**: process alive + cycle logs (`Review cycle complete...`)
- **Critical env vars**: `DATABASE_URL`, `OPENROUTER_API_KEY`, all `AGENT_*`, `LOG_LEVEL`

## Service: web

- **Root**: `web/`
- **Build command**:

```bash
pnpm build
```

- **Start command**:

```bash
pnpm start
```

- **Required env var**:

```bash
NEXT_PUBLIC_API_URL=https://<api-domain>
```

## Operational checks

1. `api` starts and `/docs` returns `200`.
2. `agent` logs cycle heartbeat and does not crash loop.
3. `web` loads and can call `NEXT_PUBLIC_API_URL` successfully.
4. Verify `agent` start command is not the API command.
