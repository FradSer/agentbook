"""Transport parity for the read contract — backend/tests/features/transport-read-parity.feature.

The same logical recall must return the same per-solution fields over REST
``/v1/search`` and MCP ``recall``. These tests encode the TARGET contract: REST
must surface the structured knowledge, confidence provenance, and truncation
flag that MCP exposes inline, all from one shared read-row builder.

Hermetic: in-memory repos, no embedding provider (keyword fallback), no network.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from backend.domain.models import Problem, Solution

_STRUCTURED_KEYS = ["root_cause_pattern", "localization_cues", "verification"]
_PARITY_KEYS = [
    "root_cause_pattern",
    "localization_cues",
    "verification",
    "root_cause_class",
    "outcome_count",
    "confidence_inputs",
]


def _approved_problem(description: str, author_id) -> Problem:
    return Problem(
        problem_id=uuid4(),
        author_id=author_id,
        description=description,
        created_at=datetime.now(UTC),
        last_activity_at=datetime.now(UTC),
        review_status="approved",
    )


def _approved_solution(
    problem_id, author_id, content: str, confidence: float = 0.8
) -> Solution:
    return Solution(
        solution_id=uuid4(),
        problem_id=problem_id,
        author_id=author_id,
        content=content,
        confidence=confidence,
        created_at=datetime.now(UTC),
        review_status="approved",
    )


def test_rest_and_mcp_return_identical_best_solution_fields(
    contract_service: tuple[Any, dict[str, Any]],
    assert_transport_parity: Callable[..., dict[str, Any]],
) -> None:
    """Scenario: REST search and MCP recall return identical best_solution fields."""
    service, ctx = contract_service
    author = ctx["author"].agent_id
    problem = _approved_problem("posify drops symbol assumptions", author)
    ctx["problems"].add(problem)
    sol = _approved_solution(problem.problem_id, author, "preserve assumptions", 0.9)
    sol.root_cause_pattern = "Dummy(positive=True) drops the symbol's assumptions"
    sol.localization_cues = ["sympy/simplify/simplify.py: posify Dummy(...)"]
    sol.verification = [{"command": "python -c '...'", "expected": "True"}]
    sol.root_cause_class = "identity-element-fallback"
    ctx["solutions"].add(sol)

    best = assert_transport_parity("posify assumptions", _PARITY_KEYS)

    assert best["root_cause_pattern"].startswith("Dummy(positive=True)")
    assert best["localization_cues"] == [
        "sympy/simplify/simplify.py: posify Dummy(...)"
    ]
    assert best["verification"][0]["expected"] == "True"
    assert best["root_cause_class"] == "identity-element-fallback"


def test_rest_exposes_confidence_provenance_like_mcp(
    contract_service: tuple[Any, dict[str, Any]],
    rest_client: Callable[..., dict[str, Any]],
) -> None:
    """Scenario: REST search exposes confidence provenance like MCP recall."""
    service, ctx = contract_service
    author = ctx["author"].agent_id
    problem = _approved_problem("celery worker hangs on SIGTERM", author)
    ctx["problems"].add(problem)
    sol = _approved_solution(problem.problem_id, author, "handle SIGTERM to drain", 0.5)
    ctx["solutions"].add(sol)

    # Real outcomes from a distinct external reporter so the provenance counts
    # are non-trivial (outcomes_n > 0, unique_reporters > 0).
    reporter = uuid4()
    from backend.domain.models import Agent

    ctx["agents"].add(Agent(api_key_hash="r", model_type="test", agent_id=reporter))
    service.report_outcome(
        reporter_id=reporter, solution_id=sol.solution_id, success=True
    )

    payload = rest_client("celery SIGTERM")
    best = payload["results"][0]["best_solution"]
    inputs = best["confidence_inputs"]

    assert isinstance(inputs["outcomes_n"], int) and inputs["outcomes_n"] >= 1
    assert isinstance(inputs["unique_reporters"], int)
    assert inputs["unique_reporters"] >= 1
    assert isinstance(inputs["verified_n"], int)
    assert isinstance(inputs["has_seed_override"], bool)


@pytest.mark.parametrize("transport", ["rest", "mcp"])
@pytest.mark.parametrize("field", _STRUCTURED_KEYS)
def test_structured_keys_present_even_when_empty(
    transport: str,
    field: str,
    contract_service: tuple[Any, dict[str, Any]],
    rest_client: Callable[..., dict[str, Any]],
    mcp_client: Callable[..., dict[str, Any]],
) -> None:
    """Scenario Outline: Structured-knowledge keys are present even when empty."""
    service, ctx = contract_service
    author = ctx["author"].agent_id
    problem = _approved_problem("redis publish flakes under load", author)
    ctx["problems"].add(problem)
    # No structured knowledge attached.
    ctx["solutions"].add(
        _approved_solution(problem.problem_id, author, "increase client timeout", 0.7)
    )

    caller = rest_client if transport == "rest" else mcp_client
    best = caller("redis publish flakes")["results"][0]["best_solution"]

    assert field in best, f"{transport} best_solution silently omitted {field!r}"
    value = best[field]
    assert value is None or value == [] or value == "", (
        f"{transport} {field!r} expected null/empty, got {value!r}"
    )


def test_preview_truncation_is_flagged_not_silent(
    contract_service: tuple[Any, dict[str, Any]],
    rest_client: Callable[..., dict[str, Any]],
    mcp_client: Callable[..., dict[str, Any]],
) -> None:
    """Scenario: Preview truncation is flagged, not silent."""
    service, ctx = contract_service
    author = ctx["author"].agent_id
    problem = _approved_problem("long solution content overflow preview", author)
    ctx["problems"].add(problem)
    # Word-rich content well past the 200-char preview budget, so a clean
    # boundary truncation lands on whitespace rather than mid-word.
    full_content = (
        "Resolve the overflow by clamping the buffer and flushing on a word "
        "boundary so the preview never cuts a token in half while the agent "
        "still receives the complete content field inline for application "
        "without paying a second trace round-trip to the backend service today."
    )
    sol = _approved_solution(problem.problem_id, author, full_content, 0.9)
    ctx["solutions"].add(sol)

    for caller in (rest_client, mcp_client):
        best = caller("long solution content overflow")["results"][0]["best_solution"]

        assert best["content_truncated"] is True
        assert best["content"] == full_content
        preview = best["content_preview"]
        assert len(preview) < len(full_content)
        # Clean boundary: preview is a whitespace-delimited prefix of the full
        # content (no token split mid-word).
        assert full_content.startswith(preview)
        assert not preview.endswith(" ")
        remainder = full_content[len(preview) :]
        assert remainder.startswith(" "), (
            f"preview cut mid-word: ...{preview[-20:]!r} | {remainder[:20]!r}..."
        )
