# Task 009b: Sandbox per-agent budget and dedup cache — Green

**depends-on**: 009a

## Description

Implement a per-agent sliding-window limiter (20 calls/hour) and an in-process dedup cache keyed by `sha256(normalize(content) + "|" + (error_signature or ""))` with a 10-minute TTL. Budget and dedup checks run *before* the concurrency semaphore; the order is dedup-hit → budget-check → semaphore-acquire → sandbox-run.

## Execution Context

**Task Number**: 009b of 41
**Phase**: Resilience — DoS gates
**Prerequisites**: Task 009a red tests committed.

## BDD Scenario

(Same as task 009a — see `bdd-specs.md`.)

## Files to Modify/Create

- Create: `backend/core/sandbox_gates.py` — `SandboxBudgetLimiter` + `SandboxDedupCache` classes.
- Modify: `backend/application/service.py::improve_solution` and `verify` paths — consult the two gates.
- Modify: `backend/core/config.py` — add `sandbox_runs_per_agent_per_hour: int = 20`, `sandbox_dedup_window_minutes: int = 10`.

## Steps

### Step 1: Budget limiter
- Reuse the existing sliding-window pattern from `backend/core/mcp_rate_limit.py`. Key = `agent_id`. Emits `{"error": "rate_limit_exceeded", "gate": "sandbox_per_agent"}` on reject with `_meta.retry_after_seconds` derived from the oldest timestamp in the window.

### Step 2: Dedup cache
- `SandboxDedupCache`: in-process `dict[str, (created_at: datetime, run_id: UUID, sandbox_score: float, success: bool)]` with manual eviction on write.
- Key: `sha256(_normalize_content(content) + "|" + (error_signature or "")).hexdigest()`.
- `_normalize_content(s: str) -> str`: strip surrounding whitespace, collapse interior `\s+` to a single space, remove trailing newlines. Do NOT normalize semantics (e.g., comment stripping); the cache must only fire on obvious duplicates.
- On hit, return `(sandbox_score, dedup_meta)` tuple where `dedup_meta = {"dedup_hit": True, "original_run_id": str(run_id)}`.

### Step 3: Service integration
- Inside `improve_solution` and the new `verify()` method (to be added by task 013b; stub here as `def verify(self, solution_id, agent_id) -> dict`):
  ```python
  cached = self._dedup_cache.get(content_key)
  if cached is not None:
      sandbox_score = cached.sandbox_score
      _meta.update({"dedup_hit": True, "original_run_id": str(cached.run_id)})
      return ...  # skip sandbox call
  if not self._budget_limiter.check(agent_id):
      return {"error": "rate_limit_exceeded", ...}
  # else: acquire semaphore + run sandbox + populate dedup cache
  ```

### Step 4: Green
- Run 009a tests. Confirm clock fixtures interact cleanly with the window expiry logic.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_sandbox_budget_dedup.py -v
uv run ruff check backend/core/sandbox_gates.py backend/application/service.py
```

## Success Criteria

- All 009a scenarios pass.
- Dedup cache memory bounded (LRU or hard cap on size of ~10k entries).
- Budget limiter emits the precise `_meta.retry_after_seconds` the BDD asserts.
