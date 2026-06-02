# Batch 3 Sprint Contract

## Tasks

| ID | Subject | Type |
|----|---------|------|
| 005-test | honest-match-labeling — Test (Red) | test |
| 005-impl | honest-match-labeling — Impl (Green) | impl |
| 006-test | recall-latency — Test (Red) | test |
| 006-impl | recall-latency — Impl (Green) | impl |

## Acceptance Criteria

### Task 005-test: honest-match-labeling — Test (Red)

- [ ] `backend/tests/features/honest-match-labeling.feature` contains the 4 Gherkin scenarios verbatim
- [ ] Asserts a zero-solution problem (`best_solution` null, sole candidate) has `match_quality` neither "strong" nor "exact", is labeled "no_solution" (or carries `has_help` false), and the top-level `no_good_match` is true
- [ ] Asserts a solution-bearing match may carry `match_quality` "strong"/"exact" with `no_good_match` false
- [ ] Asserts when one match has a solution and another has `solution_count` 0, `no_good_match` is false only on account of the solution-bearing problem, and a `match_quality:"strong"` filter never receives the solution-less row
- [ ] Asserts an orphan (remembered, no solution) problem is not surfaced as a strong recall hit and recall does not present it as if an answer exists
- [ ] Tests hermetic; `uv run pytest backend/tests/unit/test_honest_match_labeling.py -q` FAILS Red for contract divergence (current code labels zero-solution rows strong / suppresses `no_good_match`), not collection error (CODE-TEST-03)

### Task 005-impl: honest-match-labeling — Impl (Green)

- [ ] Rows whose `best_solution is None` get `match_quality` capped to a `no_solution` tier excluded from `_GOOD_MATCH_TIERS`, so they no longer suppress `no_good_match`
- [ ] Each row carries `has_help: bool` (= `best_solution is not None`) so agents filter without per-row null checks
- [ ] `has_help`/`no_solution` labeling reconciles with the `existing_problems` `list[dict]` shape and match-tier logic introduced in Batch 2 (no regression to dedup advisory)
- [ ] Business logic stays in `AgentbookService` (`_search_problems` post-processing); both transports reflect the labeling (no per-transport business logic)
- [ ] `confidence.py:__frozen_policy_version__` NOT bumped; `scripts/check_frozen_policy.sh` exits 0
- [ ] `uv run pytest backend/tests/unit/test_honest_match_labeling.py -q` exits 0 (Green)
- [ ] `make fast` exits 0 (no regressions)

### Task 006-test: recall-latency — Test (Red)

- [ ] `backend/tests/features/recall-latency.feature` contains the 4 Gherkin scenarios verbatim
- [ ] Asserts a novel-query recall on a healthy provider returns within the recall latency budget (sub-second target)
- [ ] Asserts a configured-but-unresponsive provider: the embedding call aborts at a bounded client timeout, degrades to keyword fallback within budget, and does NOT perform synchronous 1s+2s+4s blocking retry sleeps on the request path
- [ ] Asserts a miss returns within budget carrying `no_good_match` true with `search_mode` "no_match"
- [ ] Asserts a slow-provider `POST /v1/problems` returns without blocking on a multi-second synchronous embed (embedding deferred/async)
- [ ] Latency tests use the `embedding_fault(mode)` harness fixture to simulate slow/unresponsive providers deterministically (no real sleeps that make the suite slow); hermetic
- [ ] `uv run pytest backend/tests/unit/test_recall_latency.py -q` FAILS Red for contract divergence (current code does a blocking retry storm), not collection error (CODE-TEST-03)

### Task 006-impl: recall-latency — Impl (Green)

- [ ] `VoyageEmbeddingProvider.embed(...)` uses a tight per-call client timeout on the live-query path
- [ ] The live-query retry budget is capped (no synchronous 1s+2s+4s blocking sleeps on the request path); full retry retained only on the offline `embed_documents` backfill path
- [ ] A recall miss is the cheapest path and reports `no_good_match` true / `search_mode` "no_match"
- [ ] Slow-provider behavior degrades fast to keyword fallback within the latency budget
- [ ] Business logic stays in `AgentbookService`; Infrastructure (`voyage.py`) implements the bounded client — no per-transport business logic
- [ ] `confidence.py:__frozen_policy_version__` NOT bumped; `scripts/check_frozen_policy.sh` exits 0
- [ ] `uv run pytest backend/tests/unit/test_recall_latency.py -q` exits 0 (Green)
- [ ] `make fast` exits 0 (no regressions)

## Red-Green Pairs

| Test Task | Impl Task | Expected Red State | Expected Green State |
|-----------|-----------|--------------------|----------------------|
| 005-test | 005-impl | Zero-solution rows labeled strong/exact and suppress `no_good_match`; no `has_help` field | All `test_honest_match_labeling.py` assertions pass |
| 006-test | 006-impl | Slow provider triggers blocking retry storm (1s+2s+4s); recall does not bound latency | All `test_recall_latency.py` assertions pass |

**Sequencing note (file-overlap):** 005-impl and 006-impl BOTH modify `backend/application/service.py`. Run the two Red-Green pairs **sequentially** (pair 005 fully: test→impl→verify, THEN pair 006 fully), not in parallel. The `.feature` and test files are independent.

## Evaluation Criteria Preview

The evaluator will apply the following `code-v2.md` checklist items:

| Item ID | Description |
|---------|-------------|
| CODE-ASSUME-01 | Grep for `_GOOD_MATCH_TIERS`, `_search_problems`, `VoyageEmbeddingProvider.embed`, retry-delay constants before referencing |
| CODE-ASSUME-02 | Confirm exact exported names before importing from shared modules |
| CODE-EDIT-01 | Re-Read a file reformatted by a PostToolUse hook before the next Edit |
| CODE-EDIT-02 | Re-add formatter-stripped imports adjacent to other imports (recurred-watch from Batch 2) |
| CODE-LINT-01 | Conclude every task with `uv run ruff check` on touched files |
| CODE-TEST-01 | Unit tests must not hit a real DB/network/3rd-party; use `embedding_fault` double, not real Voyage |
| CODE-TEST-02 | Docker/Postgres integration tests gated behind `RUN_DOCKER_TESTS=1` |
| CODE-TEST-03 | Red tests assert the feature failure mode, not an incidental collection error |
| CODE-VERIFY-01 | Task test command AND `make fast` both exit 0 before completion |
| CODE-VERIFY-02 | Refactors touching shared infra (`service.py`, `voyage.py`) re-run the entire unit suite |
| CODE-SCOPE-01 | Task changes only files in its "Files" section (with natural-import / invalidated-test exceptions) |

## Sign-off

- **Generator:** executing-plans
- **Status:** READY
- **Revision:** 0
