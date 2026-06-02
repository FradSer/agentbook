# Evaluation Report — Round 1, Batch 1

**Mode:** code (independent superpowers-evaluator pass, spawned by main agent)
**Sprint contract:** `sprint-contract-batch-1.md`
**Checklist:** `docs/retros/checklists/code-v2.md`
**Verdict:** PASS

## Verification Commands (run independently)

| Command | Exit | Evidence |
|---|---|---|
| `uv run pytest backend/tests/features -q --collect-only` | 0 | `test_harness_smoke.py: 3` collected, no import errors |
| `uv run pytest backend/tests/unit/test_transport_read_parity.py -q` | 0 | `9 passed` |
| `make fast` | 0 | `659 passed, 1 skipped, 13 deselected in 23.91s` |
| `bash scripts/check_frozen_policy.sh` | 0 | `frozen_policy v6 is documented.` |
| `git diff --stat backend/application/confidence.py` | 0 | empty (file untouched) |
| ruff (batch files only) | 0 | `All checks passed!` |

**Red-state reconstruction:** stashed impl, kept tests, re-ran → exit 1, pattern `FFF.F.F.F`; 6 failures all contract-divergence (`REST best_solution missing key 'root_cause_pattern'`, `KeyError: 'confidence_inputs'`, silently omitted `localization_cues`, `KeyError: 'content_truncated'`). The 3 MCP-only structured-key variants passed in Red, proving the divergence is REST-specific. Impl restored byte-identical.

## Result

All three tasks (001 setup, 002-test Red, 002-impl Green) meet acceptance criteria. The shared Application-layer read-row builder (`_pick_best_solution` + `_attach_search_provenance`, `service.py:1424,1458`) backs both transports with zero per-transport business logic — MCP `recall` returns `service.search_problems` verbatim (`tools.py:499-509`); REST copies the same dict field-for-field (`search.py:73-86`). `BestSolutionResponse` widened to the canonical field set (`schemas.py:27-43`). `confidence_inputs` provenance surfaces values `_provenance_from_outcomes` already computes from frozen math (`service.py:176-185`) — no new confidence computed. Clean word-boundary truncation via `_clean_preview` (`service.py:99-115`). Frozen policy v6 untouched; CI gate green.

## Rework Items

None.

## Non-blocking note (repo debt, NOT a batch finding)

`uv run ruff check backend/` exits 1 due to two pre-existing F401 errors outside this batch's diff: `backend/infrastructure/search_stack.py:31` and `backend/tests/eval/test_lift_eligibility.py:10`. Neither file is modified by Batch 1. Flag for repo maintenance; does not block.

## Pivot

false.
