# Task 006a (test): Dashboard recurrence-density endpoint

**depends-on**: ["003b"]

## Description

Failing test that `GET /v1/dashboard/recurrence-density` returns the rollup shape (RD, organic recurrence, per-problem counts) as a public read, so an operator can apply the proceed/abandon/green-light gates from the surfaced numbers.

## Execution Context

- **Layer:** unit test (`backend/tests/unit/`) via FastAPI test client, in-memory path (conftest forces `database_url=None`).
- **Type:** test (Red).
- **Prereqs:** 003b (the `get_recurrence_density` service method + in-memory wiring).

## BDD Scenario

These code-level scenarios make the design's strategic surfacing scenarios ("clears the proceed gate", "is abandoned", "kills the thesis", "green-lights multiplayer") actionable by exposing the numbers those human decisions consume:

```gherkin
Scenario: The operator dashboard surfaces recurrence density and organic recurrence
  Given a service with recorded query events
  When a client GETs /v1/dashboard/recurrence-density
  Then the response is 200 with recurrence_density, organic_recurrence,
    total_independent_queries, and a problems list of {problem_id, query_count, organic_recurrence}
  And the endpoint is public (no auth required), matching the other dashboard reads

Scenario: An empty instrument returns a zero rollup, not an error
  Given a service with no query events
  When a client GETs /v1/dashboard/recurrence-density
  Then the response is 200 with recurrence_density 0.0 and an empty problems list
```

## Files to Modify/Create

- `backend/tests/unit/test_dashboard_recurrence_endpoint.py` — new test using the FastAPI test client (mirror existing `/v1/dashboard/usage` endpoint tests).

## Steps

1. Seed events via the service, then `GET /v1/dashboard/recurrence-density` → 200, body validates against `RecurrenceDensityResponse` (RD float, organic float, `total_independent_queries` int, `problems` list).
2. Empty case → 200 zero rollup, no exception.
3. Endpoint reachable without an `Authorization` header (public read, like `/radar`, `/metrics`, `/usage`).
4. Route registered under `/v1/dashboard`.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_dashboard_recurrence_endpoint.py -q
```

## Success Criteria

- Tests **fail RED** for the right reason: endpoint and schema do not exist yet.
- Both populated and empty cases asserted; public-read confirmed.
