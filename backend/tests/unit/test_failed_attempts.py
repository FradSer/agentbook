"""Verifies features/failed-attempts-trajectory.feature.

Failed attempts are the negative half of the trajectory: what an author
tried before a solution worked, and what a reporter tried before giving up.
These tests pin storage, secret-gating, size caps, takedown scrubbing,
REST<->MCP transport parity, and that confidence math ignores the field
entirely (v6 stays frozen).
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from backend.application.service import AgentbookService
from backend.domain.models import Agent, Outcome, Problem, Solution
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)
from backend.presentation.api.deps import get_service
from backend.presentation.mcp.tools import handle_contribute

FAILED_ATTEMPTS = [
    "tried pinning the wrong package version",
    "attempted a global sitecustomize hook",
]


def _service() -> tuple[AgentbookService, UUID]:
    agents = InMemoryAgentRepository()
    author_id = uuid4()
    agents.add(Agent(api_key_hash="h", model_type="test", agent_id=author_id))
    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    return service, author_id


def _seed_problem(service: AgentbookService, author_id: UUID):
    return service.create_problem(
        author_id=author_id,
        description="pytest fixture tempdir leaks files between test runs",
    )


def _reporter(service: AgentbookService) -> UUID:
    return service.register_agent(model_type="test")[0].agent_id


# --- Storage and read paths -------------------------------------------------


def test_contribute_with_failed_attempts_stores_and_reads() -> None:
    service, author_id = _service()
    problem = _seed_problem(service, author_id)
    result = service.contribute(
        author_id=author_id,
        description=problem.description,
        problem_id=problem.problem_id,
        solution_content="Clear the tmp_path factory cache between sessions",
        solution_failed_attempts=list(FAILED_ATTEMPTS),
    )
    assert result["status"] == "solution_added"
    book = service.get_agentbook(problem.problem_id)
    stored = book["solution_history"][0]
    assert stored["failed_attempts"] == FAILED_ATTEMPTS


def test_solution_created_directly_carries_failed_attempts() -> None:
    service, author_id = _service()
    problem = _seed_problem(service, author_id)
    solution = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Clear the tmp_path factory cache between sessions",
        failed_attempts=list(FAILED_ATTEMPTS),
    )
    assert solution.failed_attempts == FAILED_ATTEMPTS


def test_failed_attempts_default_to_empty_list() -> None:
    service, author_id = _service()
    problem = _seed_problem(service, author_id)
    service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="A plain solution without any negative trajectory attached.",
    )
    book = service.get_agentbook(problem.problem_id)
    assert book["solution_history"][0]["failed_attempts"] == []


def test_failure_report_with_failed_attempts_stored_and_inspected() -> None:
    service, author_id = _service()
    problem = _seed_problem(service, author_id)
    solution = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Clear the tmp_path factory cache between sessions",
    )
    reporter = _reporter(service)
    service.report_outcome(
        reporter_id=reporter,
        solution_id=solution.solution_id,
        success=False,
        notes="still leaking on 3.12",
        failed_attempts=["deleted only ~/.pytest_cache"],
    )
    inspected = service.inspect_resource(solution.solution_id)
    outcome_view = inspected["outcomes"][0]
    assert outcome_view["failed_attempts"] == ["deleted only ~/.pytest_cache"]


# --- Gates ------------------------------------------------------------------


@pytest.mark.parametrize("payload", [["sk-ant-api03-real-looking-key-material"]])
def test_secret_in_contribute_failed_attempts_rejected(payload: list[str]) -> None:
    service, author_id = _service()
    problem = _seed_problem(service, author_id)
    with pytest.raises(ValueError, match="secret"):
        service.contribute(
            author_id=author_id,
            description=problem.description,
            problem_id=problem.problem_id,
            solution_content="Honest content for the solution body itself.",
            solution_failed_attempts=payload,
        )
    assert service._solutions.list_by_problem(problem.problem_id) == []


def test_secret_in_report_failed_attempts_rejected() -> None:
    service, author_id = _service()
    problem = _seed_problem(service, author_id)
    solution = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Honest content for the solution body itself.",
    )
    with pytest.raises(ValueError, match="secret"):
        service.report_outcome(
            reporter_id=_reporter(service),
            solution_id=solution.solution_id,
            success=False,
            failed_attempts=[
                "my env dump contained sk-live-9f8e7d6c5b4a3f2e1d0cabcdef123456"
            ],
        )
    assert service._outcomes.list_by_solution(solution.solution_id) == []


def test_oversized_failed_attempts_rejected_on_contribute() -> None:
    service, author_id = _service()
    problem = _seed_problem(service, author_id)
    too_many = [f"attempt {i}" for i in range(11)]
    with pytest.raises(ValueError):
        service.contribute(
            author_id=author_id,
            description=problem.description,
            problem_id=problem.problem_id,
            solution_content="Honest content for the solution body itself.",
            solution_failed_attempts=too_many,
        )


def test_overlong_single_entry_rejected_on_report() -> None:
    service, author_id = _service()
    problem = _seed_problem(service, author_id)
    solution = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Honest content for the solution body itself.",
    )
    with pytest.raises(ValueError):
        service.report_outcome(
            reporter_id=_reporter(service),
            solution_id=solution.solution_id,
            success=False,
            failed_attempts=["x" * 501],
        )


# --- Takedown scrubbing ------------------------------------------------------


def test_takedown_scrubs_failed_attempts_everywhere() -> None:
    service, author_id = _service()
    problem = _seed_problem(service, author_id)
    solution = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Honest content for the solution body itself.",
        failed_attempts=["something sensitive slipped in here"],
    )
    outcome_repo: InMemoryOutcomeRepository = service._outcomes
    outcome_repo.add(
        Outcome(
            solution_id=solution.solution_id,
            reporter_id=_reporter(service),
            success=False,
            failed_attempts=["reporter-side sensitive detail"],
        )
    )
    service.takedown_solution(solution.solution_id)
    redacted = service._solutions.get(solution.solution_id)
    assert redacted is not None
    assert redacted.failed_attempts == []
    for outcome in outcome_repo.list_by_solution(solution.solution_id):
        assert outcome.failed_attempts == []


# --- Recall path --------------------------------------------------------------


def test_recall_exposes_failed_attempts_to_consumers() -> None:
    from backend.application.service import CallerContext

    service, author_id = _service()
    problem = _seed_problem(service, author_id)
    service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Clear the tmp_path factory cache between sessions",
        failed_attempts=list(FAILED_ATTEMPTS),
    )
    payload = service.search_problems(
        query=problem.description,
        limit=5,
        caller=CallerContext(),
    )
    assert payload["results"], "recall must surface the seeded problem"
    best = payload["results"][0]["best_solution"]
    assert best is not None
    assert best["failed_attempts"] == FAILED_ATTEMPTS


# --- Transport parity (MCP handle + REST route models) -----------------------


def test_mcp_contribute_forwards_failed_attempts() -> None:
    import asyncio
    import json

    service, author_id = _service()
    problem = _seed_problem(service, author_id)
    result_payload = asyncio.run(
        handle_contribute(
            service,
            author_id,
            {
                "description": problem.description,
                "problem_id": str(problem.problem_id),
                "solution_content": "Clear the tmp_path factory cache between sessions",
                "failed_attempts": list(FAILED_ATTEMPTS),
            },
        )
    )
    payload = json.loads(result_payload[0]["text"])
    # MCP contribute has no problem_id argument (existing surface), so this
    # lands on the new-problem branch; the assertion target is field
    # forwarding, not branch selection.
    assert payload["status"] == "knowledge_created"
    book = service.get_agentbook(UUID(payload["problem_id"]))
    assert book["solution_history"][0]["failed_attempts"] == FAILED_ATTEMPTS


def test_rest_request_models_accept_failed_attempts() -> None:
    from backend.presentation.api.schemas import (
        OutcomeCreateRequest,
        ProblemCreateRequest,
        SolutionCreateRequest,
    )

    inline = ProblemCreateRequest(
        description="pytest fixture tempdir leaks files between test runs",
        solution_content="Clear the tmp_path factory cache between sessions",
        failed_attempts=list(FAILED_ATTEMPTS),
    )
    assert inline.failed_attempts == FAILED_ATTEMPTS

    standalone = SolutionCreateRequest(
        content="Clear the tmp_path factory cache between sessions",
        failed_attempts=list(FAILED_ATTEMPTS),
    )
    assert standalone.failed_attempts == FAILED_ATTEMPTS

    report = OutcomeCreateRequest(
        success=False,
        failed_attempts=["deleted only ~/.pytest_cache"],
    )
    assert report.failed_attempts == ["deleted only ~/.pytest_cache"]


# --- REST route wiring (TestClient end-to-end) -------------------------------


def test_rest_routes_carry_failed_attempts_end_to_end() -> None:
    from backend.tests.conftest import _build_client

    client, api_key = _build_client()
    service = client.app.dependency_overrides[get_service]()
    headers = {"Authorization": f"Bearer {api_key}"}

    created = client.post(
        "/v1/problems",
        headers=headers,
        json={
            "description": "pytest fixture tempdir leaks files between test runs",
            "solution_content": "Clear the tmp_path factory cache between sessions",
            "failed_attempts": list(FAILED_ATTEMPTS),
        },
    )
    assert created.status_code == 201, created.text
    problem_id = created.json()["problem_id"]

    book = service.get_agentbook(UUID(problem_id))
    assert book["solution_history"][0]["failed_attempts"] == FAILED_ATTEMPTS

    solution_id = created.json()["solution_id"]
    reported = client.post(
        f"/v1/solutions/{solution_id}/outcomes",
        headers=headers,
        json={
            "success": False,
            "notes": "still leaking on 3.12",
            "failed_attempts": ["deleted only ~/.pytest_cache"],
        },
    )
    assert reported.status_code == 201, reported.text

    inspected = service.inspect_resource(UUID(solution_id))
    assert inspected["outcomes"][0]["failed_attempts"] == [
        "deleted only ~/.pytest_cache"
    ]


def test_rest_rejects_secret_in_failed_attempts_with_400() -> None:
    from backend.tests.conftest import _build_client

    client, api_key = _build_client()
    headers = {"Authorization": f"Bearer {api_key}"}
    response = client.post(
        "/v1/problems",
        headers=headers,
        json={
            "description": "pytest fixture tempdir leaks files between test runs",
            "solution_content": "Clear the tmp_path factory cache between sessions",
            "failed_attempts": [
                "sk-ant-api03-real-looking-key-material was in my notes"
            ],
        },
    )
    assert response.status_code == 400
    assert "secret_detected" in response.json()["error"][
        "message"
    ] or "secret_detected" in (response.json().get("detail") or "")


def test_failed_attempts_without_inline_solution_rejected_not_dropped() -> None:
    """The no-silent-failure contract: dead ends without the solution they
    belong to must be rejected loudly, never 201'd into oblivion."""
    service, author_id = _service()
    problem = _seed_problem(service, author_id)
    with pytest.raises(ValueError, match="requires an inline solution"):
        service.contribute(
            author_id=author_id,
            description=problem.description,
            problem_id=problem.problem_id,
            solution_failed_attempts=["a dead end with no home"],
        )


# --- Confidence math untouched ----------------------------------------------


def test_confidence_math_ignores_failed_attempts() -> None:
    service, author_id = _service()
    p1 = _seed_problem(service, author_id)
    s_plain = service.create_solution(
        problem_id=p1.problem_id,
        author_id=author_id,
        content="Identical fix text so only provenance can differ at all.",
    )
    s_with = service.create_solution(
        problem_id=p1.problem_id,
        author_id=author_id,
        content="Second identical fix text so only provenance differs here.",
        failed_attempts=["a dead end worth recording"],
    )
    reporters = [_reporter(service) for _ in range(2)]
    for reporter in reporters:
        for solution in (s_plain, s_with):
            service.report_outcome(
                reporter_id=reporter,
                solution_id=solution.solution_id,
                success=True,
            )
    refreshed_plain = service._solutions.get(s_plain.solution_id)
    refreshed_with = service._solutions.get(s_with.solution_id)
    assert refreshed_plain.confidence == refreshed_with.confidence


# --- Audit regressions: trajectory propagation --------------------------------


def test_improve_inherits_parent_failed_attempts() -> None:
    """An improved child refines the fix but must not silently lose the
    parent's authored dead ends (audit finding 1)."""
    service, author_id = _service()
    problem = _seed_problem(service, author_id)
    base = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Clear the tmp_path factory cache between sessions",
        failed_attempts=list(FAILED_ATTEMPTS),
    )
    result = service.improve_solution(
        solution_id=base.solution_id,
        improved_content="An improved rewrite with a sharper repro sequence.",
        reasoning="tighter steps",
        author_id=author_id,
    )
    candidate = service._solutions.get(result["solution_id"])
    assert candidate is not None
    assert candidate.failed_attempts == FAILED_ATTEMPTS


def test_synthesis_merges_source_failed_attempts_deduped_and_capped() -> None:
    """A synthesized canonical carries the union of its sources' dead ends,
    deduplicated and capped (audit finding 2)."""
    service, author_id = _service()
    problem = _seed_problem(service, author_id)
    service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="First working approach with enough characters here.",
        failed_attempts=["dead end one", "dead end two"],
    )
    service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Second working approach with enough characters too.",
        failed_attempts=["dead end two", "dead end three"],
    )
    result = service.synthesize_solutions(problem.problem_id)
    assert result is not None
    canonical = service._solutions.get(result["canonical_solution_id"])
    assert canonical is not None
    assert canonical.failed_attempts == [
        "dead end one",
        "dead end two",
        "dead end three",
    ]


def test_timeline_solution_events_carry_failed_attempts() -> None:
    """The public timeline must not drop the negative trajectory on
    solution events (audit finding 3)."""
    service, author_id = _service()
    problem = _seed_problem(service, author_id)
    service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Clear the tmp_path factory cache between sessions",
        failed_attempts=list(FAILED_ATTEMPTS),
    )
    timeline = service.get_problem_timeline(problem.problem_id)
    events = [e for e in timeline["timeline"] if e["event_type"] == "solution_proposed"]
    assert events, "timeline must contain the proposed-solution event"
    assert events[0]["failed_attempts"] == FAILED_ATTEMPTS


def test_worker_review_gate_scans_failed_attempts(client_and_key) -> None:
    """A legacy/unreviewed row with a credential in failed_attempts must be
    rejected by the deterministic worker gate before model approval can
    publish it (audit finding 4)."""
    from backend.core.config import settings

    client, _ = client_and_key
    service: AgentbookService = client.app.dependency_overrides[get_service]()
    author = uuid4()
    service._agents.add(Agent(agent_id=author, api_key_hash="w", model_type="t"))
    problem = Problem(author_id=author, description="A parent problem for review")
    service._problems.add(problem)
    solution = Solution(
        problem_id=problem.problem_id,
        author_id=author,
        content="A valid pending solution body with sufficient detail.",
        failed_attempts=["my notes had sk-ant-api03-real-looking-key-material"],
    )
    solution.review_status = None
    service._solutions.add(solution)
    settings.worker_api_key = "worker-secret"
    try:
        reviewed = client.post(
            f"/v1/internal/worker/content/{solution.solution_id}/review",
            headers={"Authorization": "Bearer worker-secret"},
            json={"status": "approved", "reason": "genuine solution"},
        )
        assert reviewed.status_code == 200
        assert reviewed.json()["status"] == "rejected"
        assert reviewed.json()["reason"] == "secret_detected"
        assert service._solutions.get(solution.solution_id).review_status == "rejected"
    finally:
        settings.worker_api_key = None
