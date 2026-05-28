# agentbook Outcome-Feedback Loop Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Load `superpowers:executing-plans` skill using the Skill tool to implement this plan task-by-task.

**Goal:** Lift gemma4:e4b 5-arm pass@3 union on the 17-task hard sympy subset from 15/17 → 17/17 by shipping three coupled subsystems (Lenient Edit Parser → Outcome-Driven Cue Refinement → Adaptive Sample Rotation) into `experiments/agentbook-ab/` as four sequential, independently-revertable batches with per-batch exit gates.

**Architecture:** Three subsystems share file boundaries but ship in sequence so a later batch can be deferred without sunk effort when an earlier batch already covers its target. Each batch is bracketed by Red-Green TDD task pairs and closes on an operator-run measurement task (`runs_v2.batch{N}/SUMMARY.md`) that writes the entry-gate inputs for the next batch.

**Tech Stack:** Python 3.11+, stdlib + `httpx` (already used by `harness/llm_ollama.py`), no new external dependencies. Tests use stdlib + `tmp_path` + `monkeypatch` against `subprocess.run` (no real Opus calls in unit tests).

**Design Support:**
- [BDD Specs](../2026-05-27-agentbook-outcome-loop-design/bdd-specs.md)
- [Architecture](../2026-05-27-agentbook-outcome-loop-design/architecture.md)
- [Best Practices](../2026-05-27-agentbook-outcome-loop-design/best-practices.md)
- [Batching Strategy](../2026-05-27-agentbook-outcome-loop-design/batching-strategy.md)

## Context

The current empirical baseline is gemma4:e4b 15/17 = 88.2% (Opus) on the hard sympy subset. Two tasks fail across every arm × every sample — `sympy__sympy-15976` (mathml printer, edit-parser truncation class) and `sympy__sympy-16766` (Indexed pycode printing, cue-underspecification class). Each class needs a different fix; a single intervention against one would leave the other untouched. Sequencing with mid-batch measurements lets us drop later batches without sunk effort when an earlier batch already covers their target.

| Aspect | Current State | Target State |
|---|---|---|
| Edit-block parser | Strict `_EDIT_RE` + `_SR_RE`; drops any block missing the closing ``` ``` `` fence (model hits `max_tokens=8000` mid-block → parser returns []; agent_loop emits `_NO_BLOCK_HINT` "emit bash" → doom-loop) | Strict path stays; lenient fallback recovers truncated fences, off-tag fences (`python`/`patch`), raw markers; agent_loop detects edit-intent and emits `_EDIT_MALFORMED_HINT` with `diagnose_edit_block(text)` to break the doom-loop |
| Cue knowledge in `synth_cache.json` | Single-revision: 14 top-level fields per entry, no history, abstract `localization_cues` that under-specify multi-site bugs | `revisions: list[dict]` lineage with `rev`, `parent_revision`, `created_at`, `source`, `model`, `leak_lines_removed`, `failure_evidence_count`, `stuck_criterion`, `refined_from`, `change_rationale`; top-level fields alias `revisions[-1]` so existing readers stay untouched |
| Cue refinement pipeline | Manual or via `memory/synthesize.py` only (no outcome feedback) | `memory/refine_from_outcomes.py` reads outcomes_log + failing transcripts, calls Opus with leak-scrubbed evidence, appends a new revision per stuck `(model_slug, iid)`; idempotent; `--require-no-regression` default ON |
| Per-sample arm selection | `select_arms(iid, model_slug, k=N)` returns a ranked list; orchestrator burns k samples on the same arm | `select_arm_for_sample(features, model_slug, sample_idx, tried_arms_results)` returns one arm conditioned on prior in-trial outcomes via REPLAY_WIN → FRESH_ARM → EXHAUSTED_RANKING → BURN_REPLAY |
| Orchestrator scheduling | Flat thread pool across all cells | Two-pool scheduler: parallel pool for non-rotate cells, per-`(iid, model)` chain pool for `good_rotate` so sample N+1 reads sample N's `result.json` from disk |

The design's batching strategy is the load-bearing structure: pre-flight → Batch 1 (parser) → Batch 2 (refinement) → Batch 3 (rotation, conditional on Batch 2 producing a mixed-outcome surface). Each batch ships as its own commit; the cross-batch invariant is that outcomes_log is the single source of truth for K_pre/K_post and `runs_v2.batch{N}/` archives are read-only after the batch closes.

## Execution Plan

```yaml
tasks:
  - id: "001"
    subject: "Pre-flight token-cap baseline"
    slug: "preflight-token-cap"
    type: "setup"
    depends-on: []
  - id: "002"
    subject: "Lenient Edit Parser tests (Features 2+3)"
    slug: "edit-parser-test"
    type: "test"
    depends-on: ["001"]
  - id: "003"
    subject: "Lenient Edit Parser implementation (Features 2+3)"
    slug: "edit-parser-impl"
    type: "impl"
    depends-on: ["002"]
  - id: "004"
    subject: "Batch 1 exit gate (full 17-task gemma4_e4b sweep)"
    slug: "batch1-exit-gate"
    type: "ops"
    depends-on: ["003"]
  - id: "005"
    subject: "refine_from_outcomes tests (Feature 1)"
    slug: "refinement-test"
    type: "test"
    depends-on: ["004"]
  - id: "006"
    subject: "refine_from_outcomes implementation + _synth_entry revision-aware reader"
    slug: "refinement-impl"
    type: "impl"
    depends-on: ["005"]
  - id: "007"
    subject: "Batch 2 exit gate (refined-iid re-eval + regression sweep)"
    slug: "batch2-exit-gate"
    type: "ops"
    depends-on: ["006"]
  - id: "008"
    subject: "select_arm_for_sample router tests (Feature 4 scenarios 1-6)"
    slug: "router-rotation-test"
    type: "test"
    depends-on: ["007"]
  - id: "009"
    subject: "select_arm_for_sample implementation on RuleRouter and KNNRouter"
    slug: "router-rotation-impl"
    type: "impl"
    depends-on: ["008"]
  - id: "010"
    subject: "good_rotate arm + arm_meta routing record test (Feature 4 scenario 7)"
    slug: "good-rotate-arm-test"
    type: "test"
    depends-on: ["009"]
  - id: "011"
    subject: "good_rotate branch in arm_context.py + _load_prior_sample_outcomes"
    slug: "good-rotate-arm-impl"
    type: "impl"
    depends-on: ["010"]
  - id: "012"
    subject: "Serial-within-chain scheduling test (Feature 4 scenario 8 / R6)"
    slug: "chain-scheduling-test"
    type: "test"
    depends-on: ["011"]
  - id: "013"
    subject: "Orchestrator chain scheduling implementation"
    slug: "chain-scheduling-impl"
    type: "impl"
    depends-on: ["012"]
  - id: "014"
    subject: "evaluate_offline_rotate simulator tests (Feature 5)"
    slug: "offline-simulator-test"
    type: "test"
    depends-on: ["009"]
  - id: "015"
    subject: "evaluate_offline_rotate implementation + main() CLI integration"
    slug: "offline-simulator-impl"
    type: "impl"
    depends-on: ["014"]
  - id: "016"
    subject: "Batch 3 exit gate (offline + online good_rotate sweep)"
    slug: "batch3-exit-gate"
    type: "ops"
    depends-on: ["013", "015"]
```

**Task File References (for detailed BDD scenarios):**

- [Task 001: Pre-flight token-cap baseline](./task-001-preflight-token-cap.md)
- [Task 002: Lenient Edit Parser tests](./task-002-edit-parser-test.md)
- [Task 003: Lenient Edit Parser implementation](./task-003-edit-parser-impl.md)
- [Task 004: Batch 1 exit gate](./task-004-batch1-exit-gate.md)
- [Task 005: refine_from_outcomes tests](./task-005-refinement-test.md)
- [Task 006: refine_from_outcomes implementation](./task-006-refinement-impl.md)
- [Task 007: Batch 2 exit gate](./task-007-batch2-exit-gate.md)
- [Task 008: select_arm_for_sample router tests](./task-008-router-rotation-test.md)
- [Task 009: select_arm_for_sample implementation](./task-009-router-rotation-impl.md)
- [Task 010: good_rotate arm test](./task-010-good-rotate-arm-test.md)
- [Task 011: good_rotate branch implementation](./task-011-good-rotate-arm-impl.md)
- [Task 012: Serial-within-chain scheduling test](./task-012-chain-scheduling-test.md)
- [Task 013: Orchestrator chain scheduling implementation](./task-013-chain-scheduling-impl.md)
- [Task 014: Offline simulator tests](./task-014-offline-simulator-test.md)
- [Task 015: Offline simulator implementation](./task-015-offline-simulator-impl.md)
- [Task 016: Batch 3 exit gate](./task-016-batch3-exit-gate.md)

## BDD Coverage

All 36 Gherkin scenarios from [bdd-specs.md](../2026-05-27-agentbook-outcome-loop-design/bdd-specs.md) (10 refinement + 10 parser-lenient + 5 parser-feedback + 8 rotation + 3 rotation-offline) map to at least one task.

| BDD Feature → Scenario(s) | Covering Task(s) |
|---|---|
| Feature 1: refine_from_outcomes (10 scenarios) | task-005 (test) + task-006 (impl) |
| Feature 2: Lenient Edit Parser (10 scenarios) | task-002 (test) + task-003 (impl) |
| Feature 3: parser-feedback hint (5 scenarios) | task-002 (test, bundled) + task-003 (impl, bundled) |
| Feature 4: rotation scenarios 1-6 (router-level `select_arm_for_sample`) | task-008 (test) + task-009 (impl) |
| Feature 4: rotation scenario 7 (`good_rotate` cell records arm_meta) | task-010 (test) + task-011 (impl) |
| Feature 4: rotation scenario 8 (serial-within-chain scheduling / R6) | task-012 (test) + task-013 (impl) |
| Feature 5: `evaluate_offline_rotate` (3 scenarios) | task-014 (test) + task-015 (impl) |

**Tasks without direct BDD mapping** (allowed under `PLAN-BDD-03` for setup/config/ops tasks):

| Task | Type | Rationale |
|---|---|---|
| task-001 | setup | Pre-flight `max_tokens` probe is a config change + measurement, not a behavioural feature; its job is to set Batch 1's gate-5 threshold (see batching-strategy.md "Pre-flight" branches A/B/C). |
| task-004 | ops | Batch 1 exit gate is the operator-run measurement step that produces `runs_v2.batch1/SUMMARY.md`; the design specifies the 5 gates as operational thresholds, not Gherkin scenarios. |
| task-007 | ops | Batch 2 exit gate (refined-iid re-eval + leak audit + `K_pre`/`K_post`); operational. |
| task-016 | ops | Batch 3 exit gate (offline + online `good_rotate` lift); operational. |

## Dependency Chain

```
task-001 (preflight setup)
    │
    └─→ task-002 (Batch1 parser test, RED)
            │
            └─→ task-003 (Batch1 parser impl, GREEN)
                    │
                    └─→ task-004 (Batch1 exit gate, OPS)
                            │
                            └─→ task-005 (Batch2 refinement test, RED)
                                    │
                                    └─→ task-006 (Batch2 refinement impl, GREEN)
                                            │
                                            └─→ task-007 (Batch2 exit gate, OPS)
                                                    │
                                                    └─→ task-008 (Batch3 router test, RED)
                                                            │
                                                            └─→ task-009 (Batch3 router impl, GREEN)
                                                                    │
                                                                    ├─→ task-010 (good_rotate test, RED)
                                                                    │       │
                                                                    │       └─→ task-011 (good_rotate impl, GREEN)
                                                                    │               │
                                                                    │               └─→ task-012 (chain-sched test, RED)
                                                                    │                       │
                                                                    │                       └─→ task-013 (chain-sched impl, GREEN)
                                                                    │                               │
                                                                    └─→ task-014 (offline-sim test, RED) ───────┤
                                                                            │                                    │
                                                                            └─→ task-015 (offline-sim impl, GREEN) ┤
                                                                                                                  │
                                                                                                                  v
                                                                                                          task-016 (Batch3 exit gate, OPS)
                                                                                                          [depends-on: 013, 015]
```

**Analysis** (to be filled in / verified by Phase 4 Sub-agent 2):

- No circular dependencies (DFS-checked manually below; Phase 4 will confirm).
- Strict Red-Green pairing: every `impl` task lists its paired `test` task as its only feature-internal dependency; cross-feature dependencies only fire when a later impl task technically requires an earlier impl's symbol.
- Cross-batch dependencies travel via the exit-gate task — `task-004 → 005`, `task-007 → 008`. This enforces the batching-strategy invariant: Batch N's gate must pass before Batch N+1 begins.
- Parallel paths inside Batch 3 once `task-009` lands: `{010 → 011 → 012 → 013}` and `{014 → 015}` are independent; both join at `task-016`.

## Cross-Batch Invariants (enforced by Operator workflow + exit-gate tasks)

- Each batch is its own commit.
- `_oracle/outcomes_log.json` is the single source of truth for `K_pre`/`K_post`; never grep `runs_v2/` directly.
- `runs_v2/` archival convention: `runs_v2.preflight/`, `runs_v2.batch1/`, `runs_v2.batch2/`, `runs_v2.batch3/` — read-only after closure.
- All gate measurements are written to `SUMMARY.md` inside the archive so a future retrospective reads them as-is.
- `uv run python -m pytest experiments/agentbook-ab/ -q` must pass at the end of every batch.

---

## Execution Handoff

**"Plan complete and saved to `docs/plans/2026-05-27-agentbook-outcome-loop-plan/`. Load `superpowers:executing-plans` skill using the Skill tool — it orchestrates per-batch sub-agent coordinators through the full Phase 1-6 pipeline."**
