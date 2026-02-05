# Deployment Runbook

## Backend (Railway)

1. Create service from repo root.
2. Add environment variables from `.env.example`.
3. Set start command:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

4. Run migration once after DB is ready:

```bash
uv run alembic upgrade head
```

## Frontend (Railway/Vercel)

1. Deploy `web/` directory.
2. Set:

```bash
NEXT_PUBLIC_API_URL=https://<your-api-domain>
```

3. Build and start:

```bash
pnpm build
pnpm start
```
