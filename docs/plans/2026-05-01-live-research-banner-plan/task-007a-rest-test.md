# Task 007a: GET /v1/dashboard/research/live REST endpoint — Red

**depends-on**: 006

## Description

Add failing FastAPI `TestClient` tests for the new REST snapshot endpoint at `/v1/dashboard/research/live`. Cover: anonymous access (200, no auth), response shape match against `LiveResearchSnapshotResponse`, `dynamic_search_limit` rate-limit (30/min anon, 300/min auth — verified via the `enable_limiter` fixture), `Cache-Control: no-store`, and CORS allowlist behaviour. Tests must FAIL until task 007b lands.

## Execution Context

**Task Number**: 007a of 20
**Phase**: Presentation — REST Red
**Prerequisites**: Task 006 (schemas declared).

## BDD Scenario

```gherkin
Scenario: Anonymous client subscribes successfully (public read endpoint)
  Given the request carries no Authorization header
  When the client issues a GET against "/v1/dashboard/research/live"
  Then the server responds with status 200
  And no API key is required

Scenario: REST snapshot endpoint reuses dynamic_search_limit
  Given the request is anonymous
  When the client issues 31 GETs against "/v1/dashboard/research/live" within one minute
  Then the 31st request receives status 429
  And the response body contains error "rate_limit_exceeded"

Scenario: CORS allows configured origin only, never wildcard
  Given CORS_ALLOW_ORIGINS is set to "https://agentbook.app"
  When a browser at "https://agentbook.app" opens the SSE stream
  Then the response Access-Control-Allow-Origin is "https://agentbook.app"
  And the response Access-Control-Allow-Origin is never "*"
```

(CORS scenario is shared with task 009a; both endpoints must respect the allowlist.)

**Spec Source**: `../2026-05-01-live-research-banner-design/bdd-specs.md`

## Files to Modify/Create

- Create: `backend/tests/unit/test_dashboard_live_routes.py`

## Steps

### Step 1: Write failing tests (Red)

Required test contracts:

```python
def test_get_live_returns_200_anonymous(client):
    """GET /v1/dashboard/research/live returns 200 with no Authorization header."""
    ...

def test_get_live_response_shape_matches_schema(client):
    """Response body validates against LiveResearchSnapshotResponse."""
    ...

def test_get_live_returns_active_problems(client, service_with_active_problem):
    """When service has one fresh problem, response.active has one item."""
    ...

def test_get_live_returns_idle_when_no_active(client):
    """No fresh problems → response.active == []."""
    ...

def test_get_live_cache_control_no_store(client):
    """Response carries Cache-Control: no-store."""
    ...

def test_get_live_anonymous_rate_limited_at_30_per_minute(client_with_limiter):
    """31st request from same IP within a minute returns 429."""
    ...

def test_get_live_authenticated_rate_limited_at_300_per_minute(
    client_with_limiter, valid_api_key
):
    """301st request from same agent within a minute returns 429."""
    ...

def test_get_live_cors_allowlist_echoes_configured_origin(client_with_cors):
    """Access-Control-Allow-Origin matches CORS_ALLOW_ORIGINS exactly, never '*'."""
    ...
```

Use the autouse fixtures from `backend/tests/conftest.py`. The rate-limit tests opt in via the `enable_limiter` fixture (existing pattern in this repo).

### Step 2: Confirm Red
```bash
uv run pytest backend/tests/unit/test_dashboard_live_routes.py -x
```

All 8 tests must FAIL with 404 Not Found (route does not exist) or `AttributeError: 'AgentbookService' object has no attribute 'get_live_research_snapshot'` if the test exercises a service mock incorrectly.

## Verification Commands

```bash
uv run pytest backend/tests/unit/test_dashboard_live_routes.py -x
# Expected: 8 FAILED tests
```

## Success Criteria

- 8 tests added, all FAIL for the intended reason (route not registered).
- Rate-limit tests use `enable_limiter` fixture per repo convention.
- No production code modified.
