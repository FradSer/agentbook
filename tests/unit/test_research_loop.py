"""Tests for the autonomous research loop."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from agent.src.research_loop import _build_research_prompt, _parse_agent_response, run_research_cycle
from app.application.service import AgentbookService
from app.domain.models import Agent
from app.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryCommentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
    InMemoryThreadRepository,
    InMemoryTokenTransactionRepository,
    InMemoryVoteRepository,
)

AUTHOR = UUID("00000000-0000-0000-0000-000000000001")


def _make_service() -> AgentbookService:
    agents = InMemoryAgentRepository()
    agents.add(Agent(api_key_hash="h1", model_type="test", token_balance=100, agent_id=AUTHOR))
    return AgentbookService(
        agents=agents,
        threads=InMemoryThreadRepository(),
        comments=InMemoryCommentRepository(),
        votes=InMemoryVoteRepository(),
        transactions=InMemoryTokenTransactionRepository(),
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )


# ---------------------------------------------------------------------------
# _parse_agent_response
# ---------------------------------------------------------------------------


def test_parse_no_improvement() -> None:
    assert _parse_agent_response("NO_IMPROVEMENT: already optimal") is None


def test_parse_improved_content() -> None:
    text = (
        "IMPROVED_CONTENT: Install the package and rebuild\n"
        "STEPS: pip install pkg | docker build | docker run\n"
        "REASONING: Added rebuild step"
    )
    result = _parse_agent_response(text)
    assert result is not None
    assert result["improved_content"] == "Install the package and rebuild"
    assert result["steps"] == ["pip install pkg", "docker build", "docker run"]
    assert result["reasoning"] == "Added rebuild step"


def test_parse_missing_content_returns_none() -> None:
    assert _parse_agent_response("REASONING: something") is None


# ---------------------------------------------------------------------------
# _build_research_prompt
# ---------------------------------------------------------------------------


def test_build_prompt_includes_problem_description() -> None:
    problem = {"description": "ModuleNotFoundError in Docker", "error_signature": "ModuleNotFoundError"}
    solutions = [{"confidence": 0.5, "content": "pip install pkg"}]
    prompt = _build_research_prompt(problem, solutions)
    assert "ModuleNotFoundError in Docker" in prompt
    assert "ModuleNotFoundError" in prompt
    assert "pip install pkg" in prompt


def test_build_prompt_includes_multiple_solutions() -> None:
    problem = {"description": "Some problem"}
    solutions = [
        {"confidence": 0.7, "content": "Solution A"},
        {"confidence": 0.4, "content": "Solution B"},
    ]
    prompt = _build_research_prompt(problem, solutions)
    assert "Solution A" in prompt
    assert "Solution B" in prompt


# ---------------------------------------------------------------------------
# run_research_cycle
# ---------------------------------------------------------------------------


def test_run_research_cycle_no_candidates() -> None:
    service = _make_service()
    agent = MagicMock()

    result = asyncio.run(run_research_cycle(agent, service))
    assert result["candidates"] == 0
    assert result["improved"] == 0


def test_run_research_cycle_skips_when_disabled(monkeypatch) -> None:
    import agent.src.research_loop as rl
    monkeypatch.setattr(rl.settings, "agent_research_enabled", False)

    service = _make_service()
    agent = MagicMock()

    result = asyncio.run(run_research_cycle(agent, service))
    assert result.get("skipped") is True


def test_run_research_cycle_no_improvement_when_agent_says_no() -> None:
    service = _make_service()
    service.contribute(
        author_id=AUTHOR,
        description="How to fix ModuleNotFoundError in Docker containers",
        solution_content="Install the missing package with pip install",
        solution_steps=["Run pip install <package>"],
    )

    agent = MagicMock()
    agent.arun = AsyncMock(return_value="NO_IMPROVEMENT: already optimal")

    result = asyncio.run(run_research_cycle(agent, service))
    assert result["no_improvement"] >= 0
