# Task 019a: Backend /v1/health-metrics endpoint — Red

**depends-on**: 008b, 010b, 011b

## Description

Red tests for `GET /v1/health-metrics`. Aggregates: sandbox pass rate (last 24h), verified outcome freshness histogram, circuit-breaker state, single-identity cluster alerts, counters from `_health_counters`. Public read. Cached 30s.

## Execution Context

**Task Number**: 019a of 41
**Phase**: Frontend enabler — API
**Prerequisites**: Tasks 008b, 010b, 011b (counters + breaker + clustering populated).

## BDD Scenario

```gherkin
Scenario: /health shows aggregate sandbox + cluster metrics
  Given the last 24h contains 120 sandbox runs and 4 single-identity cluster alerts
  When /health renders
  Then "Sandbox pass rate (24h)" shows the computed percentage
  And "Inflated-confidence alerts (24h): 4" is visible
  And no form elements or write buttons are rendered
```

(This task tests the backend that feeds the frontend — the `/health` rendering test is task 020a.)

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md`

## Files to Modify/Create

- Create: `backend/tests/unit/test_api_health_metrics.py`

## Steps

### Step 1: Tests
- `test_health_metrics_sandbox_pass_rate` — seed 120 verified outcomes (90 success, 30 failure); assert response `sandbox_pass_rate_24h == 0.75`.
- `test_health_metrics_cluster_alerts_count` — seed agent fixtures producing 4 single-identity clusters; assert `single_identity_cluster_count_24h == 4`.
- `test_health_metrics_circuit_state` — trip the circuit breaker; assert response `circuit_breaker = {"state": "open", "opened_at": "..."}`.
- `test_health_metrics_counters_surfaced` — bump `sandbox_timeout` and `sandbox_concurrency_rejection` counters; response includes both.
- `test_health_metrics_cached_30s` — call endpoint twice in quick succession; assert the second hit does not re-query the database (use a spy).
- `test_health_metrics_public_no_auth_required` — unauthenticated call returns 200 with the metrics body.

### Step 2: Confirm Red
- All six tests fail because the endpoint does not exist.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_api_health_metrics.py -v
```

## Success Criteria

- Six failing tests.
- Cache TTL asserted explicitly.
