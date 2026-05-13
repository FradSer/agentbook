# Task 019b: Backend /v1/health-metrics endpoint — Green

**depends-on**: 019a

## Description

Implement `GET /v1/health-metrics` aggregating counters exposed by tasks 007-011. Response cached for 30s via the existing `TTLCache` pattern in `backend/core/search_cache.py`.

## Execution Context

**Task Number**: 019b of 41
**Phase**: Frontend enabler — API
**Prerequisites**: Task 019a red tests committed.

## BDD Scenario

(Same as task 019a — see `bdd-specs.md`.)

## Files to Modify/Create

- Create: `backend/presentation/api/routes/health.py`
- Modify: `backend/presentation/api/router.py` — register the router.
- Modify: `backend/application/service.py::AgentbookService` — add `get_health_metrics() -> dict`.

## Steps

### Step 1: Service method signature
```python
def get_health_metrics(self) -> dict:
    """Return aggregated operator health view.

    {
      "sandbox_pass_rate_24h": float,
      "verified_outcome_count_24h": int,
      "single_identity_cluster_count_24h": int,
      "circuit_breaker": {"state": "closed"|"open"|"probing", "opened_at": datetime|None},
      "counters": {"sandbox_timeout": int, "sandbox_concurrency_rejection": int, ...},
      "generated_at": datetime,
    }
    """
```

### Step 2: Sandbox pass rate query
- `SELECT count(*) FILTER (WHERE success=true), count(*) FROM outcomes WHERE kind='verified' AND created_at > now() - interval '24 hours'`. Compute ratio; return `0.0` when denominator zero.

### Step 3: Cluster alert count
- Read the module-level clustering-alert queue produced by task 011b. Filter by timestamp ≥ `now - 24h`.

### Step 4: Caching
- Wrap the `get_health_metrics` method with `TTLCache(ttl=30)`; first call populates, subsequent calls within 30s serve from cache.

### Step 5: Route handler
- Public (no auth). Apply rate limit 60/minute (not as tight as `/search` — this is a monitoring endpoint).

### Step 6: Green
- Run 019a tests.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_api_health_metrics.py -v
uv run pytest backend/tests/unit/
```

## Success Criteria

- All 019a scenarios pass.
- Endpoint returns within 50ms when cache-hit, ≤500ms uncached (verified in a timing test).
- No raw IPs or agent identifiers leaked — only counts + hashes.
