"""Verifies features/contribute-actionability-hint.feature.

A prose-only contribute is accepted (knowledge_created) but must carry an
actionability score + hint naming the missing structured-knowledge fields, so
the contributor is steered toward the shape that makes the next agent's recall
actually lift. A fully-structured contribute carries score 4 and no hint.
"""

from __future__ import annotations

from uuid import uuid4

from backend.domain.models import Agent


def _service():
    from backend.application.service import AgentbookService
    from backend.infrastructure.persistence.in_memory import (
        InMemoryAgentRepository,
        InMemoryOutcomeRepository,
        InMemoryProblemRepository,
        InMemoryResearchCycleRepository,
        InMemorySolutionRepository,
    )

    agents = InMemoryAgentRepository()
    author_id = uuid4()
    agents.add(
        Agent(api_key_hash="test-hash", model_type="test-model", agent_id=author_id)
    )
    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    return service, author_id


def test_prose_only_solution_is_nudged_to_add_structured_knowledge():
    service, author_id = _service()
    result = service.contribute(
        author_id=author_id,
        description="ModuleNotFoundError importing numpy in a Docker Alpine container",
        solution_content="Install numpy with apk dependencies first then pip install",
    )
    assert result["status"] == "knowledge_created"
    assert result["actionability"] < 4
    hint = result.get("actionability_hint", "")
    # Names the legs a weak agent needs to act on the fix.
    assert "steps" in hint.lower() or "root_cause" in hint.lower()


def test_fully_structured_solution_has_full_actionability_and_no_hint():
    service, author_id = _service()
    result = service.contribute(
        author_id=author_id,
        description="ModuleNotFoundError importing numpy in a Docker Alpine container",
        solution_content="Install numpy with apk dependencies first then pip install",
        solution_steps=["apk add build-base", "pip install numpy"],
        solution_root_cause_pattern="Alpine's musl lacks the C build deps numpy's wheels need",
        solution_localization_cues=["the Dockerfile FROM python:3.x-alpine line"],
        solution_verification=[
            {
                "command": "docker build .",
                "expected": "numpy imports",
                "buggy": "ModuleNotFoundError",
            }
        ],
    )
    assert result["status"] == "knowledge_created"
    assert result["actionability"] == 4
    assert not result.get("actionability_hint")


def test_solution_attached_to_existing_problem_is_also_nudged():
    service, author_id = _service()
    problem = service.create_problem(
        author_id=author_id,
        description="ModuleNotFoundError importing numpy in a Docker Alpine container",
    )
    problem.review_status = "approved"
    service._problems.update(problem)
    result = service.contribute(
        author_id=author_id,
        description="ModuleNotFoundError importing numpy in a Docker Alpine container",
        solution_content="Install numpy with apk dependencies first then pip install",
        problem_id=problem.problem_id,
    )
    assert result["status"] in ("knowledge_created", "solution_added")
    assert result["actionability"] < 4
    assert result.get("actionability_hint")
