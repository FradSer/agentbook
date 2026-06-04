# Sprint Contract — Batch 4 (final)

## Scope

The two read-path/presentation pairs, run as **two concurrent coordinators** (independent files, no overlap, both depend on the completed 003b):

- **MCP recall recording** (`004a`/`004b`) — `backend/presentation/mcp/tools.py` + new unit test.
- **Dashboard endpoint** (`006a`/`006b`) — `backend/presentation/api/schemas.py` + `backend/presentation/api/routes/dashboard.py` + new unit test.

Fully unit-verifiable (in-memory path). Neither touches `main.py` (`_build_service` wiring is already done by Batches 2 and 3).

## Tasks

- **#6 / 004a** (test, RED): MCP recall records identity-enriched event — `task-004a-mcp-recall-test.md`.
- **#7 / 004b** (impl, GREEN): recall passes `CallerContext` into `search_problems` — `task-004b-mcp-recall-impl.md`.
- **#10 / 006a** (test, RED): `GET /v1/dashboard/recurrence-density` shape — `task-006a-dashboard-test.md`.
- **#11 / 006b** (impl, GREEN): endpoint + schemas — `task-006b-dashboard-impl.md`.

## Acceptance Criteria

**MCP (004):**
1. The `recall` handler in `dispatch_tool` builds a `CallerContext` from `_current_agent_ctx`/`_current_remote_addr_ctx` (`agent_id`/`ip_hash`/`fingerprint_hash`; anonymous → `agent_id=None`, `ip_hash` from a reused remote-addr hash) and passes it as `service.search_problems(..., caller=ctx)`.
2. Presentation does NOT touch a repo directly — it only passes `caller`; the service records (Clean Architecture).
3. The `recall` response is unchanged; recording is side-channel and best-effort.
4. Test asserts authenticated → event has `agent_id`+`ip_hash`; anonymous → `agent_id=None`, `ip_hash` from remote addr; response unchanged.

**Dashboard (006):**
5. `RecurrenceDensityResponse` + `RecurrenceDensityProblemResponse` schemas (`schemas.py`).
6. `GET /v1/dashboard/recurrence-density` (`dashboard.py`, after `/usage`), public read (no auth), `response_model=RecurrenceDensityResponse`, returns `service.get_recurrence_density()`.
7. Test asserts 200 + shape with recorded events; empty → 200 zero rollup; public (no Authorization header).

## Verification (must pass, exit 0)

```bash
uv run ruff check backend/presentation/mcp/tools.py backend/presentation/api/schemas.py backend/presentation/api/routes/dashboard.py backend/tests/unit/test_mcp_recall_recurrence.py backend/tests/unit/test_dashboard_recurrence_endpoint.py
uv run pytest backend/tests/unit/test_mcp_recall_recurrence.py backend/tests/unit/test_dashboard_recurrence_endpoint.py -q
make fast
```

## Evaluation Criteria Preview

Against `docs/retros/checklists/code-v2.md`. Emphasis: presentation never touches a repo directly (passes `CallerContext` only); `recall` response unchanged; anonymous `ip_hash` reuses an existing hash helper (no new scheme); dashboard endpoint public-read like the other `/v1/dashboard/*`; no stubs; tests real logic; full suite green.
