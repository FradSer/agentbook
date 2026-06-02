# Handoff Summary — Batch 4

## Completed Tasks

| ID | Subject | Checklist Result | Batch |
|----|---------|------------------|-------|
| 001–006 (all test+impl) | harness, transport-read-parity, contribute-no-silent-failure, write-dedup, honest-match-labeling, recall-latency | PASS | 1–3 |
| 007-test | misconfig-fail-loud — Test (Red) | PASS | 4 |
| 007-impl | misconfig-fail-loud — Impl (Green) | PASS | 4 |
| 008-test | mcp-error-contract — Test (Red) | PASS | 4 |
| 008-impl | mcp-error-contract — Impl (Green) | PASS | 4 |

## Remaining Tasks

| ID | Subject | Status | Dependencies |
|----|---------|--------|--------------|
| 009-test / 009-impl | rejection-signaling-parity | pending | 001 |
| 010-test / 010-impl | reliance-target | pending | 001, 002-impl |
| 011-test / 011-impl | outcome-summary | pending | 001 |
| 012-test / 012-impl | confidence-legibility | pending | 001, 002-impl |

## Key Decisions

- **Honest per-query provider (007):** `service.search_problems` payload now adds `dense_used: bool` and sets `embedding_provider="keyword"`/`rerank_provider=None` when `search_mode in _KEYWORD_ONLY_SEARCH_MODES` (`{in_memory_scan, keyword_fallback, no_match}`). REST passes these through (`SearchResultResponse` + `routes/search.py` `payload.get`); `dense_used` is NOT yet a typed REST field (not contract-required). `config.py` gained `warn_on_embedding_dimension_mismatch` model_validator firing in EVERY mode; production hard-raise in `validate_production_settings` unchanged.
- **MCP auth contract (008):** lives in `auth.py` — `AuthFailure` StrEnum + `AUTH_FAILURE_DETAILS` + `current_auth_error` ContextVar + `resolve_mcp_credentials()`. `tools.py` dispatcher reads `current_auth_error` (default NO_CREDENTIALS) for differentiated `unauthorized` detail. Old generic message GONE but peer substring "Authentication required" still matches (NO_CREDENTIALS message contains it).
- **MCP trace alias (008):** `trace` alias-resolves `id|problem_id|solution_id` (`_TRACE_ID_ALIASES`); rejects unknown keys naming them (`_TRACE_KNOWN_ARGS`, includes `include`). `handle_inspect` not_found carries a `detail` naming the id.
- **Transport-edge router (008):** `streamable_router.py` now (a) buffers+replays the POST body to intercept unknown JSON-RPC methods with a `-32601` envelope via `_unknown_method_error`/`_KNOWN_MCP_METHODS`, and (b) calls `auth.resolve_mcp_credentials` to set `current_agent` + `current_auth_error`. If a later batch edits the router, PRESERVE both. `_KNOWN_MCP_METHODS` is a hardcoded allowlist — extend it if the SDK gains new server-served request types.
- Prior facts still hold: read-row builder (`_pick_best_solution`/`_attach_search_provenance`), `confidence_inputs` from `_provenance_from_outcomes`, `existing_problems` `list[dict]`, `ProblemCreateRequest` `extra="forbid"`, Voyage bounded client, honest match labeling (`has_help`/`_NO_SOLUTION_TIER`).

## File Ownership (current last-writer)

| File Path | Last Modified By Task |
|-----------|-----------------------|
| backend/application/service.py | 007-impl |
| backend/core/config.py | 007-impl |
| backend/presentation/mcp/tools.py | 008-impl |
| backend/presentation/mcp/auth.py | 008-impl |
| backend/presentation/mcp/streamable_router.py | 008-impl |
| docs/mcp-setup.md | 008-impl |
| backend/infrastructure/embeddings/voyage.py | 006-impl |
| backend/application/gate.py | 003-impl |
| backend/presentation/api/schemas.py | 004-impl |
| backend/presentation/api/routes/problems.py | 003-impl |
| backend/presentation/api/routes/search.py | 002-impl |
| (feature + unit test files 002–008) | respective test tasks |

## Blockers

None.

## Follow-ups (out of plan scope — track separately)

- **Pre-existing integration failure:** `backend/tests/integration/test_mcp_streamable_http.py::test_invalid_api_key_rejected` expects 401 but gets 200 (router resolves present-but-invalid credential as anonymous → public `initialize` returns 200). Red on HEAD before this plan; smoke-deselected from `make fast`. Either fix the router to 401 on a present-but-invalid credential or update the stale test. NOT a plan regression.
- **not_found detail asymmetry:** `handle_report`/`handle_contribute` return `{"error":"not_found"}` without a `detail`, unlike `trace`. Pre-existing; outside BDD scope. Future consistency task.
- Repo-debt: `ruff check backend/` F401 in `backend/infrastructure/search_stack.py:31` and `backend/tests/eval/test_lift_eligibility.py:10`.
