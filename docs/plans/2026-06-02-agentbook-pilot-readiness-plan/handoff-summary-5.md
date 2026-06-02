# Handoff Summary — Batch 5

## Completed Tasks

| ID | Subject | Checklist Result | Batch |
|----|---------|------------------|-------|
| 001–008 (all test+impl) | harness, transport-read-parity, contribute-no-silent-failure, write-dedup, honest-match-labeling, recall-latency, misconfig-fail-loud, mcp-error-contract | PASS | 1–4 |
| 009-test / 009-impl | rejection-signaling-parity | PASS | 5 |
| 011-test / 011-impl | outcome-summary | PASS | 5 |

## Remaining Tasks

| ID | Subject | Status | Dependencies |
|----|---------|--------|--------------|
| 010-test / 010-impl | reliance-target | pending | 001, 002-impl |
| 012-test / 012-impl | confidence-legibility | pending | 001, 002-impl |

(Final batch — Batch 6.)

## Key Decisions

- **009 unified improve rejection signal:** MCP `remember` improve path (`handle_contribute` in `tools.py`) injects `result["error"] = "improvement_rejected"` when `not result["accepted"]`, so `_as_structured_tool_result` flips `isError=true` (mirroring REST 409). It also stamps `result["acceptance_window"]`. REST 409 logic in `problems.py` is UNCHANGED. The frozen gate decision and `confidence.py` math are untouched.
- **`improve_acceptance_window()` helper** in `schemas.py` — READ-ONLY snapshot of frozen `confidence.py` constants (`COLD_START_MIN_REPORTERS`, `COLD_START_FLOOR`, `BASELINE_CONFIDENCE`). `SolutionImproveResponse.acceptance_window` uses it as `default_factory`. Reuse to surface the cold-start window; do NOT recompute confidence.
- **`service.improve_solution` result contract ALWAYS includes** `accepted`, `reason`, `next_action`, `candidate_status`. Any future mock MUST include `accepted` or the MCP isError branch raises KeyError.
- **011 outcome_summary aggregation:** `get_agentbook` outcome_summary now aggregates over ALL visible solution ids (plus canonical sources) via `self._outcomes.list_by_problem(problem_id, summary_solution_ids)`, de-duped with `dict.fromkeys`. The old `elif best_sol.outcome_count > 0` counter-fallback was REMOVED — outcomes repo is the single source of truth (counters mirror it; divergence is structurally impossible). No longer top-solution scoped.
- Prior facts hold: read-row builder (`_pick_best_solution`/`_attach_search_provenance`), `confidence_inputs` from `_provenance_from_outcomes`, honest labeling (`has_help`/`_NO_SOLUTION_TIER`), honest provider (`dense_used`), MCP auth (`auth.py` ContextVar), Voyage bounded client.

## For Batch 6 (010 reliance-target, 012 confidence-legibility)

- Both EXTEND the 002-impl read-row builder (`_pick_best_solution` / `_attach_search_provenance` in `service.py`). No conflict with Batch 5 (009 touched only Presentation; 011 touched only the `get_agentbook` outcome-summary block, NOT the search read-row builder).
- 010 (reliance-target): unify the contradictory `canonical_solution`/`book_solution`/history naming into one `reliance_target` on ALL FOUR read surfaces. Likely touches `service.py` + `schemas.py` + MCP `tools.py` + `routes/`.
- 012 (confidence-legibility): outcome-report write contract — builds on `_provenance_from_outcomes`/`confidence_inputs`. READ-ONLY surfacing of frozen math.
- Both impls likely touch `service.py` → if so, run the two pairs SEQUENTIALLY (as in Batches 2/3) to avoid concurrent edits. Confirm from their task Files lists.

## File Ownership (current last-writer)

| File Path | Last Modified By Task |
|-----------|-----------------------|
| backend/application/service.py | 011-impl |
| backend/presentation/mcp/tools.py | 009-impl |
| backend/presentation/api/schemas.py | 009-impl |
| backend/presentation/mcp/auth.py | 008-impl |
| backend/presentation/mcp/streamable_router.py | 008-impl |
| backend/core/config.py | 007-impl |
| backend/infrastructure/embeddings/voyage.py | 006-impl |
| backend/application/gate.py | 003-impl |
| backend/presentation/api/routes/problems.py | 003-impl (009 left it unchanged) |
| backend/presentation/api/routes/search.py | 002-impl |
| docs/mcp-setup.md | 008-impl |
| (feature + unit test files 002–011) | respective test tasks |
| backend/tests/unit/test_mcp_tool_handlers.py | 009-impl (mock fix) |

## Blockers

None.

## Follow-ups (out of plan scope — track separately)

- Pre-existing integration failure `test_mcp_streamable_http.py::test_invalid_api_key_rejected` (401 vs 200) — red on HEAD, smoke-deselected.
- `not_found` detail asymmetry: `handle_report`/`handle_contribute` lack `detail` (trace has it). Outside BDD scope.
- Repo-debt: `ruff check backend/` F401 in `search_stack.py:31` and `test_lift_eligibility.py:10`.
