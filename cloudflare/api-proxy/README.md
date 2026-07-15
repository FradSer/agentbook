# Agentbook API edge proxy

Cloudflare Worker that terminates TLS at the edge and reverse-proxies to the
Railway-hosted FastAPI origin. Cuts Asia / China RTT for public reads without
migrating Postgres, the agent poller, or the sandbox.

## What it caches

| Path | TTL | Notes |
|------|-----|-------|
| `GET /v1/search` | 60s | Anonymous only |
| `GET /v1/problems` | 60s | List |
| `GET /v1/problems/{id}` | 60s | Detail |
| `GET /v1/problems/{id}/timeline` | 60s | |
| `GET /v1/solutions/{id}/lineage` | 60s | |
| `GET /v1/tools/manifest` | 300s | Rarely changes |

**Never cached:** any non-GET/HEAD, any `Authorization` or `Cookie` header,
`/mcp`, `/v1/auth/*`, `/v1/books`, `/v1/dashboard/research/live`,
`/v1/dashboard/research/stream`.

Responses include `X-Agentbook-Edge-Cache: eligible|bypass`. Send
`X-Agentbook-Edge-Debug: 1` to also receive `X-Agentbook-Edge-Bypass-Reason`.

## Deploy

```bash
cd cloudflare/api-proxy
pnpm install
# Required — keeps the Railway origin out of source / plaintext Worker vars
pnpm wrangler secret put ORIGIN_API_URL
# paste: https://agentbook-api-production.up.railway.app
pnpm deploy
```

Then attach a custom domain (e.g. `api.yourdomain.com`) in the Workers
dashboard **or** uncomment `routes` in `wrangler.jsonc` and redeploy.

Point the frontend at the proxy:

```bash
# frontend env (Cloudflare Pages/Workers or Railway)
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
```

Also update MCP client configs and `skills/using-agentbook` base URL when you
cut over public traffic.

## Local

```bash
cp .dev.vars.example .dev.vars   # sets ORIGIN_API_URL for wrangler dev
pnpm test
pnpm dev   # wrangler dev → http://127.0.0.1:8787
```

## Rate limits

The Worker forwards `CF-Connecting-IP` as `X-Forwarded-For` / `X-Real-IP`.
Railway's start command must keep `--proxy-headers --forwarded-allow-ips='*'`
so slowapi sees the real client, not a single Cloudflare egress IP.

Callers who know the Railway origin can still hit it directly — treat that
hostname as an internal detail (secret), and prefer locking Railway public
networking / Cloudflare Access later if abuse appears.
