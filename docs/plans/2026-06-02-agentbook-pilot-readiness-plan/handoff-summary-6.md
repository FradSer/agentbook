# Handoff Summary — Batch 6 (FINAL)

## Completed Tasks

| ID | Subject | Checklist Result | Batch |
|----|---------|------------------|-------|
| 001–009, 011 (all test+impl) | full P0–P1 layer (harness, transport-read-parity, contribute-no-silent-failure, write-dedup, honest-match-labeling, recall-latency, misconfig-fail-loud, mcp-error-contract, rejection-signaling-parity, outcome-summary) | PASS | 1–5 |
| 010-test / 010-impl | reliance-target | PASS | 6 |
| 012-test / 012-impl | confidence-legibility | PASS | 6 |

**ALL 23 plan tasks complete.**

## Remaining Tasks

None.

## Key Decisions

- **010 reliance-target:** one `_resolve_reliance_target(problem_id)` resolver in `service.py` (delegates selection to existing `_resolve_book_solution`: canonical if synthesized, else highest-confidence active root/promoted; enriched with `note` + `confidence_note` + `is_synthesized`). Emitted under the SAME `reliance_target` key on `get_agentbook` (GET problem), `get_problem_timeline` (timeline), and `inspect_resource` (MCP trace). MCP trace now also carries the documented `canonical_solution`/`solution_history`/`outcome_summary` keys (legacy `data`/`solutions` retained for back-compat; timeline's legacy `book_solution` retained). `AgentbookViewResponse.reliance_target` + `ProblemTimelineResponse.reliance_target` added to `schemas.py` so Pydantic does not strip the field.
- **012 confidence-legibility:** three of four scenarios were already satisfied by structured fields from earlier batches (`confidence_capped_by`, `external_reporters`, `external_reporters_for_full_confidence`, `confidence_note`). The only real gap was the `replaced` flag on re-report, now surfaced from `upsert`'s `inserted` return (`replaced = not inserted`); `OutcomeReportResponse.replaced` added to `schemas.py`.
- No confidence math changed; frozen policy v6 untouched across all 6 batches.

## File Ownership (final last-writer)

| File Path | Last Modified By Task |
|-----------|-----------------------|
| backend/application/service.py | 012-impl |
| backend/presentation/api/schemas.py | 012-impl |
| backend/presentation/mcp/tools.py | 009-impl |
| backend/presentation/mcp/auth.py | 008-impl |
| backend/presentation/mcp/streamable_router.py | 008-impl |
| backend/core/config.py | 007-impl |
| backend/infrastructure/embeddings/voyage.py | 006-impl |
| backend/application/gate.py | 003-impl |
| backend/presentation/api/routes/problems.py | 003-impl |
| backend/presentation/api/routes/search.py | 002-impl |
| docs/mcp-setup.md | 008-impl |
| backend/tests/conftest.py | 001 |
| (12 new feature files + 12 new unit test files, 001–012) | respective test tasks |
| (peer-test fixes: test_gate, test_response_transparency, test_search_rerank_integration, test_voyage_embedding_provider, test_mcp_tool_handlers) | respective impl tasks |

## Blockers

None. Final state: `make fast` 714 passed, 1 skipped; frozen-policy gate green; ruff clean on all plan-touched files.

## Follow-ups (out of plan scope — track separately)

- Pre-existing integration failure `test_mcp_streamable_http.py::test_invalid_api_key_rejected` (401 vs 200) — red on HEAD, Docker-gated/smoke-deselected, NOT a plan regression. Candidate follow-up: 401 on present-but-invalid credential, or update the stale test.
- `not_found` detail asymmetry: `handle_report`/`handle_contribute` lack `detail` (trace has it). Outside BDD scope.
- Deferred P2 (from `_index.md`): persist gate `reason` on the candidate `Solution` (Domain field + Alembic migration) — has no BDD scenario; add a spec first.
- Repo-debt: `ruff check backend/` F401 in `search_stack.py:31` and `test_lift_eligibility.py:10`.
- Doc drift: CLAUDE.md/README say frozen policy "v5"; actual is "v6". Trust `confidence.py:__frozen_policy_version__`.
- Retro note: 006 and 010 achieved tighter scope than their task Files predicted by keeping logic in Application/Infrastructure (plan over-predicted Presentation edits).
