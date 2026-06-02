# Evaluation Report — Round 1, Batch 2

**Mode:** code (independent superpowers-evaluator pass, spawned by main agent)
**Sprint contract:** `sprint-contract-batch-2.md`
**Checklist:** `docs/retros/checklists/code-v2.md`
**Verdict:** PASS

## Verification Commands (run independently)

| Command | Exit | Evidence |
|---|---|---|
| `uv run pytest backend/tests/unit/test_contribute_no_silent_failure.py -q` | 0 | 8 passed |
| `uv run pytest backend/tests/unit/test_write_dedup.py -q` | 0 | 4 passed |
| `make fast` | 0 | 671 passed, 1 skipped, 13 deselected in 24.31s |
| `bash scripts/check_frozen_policy.sh` | 0 | "frozen_policy v6 is documented." |
| `git diff --stat backend/application/confidence.py` | 0 | empty (untouched) |
| ruff (8 batch files) | 0 | All checks passed! |
| Red-state repro (impl stashed) | — | 10 failures, all contract-divergence assertions; no collection errors |

## Result

All four tasks satisfy every applicable item. Spotlight verifications:
1. `ProblemCreateRequest` `extra="forbid"` (`schemas.py:83`) + `model_validator` (`schemas.py:85-102`) emits a naming 422 advising the two-step path — not generic.
2. Inline solution genuinely attached via `service.contribute` → `create_solution` (`problems.py:38-49`, `service.py:1603`); test GETs problem, asserts `solution_count==1` + content in `solution_history`.
3. `error_signature` dedup leg is a pure dict scan (`find_by_error_signature`, in_memory `:146`); `existing_problems` populates with `openrouter_api_key=None` — embedding-independent.
4. Logic in `AgentbookService._dedup_advisory` (`service.py:1636`) + `contribute` (`service.py:1550`); `problems.py` route + `tools.py` only serialize/forward.
5. Frozen policy untouched; CI gate green.
6. Red failures reproduced as genuine contract divergence on feature lines, not import errors.
7. `test_gate.py` edit is the lone peer change — old `"short" in reason` assertion invalidated by the PR-18 message; CODE-SCOPE-01 exception (b), not scope creep.
8. No stubs/placeholders (grep clean across 5 impl files).

## Rework Items

None.

## Recurring-pattern signal (1 occurrence so far)

CODE-EDIT-02: ruff autofix repeatedly strips newly-added pydantic imports (`ConfigDict`, `model_validator`) when the symbol's first use lands in a later edit. Mitigation: add the import in the combined pydantic import line and grep-verify before running tests. Cost one Green cycle on 003-impl. Not yet at the 2-batch injection threshold; monitor in Batch 3.

## Pivot

false.
