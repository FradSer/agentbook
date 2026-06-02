# Batch 6 Sprint Contract (FINAL)

## Tasks

| ID | Subject | Type |
|----|---------|------|
| 010-test | reliance-target — Test (Red) | test |
| 010-impl | reliance-target — Impl (Green) | impl |
| 012-test | confidence-legibility — Test (Red) | test |
| 012-impl | confidence-legibility — Impl (Green) | impl |

## Acceptance Criteria

### Task 010-test: reliance-target — Test (Red)

- [ ] `backend/tests/features/reliance-target.feature` contains the 4 Gherkin scenarios verbatim
- [ ] Asserts a problem with two active solutions and no synthesis pass: `canonical_solution` is null AND the payload carries a reliance target equal to the highest-confidence active solution AND a note explains the fallback (rely on highest-confidence active solution until synthesis runs)
- [ ] Asserts the surfaced reliance target is the SAME `solution_id` (highest-confidence active) across all three surfaces — `GET /v1/problems/{id}`, MCP `trace`, `GET /v1/problems/{id}/timeline` — and each surface flags synthesized vs fallback
- [ ] Asserts MCP `trace` exposes `canonical_solution` (null in pre-pilot), `solution_history`, and `outcome_summary` — NOT only under divergent keys (`canonical_solution_id`, `solutions`)
- [ ] Asserts a 0.3-confidence solution with a perfect success record carries a `confidence_note` (on `GET /v1/problems/{id}` and MCP `trace`) explaining it is held at the 0.3 baseline until external reporters confirm, and that author self-reports never raise confidence
- [ ] Uses the cross-transport parity helper; hermetic (in-memory repos)
- [ ] `uv run pytest backend/tests/unit/test_reliance_target.py -q` FAILS Red for contract divergence (today the surfaces disagree: `canonical_solution` vs `canonical_solution_id` vs `book_solution`), not collection error (CODE-TEST-03)

### Task 010-impl: reliance-target — Impl (Green)

- [ ] ONE reliance-target resolver (`_resolve_reliance_target(problem_id)` / promoted `_resolve_book_solution`) returns `{solution_id, is_synthesized, <canonical read row>}` = canonical_solution if present else highest-confidence active `solution_history[0]`
- [ ] The SAME reliance target is emitted on `GET /v1/problems/{id}`, MCP `trace`, `GET /v1/problems/{id}/timeline`, and is aligned with search `best_solution`
- [ ] MCP `trace` exposes the documented `canonical_solution`/`solution_history`/`outcome_summary` keys (PR-4)
- [ ] A fallback note + `is_synthesized` flag self-describe whether the target is synthesized or a cold-start fallback
- [ ] Business logic stays in `AgentbookService`; Presentation (`problems.py`, `tools.py`) only serializes
- [ ] `confidence.py:__frozen_policy_version__` NOT bumped; `scripts/check_frozen_policy.sh` exits 0
- [ ] `uv run pytest backend/tests/unit/test_reliance_target.py -q` exits 0 (Green)
- [ ] `make fast` exits 0 (no regressions)

### Task 012-test: confidence-legibility — Test (Red)

- [ ] `backend/tests/features/confidence-legibility.feature` contains the 4 Gherkin scenarios verbatim
- [ ] Asserts a second external success on a solution with one prior external confirm: response carries `confidence_capped_by` "cold_start_floor", `external_reporters` 2, `external_reporters_for_full_confidence` 3, `confidence_delta` 0.0, and a `confidence_note` "2 of 3 distinct external reporters so far"
- [ ] Asserts an author self-report: `confidence_delta` 0.0, `external_reporters` 0, and a `confidence_note` stating the author's own reports never move confidence
- [ ] Asserts a third distinct external reporter: `confidence_capped_by` becomes null, `confidence_delta` positive, the jump explained by `external_reporters` reaching the threshold
- [ ] Asserts a re-report by the same agent on the same solution indicates the prior report was replaced (`replaced` true, or HTTP 200 not 201) and `outcome_count` stays 1 for that reporter-solution pair
- [ ] Hermetic (in-memory repos)
- [ ] `uv run pytest backend/tests/unit/test_confidence_legibility.py -q` FAILS Red for contract divergence, not collection error (CODE-TEST-03)

### Task 012-impl: confidence-legibility — Impl (Green)

- [ ] Structured confidence provenance the FROZEN math already computes is carried onto read surfaces: `confidence_inputs`, `confidence_capped_by`, `external_reporters_for_full_confidence`, machine-readable `confidence_note` — so a 0.3/0.5 read is self-explanatory
- [ ] Outcome re-report signals replace vs append (`replaced: true` or HTTP 200), so an agent can reconstruct its own history (PR-7); `outcome_count` stays 1 per reporter-solution pair
- [ ] All confidence values are READ-ONLY surfacings of `_provenance_from_outcomes`/frozen math — NO new computation, NO math change
- [ ] Business logic stays in `AgentbookService` (`service.py` only)
- [ ] `confidence.py:__frozen_policy_version__` NOT bumped; `scripts/check_frozen_policy.sh` exits 0
- [ ] `uv run pytest backend/tests/unit/test_confidence_legibility.py -q` exits 0 (Green)
- [ ] `make fast` exits 0 (no regressions)

## Red-Green Pairs

| Test Task | Impl Task | Expected Red State | Expected Green State |
|-----------|-----------|--------------------|----------------------|
| 010-test | 010-impl | Read surfaces disagree (`canonical_solution`/`canonical_solution_id`/`book_solution`); no unified reliance target / fallback note | All `test_reliance_target.py` assertions pass |
| 012-test | 012-impl | Outcome-report response lacks structured `confidence_capped_by`/`external_reporters_for_full_confidence`/`replaced`; 0.0 delta indistinguishable from a lost report | All `test_confidence_legibility.py` assertions pass |

**Sequencing note (file-overlap):** 010-impl and 012-impl BOTH modify `backend/application/service.py`. Run the two Red-Green pairs **SEQUENTIALLY** (pair 010 fully: test→impl→verify, THEN pair 012 fully), not in parallel. Both depend on 002-impl (the shared read-row builder), which is complete. The `.feature` and test files are independent.

## Evaluation Criteria Preview

The evaluator will apply the following `code-v2.md` checklist items:

| Item ID | Description |
|---------|-------------|
| CODE-ASSUME-01 | Grep for `_resolve_book_solution`, `_provenance_from_outcomes`, `confidence_capped_by`, `report_outcome`, timeline builder before referencing |
| CODE-ASSUME-02 | Confirm exact exported names before importing from shared modules |
| CODE-EDIT-01 | Re-Read a file reformatted by a PostToolUse hook before the next Edit |
| CODE-EDIT-02 | Co-locate a newly-added import with its first use in the same edit (prior recurring pattern) |
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
