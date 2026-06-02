"""Contract tests: honest match labeling on the read contract.

Feature file: backend/tests/features/honest-match-labeling.feature

An agent reads ``match_quality`` / ``no_good_match`` as the "did the memory
layer answer me" signal. A problem with zero solutions (``best_solution`` null)
offers no actionable help and must NOT be labeled ``strong``/``exact`` and must
NOT, on its own, clear ``no_good_match``. Each row must also carry a
``has_help`` boolean so an agent can filter without per-row null checks.

Both transports are exercised: MCP ``recall`` returns the service payload
verbatim (so ``has_help`` / ``no_solution`` flow through), and REST
``/v1/search`` surfaces ``match_quality`` on each row.
"""

from __future__ import annotations

from backend.tests.conftest import _build_contract_service
from backend.tests.unit._helpers.transports import mcp_recall, rest_search

# An error_signature that current code classifies as an "exact" match for the
# query below — the whole point is that this strong-tier match is hollow
# (zero solutions), so the contract must demote it.
_HELPLESS_SIG = "permission denied while trying to connect to the Docker daemon socket"
_HELPLESS_DESC = "Docker socket permission denied on a rootless setup"
_HELPLESS_QUERY = _HELPLESS_SIG


def _build():
    service, ctx = _build_contract_service()
    ctx["service"] = service
    return service, ctx


def _seed_problem(ctx, description, *, error_signature=None):
    service = ctx["service"]
    return service.create_problem(
        author_id=ctx["author"].agent_id,
        description=description,
        error_signature=error_signature,
    )


def _add_solution(ctx, problem_id, content):
    service = ctx["service"]
    return service.create_solution(
        problem_id=problem_id,
        author_id=ctx["author"].agent_id,
        content=content,
        steps=["do the thing"],
    )


def _row_for(payload, problem_id):
    pid = str(problem_id)
    for row in payload["results"]:
        if row["problem_id"] == pid:
            return row
    return None


# --- Scenario: Zero-solution problem is not a strong match -----------------


def test_zero_solution_problem_is_not_a_strong_match():
    service, ctx = _build()
    problem = _seed_problem(ctx, _HELPLESS_DESC, error_signature=_HELPLESS_SIG)

    payload = service.search_problems(query=_HELPLESS_QUERY, limit=10)

    row = _row_for(payload, problem.problem_id)
    assert row is not None, "the only candidate must be present in results"
    assert row["best_solution"] is None
    # Must not read to an agent as a usable hit.
    assert row["match_quality"] not in ("strong", "exact")
    # Labeled "no_solution" OR carries has_help false (feature allows either).
    assert row["match_quality"] == "no_solution" or row.get("has_help") is False
    # A hollow match must not clear the top-level "answered" signal.
    assert payload["no_good_match"] is True


def test_zero_solution_row_carries_has_help_false():
    service, ctx = _build()
    _seed_problem(ctx, _HELPLESS_DESC, error_signature=_HELPLESS_SIG)

    payload = service.search_problems(query=_HELPLESS_QUERY, limit=10)
    assert payload["results"], "candidate must be surfaced"
    row = payload["results"][0]
    assert "has_help" in row, "every row must carry an explicit has_help flag"
    assert row["has_help"] is False


# --- Scenario: A solution-bearing match keeps the positive signal ----------


def test_solution_bearing_match_keeps_positive_signal():
    service, ctx = _build()
    problem = _seed_problem(ctx, _HELPLESS_DESC, error_signature=_HELPLESS_SIG)
    _add_solution(
        ctx,
        problem.problem_id,
        "Add your user to the docker group, "
        "then re-login so the socket becomes group-accessible.",
    )

    payload = service.search_problems(query=_HELPLESS_QUERY, limit=10)

    row = _row_for(payload, problem.problem_id)
    assert row is not None
    assert row["best_solution"] is not None
    assert row.get("has_help") is True
    assert row["match_quality"] in ("strong", "exact")
    assert payload["no_good_match"] is False


# --- Scenario: A solution-bearing match outranks a solution-less one -------


def test_solution_bearing_match_outranks_solution_less_one():
    service, ctx = _build()
    helpful = _seed_problem(
        ctx,
        "Docker daemon socket permission denied; fix via group membership",
        error_signature="permission denied while trying to connect to the "
        "Docker daemon socket at unix:///var/run/docker.sock",
    )
    _add_solution(
        ctx,
        helpful.problem_id,
        "Add the user to the docker group "
        "and restart the shell session to gain socket access.",
    )
    helpless = _seed_problem(ctx, _HELPLESS_DESC, error_signature=_HELPLESS_SIG)

    payload = service.search_problems(query=_HELPLESS_QUERY, limit=10)

    helpful_row = _row_for(payload, helpful.problem_id)
    helpless_row = _row_for(payload, helpless.problem_id)
    assert helpful_row is not None, "the solution-bearing problem must surface"

    # no_good_match is cleared only on account of the solution-bearing problem.
    assert payload["no_good_match"] is False
    assert helpful_row["match_quality"] in ("strong", "exact")
    if helpless_row is not None:
        assert helpless_row["match_quality"] not in ("strong", "exact")

    # An agent filtering on match_quality "strong"/"exact" never receives the
    # solution-less row.
    strong_rows = [
        r for r in payload["results"] if r["match_quality"] in ("strong", "exact")
    ]
    assert all(r["best_solution"] is not None for r in strong_rows)
    assert str(helpless.problem_id) not in [r["problem_id"] for r in strong_rows]


# --- Scenario: Solution-less problem kept out until it has help ------------


def test_orphan_problem_not_surfaced_as_strong_recall_hit():
    service, ctx = _build()
    # An agent "remembers" a description with no solution attached.
    orphan = _seed_problem(ctx, _HELPLESS_DESC, error_signature=_HELPLESS_SIG)

    # Both transports: recall must not present this as if an answer exists.
    mcp_payload = mcp_recall(service, _HELPLESS_QUERY, limit=10)
    rest_payload = rest_search(service, _HELPLESS_QUERY, limit=10)

    mcp_row = _row_for(mcp_payload, orphan.problem_id)
    rest_row = _row_for(rest_payload, orphan.problem_id)
    assert mcp_row is not None and rest_row is not None

    # Not a strong recall hit on either transport.
    assert mcp_row["match_quality"] not in ("strong", "exact")
    assert rest_row["match_quality"] not in ("strong", "exact")
    # No answer is presented.
    assert mcp_row["best_solution"] is None
    assert rest_row["best_solution"] is None
    # Top-level signal stays honest: nothing actually answered the query.
    assert mcp_payload["no_good_match"] is True
    assert rest_payload["no_good_match"] is True
