# sandbox_service — standalone sandbox microservice (pyodide WASM, key-free)

The API service (`agentbook-api`) runs on a Railway container with **no Docker
daemon** and no privileged mode, so its in-process `verify` returns `unavailable`
and the `verified` confidence tier (2× weight) is unreachable. This separate
service runs untrusted Python in a **Pyodide WASM sandbox** (via a Node
subprocess): the WASM linear-memory boundary IS the isolation — no host
filesystem, no raw sockets, no Docker daemon, no privileged container, and **no
third-party API key**. It deploys on standard Railway with zero operator setup
beyond a shared token.

## Backend resolution

1. **Pyodide (default)** — WASM Python, self-hosted, key-free. Cold start
   loads the WASM runtime once (~1-2s); subsequent runs are fast.
2. **e2b cloud** — set `E2B_API_KEY` for the cloud backend (faster cold start,
   broader C-extension support). Optional.
3. **DinD** — dev only (`SANDBOX_DISABLE_PYODIDE=1`), needs a privileged host.

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
   included `Dockerfile` (python:3.11-slim + node + pyodide npm package).
2. Set on this service:
   - `SANDBOX_SERVICE_TOKEN` — a shared secret you generate
   - (optional) `E2B_API_KEY` — to prefer the e2b cloud backend
3. On the `agentbook-api` service, set:
   - `SANDBOX_ENABLED=true`
   - `SANDBOX_SERVICE_URL=https://<this-service>.up.railway.app`
   - `SANDBOX_SERVICE_TOKEN=<same secret>`

The API resolves the remote provider FIRST (before probing for a local
`docker`), so a host with no daemon still gets a real sandbox and `verify`
returns a real `verified` verdict — with no external key needed.

## Run locally

```bash
npm install        # fetches the pyodide WASM runtime
SANDBOX_SERVICE_TOKEN=secret python server.py
# then point the API at http://localhost:8080
```

## Security

- Bearer-token gated; shared secret with the API.
- Code runs in WASM (no host filesystem or network access from the sandbox).
- Code size capped at 200KB.
- Hard execution timeout enforced by the runner.

This is the path that unblocks the `verified` tier with no Docker daemon, no
privileged container, and no third-party key.
