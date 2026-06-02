# Evaluation Report — Round 1, Batch 4

**Mode:** code (independent superpowers-evaluator pass, spawned by main agent)
**Sprint contract:** `sprint-contract-batch-4.md`
**Checklist:** `docs/retros/checklists/code-v2.md`
**Verdict:** PASS

## Verification Commands (run independently)

| Command | Exit | Evidence |
|---|---|---|
| `uv run pytest backend/tests/unit/test_misconfig_fail_loud.py -q` | 0 | 5 passed |
| `uv run pytest backend/tests/unit/test_mcp_error_contract.py -q` | 0 | 10 passed |
| `make fast` | 0 | 700 passed, 1 skipped, 13 deselected in 24.53s |
| `bash scripts/check_frozen_policy.sh` | 0 | "frozen_policy v6 is documented" |
| `git diff --stat backend/application/confidence.py` | empty | frozen math untouched |
| ruff (7 batch .py files) | 0 | All checks passed! |

## Result

**007 honest provider:** `dense_used = search_mode not in _KEYWORD_ONLY_SEARCH_MODES`; provider→"keyword", rerank→None under fallback (`service.py:553-565,100-102`). `warn_on_embedding_dimension_mismatch` validator fires in every mode (`config.py:104-124`); production hard-raise retained (`config.py:155-162`). Logic stays in `AgentbookService`; config.py only validates/warns.

**008 mcp-error-contract:** `_TRACE_ID_ALIASES=("id","problem_id","solution_id")`; unknown-arg branch names the key (not "X required"); `resolve_mcp_credentials` maps MISSING_HEADER→NO_CREDENTIALS, parse-fail→MALFORMED_BEARER, UnauthorizedError→INVALID_KEY (`auth.py:55-82`) without leaking account existence; `handle_inspect` not_found carries a detail naming the id; `docs/mcp-setup.md` documents `-32700`/`-32601`/`-32602` + branch-on-error-first.

## CODE-SCOPE-01 — Router extension (PRIMARY): ACCEPTED natural extension

008 modified `streamable_router.py` (not in its Files list). Verified justified and clean:
- **Necessity:** the MCP SDK collapses unknown methods into `-32602`; emitting `-32601` requires inspecting the raw JSON body BEFORE the SDK parses it — only the ASGI handler sees it (buffer + `_unknown_method_error` + one-shot replay). `current_auth_error` is a per-request ContextVar settable only at the transport edge. Both BDD scenarios are unsatisfiable within the listed files.
- **Presentation-only:** router does header validation, JSON-RPC envelope construction, method allowlist check, body buffer/replay, credential resolution delegated to `auth.resolve_mcp_credentials` → `service.authenticate`. Zero domain/confidence logic.
- **`_KNOWN_MCP_METHODS`:** superset of every method agentbook serves (`initialize`/`ping`/`tools/list`/`tools/call`). Omitted methods (`roots/list`, `sampling/*`, `elicitation/*`, `tasks/*`) are server→client or unimplemented — `-32601` for them is correct. Maintainability note only: a future SDK upgrade adding a server-served method needs an allowlist entry.

## Pre-existing integration failure — confirmed NOT a Batch 4 regression

`backend/tests/integration/test_mcp_streamable_http.py::test_invalid_api_key_rejected` (expects 401, gets 200). Gated behind `RUN_DOCKER_TESTS=1`; `collect_ignore_glob` excludes it from `make fast`. Reproduced FAILING identically on clean HEAD via `git stash push --include-untracked` then pop (same assertion line). The 008 router deliberately resolves a bad credential as anonymous (so it does not lock callers out of public tools) — same behavior pre- and post-Batch 4. **Genuinely pre-existing.**

## Minor observation (not a finding, future consistency task)

`handle_report` and `handle_contribute` return `{"error":"not_found"}` WITHOUT a `detail`, unlike `trace`. The 008 contract asserts the `not_found` detail only for `trace` (passes). The report/remember asymmetry is pre-existing and outside this batch's BDD scope.

## Rework Items

None.

## Recurring pattern (2 batches now — INJECT into Batch 5 preamble)

**CODE-EDIT-02:** ruff autofix strips a freshly-added import (`ConfigDict` in Batch 2; `auth`/`json` in Batch 4's `streamable_router.py`) when the symbol's first use lands in a later edit. Occurred in Batch 2 and Batch 4. Mitigation: add the import in the existing import group AND introduce its first use in the same edit, then grep-verify before running tests.

## Pivot

false.
