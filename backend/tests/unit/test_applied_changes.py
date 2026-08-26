"""Verifies features/applied-changes-telemetry.feature.

applied_changes on outcomes: the edit-distance signal ("changed step 3,
skipped step 5") captured with client cooperation. Storage, secret-gating,
size caps, takedown scrubbing, transport parity, confidence untouched —
mirroring the failed_attempts slice but scoped to outcomes.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from backend.application.service import AgentbookService
from backend.domain.models import Agent
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)

APPLIED = ["skipped step 5 entirely", "used uv instead of pip in step 3"]


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


def _seed_solution(service: AgentbookService, author_id: UUID) -> UUID:
    problem = service.create_problem(
        author_id=author_id,
        description="pytest fixture tempdir leaks files between test runs",
    )
    solution = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Clear the tmp_path factory cache between sessions",
    )
    return solution.solution_id


def _reporter(service: AgentbookService) -> UUID:
    return service.register_agent(model_type="test")[0].agent_id


def test_success_report_with_applied_changes_stored_and_inspected() -> None:
    service, author_id = _service()
    sid = _seed_solution(service, author_id)
    service.report_outcome(
        reporter_id=_reporter(service),
        solution_id=sid,
        success=True,
        applied_changes=list(APPLIED),
    )
    inspected = service.inspect_resource(sid)
    assert inspected["outcomes"][0]["applied_changes"] == APPLIED
    timeline = service.get_problem_timeline(UUID(str(inspected["data"]["problem_id"])))
    outcome_events = [
        e for e in timeline["timeline"] if e["event_type"] == "outcome_reported"
    ]
    assert outcome_events[0]["applied_changes"] == APPLIED


def test_applied_changes_default_to_empty() -> None:
    service, author_id = _service()
    sid = _seed_solution(service, author_id)
    service.report_outcome(
        reporter_id=_reporter(service), solution_id=sid, success=True
    )
    inspected = service.inspect_resource(sid)
    assert inspected["outcomes"][0]["applied_changes"] == []


def test_secret_in_applied_changes_rejected() -> None:
    service, author_id = _service()
    sid = _seed_solution(service, author_id)
    with pytest.raises(ValueError, match="secret"):
        service.report_outcome(
            reporter_id=_reporter(service),
            solution_id=sid,
            success=True,
            applied_changes=["swapped key to sk-ant-api03-real-looking-key-material"],
        )
    assert service._outcomes.list_by_solution(sid) == []


def test_oversized_applied_changes_rejected() -> None:
    service, author_id = _service()
    sid = _seed_solution(service, author_id)
    too_many = [f"change {i}" for i in range(11)]
    with pytest.raises(ValueError):
        service.report_outcome(
            reporter_id=_reporter(service),
            solution_id=sid,
            success=False,
            applied_changes=too_many,
        )
    with pytest.raises(ValueError):
        service.report_outcome(
            reporter_id=_reporter(service),
            solution_id=sid,
            success=False,
            applied_changes=["x" * 501],
        )


def test_takedown_scrubs_applied_changes() -> None:
    service, author_id = _service()
    sid = _seed_solution(service, author_id)
    service.report_outcome(
        reporter_id=_reporter(service),
        solution_id=sid,
        success=True,
        applied_changes=list(APPLIED),
    )
    service.takedown_solution(sid)
    for o in service._outcomes.list_by_solution(sid):
        assert o.applied_changes == []


def test_rest_request_model_accepts_applied_changes() -> None:
    from backend.presentation.api.schemas import OutcomeCreateRequest

    report = OutcomeCreateRequest(
        success=True,
        applied_changes=list(APPLIED),
    )
    assert report.applied_changes == APPLIED


def test_mcp_report_forwards_applied_changes() -> None:
    import asyncio
    import json

    from backend.presentation.mcp.tools import handle_report

    service, author_id = _service()
    sid = _seed_solution(service, author_id)
    payload_rows = asyncio.run(
        handle_report(
            service,
            author_id,
            {
                "solution_id": str(sid),
                "success": True,
                "applied_changes": list(APPLIED),
            },
        )
    )
    payload = json.loads(payload_rows[0]["text"])
    assert payload["status"] == "reported"
    inspected = service.inspect_resource(sid)
    assert inspected["outcomes"][0]["applied_changes"] == APPLIED


def test_confidence_math_ignores_applied_changes() -> None:
    service, author_id = _service()
    p = service.create_problem(
        author_id=author_id,
        description="Second fixture family for confidence parity checks",
    )
    s_plain = service.create_solution(
        problem_id=p.problem_id, author_id=author_id, content="Fix text one."
    )
    s_with = service.create_solution(
        problem_id=p.problem_id, author_id=author_id, content="Fix text two."
    )
    reporters = [_reporter(service) for _ in range(2)]
    for i, reporter in enumerate(reporters):
        service.report_outcome(
            reporter_id=reporter, solution_id=s_plain.solution_id, success=True
        )
        service.report_outcome(
            reporter_id=reporter,
            solution_id=s_with.solution_id,
            success=True,
            applied_changes=[f"tweak {i}"] if i == 0 else [],
        )
    plain = service._solutions.get(s_plain.solution_id)
    with_chg = service._solutions.get(s_with.solution_id)
    assert plain.confidence == with_chg.confidence
