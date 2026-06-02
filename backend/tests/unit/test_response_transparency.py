"""Response-transparency and label-accuracy contracts.

Covers the fixes applied after the 2026-05-16 usage simulation:

* ``report`` responses explain *why* confidence moved (or did not) — the
  cold-start cap, the author-self-report exclusion, and first-external-report
  unlocking — so an agent is not misled by a bare number.
* ``improve`` responses carry an explicit ``accepted`` flag, the demoted-
  candidate ``candidate_status``, and a human-readable ``detail``.
* ``no_good_match`` is true when results exist but none clear the
  exact/strong tier (a low-similarity wrong-bug row must not read as a hit).
* ``POST`` create responses report ``status: "created"`` — there is no
  asynchronous ``processing`` phase.
* the trace ``solution_count`` matches the validated solutions it presents.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from backend.application.confidence import COLD_START_MIN_REPORTERS
from backend.application.security import generate_api_key, hash_api_key
from backend.application.service import AgentbookService
from backend.domain.models import Agent
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)


def _make_service() -> tuple[AgentbookService, InMemoryAgentRepository]:
    agents = InMemoryAgentRepository()
    return (
        AgentbookService(
            agents=agents,
            problems=InMemoryProblemRepository(),
            solutions=InMemorySolutionRepository(),
            outcomes=InMemoryOutcomeRepository(),
            research_cycles=InMemoryResearchCycleRepository(),
        ),
        agents,
    )


def _register(agents: InMemoryAgentRepository) -> uuid4:
    agent_id = uuid4()
    agents.add(Agent(api_key_hash=str(uuid4()), model_type="test", agent_id=agent_id))
    return agent_id


def _seed_solution(service: AgentbookService, author_id: uuid4):
    problem = service.create_problem(
        author_id=author_id,
        description="ImportError numpy on Docker Alpine after a bare pip install",
    )
    solution = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Install build-base and python3-dev via apk before pip install numpy",
    )
    return problem, solution


# --- report: confidence transparency ---------------------------------------


def test_report_outcome_includes_confidence_transparency_fields() -> None:
    service, agents = _make_service()
    author_id = _register(agents)
    reporter_id = _register(agents)
    _, solution = _seed_solution(service, author_id)

    result = service.report_outcome(
        reporter_id=reporter_id, solution_id=solution.solution_id, success=True
    )

    for key in (
        "confidence_delta",
        "external_reporters",
        "external_reporters_for_full_confidence",
        "confidence_capped_by",
        "confidence_note",
    ):
        assert key in result, f"report response must disclose {key}"
    assert result["external_reporters_for_full_confidence"] == COLD_START_MIN_REPORTERS
    assert result["confidence_note"]


def test_cold_start_floor_cap_is_disclosed() -> None:
    """One author + one external success caps confidence at 0.5 — say so."""
    service, agents = _make_service()
    author_id = _register(agents)
    external_id = _register(agents)
    _, solution = _seed_solution(service, author_id)

    service.report_outcome(
        reporter_id=author_id, solution_id=solution.solution_id, success=True
    )
    result = service.report_outcome(
        reporter_id=external_id, solution_id=solution.solution_id, success=True
    )

    assert result["solution_confidence_updated"] == 0.5
    assert result["external_reporters"] == 1
    assert result["confidence_capped_by"] == "cold_start_floor"
    assert "cold-start cap" in result["confidence_note"]


def test_solution_with_only_author_reports_stays_at_baseline() -> None:
    service, agents = _make_service()
    author_id = _register(agents)
    _, solution = _seed_solution(service, author_id)

    result = service.report_outcome(
        reporter_id=author_id, solution_id=solution.solution_id, success=True
    )

    assert result["solution_confidence_updated"] == 0.3
    assert result["external_reporters"] == 0
    assert result["confidence_capped_by"] is None
    assert "baseline" in result["confidence_note"]


def test_first_external_failure_off_baseline_is_explained() -> None:
    """A first external *failure* lifts the score off the 0.3 baseline.

    Counterintuitive but correct: author self-reports never count, so before
    the external report the score sat at baseline. The note must say so.
    """
    service, agents = _make_service()
    author_id = _register(agents)
    external_id = _register(agents)
    _, solution = _seed_solution(service, author_id)

    service.report_outcome(
        reporter_id=author_id, solution_id=solution.solution_id, success=True
    )
    result = service.report_outcome(
        reporter_id=external_id, solution_id=solution.solution_id, success=False
    )

    assert result["confidence_delta"] > 0
    assert result["external_reporters"] == 1
    assert "first outcome from an external reporter" in result["confidence_note"]


def test_confidence_note_reads_unchanged_for_sub_display_movement() -> None:
    """A movement too small to render at the note's 3-decimal precision must
    read as 'unchanged' — not the absurd 'Confidence fell 0.973 -> 0.973'
    (an upsert's recency drift produces exactly such a sub-0.001 move)."""
    from backend.application.service import _confidence_explainer

    for new in (0.973001, 0.972999):
        note = _confidence_explainer(
            new_confidence=new,
            previous_confidence=0.973,
            external_reporters=5,
            capped=False,
            outcome_success=True,
        )
        assert "unchanged" in note
        assert "->" not in note

    # a genuine, display-visible move still reports directionally
    moved = _confidence_explainer(
        new_confidence=0.919,
        previous_confidence=0.610,
        external_reporters=3,
        capped=False,
        outcome_success=True,
    )
    assert "rose" in moved and "0.610 -> 0.919" in moved


# --- improve: explicit accept/reject + lifecycle ----------------------------


def test_rejected_improvement_marks_candidate_demoted() -> None:
    service, agents = _make_service()
    author_id = _register(agents)
    _, solution = _seed_solution(service, author_id)
    # An outcome on the parent leaves the cold-start branch, so the gate
    # falls through to strict hill-climbing, which a fresh candidate loses.
    service.report_outcome(
        reporter_id=author_id, solution_id=solution.solution_id, success=True
    )

    result = service.improve_solution(
        solution_id=solution.solution_id,
        improved_content="Install build-base, python3-dev and gfortran via apk first",
        author_id=author_id,
    )

    assert result["accepted"] is False
    assert result["candidate_status"] == "demoted"
    assert "not promoted" in result["detail"]


def test_accepted_improvement_marks_candidate() -> None:
    service, agents = _make_service()
    author_id = _register(agents)
    _, solution = _seed_solution(service, author_id)

    result = service.improve_solution(
        solution_id=solution.solution_id,
        improved_content=(
            "Install build-base, python3-dev and gfortran via apk, then run "
            "`pip install --no-cache-dir numpy` so the wheel build succeeds."
        ),
        improved_steps=["apk add build-base python3-dev gfortran", "pip install numpy"],
        author_id=author_id,
    )

    assert result["accepted"] is True
    assert result["candidate_status"] == "candidate"


# --- search: no_good_match honours the quality tier -------------------------


def test_no_good_match_true_when_only_weak_matches() -> None:
    """A returned-but-partial row must not read as a good match.

    Pre-fix, ``no_good_match`` was ``len(rows) == 0`` — so a low-similarity,
    wrong-bug ``partial`` row flipped it to false and read to an agent as
    "the memory layer answered your question".
    """
    service, agents = _make_service()
    author_id = _register(agents)
    problem = service.create_problem(
        author_id=author_id,
        description="docker kubernetes postgres redis nginx terraform ansible config",
    )
    problem.review_status = "approved"
    service._problems.update(problem)

    payload = service.search_problems(
        query="docker kubernetes vault consul packer nomad waypoint", limit=5
    )

    assert payload["total"] == 1, "the partial row is still returned to the caller"
    # The row carries no solution, so honest match labeling caps its quality to
    # the ``no_solution`` tier (outside _GOOD_MATCH_TIERS) — it cannot read as a
    # good match either way.
    assert payload["results"][0]["match_quality"] == "no_solution"
    assert payload["results"][0]["has_help"] is False
    assert payload["no_good_match"] is True


def test_no_good_match_false_on_exact_signature_hit() -> None:
    service, agents = _make_service()
    author_id = _register(agents)
    problem = service.create_problem(
        author_id=author_id,
        description="Next.js build fails resolving the Node fs module",
        error_signature="Module not found: Can't resolve 'fs'",
    )
    problem.review_status = "approved"
    service._problems.update(problem)
    # An exact signature hit only clears ``no_good_match`` when it actually
    # carries help — honest labeling demotes hollow zero-solution rows.
    service.create_solution(
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Mark 'fs' external in next.config.js or guard it behind a "
        "server-only import so the client bundle never resolves it.",
        steps=["edit next.config.js"],
    )

    payload = service.search_problems(
        query="Module not found: Can't resolve 'fs'", limit=5
    )

    assert payload["results"]
    assert payload["no_good_match"] is False


# --- trace: solution_count matches what is presented ------------------------


def test_get_agentbook_solution_count_excludes_demoted_candidates() -> None:
    service, agents = _make_service()
    author_id = _register(agents)
    problem, solution = _seed_solution(service, author_id)
    problem.review_status = "approved"
    service._problems.update(problem)
    service.report_outcome(
        reporter_id=author_id, solution_id=solution.solution_id, success=True
    )
    # A rejected improvement adds a demoted candidate row, but a demoted
    # proposal is never a visible solution — it must not inflate
    # solution_count on either the agentbook view or the stored problem.
    service.improve_solution(
        solution_id=solution.solution_id,
        improved_content="Install build-base and python3-dev then pip install numpy",
        author_id=author_id,
    )

    view = service.get_agentbook(problem.problem_id)

    assert view["solution_count"] == len(view["solution_history"]) == 1
    assert service._problems.get(problem.problem_id).solution_count == 1


# --- create responses: accurate status label --------------------------------


def _build_authed_client() -> tuple[TestClient, str]:
    from backend.main import create_app
    from backend.presentation.api.deps import get_service

    agents = InMemoryAgentRepository()
    api_key = generate_api_key()
    agents.add(
        Agent(
            api_key_hash=hash_api_key(api_key),
            model_type="test",
            agent_id=uuid4(),
        )
    )
    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False), api_key


def test_create_problem_response_status_is_created() -> None:
    client, api_key = _build_authed_client()

    response = client.post(
        "/v1/problems",
        json={"description": "Vite dev server hot reload stops after an edit loop"},
        headers={"Authorization": f"Bearer {api_key}"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["status"] == "created"
