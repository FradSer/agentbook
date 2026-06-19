"""best_solution selection breaks a confidence tie toward actionability.

At cold-start every solution sits at the 0.3 baseline, so selecting purely by
confidence would surface whichever solution was contributed first. A recalling
agent should instead get the most actionable answer — the one carrying the
transferable structured knowledge a weak model can act on.
"""

from __future__ import annotations

from uuid import uuid4

from backend.application.service import AgentbookService
from backend.domain.models import Agent
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)


def _service():
    agents = InMemoryAgentRepository()
    author = uuid4()
    agents.add(Agent(api_key_hash="h", model_type="test", agent_id=author))
    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    return service, author


def test_tie_breaks_toward_the_more_structured_solution():
    service, author = _service()
    problem = service.create_problem(
        author_id=author,
        description="Async pool raises Event loop is closed on shutdown teardown",
    )
    # Thin solution contributed FIRST — would win a pure-confidence max.
    thin = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author,
        content="Close the pool before the loop stops.",
    )
    # Richer solution with transferable structured knowledge, same 0.3 baseline.
    rich = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author,
        content="Bind the pool to the running loop and await close() before it ends.",
        steps=["create the pool inside the loop", "await pool.close() on shutdown"],
        root_cause_pattern="the pool outlived the event loop it was bound to",
        localization_cues=["lifespan shutdown handler"],
        verification=[{"command": "pytest -k pool", "expected": "pass"}],
    )
    assert thin.confidence == rich.confidence == 0.3

    best = service._pick_best_solution(problem.problem_id, full=True)
    assert best is not None
    assert best["solution_id"] == str(rich.solution_id)
    assert best["steps"] and best["root_cause_pattern"] and best["verification"]


def test_higher_confidence_still_wins_over_structure():
    # Confidence remains primary: a validated thin solution beats an unvalidated
    # rich one once outcomes exist.
    service, author = _service()
    problem = service.create_problem(
        author_id=author, description="SSL verify failed on outbound HTTPS in CI"
    )
    rich = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author,
        content="Point REQUESTS_CA_BUNDLE at the system trust store.",
        steps=["set REQUESTS_CA_BUNDLE"],
        root_cause_pattern="missing CA bundle",
        verification=[{"command": "curl https://x", "expected": "200"}],
    )
    thin = service.create_solution(
        problem_id=problem.problem_id,
        author_id=author,
        content="Update certifi.",
    )
    thin.confidence = 0.9
    service._solutions.update(thin)

    best = service._pick_best_solution(problem.problem_id, full=True)
    assert best["solution_id"] == str(thin.solution_id)
    assert best["solution_id"] != str(rich.solution_id)
