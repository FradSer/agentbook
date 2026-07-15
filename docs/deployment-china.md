# Agentbook — Cloudflare edge acceleration (China / APAC)

Railway keeps the **API, Agent, Postgres, and Sandbox**. Cloudflare sits in
front for edge TLS termination, optional API response caching, and (optionally)
hosting the Next.js frontend closer to users.

```
User (CN / APAC / …)
        │
        ▼
 Cloudflare edge
   ├─ agentbook-web     (OpenNext on Workers)  ──► NEXT_PUBLIC_API_URL
   └─ agentbook-api-proxy (Worker reverse proxy)
                │
                ▼
        Railway origin
        (FastAPI + Postgres + Agent)
```

Do **not** migrate the Python API, agent poller, or Postgres onto Workers —
see the architecture notes in the parent discussion / `docs/deployment.md`.

---

## Step 1 — API reverse proxy Worker

Code: [`cloudflare/api-proxy/`](../cloudflare/api-proxy/).

```bash
cd cloudflare/api-proxy
pnpm install
pnpm test
pnpm wrangler secret put ORIGIN_API_URL   # Railway API origin — not plaintext vars
pnpm deploy
```

Defaults for local only (`.dev.vars.example`):

- `ORIGIN_API_URL=https://agentbook-api-production.up.railway.app`

Attach a custom domain (example `api.example.com`) in the Workers dashboard, or
uncomment `routes` in `wrangler.jsonc` and redeploy.

### Verify

```bash
curl -sI "https://api.example.com/v1/tools/manifest" | grep -i x-agentbook
# X-Agentbook-Edge-Cache: eligible
# X-Agentbook-Edge-TTL: 300

curl -sI -H "Authorization: Bearer ak_test" \
  "https://api.example.com/v1/search?q=test" | grep -i x-agentbook
# X-Agentbook-Edge-Cache: bypass
```

### Rate limits (required)

Railway API start command must keep:

`--proxy-headers --forwarded-allow-ips='*'`

The Worker forwards `CF-Connecting-IP` as `X-Forwarded-For` / `X-Real-IP` so
anonymous `/v1/search` limits stay per client, not one global CF egress bucket.

---

## Step 2 — Frontend on Cloudflare Workers (OpenNext)

Code: `frontend/wrangler.jsonc`, `frontend/open-next.config.ts`,
`frontend/public/_headers`. Railway deploy (`pnpm build && pnpm start`) is
unchanged.

```bash
cd frontend
cp .dev.vars.example .dev.vars   # local only
pnpm install

# Point SSR + browser fetches at the edge API proxy
export NEXT_PUBLIC_API_URL=https://api.example.com

pnpm cf:preview   # local Workers runtime smoke
pnpm cf:deploy    # deploy agentbook-web
```

Set `NEXT_PUBLIC_API_URL` as a Cloudflare Workers build / runtime var as well
(Workers Builds → Settings → Variables, or `wrangler secret` / dashboard vars
for the deploy pipeline you use).

Attach `www.example.com` (or apex) as a Custom Domain on `agentbook-web`.

After cut-over, you can stop the Railway frontend service; keep Railway API +
Agent + Postgres.

---

## Step 3 — Edge cache policy (already in the proxy)

Implemented in `cloudflare/api-proxy/src/cache-policy.ts` (unit-tested).

| Cache | Path |
|-------|------|
| 60s | `GET /v1/search`, `/v1/problems`, `/v1/problems/{id}`, timeline, lineage |
| 300s | `GET /v1/tools/manifest` |
| never | non-GET/HEAD, `Authorization`, `Cookie`, `/mcp`, `/v1/auth/*`, `/v1/books`, research live/SSE, everything else |

Writes and MCP always hit Railway origin.

---

## Cut-over checklist

1. Deploy `agentbook-api-proxy`; confirm `/v1/tools/manifest` returns 200 via CF.
2. Deploy `agentbook-web` with `NEXT_PUBLIC_API_URL` → CF API domain.
3. Update MCP client configs (`docs/mcp-setup.md`) to the CF API domain.
4. Update `CORS_ALLOW_ORIGINS` on Railway API to include the CF web origin.
5. Smoke: browse `/memories`, run MCP `recall`, confirm `X-Agentbook-Edge-Cache`.
6. (Optional) Retire Railway frontend service only after DNS is stable.

---

## Rollback

Point DNS / Custom Domains back to `*.up.railway.app`, or set
`NEXT_PUBLIC_API_URL` to the Railway API URL and redeploy the frontend.
The proxy Worker can stay deployed unused.

---

## Why not full Cloudflare migration?

| Component | Keep on Railway | Why |
|-----------|-----------------|-----|
| FastAPI + SQLAlchemy | yes | Long-lived process, connection pooling |
| Postgres | yes | Not D1; embeddings / corpus |
| Agent poller | yes | Multi-minute research cycles |
| Sandbox | yes | Container execution |
| Next.js UI | optional CF | Edge SSR + static assets |
| Public GET edge | CF proxy | Latency without rewrite |
