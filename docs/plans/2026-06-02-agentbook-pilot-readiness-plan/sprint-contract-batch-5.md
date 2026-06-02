# Batch 5 Sprint Contract

## Recurring Failure Patterns (from prior batch analysis)

Injected because this checklist item recurred in 2+ prior batches:

- **CODE-EDIT-02 (Batches 2 + 4): ruff autofix strips a freshly-added import.** When you add an import (`ConfigDict`, `auth`, `json`, etc.) but its first *use* lands in a LATER edit, the PostToolUse ruff formatter deletes the "unused" import before you use it. **Mitigation:** add the import in the existing import group AND introduce its first use in the SAME edit; then grep-verify the import survived before running tests. If a `ruff check` later reports an undefined name you know you imported, this is why — re-add and co-locate with a use.

---

## Tasks

| ID | Subject | Type |
|----|---------|------|
| 009-test | rejection-signaling-parity — Test (Red) | test |
| 009-impl | rejection-signaling-parity — Impl (Green) | impl |
| 011-test | outcome-summary — Test (Red) | test |
| 011-impl | outcome-summary — Impl (Green) | impl |

## Acceptance Criteria

### Task 009-test: rejection-signaling-parity — Test (Red)

- [ ] `backend/tests/features/rejection-signaling-parity.feature` contains the 2 Gherkin scenarios verbatim
- [ ] Asserts a frozen-gate rejection ("content_bloat") submitted over REST `POST /v1/solutions/{id}/improve` AND over MCP `remember` improve-mode signals rejection through the single authoritative field on BOTH (non-2xx / `result.isError` true)
- [ ] Asserts both transports carry the same `reason` ("content_bloat") and the same `next_action`, so a client keying off HTTP status or `isError` detects the rejection identically
- [ ] Asserts an accepted improvement (cold-start acceptance window) signals acceptance on both (2xx / `result.isError` false) with `candidate_status` "candidate"
- [ ] Asserts neither transport reports success for a submission the other reports as rejected
- [ ] Uses the cross-transport parity helper to compare REST and MCP rejection/acceptance field-by-field; hermetic (in-memory repos)
- [ ] `uv run pytest backend/tests/unit/test_rejection_signaling_parity.py -q` FAILS Red for contract divergence (today MCP returns 200 + `isError:false` while REST returns 409), not collection error (CODE-TEST-03)

### Task 009-impl: rejection-signaling-parity — Impl (Green)

- [ ] A frozen-gate rejection surfaces as non-2xx / `result.isError=true` on BOTH REST and MCP improve paths, carrying the same `reason` and `next_action`
- [ ] Acceptance-window constraints are surfaced in the improve response, derived READ-ONLY from the FROZEN constants in `confidence.py` (no math change, no new computation)
- [ ] The frozen gate DECISION is unchanged — only the rejection *signalling* is unified across transports
- [ ] Business logic stays in `AgentbookService`; Presentation (`tools.py`, `problems.py` improve handler, `schemas.py`) only serializes
- [ ] `confidence.py:__frozen_policy_version__` NOT bumped; `scripts/check_frozen_policy.sh` exits 0
- [ ] `uv run pytest backend/tests/unit/test_rejection_signaling_parity.py -q` exits 0 (Green)
- [ ] `make fast` exits 0 (no regressions)

### Task 011-test: outcome-summary — Test (Red)

- [ ] `backend/tests/features/outcome-summary.feature` contains the 2 Gherkin scenarios verbatim
- [ ] Asserts a problem with two solutions each carrying one success outcome reports `outcome_summary.total` 2 and `outcome_summary.successes` 2, agreeing with the count of `outcome_reported` events on the timeline
- [ ] Asserts when the top solution has a success and a second solution has a failure, `total` is 2, `successes` is 1, `failures` is 1 — the non-top solution's failure is NOT invisible in the headline metric
- [ ] Hermetic (in-memory repos)
- [ ] `uv run pytest backend/tests/unit/test_outcome_summary.py -q` FAILS Red for contract divergence (today `outcome_summary` scopes to the top solution only), not collection error (CODE-TEST-03)

### Task 011-impl: outcome-summary — Impl (Green)

- [ ] `outcome_summary` aggregates over ALL visible (non-superseded) solutions of a problem, not just the top/canonical one (e.g. via `self._outcomes.list_by_problem(problem_id, [s.solution_id for s in visible_solutions])`)
- [ ] A 2-solution / 2-outcome problem reports `total=2`; failures on non-top solutions are visible in `successes`/`failures`
- [ ] Business logic stays in `AgentbookService` (`service.py` only)
- [ ] `confidence.py:__frozen_policy_version__` NOT bumped; `scripts/check_frozen_policy.sh` exits 0
- [ ] `uv run pytest backend/tests/unit/test_outcome_summary.py -q` exits 0 (Green)
- [ ] `make fast` exits 0 (no regressions)

## Red-Green Pairs

| Test Task | Impl Task | Expected Red State | Expected Green State |
|-----------|-----------|--------------------|----------------------|
| 009-test | 009-impl | MCP improve rejection returns 200 + `isError:false` while REST returns 409 — divergent signalling | All `test_rejection_signaling_parity.py` assertions pass |
| 011-test | 011-impl | `outcome_summary` counts only the top solution's outcomes; non-top failures invisible | All `test_outcome_summary.py` assertions pass |

**Sequencing note:** The two pairs touch DISJOINT files (009: `presentation/mcp/tools.py`, `presentation/api/routes/problems.py`, `presentation/api/schemas.py`; 011: `application/service.py`). They MAY run in parallel. Within each pair, the impl waits on its own confirmed Red.

## Evaluation Criteria Preview

The evaluator will apply the following `code-v2.md` checklist items:

| Item ID | Description |
|---------|-------------|
| CODE-ASSUME-01 | Grep for the improve handler, gate `reason`/`next_action`, `list_by_problem`, acceptance-window constants before referencing |
| CODE-ASSUME-02 | Confirm exact exported names before importing from shared modules |
| CODE-EDIT-01 | Re-Read a file reformatted by a PostToolUse hook before the next Edit |
| CODE-EDIT-02 | Re-add formatter-stripped imports adjacent to other imports + co-locate first use (RECURRING — see preamble) |
| CODE-LINT-01 | Conclude every task with `uv run ruff check` on touched files |
| CODE-TEST-01 | Unit tests must not hit a real DB/network/3rd-party; use in-memory repos / fakes |
| CODE-TEST-02 | Docker/Postgres integration tests gated behind `RUN_DOCKER_TESTS=1` |
| CODE-TEST-03 | Red tests assert the feature failure mode, not an incidental collection error |
| CODE-VERIFY-01 | Task test command AND `make fast` both exit 0 before completion |
| CODE-VERIFY-02 | Refactors touching shared infra (`service.py`) re-run the entire unit suite |
| CODE-SCOPE-01 | Task changes only files in its "Files" section (with natural-import / invalidated-test exceptions) |

## Sign-off

- **Generator:** executing-plans
- **Status:** READY
- **Revision:** 0
