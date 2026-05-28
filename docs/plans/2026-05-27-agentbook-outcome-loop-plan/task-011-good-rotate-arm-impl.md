# Task 011: good_rotate branch in arm_context.py + _load_prior_sample_outcomes

**depends-on**: task-010

## Description

Turn task-010's Red test Green. Add the `good_rotate` branch to `build_prompt` in `pipeline/arm_context.py` (peer to the existing `good_router` branch at lines 211-226), introduce `_load_prior_sample_outcomes(iid, model_slug, sample_idx)`, and add `sample_idx: int | None = None` to `build_prompt`'s signature so the orchestrator can plumb it through.

The `good_rotate` branch must:
1. Read `_oracle/synth_cache.json` and call `extract_features(cache[iid])`.
2. Call `_load_prior_sample_outcomes` to read prior sibling `runs_v2/<iid>__good_rotate__<model_slug>__s<j>/result.json` files (`j < sample_idx`) and assemble `{routed_to: [resolved_bool, ...]}`.
3. Consult `pipeline.router._ACTIVE_ROUTER.select_arm_for_sample(features, model_slug, sample_idx, tried)` for the sub-arm.
4. Recursively call `build_prompt(iid, sub_arm, ..., sample_idx=sample_idx)` and stamp `routed_from`, `routed_to`, `rotate_sample_idx`, `rotate_tried_history`, `hint="good_rotate"` into the returned `meta`.

## Execution Context

**Task Number**: 011 of 016
**Phase**: Batch 3 — Adaptive Sample Rotation (GREEN, arm_context)
**Prerequisites**:
- task-010 complete: 1 Red test failing as expected.

## BDD Scenario

```gherkin
# Green pair for task-010. Same scenario.

Scenario: good_rotate cell records the routing decision in arm_meta
  Given an orchestrator runs a good_rotate cell at sample_idx=1 for sympy__sympy-15017 on gemma4_e4b
  And the prior sample at sample_idx=0 has a result.json with arm_meta.routed_to="good_multi_loop" and resolved=False
  When build_prompt(iid, "good_rotate", ...) executes
  Then _load_prior_sample_outcomes returns {"good_multi_loop": [False]}
  And select_arm_for_sample is consulted with that history
  And the returned arm_meta carries routed_from="good_rotate", routed_to=<the chosen sub-arm>, rotate_sample_idx=1, rotate_tried_history={"good_multi_loop": [False]}
```

**Spec Source**: [bdd-specs.md Feature 4 scenario 7](../2026-05-27-agentbook-outcome-loop-design/bdd-specs.md).

## Files to Modify/Create

- Modify: `experiments/agentbook-ab/pipeline/arm_context.py`:
  - Extend `build_prompt` signature with `sample_idx: int | None = None`.
  - Add `good_rotate` branch (peer to `good_router`, lines 211-226) per [architecture.md § `good_rotate` arm](../2026-05-27-agentbook-outcome-loop-design/architecture.md).
  - Add module-level `_load_prior_sample_outcomes(iid: str, model_slug: str, sample_idx: int) -> dict[str, list[bool]]`.

## Steps

### Step 1: Extend `build_prompt` signature
- Add `sample_idx: int | None = None` as a trailing keyword arg. No call-site change required outside `good_rotate` and the orchestrator (orchestrator update is task-013).
- Existing callers that pass positional args continue unchanged.

### Step 2: Add `_load_prior_sample_outcomes`
- Signature:

```python
def _load_prior_sample_outcomes(
    iid: str, model_slug: str, sample_idx: int
) -> dict[str, list[bool]]: ...
```

- Walk `runs_v2/<iid>__good_rotate__<model_slug>__s<j>/result.json` for `j in range(sample_idx)`.
- For each found file, extract `arm_meta.routed_to` and `resolved`; accumulate into the dict.
- Return `{}` when `sample_idx == 0`.
- Tolerant to missing directories (returns `{}` for any `j` without a `result.json`).

### Step 3: Add the `good_rotate` branch
- Insert per [architecture.md](../2026-05-27-agentbook-outcome-loop-design/architecture.md):
  - On `arm == "good_rotate"`, guard for `model_slug` set (else `{"hint": "good_rotate", "missing_model": True}`).
  - Guard for `iid in cache` (else `{"hint": "good_rotate", "no_features": True}`).
  - Compute `features = extract_features(cache[iid])`.
  - `tried = _load_prior_sample_outcomes(iid, model_slug, sample_idx)`.
  - `sub_arm = _ACTIVE_ROUTER.select_arm_for_sample(features, model_slug, sample_idx, tried)`.
  - Recursively call `build_prompt(iid, sub_arm, client=client, model_slug=model_slug, sample_idx=sample_idx)`.
  - Stamp `meta["routed_from"]="good_rotate"`, `meta["routed_to"]=sub_arm`, `meta["rotate_sample_idx"]=sample_idx`, `meta["rotate_tried_history"]=tried`, `meta["hint"]="good_rotate"`.

### Step 4: Re-run the Red test; confirm Green

### Step 5: Project-wide regression sweep

## Verification Commands

```bash
# Single test
cd experiments/agentbook-ab && \
  uv run python -m pytest pipeline/tests/test_arm_context.py -q

# Full sweep
cd experiments/agentbook-ab && \
  uv run python -m pytest -q

# Ruff
uv run ruff check --fix experiments/agentbook-ab/pipeline/arm_context.py
```

## Success Criteria

- `test_good_rotate_cell_records_arm_meta` PASSES.
- `build_prompt` signature carries the new `sample_idx` kwarg; existing positional callers unaffected.
- `_load_prior_sample_outcomes` returns `{}` when `sample_idx == 0`; aggregates `arm_meta.routed_to` → `[resolved_bool, ...]` across prior samples otherwise.
- `good_rotate` branch records all four `arm_meta` keys: `routed_from`, `routed_to`, `rotate_sample_idx`, `rotate_tried_history`.
- Full pytest suite stays green.
- Ruff passes.
- No new external Python dependencies.
