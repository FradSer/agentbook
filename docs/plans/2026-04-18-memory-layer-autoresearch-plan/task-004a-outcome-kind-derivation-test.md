# Task 004a: Server-side kind derivation in report_outcome — Red

**depends-on**: 002b

## Description

Write a failing test that asserts `AgentbookService.report_outcome` derives `outcome.kind` strictly from `reporter_id`: `verified` when `reporter_id == SANDBOX_AGENT_ID`, `observed` otherwise. A caller attempting to pass `kind="verified"` via the REST or MCP request body MUST have that field ignored.

## Execution Context

**Task Number**: 004a of 41
**Phase**: Foundation — Derivation
**Prerequisites**: Task 002b in place.

## BDD Scenario

```gherkin
Scenario: Report schema never accepts kind from the caller
  Given an authenticated MCP client calls "report" with kind="verified" in arguments
  When the dispatcher validates the payload
  Then the "kind" key is ignored by the server
  And the persisted Outcome has kind="observed"
  And kind is derived strictly from reporter_id == SANDBOX_AGENT_ID
```

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md`

## Files to Modify/Create

- Create: `backend/tests/unit/test_outcome_kind_derivation.py`

## Steps

### Step 1: Write failing tests
Assert the following contracts:
- `service.report_outcome(reporter_id=<random UUID>, ...)` → persisted Outcome has `kind == "observed"`.
- `service.report_outcome(reporter_id=SANDBOX_AGENT_ID, ...)` → persisted Outcome has `kind == "verified"`.
- `service.report_outcome(..., kwargs={"kind": "verified"})` → `kind` kwarg raises `TypeError` (the method does not accept it) OR is silently dropped — pick the stricter option and assert it.
- MCP `dispatch_tool("report", arguments={"kind": "verified", ...})` → persisted Outcome has `kind == "observed"` and no error is raised.

### Step 2: Confirm Red
- Run `uv run pytest backend/tests/unit/test_outcome_kind_derivation.py -x` and confirm tests fail because today's `report_outcome` does not set `kind`.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_outcome_kind_derivation.py -x
```

## Success Criteria

- Four failing tests authored (three service-layer, one MCP dispatcher-level).
- No production code touched.
