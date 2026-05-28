# Task 015: evaluate_offline_rotate implementation + main() CLI integration

**depends-on**: task-014

## Description

Make task-014's 3 Red tests Green. Add `evaluate_offline_rotate(router, k=3, models=...)` to `pipeline/router.py`, parallel to the existing `evaluate_offline`, simulating per-sample arm rotation against the current outcomes log under LOO. Extend `main()` to print a third per-router/k row labeled `rotation=True` alongside the existing k=1/k=2/k=3 rows.

## Execution Context

**Task Number**: 015 of 016
**Phase**: Batch 3 — Adaptive Sample Rotation (GREEN, offline simulator)
**Prerequisites**:
- task-014 complete: 3 Red tests failing as expected.

## BDD Scenario

```gherkin
# Green pair for task-014. The same 3 Feature 5 scenarios (quoted in task-014)
# are the acceptance contract.

Scenario: rotate coverage at k=3 is >= the best static single arm under LOO
  Given the outcomes log contains gemma4_e4b s=0..s=2 data for all 5 arms × 17 tasks
  And the best static arm for gemma4_e4b at pass@3 is good_multi_loop (13/17)
  When evaluate_offline_rotate(RuleRouter(), k=3, models=("gemma4_e4b",)) runs under LOO
  Then the reported coverage_rotate is >= 13/17
  And the reported coverage_rotate is <= ceiling_all_arms_union (15/17)
  And the per-model report carries arms_used_count showing >= 2 distinct arms were dispatched across tasks
```

**Spec Source**: [bdd-specs.md Feature 5](../2026-05-27-agentbook-outcome-loop-design/bdd-specs.md) (all 3 scenarios quoted in task-014).

## Files to Modify/Create

- Modify: `experiments/agentbook-ab/pipeline/router.py`:
  - Add `evaluate_offline_rotate(router, k=3, models=...)`.
  - Extend `main()` to print the rotation row.

## Steps

### Step 1: Add `evaluate_offline_rotate` signature
- Mirror `evaluate_offline` style:

```python
def evaluate_offline_rotate(
    router, *, k: int = 3, models: tuple[str, ...] = ("gemma4_e4b",),
) -> dict[str, dict]: ...
```

- Returns a `{model: {coverage_rotate, ceiling_all_arms_union, arms_used_count, unmet_samples}}` dict per [architecture.md § `evaluate_offline_rotate`](../2026-05-27-agentbook-outcome-loop-design/architecture.md).

### Step 2: Implement the simulator
- For each `(model, iid)`:
  - Initialise `tried: dict[str, list[bool]] = {}`, `consume_idx: dict[str, int] = defaultdict(int)`.
  - For `s in range(k)`:
    - `arm = router.select_arm_for_sample(features, model, sample_idx=s, tried_arms_results=tried, exclude_iid=iid)` (LOO).
    - Look up `outcomes[(model, iid, arm, consume_idx[arm])]`; on miss fall back to `(model, iid, arm, 0)`; increment `unmet_samples` if fallback fires.
    - Record `tried.setdefault(arm, []).append(resolved)`; increment `consume_idx[arm]`.
    - Short-circuit on `resolved == True` (REPLAY_WIN already covered by `_pick_unexplored`).
  - Count `iid` as covered if any `resolved == True`.
- Compute `ceiling_all_arms_union` from arm-level pass@k (existing `evaluate_offline` utility).
- Compute `arms_used_count = |{arm for arm in tried.keys() across all iids}|`.

### Step 3: Extend `main()`
- After the existing k=1/k=2/k=3 print loop, add a `rotation=True` row per router/k combination labeled `rotate` with coverage and `arms_used_count` columns.

### Step 4: Re-run the 3 Red tests; confirm Green

### Step 5: Project-wide regression sweep

## Verification Commands

```bash
# Run the offline-simulator tests
cd experiments/agentbook-ab && \
  uv run python -m pytest pipeline/tests/test_router.py -q -k "offline_rotate"

# Full sweep
cd experiments/agentbook-ab && \
  uv run python -m pytest -q

# Smoke: print the new rotation row
cd experiments/agentbook-ab && \
  uv run python -m pipeline.router | tee /tmp/router-report-with-rotate.txt

# Ruff
uv run ruff check --fix experiments/agentbook-ab/pipeline/router.py
```

## Success Criteria

- All 3 Feature-5 tests in `pipeline/tests/test_router.py` PASS.
- `evaluate_offline_rotate` is module-level and importable.
- `main()` prints a `rotate` row per router/k combination alongside the existing pass@k rows.
- LOO safety: KNN score computation never sees the held-out iid (asserted by the LOO test).
- `unmet_samples` counter is exposed in the returned dict and reflects fallback hits.
- Full pytest suite stays green.
- Ruff passes.
- No new external Python dependencies.
