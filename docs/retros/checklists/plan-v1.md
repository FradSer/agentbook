# Plan Mode Checklist — v1

Initial seed distilled from the 2026-04-18 memory-layer-autoresearch plan. Binary PASS/FAIL items the evaluator (writing-plans skill) applies against `_index.md` and every task file before the plan is committed.

## _index.md structure

- **PLAN-INDEX-01**: `_index.md` contains the "Execution Plan" YAML block with `id`, `subject`, `slug`, `type`, `depends-on` per task.
- **PLAN-INDEX-02**: `_index.md` contains a "Task File References" section linking to every task file.
- **PLAN-INDEX-03**: `_index.md` contains a "BDD Coverage" section mapping each Gherkin scenario in the design to ≥1 task.
- **PLAN-INDEX-04**: `_index.md` contains a "Dependency Chain" section with a visual dependency graph populated in Phase 4.

## Task file uniformity

- **PLAN-TASK-01**: Every task file has a `**depends-on**:` header immediately after the H1 title. Use `(none)` when empty — never omit.
- **PLAN-TASK-02**: Every task file carries the six required sections: Description, Execution Context, BDD Scenario (Gherkin block), Files to Modify/Create, Steps, Verification Commands, Success Criteria.
- **PLAN-TASK-03**: The Gherkin block quotes the scenario verbatim from `bdd-specs.md` — not just a cross-reference link.
- **PLAN-TASK-04**: Task filename follows `task-<NNN>-<feature>-<type>.md` convention (including letter-suffixed Red/Green pairs like `NNNa` / `NNNb`).

## BDD mapping

- **PLAN-BDD-01**: Every Gherkin scenario in the referenced design `bdd-specs.md` appears in ≥1 task file.
- **PLAN-BDD-02**: Tasks with `type: test` are strictly paired with a `type: impl` task sharing the same NN prefix.
- **PLAN-BDD-03**: `_index.md` coverage table notes any tasks without direct BDD mapping (config/refactor/docs tasks) and explains why.

## Dependency graph

- **PLAN-DEP-01**: `depends-on` is present on every task (explicitly `[]` when no deps).
- **PLAN-DEP-02**: Every `depends-on` id resolves to an existing task in the plan.
- **PLAN-DEP-03**: Every `NNNb` impl task has `NNNa` (its paired test) as a dependency.
- **PLAN-DEP-04**: DFS cycle check on the dependency graph returns zero back-edges.

## Contract over implementation

- **PLAN-CONTRACT-01**: Task files specify interface signatures, file paths, and acceptance contracts — not full implementation bodies.
- **PLAN-CONTRACT-02**: Any executable snippet in a task file is labelled "Intent only" or equivalent so the executor knows it is prescriptive not final.

## Verification

- **PLAN-VERIFY-01**: Every task file's Verification Commands section lists a runnable command whose exit code is the accept/reject signal.
- **PLAN-VERIFY-02**: Test tasks explicitly declare the Red-confirmation step (assert-tests-fail-for-the-right-reason) before declaring the task complete.
