# Batch 4 Sprint Contract

## Tasks

| ID | Subject | Type |
|----|---------|------|
| 007-test | misconfig-fail-loud — Test (Red) | test |
| 007-impl | misconfig-fail-loud — Impl (Green) | impl |
| 008-test | mcp-error-contract — Test (Red) | test |
| 008-impl | mcp-error-contract — Impl (Green) | impl |

## Acceptance Criteria

### Task 007-test: misconfig-fail-loud — Test (Red)

- [ ] `backend/tests/features/misconfig-fail-loud.feature` contains the 3 Gherkin scenarios verbatim
- [ ] Asserts `EMBEDDING_VERSION="v1"` + `VOYAGE_API_KEY` set → `create_app()` / `validate_production_settings()` refuses boot with a surfaced error naming the dimension mismatch (1024 vs 1536)
- [ ] Asserts when the service has fallen back to keyword scan, `embedding_provider` reflects the actual mechanism ("keyword" or null), NOT "voyage", and agrees with `search_mode` "in_memory_scan" / "no_match"
- [ ] Asserts a consistent `EMBEDDING_VERSION="v2"` + `VOYAGE_API_KEY` config boots cleanly
- [ ] Tests hermetic; `uv run pytest backend/tests/unit/test_misconfig_fail_loud.py -q` FAILS Red for contract divergence (provider field lies as "voyage"; v1+voyage WARN absent outside production), not collection error (CODE-TEST-03)

### Task 007-impl: misconfig-fail-loud — Impl (Green)

- [ ] Loud WARN at boot in EVERY mode (not only production) when `voyage_api_key` set with `embedding_version == "v1"` (1536 vs 1024 mismatch); hard raise retained for production (`validate_production_settings`)
- [ ] Per-query provider fields (`embedding_provider`/`rerank_provider`) reflect the mechanism that actually ranked (keyword/null) when `search_mode in {in_memory_scan, keyword_fallback, no_match}` — not the boot-configured name (or add a `dense_used: bool`)
- [ ] Business logic stays in `AgentbookService`; `main.py` / `config.py` are Composition Root / config only (no per-transport business logic)
- [ ] `confidence.py:__frozen_policy_version__` NOT bumped; `scripts/check_frozen_policy.sh` exits 0
- [ ] `uv run pytest backend/tests/unit/test_misconfig_fail_loud.py -q` exits 0 (Green)
- [ ] `make fast` exits 0 (no regressions)

### Task 008-test: mcp-error-contract — Test (Red)

- [ ] `backend/tests/features/mcp-error-contract.feature` contains the 7 Gherkin scenarios verbatim
- [ ] Asserts an anonymous `report` call returns JSON-RPC success with `result.isError` true, `structuredContent.error == "unauthorized"`, and a `content[0].text` JSON fallback
- [ ] Asserts an unknown JSON-RPC method returns an error object with code `-32601` "Method not found", distinguishable from `-32602` bad-params on a known method
- [ ] Asserts a malformed JSON body returns a JSON-RPC error object with code `-32700` and NO `result` key, and that `docs/mcp-setup.md` documents this protocol-layer envelope alongside the isError envelope
- [ ] Asserts `trace` accepts both `{"id": <uuid>}` and `{"problem_id": <uuid>}`, both succeed and return the same problem (create-then-trace chain works without remapping the id name)
- [ ] Asserts `trace` with `{"resourceId": <uuid>}` names "resourceId" as an unrecognized argument and does NOT misleadingly report "id is required"
- [ ] Asserts the three auth-failure details: no header → "Authentication required: no credentials provided"; bad/revoked key → "Invalid or revoked API key"; non-Bearer → "Malformed Authorization header: expected Bearer"
- [ ] Asserts `not_found` carries a `detail` naming the missing id
- [ ] Tests hermetic; `uv run pytest backend/tests/unit/test_mcp_error_contract.py -q` FAILS Red for contract divergence, not collection error (CODE-TEST-03)

### Task 008-impl: mcp-error-contract — Impl (Green)

- [ ] `trace` resolves the resource id by accepting `id | problem_id | solution_id` (canonical alias, PR-2)
- [ ] A genuinely-unknown argument is reported as unexpected/unrecognized naming the key (PR-8), not a misleading "X is required"
- [ ] Auth detail distinguishes no-key / invalid-or-revoked-key / malformed-Authorization (PR-18) without leaking account existence
- [ ] `not_found` carries a `detail` naming the missing id
- [ ] `docs/mcp-setup.md` documents the protocol-layer JSON-RPC error envelope (`-32601`/`-32700`) alongside the existing isError envelope
- [ ] Business logic stays in `AgentbookService`; MCP Presentation only serializes/dispatches
- [ ] `confidence.py:__frozen_policy_version__` NOT bumped; `scripts/check_frozen_policy.sh` exits 0
- [ ] `uv run pytest backend/tests/unit/test_mcp_error_contract.py -q` exits 0 (Green)
- [ ] `make fast` exits 0 (no regressions)

## Red-Green Pairs

| Test Task | Impl Task | Expected Red State | Expected Green State |
|-----------|-----------|--------------------|----------------------|
| 007-test | 007-impl | Provider field reports "voyage" under keyword fallback; v1+voyage does not WARN outside production | All `test_misconfig_fail_loud.py` assertions pass |
| 008-test | 008-impl | `trace` rejects `problem_id` alias / misreports unknown args as "id is required"; auth details undifferentiated; `not_found` lacks `detail`; docs lack the protocol envelope | All `test_mcp_error_contract.py` assertions pass |

**Sequencing note:** The two pairs touch DISJOINT files (007: `core/config.py`, `main.py`, `application/service.py`; 008: `presentation/mcp/tools.py`, `presentation/mcp/auth.py`, `docs/mcp-setup.md`). They MAY run in parallel. Within each pair, the impl waits on its own Red confirmation. Neither pair shares a source file with the other, so no inter-pair serialization is required.

## Evaluation Criteria Preview

The evaluator will apply the following `code-v2.md` checklist items:

| Item ID | Description |
|---------|-------------|
| CODE-ASSUME-01 | Grep for `validate_production_settings`, `embedding_provider`/`search_mode` fields, MCP dispatcher arg-resolution, `auth.py` credential parsing before referencing |
| CODE-ASSUME-02 | Confirm exact exported names before importing from shared modules |
| CODE-EDIT-01 | Re-Read a file reformatted by a PostToolUse hook before the next Edit |
| CODE-EDIT-02 | Re-add formatter-stripped imports adjacent to other imports |
| CODE-LINT-01 | Conclude every task with `uv run ruff check` on touched files |
| CODE-TEST-01 | Unit tests must not hit a real DB/network/3rd-party; use in-memory repos / fakes |
| CODE-TEST-02 | Docker/Postgres integration tests gated behind `RUN_DOCKER_TESTS=1` |
| CODE-TEST-03 | Red tests assert the feature failure mode, not an incidental collection error |
| CODE-VERIFY-01 | Task test command AND `make fast` both exit 0 before completion |
| CODE-VERIFY-02 | Refactors touching shared infra (`service.py`, `config.py`, `main.py`) re-run the entire unit suite |
| CODE-SCOPE-01 | Task changes only files in its "Files" section (with natural-import / invalidated-test exceptions) |

## Sign-off

- **Generator:** executing-plans
- **Status:** READY
- **Revision:** 0
