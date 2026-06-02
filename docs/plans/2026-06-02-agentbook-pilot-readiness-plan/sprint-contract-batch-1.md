# Batch 1 Sprint Contract

## Tasks

| ID | Subject | Type |
|----|---------|------|
| 001 | Shared cross-transport contract test harness | setup |
| 002-test | transport-read-parity — Test (Red) | test |
| 002-impl | transport-read-parity — Impl (Green) | impl |

## Acceptance Criteria

### Task 001: Shared cross-transport contract test harness

Setup task — no BDD scenario; criteria derive from the task Goal + Verification.

- [ ] `backend/tests/features/conftest.py` (or extended `backend/tests/conftest.py`) exposes fixtures `rest_client`, `mcp_client`, `assert_transport_parity(problem_id, fields)`, and `embedding_fault(mode)`
- [ ] `assert_transport_parity` diffs the REST `/v1/search` and MCP `recall` read-row/`best_solution` dicts field-by-field for the same problem
- [ ] `embedding_fault` can simulate slow / failing / dimension-mismatch embedding providers deterministically
- [ ] Fixtures isolate DB (in-memory repos, `database_url=None`) and embeddings (provider double) per existing conftest conventions
- [ ] `backend/tests/unit/_helpers/transports.py` provides thin REST + MCP JSON-RPC callers reused by feature tests
- [ ] `uv run pytest backend/tests/features -q --collect-only` exits 0 (fixtures import cleanly)

### Task 002-test: transport-read-parity — Test (Red)

Red test task — done when tests are written and FAIL for the right reason (target contract diverges from current `main`).

- [ ] `backend/tests/features/transport-read-parity.feature` contains the Gherkin scenarios verbatim from the task file
- [ ] `backend/tests/unit/test_transport_read_parity.py` asserts: both REST and MCP `best_solution` payloads expose keys `root_cause_pattern`, `localization_cues`, `verification`, `root_cause_class`, `outcome_count`, `confidence_inputs`
- [ ] Asserts the values for those keys are equal across the two transports
- [ ] Asserts `best_solution.confidence_inputs` carries integer `outcomes_n`, `unique_reporters`, `verified_n` and a boolean `has_seed_override`, readable without a second round-trip to `GET /v1/problems/{id}`
- [ ] Asserts structured-knowledge keys (`root_cause_pattern`, `localization_cues`, `verification`) are present with null/empty value over BOTH transports and never silently omitted
- [ ] Asserts `content_preview` truncates on a clean word boundary (not mid-word), the payload carries boolean `content_truncated=true`, and a full `content` field is retrievable on the read contract without a separate trace call
- [ ] Tests use in-memory repos / test doubles (no real DB, Voyage, or network); `enable_limiter` used only where a scenario asserts rate-limit behavior
- [ ] Running `uv run pytest backend/tests/unit/test_transport_read_parity.py -q` FAILS (Red) and the failure is the contract divergence, not an import/collection error (CODE-TEST-03)

### Task 002-impl: transport-read-parity — Impl (Green)

Green impl task — done when paired tests pass and no regressions.

- [ ] REST `/v1/search` `best_solution` exposes the same keys as MCP `recall`: `root_cause_pattern`, `localization_cues`, `verification`, `root_cause_class`, `outcome_count`, `confidence_inputs`, with values equal across transports
- [ ] ONE shared read-row builder (Application layer or shared Presentation serializer) backs both transports — no per-transport business logic
- [ ] `BestSolutionResponse` widened to declare the full canonical field set per the interface contract (`solution_id`, `confidence`, `content`, `content_preview`, `content_truncated`, `steps`, `root_cause_pattern`, `localization_cues`, `verification`, `root_cause_class`, `outcome_count`, `confidence_inputs`)
- [ ] `confidence_inputs` carries integer `outcomes_n`, `unique_reporters`, `verified_n` and boolean `has_seed_override`, surfacing values the frozen math already computes
- [ ] Structured-knowledge keys are always present (null/empty when absent), never silently omitted, on both transports
- [ ] `content_preview` truncates on a clean word boundary with `content_truncated` flag; full `content` field retrievable on the read contract
- [ ] `confidence.py:__frozen_policy_version__` is NOT bumped (CI gate `scripts/check_frozen_policy.sh` stays green)
- [ ] `uv run pytest backend/tests/unit/test_transport_read_parity.py -q` exits 0 (Green)
- [ ] `make fast` exits 0 (no regressions)

## Red-Green Pairs

| Test Task | Impl Task | Expected Red State | Expected Green State |
|-----------|-----------|--------------------|----------------------|
| 002-test | 002-impl | Tests run; assertions fail because REST read row drops structured knowledge / confidence provenance and content truncation is unflagged | All `test_transport_read_parity.py` assertions pass after the shared read-row builder lands |

Task 001 (setup) is not part of a Red-Green pair — no Red state expectation; done when `--collect-only` exits 0.

## Evaluation Criteria Preview

The evaluator will apply the following `code-v2.md` checklist items to this batch:

| Item ID | Description |
|---------|-------------|
| CODE-ASSUME-01 | Grep for fixtures/helpers/repo methods/attributes by name before referencing them in a test; do not invent names |
| CODE-ASSUME-02 | Confirm exact exported type names before importing from shared modules |
| CODE-EDIT-01 | Re-Read a file reformatted by a PostToolUse hook before the next Edit |
| CODE-EDIT-02 | Re-add formatter-stripped imports adjacent to other imports in the same module |
| CODE-LINT-01 | Conclude every task with a lint run (`uv run ruff check`) before marking completed |
| CODE-TEST-01 | Unit tests must not hit a real DB, network, or third-party API — use in-memory repos / fakes |
| CODE-TEST-02 | Docker/Postgres integration tests gated behind `RUN_DOCKER_TESTS=1` |
| CODE-TEST-03 | Red tests assert the feature failure mode, not an incidental collection/import error |
| CODE-VERIFY-01 | Task test command AND full-suite regression command both exit 0 before completion |
| CODE-VERIFY-02 | Refactors touching shared infra (`confidence.py`, `service.py`, router registration) re-run the entire unit suite |
| CODE-SCOPE-01 | Task changes only the files in its "Files" section (with the natural-import / invalidated-test exceptions) |

## Sign-off

- **Generator:** executing-plans
- **Status:** READY
- **Revision:** 0
