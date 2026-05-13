# Task 004b: Server-side kind derivation in report_outcome — Green

**depends-on**: 004a

## Description

In `AgentbookService.report_outcome`, derive `outcome.kind` from `reporter_id`. Tighten the MCP `report` dispatcher to drop any client-supplied `kind` key before passing arguments to the service. The REST `OutcomeCreateRequest` Pydantic model must NOT list `kind` as a field — Pydantic's default `model_config` in this codebase is strict, so an unknown field raises; if loose, add `model_config = ConfigDict(extra="ignore")`.

## Execution Context

**Task Number**: 004b of 41
**Phase**: Foundation — Derivation
**Prerequisites**: Task 004a red tests committed.

## BDD Scenario

(Same scenario as task 004a — see `bdd-specs.md`.)

## Files to Modify/Create

- Modify: `backend/application/service.py::report_outcome` — derive `kind` from `reporter_id`.
- Modify: `backend/presentation/mcp/tools.py::handle_report` — strip `kind` from `arguments` before dispatch.
- Verify: `backend/presentation/api/schemas.py::OutcomeCreateRequest` — confirm it does not expose `kind`; add `ConfigDict(extra="ignore")` if schemas use `extra="allow"` or `extra="forbid"` with caller-facing impact.

## Steps

### Step 1: Derive in service
- At the top of `report_outcome`, compute `kind = "verified" if reporter_id == SANDBOX_AGENT_ID else "observed"` and pass it to the `Outcome(...)` constructor.

### Step 2: Strip in MCP dispatcher
- In `handle_report`, before calling `service.report_outcome(...)`, `arguments.pop("kind", None)`. Do not raise on presence; silent drop is the correct behaviour per the BDD scenario.

### Step 3: Verify REST schema
- Grep `backend/presentation/api/schemas.py` for `OutcomeCreateRequest`. Ensure no `kind` field. If the request is currently permissive, set `model_config = ConfigDict(extra="ignore")` so legacy clients including `kind` in their payload are silently accepted.

### Step 4: Green the tests
- Run the test file from 004a and the broader suite. All should pass.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_outcome_kind_derivation.py -v
uv run pytest backend/tests/unit/
uv run pytest backend/tests/integration/ -k outcome
```

## Success Criteria

- All 004a tests green.
- Unit + integration suites unbroken.
- No request-body path allows caller-supplied `kind` to reach persistence.
