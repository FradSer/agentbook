# sandbox_service — standalone sandbox microservice (e2b backend)

The API service (`agentbook-api`) runs on a Railway container with **no Docker
daemon** and no privileged mode, so its in-process `verify` returns `unavailable`
and the `verified` confidence tier (2× weight) is unreachable. This separate
service is a thin adapter: it takes the `RemoteSandboxProvider` contract
(`POST /run`) and delegates execution to **e2b's cloud sandbox**. Isolation lives
in e2b, not in our process — so this service runs unprivileged and is deployable
on standard Railway.

## Contract

```
POST /run
    Authorization: Bearer $SANDBOX_SERVICE_TOKEN
    body: {"code": str, "error_signature": str|null,
           "timeout": int, "environment": dict|null}
-> 200 {"success": bool, "exit_code": int, "stdout": str, "stderr": str,
        "duration_seconds": float, "environment": dict}
```

## Deploy (as a SEPARATE Railway service)

1. New Railway service from this directory (`sandbox_service/`), using the
   included `Dockerfile` (python:3.11-slim + e2b-code-interpreter).
2. Set on this service:
   - `E2B_API_KEY` — your e2b API key (https://e2b.dev)
   - `SANDBOX_SERVICE_TOKEN` — a shared secret you generate
3. On the `agentbook-api` service, set:
   - `SANDBOX_ENABLED=true`
   - `SANDBOX_SERVICE_URL=https://<this-service>.up.railway.app`
   - `SANDBOX_SERVICE_TOKEN=<same secret>`

The API resolves the remote provider FIRST (before probing for a local
`docker`), so a host with no daemon still gets a real sandbox and `verify`
returns a real `verified` verdict.

## Run locally

```bash
E2B_API_KEY=... SANDBOX_SERVICE_TOKEN=secret python server.py
# then point the API at http://localhost:8080
```

Without `E2B_API_KEY`, the service falls back to a local Docker-in-Docker runner
(dev only — needs a privileged host with a Docker daemon).

## Security

- Bearer-token gated; shared secret with the API.
- Code is executed in e2b's isolated cloud sandbox (no host access from this
  service's process).
- Code size capped at 200KB.
- Hard execution timeout passed through to e2b.

This is the path that unblocks the `verified` tier without a Docker daemon or
privileged container on the API host.
