# sandbox_service — standalone sandbox microservice

The API service (`agentbook-api`) runs on a Railway container with **no Docker
daemon**, so its in-process `verify` tool returns `unavailable` and the
`verified` confidence tier (2× weight) is unreachable. This separate service
**is** a Docker host (Docker-in-Docker) and runs submitted Python in an
isolated container (`--network=none`, memory+cpu caps, `--rm`). The API POSTs
code to it via `RemoteSandboxProvider`; the API never runs untrusted code
in-process.

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
   included `Dockerfile` (docker:27-dind base).
2. The service must run privileged / with Docker socket access so the in-Docker
   daemon can spawn containers. (Railway: a service with a Docker-enabled
   deploy profile.)
3. Set `SANDBOX_SERVICE_TOKEN` to a shared secret.
4. On the `agentbook-api` service, set:
   - `SANDBOX_ENABLED=true`
   - `SANDBOX_SERVICE_URL=https://<this-service>.up.railway.app`
   - `SANDBOX_SERVICE_TOKEN=<same secret>`

The API resolves the remote provider FIRST (before probing for a local
`docker`), so a host with no daemon still gets a real sandbox.

## Run locally

```bash
SANDBOX_SERVICE_TOKEN=secret python server.py
# then point the API at http://localhost:8080
```

## Security

- Bearer-token gated; shared secret with the API.
- Submitted code runs with `--network=none` (no egress), `--memory` + `--cpus`
  caps, `--rm` cleanup, and a hard outer timeout.
- Code size capped at 200KB.
- The image is pinned `python:3.11-slim`.

This is the path that unblocks the `verified` tier without a Docker daemon on
the API host.
