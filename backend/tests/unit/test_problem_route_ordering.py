"""Regression test for the order-sensitive problem routes.

`/v1/problems/{problem_id}/timeline` MUST be registered before
`/v1/problems/{problem_id}` in `backend/presentation/api/routes/problems.py`.
FastAPI matches in registration order, so reordering would silently
swallow the timeline path under the catch-all and return 404 in prod.

This test fails fast on regressions instead of waiting for the manual
smoke test to catch it.
"""

from __future__ import annotations

from backend.presentation.api.routes import problems as problems_module


def test_timeline_route_is_registered_before_agentbook_route() -> None:
    paths = [route.path for route in problems_module.router.routes]
    timeline = "/v1/problems/{problem_id}/timeline"
    agentbook = "/v1/problems/{problem_id}"

    assert timeline in paths, f"expected {timeline} registered, got {paths}"
    assert agentbook in paths, f"expected {agentbook} registered, got {paths}"
    assert paths.index(timeline) < paths.index(agentbook), (
        "Route ordering broken: '/timeline' must be declared before "
        "'/{problem_id}' or it will never match. See CLAUDE.md."
    )


def test_problems_router_exposes_expected_routes() -> None:
    paths = {route.path for route in problems_module.router.routes}
    assert {
        "/v1/problems",
        "/v1/problems/{problem_id}",
        "/v1/problems/{problem_id}/timeline",
        "/v1/problems/{problem_id}/solutions",
    }.issubset(paths)


def test_solutions_router_exposes_expected_routes() -> None:
    paths = {route.path for route in problems_module.solutions_router.routes}
    assert {
        "/v1/solutions/{solution_id}/improve",
        "/v1/solutions/{solution_id}/outcomes",
        "/v1/solutions/{solution_id}/lineage",
    }.issubset(paths)
