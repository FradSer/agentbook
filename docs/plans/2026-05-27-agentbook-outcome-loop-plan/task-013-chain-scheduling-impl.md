# Task 013: Orchestrator chain scheduling implementation

**depends-on**: task-012

## Description

Make task-012's Red test Green. Split scheduling in `pipeline/orchestrator.py` into two pools: a parallel pool for non-rotate cells and a per-`(iid, model)` chain pool for `good_rotate` cells. Within each chain, `run_chain` calls `run_cell` serially so sample N+1's `_load_prior_sample_outcomes` finds sample N's `result.json` on disk. Across chains, scheduling stays parallel (capped by `args.workers`).

Also extend the `_has_memory` gate with a `good_rotate` case (union of all sub-arm requirements) and the `bootstrap_outcomes_log` harvest to include archived `runs_v2.cues_v1/` etc. directories when present, and pass `cell.sample_idx` to `build_prompt` in `run_cell`.

## Execution Context

**Task Number**: 013 of 016
**Phase**: Batch 3 — Adaptive Sample Rotation (GREEN, orchestrator)
**Prerequisites**:
- task-012 complete: 1 Red test failing as expected.

## BDD Scenario

```gherkin
# Green pair for task-012. Same scenario.

Scenario: Orchestrator schedules good_rotate samples serially within (iid, model) chain (R6)
  Given the orchestrator enumerates 3 good_rotate cells for (sympy__sympy-15017, gemma4:e4b) at sample_idx=0/1/2
  And the run_chain function dispatches them as a single chain
  When the chain executes under args.workers=12
  Then sample_idx=1 starts only after sample_idx=0's result.json has been written to runs_v2/
  And sample_idx=2 starts only after sample_idx=1's result.json has been written
  And other tasks' chains may execute in parallel (chain-level parallelism preserved)
  And no two cells in the SAME chain ever overlap in wall time
```

**Spec Source**: [bdd-specs.md Feature 4 scenario 8](../2026-05-27-agentbook-outcome-loop-design/bdd-specs.md).

## Files to Modify/Create

- Modify: `experiments/agentbook-ab/pipeline/orchestrator.py`:
  - Split scheduling at `main()` after `enumerate_cells`.
  - Add `run_chain(chain: list[Cell])` that calls `run_cell` serially.
  - Extend `_has_memory` with the `good_rotate` case.
  - Update `run_cell` to pass `cell.sample_idx` to `build_prompt`.
  - Extend `bootstrap_outcomes_log` harvest to include archived `runs_v2.cues_v1/` etc. directories.

## Steps

### Step 1: Split scheduling in `main()`
- After `enumerate_cells` produces `todo`:

```python
rotate_cells = [c for c in todo if c.arm == "good_rotate"]
other_cells  = [c for c in todo if c.arm != "good_rotate"]
chains: dict[tuple[str, str], list[Cell]] = defaultdict(list)
for c in rotate_cells:
    chains[(c.iid, c.model)].append(c)
for chain in chains.values():
    chain.sort(key=lambda c: c.sample_idx)
```

- Run Pool A (existing parallel pool) over `other_cells`.
- Run Pool B over `chains.values()`, where each chain is dispatched as one unit via `run_chain`. The pool's worker count caps **chain concurrency**, not cell concurrency.

### Step 2: Implement `run_chain`
- Signature: `def run_chain(chain: list[Cell], llm, client, ...) -> None: ...`.
- Body: iterate `chain` in `sample_idx` order; for each cell, call `run_cell(c, llm, client, ...)`. No `ThreadPoolExecutor` inside the chain — the serial loop is the load-bearing invariant.

### Step 3: Extend `_has_memory` gate
- Add the `good_rotate` case: `if c.arm == "good_rotate": return c.iid in mem_ids and c.iid in synth_ids and c.iid in loop_ids` (union of all sub-arm requirements per [architecture.md § orchestrator](../2026-05-27-agentbook-outcome-loop-design/architecture.md)).

### Step 4: Pass `sample_idx` to `build_prompt`
- Inside `run_cell`, change the call to `build_prompt(cell.iid, cell.arm, client=client, model_slug=cell.model_slug, sample_idx=cell.sample_idx)`.
- Confirm `Cell` already carries `sample_idx`; if not, add it as a dataclass field (verify against existing schema before assuming).

### Step 5: Extend `bootstrap_outcomes_log` harvest
- Include archived directories matching `runs_v2*` (e.g. `runs_v2.cues_v1/`, `runs_v2.preflight/`, `runs_v2.batch1/`, etc.) when present so the outcomes log carries full lineage across batches. Skip the active `runs_v2/` only when explicitly excluded.

### Step 6: Re-run the orchestrator test; confirm Green

### Step 7: Project-wide regression sweep

## Verification Commands

```bash
# Orchestrator test
cd experiments/agentbook-ab && \
  uv run python -m pytest pipeline/tests/test_orchestrator.py -q

# Full sweep
cd experiments/agentbook-ab && \
  uv run python -m pytest -q

# Smoke: dry-run orchestrator help and a tiny --dry-run plan
cd experiments/agentbook-ab && \
  uv run python -m pipeline.orchestrator --help

# Ruff
uv run ruff check --fix experiments/agentbook-ab/pipeline/orchestrator.py
```

## Success Criteria

- `test_good_rotate_chain_runs_serial_within_chain` PASSES.
- `good_rotate` cells run serially within each `(iid, model)` chain; non-`good_rotate` cells continue to run in the existing parallel pool unchanged.
- `_has_memory` returns `True` for `good_rotate` iff the iid has all sub-arm prerequisites (`mem_ids ∩ synth_ids ∩ loop_ids`).
- `run_cell` passes `cell.sample_idx` to `build_prompt`.
- `bootstrap_outcomes_log` harvest reads archived `runs_v2.*/` directories.
- Full pytest suite stays green.
- Ruff passes.
- No new external Python dependencies.
