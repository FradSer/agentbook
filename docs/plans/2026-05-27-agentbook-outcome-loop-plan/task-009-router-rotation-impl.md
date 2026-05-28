# Task 009: select_arm_for_sample implementation on RuleRouter and KNNRouter

**depends-on**: task-008

## Description

Make the 6 Red tests from task-008 Green. Add a module-level `_pick_unexplored(ranking, tried_arms_results)` helper in `pipeline/router.py` implementing the four decision branches in order — REPLAY_WIN → FRESH_ARM → EXHAUSTED_RANKING → BURN_REPLAY. Add `select_arm_for_sample` methods on both `RuleRouter` and `KNNRouter` whose bodies call `self.select(...)` for the ranking and delegate to `_pick_unexplored`. The existing `select_arms` signature is preserved verbatim.

## Execution Context

**Task Number**: 009 of 016
**Phase**: Batch 3 — Adaptive Sample Rotation (GREEN, router core)
**Prerequisites**:
- task-008 complete: 5 Red tests (1-5) failing as expected, test 6 (signature-backcompat) green.

## BDD Scenario

```gherkin
# This task is the Green pair for task-008. The 6 Feature 4 scenarios from
# bdd-specs.md (quoted verbatim in task-008) are the acceptance contract.

Scenario: A prior win short-circuits to REPLAY_WIN
  Given tried_arms_results = {"good_multi_loop": [False], "good_loop": [True]}
  When select_arm_for_sample(..., sample_idx=2, tried_arms_results=...) is called
  Then it returns "good_loop"

Scenario: All RUNTIME_ARMS tried, all failed -- BURN_REPLAY returns the top-ranked arm
  Given a KNNRouter and tried_arms_results that records resolved=False for every arm in RUNTIME_ARMS
  When select_arm_for_sample(features, "gemma4_e4b", sample_idx=4, tried_arms_results=..., exclude_iid="sympy__sympy-15017") is called
  Then it returns ranking[0]
  And the returned arm is in RUNTIME_ARMS
```

**Spec Source**: [bdd-specs.md Feature 4 scenarios 1-6](../2026-05-27-agentbook-outcome-loop-design/bdd-specs.md) (all 6 quoted in task-008).

## Files to Modify/Create

- Modify: `experiments/agentbook-ab/pipeline/router.py` — add module-level `_pick_unexplored(...)`, add `select_arm_for_sample(...)` on both `RuleRouter` and `KNNRouter`. No change to `select` / `select_arms` signatures.

## Steps

### Step 1: Add `_pick_unexplored`
- Signature (no body):

```python
def _pick_unexplored(
    ranking: list[str], tried_arms_results: dict[str, list[bool]]
) -> str: ...
```

- Decision order per [architecture.md § `select_arm_for_sample`](../2026-05-27-agentbook-outcome-loop-design/architecture.md):
  1. REPLAY_WIN — first arm in `tried_arms_results` with any `True` result.
  2. FRESH_ARM — highest-ranked arm in `ranking` not in `tried_arms_results.keys()`.
  3. EXHAUSTED_RANKING — iterate `RUNTIME_ARMS` for any not yet tried.
  4. BURN_REPLAY — return `ranking[0]`.

### Step 2: Add `select_arm_for_sample` on `RuleRouter`
- Signature:

```python
def select_arm_for_sample(
    self, features: dict, model_slug: str, sample_idx: int,
    tried_arms_results: dict[str, list[bool]],
) -> str: ...
```

- Body: `ranking = self.select(features, model_slug, k=len(RUNTIME_ARMS))` then `return _pick_unexplored(ranking, tried_arms_results)`.

### Step 3: Add `select_arm_for_sample` on `KNNRouter`
- Signature:

```python
def select_arm_for_sample(
    self, features: dict, model_slug: str, sample_idx: int,
    tried_arms_results: dict[str, list[bool]],
    *, outcomes: list[dict] | None = None, exclude_iid: str | None = None,
) -> str: ...
```

- Body: pass `outcomes` and `exclude_iid` through to `self.select(...)` for LOO safety; delegate to `_pick_unexplored`.

### Step 4: Re-run the 6 router tests; confirm all Green
### Step 5: Project-wide regression sweep

## Verification Commands

```bash
# All 6 router tests pass
cd experiments/agentbook-ab && \
  uv run python -m pytest pipeline/tests/test_router.py -q

# Full sweep
cd experiments/agentbook-ab && \
  uv run python -m pytest -q

# Ruff
uv run ruff check --fix experiments/agentbook-ab/pipeline/router.py
```

## Success Criteria

- All 6 tests in `pipeline/tests/test_router.py` PASS.
- `_pick_unexplored` is module-level (so `evaluate_offline_rotate` can reuse it later in task-015).
- `select_arms` signature byte-for-byte unchanged (PLAN-DEP / Scenario 6 backwards-compat).
- Both routers expose `select_arm_for_sample`; the `KNNRouter` variant accepts `outcomes` and `exclude_iid` kwargs.
- Full pytest suite stays green.
- Ruff passes.
- No new external Python dependencies.
