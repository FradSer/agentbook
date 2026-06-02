# Handoff State — Agentbook Pilot-Readiness Plan

Rolling cross-batch memory. Rewritten by the main agent after each batch.

## Plan

23 tasks (1 setup + 11 Red-Green test/impl pairs) closing the consistency / trust / latency layer per the pilot-readiness design (`efbdabe`). Frozen confidence policy is **v6** — never altered; confidence tasks only *surface* values `confidence.py` already computes. Clean Architecture: business logic stays in `AgentbookService`; both transports (REST, MCP) call shared Application logic.

## Batch Map

| Batch | Tasks | Status | Notes |
|-------|-------|--------|-------|
| 1 | 001 setup, 002 | DONE (PASS) | Shared read-row builder |
| 2 | 003, 004 | DONE (PASS) | contribute-no-silent-failure, write-dedup |
| 3 | 005, 006 | DONE (PASS) | honest-match-labeling, recall-latency |
| 4 | 007, 008 | DONE (PASS) | misconfig-fail-loud, mcp-error-contract |
| 5 | 009, 011 | DONE (PASS) | rejection-signaling-parity, outcome-summary |
| 6 | 010, 012 | DONE (PASS) | reliance-target, confidence-legibility |

**ALL 23 TASKS COMPLETE.** Final state: `make fast` 714 passed, 1 skipped; frozen-policy gate green (v6 untouched); ruff clean on all plan-touched files. Each batch independently evaluated PASS, zero rework rounds across the whole plan.

## Completed Task IDs

001–009, 011 (all test+impl) — Batches 1-5 PASS, independent evaluator confirmed each. Remaining: 010, 012 (Batch 6).

## Reusable Harness (USE IN ALL REMAINING FEATURE TESTS)

- Fixtures in **package-root `backend/tests/conftest.py`**: `rest_client`, `mcp_client`, `assert_transport_parity(query, fields)`, `embedding_fault(mode)`, `_build_contract_service`/`_build_client`.
- `backend/tests/unit/_helpers/transports.py`: `rest_search`, `mcp_recall`, `best_solution_for`. MCP dispatch = `dispatch_tool`; auth via `auth.resolve_mcp_credentials` + `current_auth_error`/`current_agent` ContextVars.
- `database_url=None`/`openrouter_api_key=None` forced by autouse fixture; keep tests hermetic (CODE-TEST-01).

## Batch 6 guidance (010 reliance-target, 012 confidence-legibility)

- Both EXTEND the 002-impl read-row builder (`_pick_best_solution` / `_attach_search_provenance` in `service.py`).
- 010 (reliance-target): unify contradictory `canonical_solution`/`book_solution`/history naming into ONE `reliance_target` on ALL FOUR read surfaces. Depends on 002-impl. Read its task Files list.
- 012 (confidence-legibility): outcome-report write contract; READ-ONLY surfacing of frozen math via `_provenance_from_outcomes`/`confidence_inputs`. Depends on 002-impl.
- **If both impls touch `service.py` (likely), run the two pairs SEQUENTIALLY (test→impl per pair) to avoid concurrent edits — as in Batches 2/3. Confirm from the task Files lists before deciding.**

## Key Architectural Decisions (carried forward — GREP for symbols, line numbers drift)

- **Search payload pipeline (`AgentbookService._search_problems`/`search_problems`):** provenance (`_attach_search_provenance` via `_pick_best_solution`) → honest labeling (`has_help`, `_NO_SOLUTION_TIER`, `no_good_match` from `_GOOD_MATCH_TIERS`) → honest provider (`dense_used`, `embedding_provider`="keyword"/`rerank_provider`=None when `search_mode in _KEYWORD_ONLY_SEARCH_MODES`). MCP `recall` returns the payload verbatim; REST exposes `match_quality`/`embedding_provider` but NOT `has_help`/`dense_used` as typed fields yet.
- **`confidence_inputs` provenance = `_provenance_from_outcomes`**, surfacing frozen-math values only. 012 builds on this.
- **`outcome_summary` (get_agentbook):** aggregates over ALL visible + canonical-source solution ids via `list_by_problem` (single source of truth; counter-fallback removed). Not top-solution scoped.
- **Improve rejection parity (009):** MCP `handle_contribute` sets `result["error"]="improvement_rejected"` when `not accepted` → `isError=true`; `improve_acceptance_window()` (`schemas.py`) is a READ-ONLY frozen-constant snapshot. `service.improve_solution` always returns `accepted`/`reason`/`next_action`/`candidate_status`.
- **`existing_problems` `list[dict]`**; `_dedup_advisory`. `ProblemCreateRequest` `extra="forbid"` + guided naming-422.
- **MCP auth (`auth.py`):** `AuthFailure` StrEnum + `AUTH_FAILURE_DETAILS` + `current_auth_error` ContextVar + `resolve_mcp_credentials()`. trace alias `id|problem_id|solution_id`. Transport-edge `streamable_router.py` owns `-32601` + per-request auth-cause — PRESERVE if edited.
- **Voyage bounded client (`voyage.py`):** live `embed()` single-attempt, `timeout=2.0`, `max_retries=0`.
- Frozen confidence policy version is **v6** (CLAUDE.md/README say v5 — out of date; trust `confidence.py:__frozen_policy_version__` and `scripts/check_frozen_policy.sh`). No task bumps it.
- Code checklist in force: `docs/retros/checklists/code-v2.md`.
- Route ordering: `/problems/{id}/timeline` before `/problems/{id}` in `problems.py`.

## Recurring Failure Patterns (from prior evaluation reports)

None active. (CODE-EDIT-02 ruff-strips-import recurred in Batches 2+4, was injected into the Batch 5 contract preamble, and did NOT recur in Batch 5 — RESOLVED, dropped from watch. If Batch 6 adds imports, keep the co-locate-import-with-first-use discipline.)

## Modified Files (accumulated — last writer)

service.py (011-impl), tools.py (009-impl), schemas.py (009-impl), auth.py (008-impl), streamable_router.py (008-impl), config.py (007-impl), voyage.py (006-impl), gate.py (003-impl), problems.py (003-impl), search.py (002-impl), docs/mcp-setup.md (008-impl), conftest.py (001), plus feature + unit test files for 002-011 and peer-test fixes. See `handoff-summary-5.md`.

## Blockers

None.

## Follow-ups (out of plan scope — track separately)

- Pre-existing integration failure `test_mcp_streamable_http.py::test_invalid_api_key_rejected` (401 vs 200) — red on HEAD, smoke-deselected, NOT a plan regression.
- `not_found` detail asymmetry: `handle_report`/`handle_contribute` lack `detail` (trace has it). Outside BDD scope.
- Repo-debt: `ruff check backend/` F401 in `search_stack.py:31` and `test_lift_eligibility.py:10`. Scope ruff to touched files; ruff misparses `.feature` files.
