# Task 008 (mcp-error-contract) — Test (Red)

**type:** test
**theme:** P0-A/P2
**closes:** PR-8, PR-2(alias), PR-18(auth/not_found)
**depends-on:** [001]

## Goal

Write the failing (Red) BDD tests for the **MCP error contract distinguishes protocol from tool errors** behavior. These tests encode the target contract and MUST fail against current `main` before the paired impl task (008-mcp-error-contract-impl) makes them pass.

## BDD Scenarios (source of truth)

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

- `backend/tests/features/mcp-error-contract.feature` — the Gherkin above, verbatim.
- `backend/tests/unit/test_mcp_error_contract.py` — step implementations / assertions. Isolate external dependencies (DB, Voyage, network) with in-memory repos and test doubles per `backend/tests/conftest.py` conventions; use the `enable_limiter` fixture only where a scenario asserts rate-limit behavior.

## Steps

1. Copy the scenarios above into `mcp-error-contract.feature`.
2. Implement step defs / test functions asserting the target contract (NOT current behavior). For cross-transport parity scenarios, assert REST and MCP payloads field-by-field via a shared helper.
3. Run the tests; confirm they FAIL (Red) for the documented reason (current behavior diverges).

## Verification

```bash
uv run pytest backend/tests/unit/test_mcp_error_contract.py -q   # expect FAIL (Red) before impl
```
