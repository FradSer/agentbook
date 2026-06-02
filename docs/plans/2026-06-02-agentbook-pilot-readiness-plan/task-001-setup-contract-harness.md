# Task 001 (setup-contract-harness) — Setup

**type:** setup
**depends-on:** []

## Goal

Provide the shared test scaffolding every feature task reuses: a running-app fixture for both transports, a cross-transport parity helper (assert REST `/v1/search` and MCP `recall` payloads field-by-field for the same problem), and an embedding-fault injector (force the Voyage provider to time out / fail) so latency and misconfig scenarios are deterministic.

## Files

- `backend/tests/features/conftest.py` (or extend `backend/tests/conftest.py`) — fixtures: `rest_client`, `mcp_client`, `assert_transport_parity(problem_id, fields)`, `embedding_fault(mode)`.
- `backend/tests/unit/_helpers/transports.py` — thin REST + MCP JSON-RPC callers reused by feature tests.

## Steps

1. Add fixtures isolating DB (in-memory repos, `database_url=None`) and embeddings (provider double) per existing conftest conventions.
2. Implement `assert_transport_parity` to diff the two transports' `best_solution`/read-row dicts.
3. Implement `embedding_fault` to simulate slow/failing/dimension-mismatch providers.

## Verification

```bash
uv run pytest backend/tests/features -q --collect-only   # fixtures import cleanly
```
