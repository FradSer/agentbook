# Batch 2 Sprint Contract

## Tasks

| ID | Subject | Type |
|----|---------|------|
| 003-test | contribute-no-silent-failure — Test (Red) | test |
| 003-impl | contribute-no-silent-failure — Impl (Green) | impl |
| 004-test | write-dedup — Test (Red) | test |
| 004-impl | write-dedup — Impl (Green) | impl |

## Acceptance Criteria

### Task 003-test: contribute-no-silent-failure — Test (Red)

Red test task — done when tests are written and FAIL for the right reason (contract divergence, not collection error).

- [ ] `backend/tests/features/contribute-no-silent-failure.feature` contains the 6 Gherkin scenarios verbatim
- [ ] Asserts POST `/v1/problems` with inline `solution` returns 201, the returned problem shows `solution_count` 1, and the content is present in `solution_history`
- [ ] Asserts an unknown `solution` key returns 422 that names the field `solution` as unexpected, advises the two-step path `POST /v1/problems/{id}/solutions`, and creates no problem with a silently discarded solution
- [ ] Asserts MCP-vocabulary aliases `solution_content` and `solution_steps` either are honored or return 422 naming the alias — never 201 with `solution_count` 0 when solution content was supplied
- [ ] Asserts a problem-only create returns 201 with `solution_count` 0 AND a next-step affordance pointing at `POST /v1/problems/{id}/solutions`
- [ ] Asserts the OpenAPI schema for the solution-create request documents the `verification` inner shape `{command, expected, buggy}` and that `environment` is an object (not a string)
- [ ] Asserts a too-short solution returns 422 whose message states the minimum (e.g. "at least 10 characters"), mirroring the description validator's minimum-length message
- [ ] Tests hermetic (in-memory repos / doubles); `enable_limiter` only where a scenario asserts rate-limit behavior
- [ ] `uv run pytest backend/tests/unit/test_contribute_no_silent_failure.py -q` FAILS Red for contract divergence, not import/collection error (CODE-TEST-03)

### Task 003-impl: contribute-no-silent-failure — Impl (Green)

- [ ] Write request models add `model_config = ConfigDict(extra="forbid")` so unknown fields produce a naming 422
- [ ] `create_problem` routes to `service.contribute(...)` when inline solution content is present (attaches solution, returns `solution_id`); problem-only create returns a next-step affordance
- [ ] Solution-create request fields carry `Field(description=, examples=)` mirroring the MCP inline shapes (`verification` documents `{command, expected, buggy}`; `environment` documented as object) — PR-16
- [ ] Too-short solution 422 states the minimum length in `gate.py` (PR-18 length-floor), mirroring the description validator message
- [ ] Business logic stays in `AgentbookService`; Presentation only serializes (no per-transport business logic)
- [ ] `confidence.py:__frozen_policy_version__` NOT bumped; `scripts/check_frozen_policy.sh` exits 0
- [ ] `uv run pytest backend/tests/unit/test_contribute_no_silent_failure.py -q` exits 0 (Green)
- [ ] `make fast` exits 0 (no regressions)

### Task 004-test: write-dedup — Test (Red)

Red test task — done when tests are written and FAIL for the right reason.

- [ ] `backend/tests/features/write-dedup.feature` contains the 4 Gherkin scenarios verbatim
- [ ] Asserts contributing a problem with an identical `error_signature` populates `existing_problems` with the prior `problem_id` and advises improve-mode (provide `solution_id`)
- [ ] Asserts a near-identical/paraphrased description yields non-empty `existing_problems` whose top entry `match_quality` is "strong" or "exact"
- [ ] Asserts a genuinely novel problem yields empty `existing_problems` and creates a new problem
- [ ] Asserts the MCP `remember` tool description instructs recall-first / improve-on-match
- [ ] The `error_signature` dedup leg is asserted to work WITHOUT embeddings (keyword-fallback / `openrouter_api_key=None`) — embedding-independent
- [ ] Tests hermetic; `uv run pytest backend/tests/unit/test_write_dedup.py -q` FAILS Red for contract divergence, not collection error (CODE-TEST-03)

### Task 004-impl: write-dedup — Impl (Green)

- [ ] `service.contribute` folds an exact `error_signature` match leg (via `ProblemRepository.find_by_error_signature`) into the similarity advisory, populating `existing_problems` independent of embedding availability
- [ ] `existing_problems` surfaced on the REST problem-create response
- [ ] MCP `remember` tool description prepended with recall-first / improve-on-match guidance (PR-17)
- [ ] Business logic stays in `AgentbookService`; both transports call shared Application logic
- [ ] `confidence.py:__frozen_policy_version__` NOT bumped; `scripts/check_frozen_policy.sh` exits 0
- [ ] `uv run pytest backend/tests/unit/test_write_dedup.py -q` exits 0 (Green)
- [ ] `make fast` exits 0 (no regressions)

## Red-Green Pairs

| Test Task | Impl Task | Expected Red State | Expected Green State |
|-----------|-----------|--------------------|----------------------|
| 003-test | 003-impl | Inline solution silently dropped (201, solution_count 0); unknown fields accepted; no length-floor message | All `test_contribute_no_silent_failure.py` assertions pass |
| 004-test | 004-impl | `existing_problems` null/empty under keyword fallback; `remember` description lacks recall-first steer | All `test_write_dedup.py` assertions pass |

**Sequencing note (file-overlap):** 003-impl and 004-impl BOTH modify `backend/application/service.py` and `backend/presentation/api/schemas.py`. Run the two Red-Green pairs **sequentially** (pair 003 fully: test→impl→verify, THEN pair 004 fully), not in parallel, to avoid concurrent edits to the shared files. Test files (`test_contribute_no_silent_failure.py`, `test_write_dedup.py`, and the two `.feature` files) are independent and may be written first.

## Evaluation Criteria Preview

The evaluator will apply the following `code-v2.md` checklist items:

| Item ID | Description |
|---------|-------------|
| CODE-ASSUME-01 | Grep for fixtures/helpers/repo methods (e.g. `find_by_error_signature`, `contribute`) before referencing them |
| CODE-ASSUME-02 | Confirm exact exported type names before importing from shared modules |
| CODE-EDIT-01 | Re-Read a file reformatted by a PostToolUse hook before the next Edit |
| CODE-EDIT-02 | Re-add formatter-stripped imports adjacent to other imports |
| CODE-LINT-01 | Conclude every task with `uv run ruff check` on touched files |
| CODE-TEST-01 | Unit tests must not hit a real DB/network/3rd-party — in-memory repos / fakes |
| CODE-TEST-02 | Docker/Postgres integration tests gated behind `RUN_DOCKER_TESTS=1` |
| CODE-TEST-03 | Red tests assert the feature failure mode, not an incidental collection error |
| CODE-VERIFY-01 | Task test command AND `make fast` both exit 0 before completion |
| CODE-VERIFY-02 | Refactors touching shared infra (`service.py`) re-run the entire unit suite |
| CODE-SCOPE-01 | Task changes only files in its "Files" section (with natural-import / invalidated-test exceptions) |

## Sign-off

- **Generator:** executing-plans
- **Status:** READY
- **Revision:** 0
