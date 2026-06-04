# Task 006b (impl): Dashboard endpoint + schema + composition-root wiring

**depends-on**: ["006a"]

## Description

Expose `GET /v1/dashboard/recurrence-density` with a typed response, completing the instrument end-to-end on the in-memory path. Make Task 006a's tests pass. (The SQLAlchemy wiring is owned by Task 005b; this endpoint runs on the service method from 003b and needs no DB dependency, so 006b depends only on 006a.)

## Execution Context

- **Layer:** presentation (`backend/presentation/api/`), reads the service via DI.
- **Type:** impl (Green).
- **Prereqs:** 006a. (Service rollup from 003b is reached transitively via 006a → 003b.)

## BDD Scenario

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

- `backend/presentation/api/schemas.py` — add `RecurrenceDensityProblemResponse` and `RecurrenceDensityResponse`.
- `backend/presentation/api/routes/dashboard.py` — add the `@router.get("/recurrence-density")` endpoint after `/usage`.

## Steps

1. **Schemas** — **Intent only:**

   ```python
   # Intent only — response contract
   class RecurrenceDensityProblemResponse(BaseModel):
       problem_id: str
       query_count: int
       organic_recurrence: float

   class RecurrenceDensityResponse(BaseModel):
       recurrence_density: float
       organic_recurrence: float
       total_independent_queries: int
       problems: list[RecurrenceDensityProblemResponse]
   ```

2. **Endpoint** (mirror `get_usage`) — **Intent only:**

   ```python
   # Intent only — endpoint sketch
   @router.get("/recurrence-density", response_model=RecurrenceDensityResponse)
   def get_recurrence_density(
       request: Request,
       service: AgentbookService = Depends(get_service),
   ) -> dict:
       """Recurrence-density rollup: how often independent agents hit existing
       entries. Public read; powers the bootstrap proceed/abandon/green-light gates."""
       return service.get_recurrence_density()
   ```

3. Public read (no auth dependency), consistent with the other `/v1/dashboard/*` endpoints. No extra rate-limit beyond the global default (operator read of aggregates, not a hot path).

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_dashboard_recurrence_endpoint.py -q
make fast
```

## Success Criteria

- Task 006a tests pass **GREEN**; `make fast` clean.
- Endpoint is public and returns the typed rollup.
- End-to-end smoke: start the server, run a `recall`, then `curl /v1/dashboard/recurrence-density` reflects the event.
