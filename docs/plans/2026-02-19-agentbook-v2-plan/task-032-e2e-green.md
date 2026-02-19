# Task 032 — Green: Make E2E Tests Pass (Final Integration Wiring)

**Type:** Green (integration wiring, not new code)
**Depends-on:** task-031, task-028, task-026, task-030
**BDD refs:** All Cross-Feature E2E scenarios

## Goal

Resolve any remaining wiring issues that prevent the E2E tests from passing. This task is intentionally last — it surfaces integration gaps between layers that unit tests cannot catch.

## What to do

### 1. Run E2E tests and identify failures

```bash
RUN_DOCKER_TESTS=1 uv run pytest tests/integration/test_e2e_v2_workflow.py -v -m smoke 2>&1 | head -100
```

Common expected gaps at this stage:
- `app.state.service_v2` not set during test app startup
- `dashboard.py` route not registered in `router.py`
- `AgentbookServiceV2` not injected into `mcp_server._service_v2`
- v1 compat wrapper not finding v2 problem by `thread_id` (UUID namespace mismatch)

### 2. Fix each wiring issue

For each failing test:
1. Identify which layer the gap is in (startup, routing, service, MCP)
2. Apply minimal fix — no new logic, only wiring
3. Re-run the failing test to verify

### 3. Update smoke_test.sh

Update `scripts/smoke_test.sh` to exercise the v2 endpoints:
- `resolve` tool call
- `contribute` tool call
- `report_outcome` call
- `GET /v1/dashboard/radar`
- `GET /v1/dashboard/metrics`

### 4. Full test suite green

Run the full suite to confirm nothing regressed:

```bash
make fast    # unit tests
make smoke   # integration tests
cd web && pnpm test && pnpm build
```

## Files potentially modified

- `app/main.py` — startup wiring for `service_v2`
- `app/presentation/api/router.py` — register dashboard routes if missed
- `scripts/smoke_test.sh` — add v2 endpoint tests

## Verification

```bash
make full
```

All unit, smoke, and frontend build checks must pass.
