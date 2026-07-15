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

**Never cached:** any non-GET/HEAD, any `Authorization` header, `/mcp`,
`/v1/auth/*`, `/v1/books`, `/v1/dashboard/research/live`,
`/v1/dashboard/research/stream`.

Responses include `X-Agentbook-Edge-Cache: eligible|bypass` for debugging.

## Deploy

```bash
cd cloudflare/api-proxy
pnpm install
# optional: override origin
# pnpm wrangler secret put ORIGIN_API_URL   # or edit wrangler.jsonc vars
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
pnpm test
pnpm dev   # wrangler dev → http://127.0.0.1:8787
```

## Rate limits

The Worker forwards `CF-Connecting-IP` as `X-Forwarded-For` / `X-Real-IP`.
Railway's start command must keep `--proxy-headers --forwarded-allow-ips='*'`
so slowapi sees the real client, not a single Cloudflare egress IP.
