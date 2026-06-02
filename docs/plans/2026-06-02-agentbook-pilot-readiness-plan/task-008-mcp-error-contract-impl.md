# Task 008 (mcp-error-contract) — Impl (Green)

**type:** impl
**theme:** P0-A/P2
**closes:** PR-8, PR-2(alias), PR-18(auth/not_found)
**depends-on:** [008-mcp-error-contract-test]

## Goal

Make the Red tests from 008-mcp-error-contract-test pass. Accept the canonical `problem_id` alias on `trace` (id|problem_id|solution_id) (PR-2); report a genuinely-unknown argument as unexpected rather than a misleading 'X is required' (PR-8); distinguish no-key / invalid-or-revoked-key / malformed-Authorization in the auth detail (PR-18) without leaking account existence; ensure `not_found` carries a `detail` naming the missing id; document the protocol-layer JSON-RPC error envelope (-32601/-32700) alongside the isError envelope.

Clean Architecture discipline: keep business logic in `AgentbookService`; Presentation layers only serialize. Do NOT bump `confidence.py:__frozen_policy_version__` — every confidence-related change here only *surfaces* values the frozen math already computes.

## BDD Scenarios (target behavior)

```gherkin
Feature: MCP error contract distinguishes protocol from tool errors

  The MCP error surface must let a client distinguish protocol-layer failures
  (parse error, unknown method, missing tool name) from tool-layer failures,
  and distinguish an invalid or revoked key from no key at all. Tool errors are
  JSON-RPC SUCCESS with result.isError true and structuredContent; protocol
  errors are JSON-RPC error objects — and the docs must describe both shapes.

  Scenario: Tool-layer error returns the documented isError envelope
    Given an anonymous caller invokes the write tool "report"
    Then the response is JSON-RPC success with result.isError true
    And result.structuredContent.error is "unauthorized"
    And a content[0].text JSON fallback is present

  Scenario: Unknown method returns -32601, not -32602
    When a client calls JSON-RPC method "foo/bar"
    Then the response is a JSON-RPC error object with code -32601 "Method not found"
    And it is distinguishable from a known method called with bad params (-32602)

  Scenario: Parse and missing-name errors are protocol-layer, and documented
    Given a malformed JSON body is sent to /mcp
    Then the response is a JSON-RPC error object with code -32700 and no result key
    And docs/mcp-setup.md documents this second (protocol-layer) envelope alongside the isError envelope

  Scenario: MCP trace accepts the canonical problem_id alias (transport parity)
    Given a problem exists with a known UUID
    When a client invokes trace with {"id": "<uuid>"}
    And a client invokes trace with {"problem_id": "<uuid>"}
    Then both calls succeed and return the same problem
    And a create-then-trace chain works without remapping the identifier name across transports

  Scenario: Unknown tool argument is reported as unexpected, not "X is required"
    Given a client invokes trace with {"resourceId": "<uuid>"} instead of {"id": "<uuid>"} or {"problem_id": "<uuid>"}
    Then the error names "resourceId" as an unrecognized argument
    And it does not misleadingly report "id is required" as if nothing was sent

  Scenario Outline: Auth failures distinguish no-key from bad-key
    Given an MCP write tool is invoked with <credential>
    Then the error detail is "<detail>"

    Examples:
      | credential                          | detail                                            |
      | no Authorization header             | Authentication required: no credentials provided  |
      | Bearer ak_invalid_or_revoked_key    | Invalid or revoked API key                        |
      | Authorization without Bearer prefix | Malformed Authorization header: expected Bearer   |

  Scenario: not_found carries a detail naming the missing id
    Given a client invokes trace with a valid but absent UUID
    Then structuredContent.error is "not_found"
    And a detail field is present naming which id was not found
```

## Files

- `backend/presentation/mcp/tools.py`
- `backend/presentation/mcp/auth.py`
- `docs/mcp-setup.md`

## Interface contract (signatures only — no implementation bodies)

```python
# Presentation (MCP dispatcher) — intent, not a body:
# resolve the resource id by accepting id | problem_id | solution_id (canonical alias),
# then raise an "unexpected argument" error naming any unrecognized key (not "id is required").
def handle_inspect(arguments: dict) -> dict: ...  # alias-resolves id/problem_id/solution_id
```

## Steps

1. Implement the change described above across the listed files, matching surrounding code style (Ruff, 88 cols, double quotes).
2. Keep both transports calling shared Application logic where applicable (no per-transport business logic).
3. Run the paired test file; confirm GREEN. Run `make fast` to confirm no regressions.

## Verification

```bash
uv run pytest backend/tests/unit/test_mcp_error_contract.py -q   # expect PASS (Green)
make fast                                                   # no regressions
```
