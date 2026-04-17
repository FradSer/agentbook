# Task 009a: Sandbox per-agent budget and dedup cache — Red

**depends-on**: 007b

## Description

Red tests for two additional DoS gates: a per-agent hourly budget (20 sandbox runs/agent) enforced by a sliding-window limiter, and a submission dedup cache keyed on `(normalized_content, error_signature)` with a 10-minute window. Budget exhaustion returns `rate_limit_exceeded`; dedup hits return the cached verdict without spawning a container; the window expiring forces a fresh run.

## Execution Context

**Task Number**: 009a of 41
**Phase**: Resilience — DoS gates
**Prerequisites**: Task 007b committed.

## BDD Scenario

```gherkin
Scenario: Per-agent hourly budget exhausted
  Given an authenticated agent has triggered 20 sandbox runs in the last 60 minutes
  When the agent calls "verify" a 21st time
  Then the dispatcher returns {"error": "rate_limit_exceeded", "gate": "sandbox_per_agent"}
  And no sandbox run is enqueued
  And the next allowed call time is returned in _meta.retry_after_seconds

Scenario: Duplicate submission returns cached verdict
  Given solution S1 was sandbox-verified 3 minutes ago with success=True
  And a new proposed solution has identical normalized_content and error_signature
  When evaluate_improvement would invoke the sandbox
  Then the cached verdict is reused
  And no new container is spawned
  And the response _meta contains {"dedup_hit": true, "original_run_id": ...}

Scenario: Dedup window expires after 10 minutes
  Given an identical submission was sandbox-verified 11 minutes ago
  When the pipeline invokes the sandbox
  Then a fresh sandbox run is spawned
  And the dedup cache is refreshed with the new verdict
```

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md`

## Files to Modify/Create

- Create: `backend/tests/unit/test_sandbox_budget_dedup.py`

## Steps

### Step 1: Budget tests
- `test_per_agent_budget_rejects_21st_call` — parameterise with a controlled-clock fixture; call `service.verify(solution_id, agent_id)` 20 times within a simulated 60-minute window; assert call 21 returns `{"error": "rate_limit_exceeded", "gate": "sandbox_per_agent"}` and has `_meta.retry_after_seconds` set.
- `test_budget_rolls_forward` — after the window expires, the 21st call succeeds.

### Step 2: Dedup tests
- `test_dedup_cache_reuses_verdict` — submit solution A with content X, error_sig Y; sandbox runs once; submit solution B (different `solution_id`) with identical `(normalized_content, error_signature)` 3 minutes later; assert the sandbox is NOT called a second time, the response contains `_meta.dedup_hit=true` and `_meta.original_run_id` pointing at A's run.
- `test_dedup_window_expires` — same as above but 11 minutes later; assert the sandbox IS called again.
- `test_dedup_normalization` — trivial whitespace/indentation differences in content do not defeat the dedup cache; the `_normalize_content` helper collapses them.

### Step 3: Confirm Red
- All five tests fail because neither gate exists yet.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_sandbox_budget_dedup.py -v
```

## Success Criteria

- Five failing tests.
- Clock fixture reusable by task 010a.
