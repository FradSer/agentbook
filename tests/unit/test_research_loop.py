"""Tests for the autonomous research loop."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from agent.src.research_loop import _build_research_prompt, run_research_cycle
from app.application.service import AgentbookService
from app.domain.models import Agent, Problem
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
# _build_research_prompt
# ---------------------------------------------------------------------------


def test_build_prompt_includes_problem_description() -> None:
    problem = {"description": "ModuleNotFoundError in Docker", "error_signature": "ModuleNotFoundError", "problem_id": "abc"}
    solutions = [{"solution_id": "s1", "confidence": 0.5, "content": "pip install pkg"}]
    prompt = _build_research_prompt(problem, solutions)
    assert "ModuleNotFoundError in Docker" in prompt
    assert "ModuleNotFoundError" in prompt
    assert "pip install pkg" in prompt


def test_build_prompt_includes_multiple_solutions() -> None:
    problem = {"description": "Some problem", "problem_id": "abc"}
    solutions = [
        {"solution_id": "s1", "confidence": 0.7, "content": "Solution A"},
        {"solution_id": "s2", "confidence": 0.4, "content": "Solution B"},
    ]
    prompt = _build_research_prompt(problem, solutions)
    assert "Solution A" in prompt
    assert "Solution B" in prompt


def test_build_prompt_includes_outcome_data() -> None:
    problem = {"description": "Some problem", "problem_id": "abc"}
    solutions = [{"solution_id": "s1", "confidence": 0.5, "content": "pip install pkg"}]
    outcomes_by_solution = {
        "s1": [
            {"success": True, "environment": {"os": "ubuntu"}, "notes": None},
            {"success": True, "environment": {"os": "alpine"}, "notes": None},
            {"success": False, "environment": {"os": "windows"}, "notes": "pip not found on PATH"},
        ]
    }
    prompt = _build_research_prompt(problem, solutions, outcomes_by_solution)
    assert "2 success" in prompt
    assert "1 failure" in prompt
    assert "pip not found on PATH" in prompt


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
    agent.arun = AsyncMock(return_value="Status: no_improvement. Reason: already optimal")

    result = asyncio.run(run_research_cycle(agent, service))
    assert result["no_improvement"] >= 1


def test_run_research_cycle_no_tool_call_logs_warning(caplog) -> None:
    """Agent returns prose without calling a tool — logged as warning, counted as no_improvement."""
    import logging
    service = _make_service()
    service.contribute(
        author_id=AUTHOR,
        description="How to fix ModuleNotFoundError in Docker containers",
        solution_content="Install the missing package with pip install",
        solution_steps=["Run pip install <package>"],
    )

    agent = MagicMock()
    agent.arun = AsyncMock(return_value="I think the solution is already optimal.")

    with caplog.at_level(logging.WARNING, logger="agent.src.research_loop"):
        result = asyncio.run(run_research_cycle(agent, service))

    assert result["no_improvement"] >= 1
    assert any("no recognisable tool call" in r.message for r in caplog.records)


def test_run_research_cycle_improved_when_agent_calls_propose() -> None:
    """Agent calls propose_improvement tool; verify solution persisted in repo."""
    from agent.src.tools import get_researcher_tools

    service = _make_service()
    contribute_result = service.contribute(
        author_id=AUTHOR,
        description="How to fix ModuleNotFoundError in Docker containers",
        solution_content="Install the missing package with pip install",
        solution_steps=["Run pip install <package>"],
    )
    problem_id = str(contribute_result["problem_id"])
    solution_id = str(contribute_result["solution_id"])

    # Use real tool so the service.improve_solution call actually happens
    tools = get_researcher_tools(service)
    propose_tool = next(t for t in tools if t.name == "propose_improvement")

    async def fake_arun(prompt: str) -> str:
        return propose_tool.entrypoint(
            solution_id=solution_id,
            improved_content="Install the missing package with pip install and verify import works",
            reasoning="Added verification step",
            steps=["Run pip install <package>", "Verify with python -c 'import pkg'"],
        )

    agent = MagicMock()
    agent.arun = fake_arun

    result = asyncio.run(run_research_cycle(agent, service))
    assert result["improved"] >= 1

    # Verify a new solution was actually persisted in the repo
    context = service.get_context(id=UUID(problem_id), include=["solutions"])
    assert len(context["solutions"]) >= 2


# ---------------------------------------------------------------------------
# Cooldown
# ---------------------------------------------------------------------------


def test_find_research_candidates_cooldown_skips_recently_researched() -> None:
    from agent.src.synthesis import SYSTEM_AGENT_ID

    service = _make_service()
    result = service.contribute(
        author_id=AUTHOR,
        description="How to fix ImportError when using Docker containers in CI",
        solution_content="Install the missing package with pip install",
        solution_steps=["Run pip install <package>"],
    )
    problem_id = result["problem_id"]
    solution_id = UUID(str(result["solution_id"]))

    # Record a research cycle via the service (improve_solution creates a ResearchCycle internally)
    service.improve_solution(
        author_id=SYSTEM_AGENT_ID,
        solution_id=solution_id,
        improved_content="Install the missing package with pip install and verify import works",
        improved_steps=["Run pip install <package>", "Verify with python -c 'import pkg'"],
        reasoning="Test cycle",
        author_verified=True,
    )

    # With cooldown_hours=6, recently researched problem should be excluded
    candidates = service.find_research_candidates(limit=10, cooldown_hours=6)
    candidate_ids = [c["problem_id"] for c in candidates]
    assert str(problem_id) not in candidate_ids


# ---------------------------------------------------------------------------
# Cold-start bootstrapping
# ---------------------------------------------------------------------------


def test_cold_start_improvement_succeeds() -> None:
    """Researcher with author_verified=True produces 0.5 baseline that beats 0.3."""
    from agent.src.synthesis import SYSTEM_AGENT_ID

    service = _make_service()
    result = service.contribute(
        author_id=AUTHOR,
        description="Cold start test problem with enough detail to pass quality gate",
        solution_content="Basic solution that needs improvement for this test",
        solution_steps=["Step one"],
    )
    solution_id = UUID(str(result["solution_id"]))

    existing = service._solutions.get(solution_id)
    assert existing is not None
    assert existing.confidence == pytest.approx(0.3)

    improve_result = service.improve_solution(
        author_id=SYSTEM_AGENT_ID,
        solution_id=solution_id,
        improved_content="Improved solution: install package with verification step",
        improved_steps=["Run pip install <package>", "Verify with python -c 'import pkg'"],
        reasoning="Added verification step",
        author_verified=True,
    )
    assert improve_result["status"] == "improved"
    assert improve_result["new_confidence"] == pytest.approx(0.5)
    # previous_confidence now reports the incumbent solution's confidence, not the problem best
    assert improve_result["previous_confidence"] == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Bloat filter
# ---------------------------------------------------------------------------


def test_bloat_filter_rejects_verbose_without_gain() -> None:
    """2x length with <=0.05 confidence gain is rejected."""
    from agent.src.synthesis import SYSTEM_AGENT_ID

    service = _make_service()
    result = service.contribute(
        author_id=AUTHOR,
        description="Bloat filter test problem with sufficient description length",
        solution_content="Short solution content here",
        solution_steps=["Step one"],
        author_verified=True,  # gives 0.5 confidence
    )
    solution_id = UUID(str(result["solution_id"]))

    existing = service._solutions.get(solution_id)
    assert existing is not None
    assert existing.confidence == pytest.approx(0.5)

    bloated = "Short solution content here " * 10
    improve_result = service.improve_solution(
        author_id=SYSTEM_AGENT_ID,
        solution_id=solution_id,
        improved_content=bloated,
        reasoning="Verbose but no real gain",
        author_verified=True,  # same 0.5 baseline -> not > existing 0.5
    )
    assert improve_result["status"] == "no_improvement"


def test_bloat_filter_allows_verbose_with_significant_gain() -> None:
    """2x length is allowed when confidence gain > 0.05."""
    from agent.src.synthesis import SYSTEM_AGENT_ID

    service = _make_service()
    result = service.contribute(
        author_id=AUTHOR,
        description="Bloat allow test problem with sufficient description",
        solution_content="Short solution content here",
        solution_steps=["Step one"],
        # NOT author_verified -> confidence=0.3
    )
    solution_id = UUID(str(result["solution_id"]))

    existing = service._solutions.get(solution_id)
    assert existing is not None
    assert existing.confidence == pytest.approx(0.3)

    # 0.5 > 0.3 + 0.05 = 0.35, so gain 0.2 exceeds threshold
    bloated = "Short solution content here " * 10
    improve_result = service.improve_solution(
        author_id=SYSTEM_AGENT_ID,
        solution_id=solution_id,
        improved_content=bloated,
        reasoning="Verbose but significant gain",
        author_verified=True,
    )
    assert improve_result["status"] == "improved"


# ---------------------------------------------------------------------------
# synthesize_solutions service method
# ---------------------------------------------------------------------------


def test_synthesize_solutions_service_method() -> None:
    from agent.src.synthesis import SYSTEM_AGENT_ID
    from app.domain.models import Solution

    service = _make_service()
    p_result = service.contribute(
        author_id=AUTHOR,
        description="Synthesis test problem with enough content to pass quality gate",
        solution_content="First solution approach for synthesis testing",
        solution_steps=["Step A"],
    )
    problem_id = UUID(str(p_result["problem_id"]))

    second = Solution(
        problem_id=problem_id,
        author_id=AUTHOR,
        content="Second solution approach for synthesis testing",
        steps=["Step B"],
    )
    service._solutions.add(second)

    result = service.synthesize_solutions(
        problem_id=problem_id,
        synthesized_content="Canonical synthesis of both approaches for testing",
        author_id=SYSTEM_AGENT_ID,
    )
    assert result is not None
    assert result["synthesized_from"] >= 2
    assert "canonical_solution_id" in result


def test_synthesize_solutions_returns_none_for_single_solution() -> None:
    from agent.src.synthesis import SYSTEM_AGENT_ID

    service = _make_service()
    p_result = service.contribute(
        author_id=AUTHOR,
        description="Single solution synthesis test with enough description",
        solution_content="Only solution here for synthesis test",
        solution_steps=["Step A"],
    )
    problem_id = UUID(str(p_result["problem_id"]))

    result = service.synthesize_solutions(
        problem_id=problem_id,
        synthesized_content="Canonical content",
        author_id=SYSTEM_AGENT_ID,
    )
    assert result is None


# ---------------------------------------------------------------------------
# Exception path in run_research_cycle
# ---------------------------------------------------------------------------


def test_run_research_cycle_context_fetch_error_skips_problem(caplog) -> None:
    """If get_context raises, the problem is skipped with a warning and counted as no_improvement."""
    import logging
    from unittest.mock import patch

    service = _make_service()
    service.contribute(
        author_id=AUTHOR,
        description="Context fetch error test problem with sufficient description",
        solution_content="Basic solution for error test",
        solution_steps=["Step one"],
    )

    agent = MagicMock()

    with patch.object(service, "get_context", side_effect=RuntimeError("db down")):
        with caplog.at_level(logging.WARNING, logger="agent.src.research_loop"):
            result = asyncio.run(run_research_cycle(agent, service))

    assert result["candidates"] >= 1
    assert result["improved"] == 0
    assert any("Failed to get context" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# _maybe_synthesize via run_research_cycle (end-to-end path)
# ---------------------------------------------------------------------------


def test_maybe_synthesize_triggered_on_improvement() -> None:
    """Synthesis runs without error when ≥10 active solutions exist after improvement."""
    from agent.src.synthesis import SYSTEM_AGENT_ID
    from agent.src.tools import get_researcher_tools
    from app.domain.models import Solution

    service = _make_service()
    contribute_result = service.contribute(
        author_id=AUTHOR,
        description="Synthesis trigger test problem with enough description",
        solution_content="Base solution for synthesis trigger test",
        solution_steps=["Step A"],
    )
    problem_id = UUID(str(contribute_result["problem_id"]))
    solution_id = str(contribute_result["solution_id"])

    # Add 9 more solutions to reach the ≥10 threshold
    for i in range(9):
        service._solutions.add(Solution(
            problem_id=problem_id,
            author_id=AUTHOR,
            content=f"Alternative solution approach {i} for synthesis trigger test",
        ))

    tools = get_researcher_tools(service)
    propose_tool = next(t for t in tools if t.name == "propose_improvement")

    async def fake_arun(prompt: str) -> str:
        if "synthesize" in prompt.lower():
            return "Canonical synthesized solution content that is detailed enough"
        return propose_tool.entrypoint(
            solution_id=solution_id,
            improved_content="Install the missing package with pip install and verify import works",
            reasoning="Added verification step",
            steps=["Run pip install <package>", "Verify with python -c 'import pkg'"],
        )

    agent = MagicMock()
    agent.arun = fake_arun

    result = asyncio.run(run_research_cycle(agent, service))
    assert result["improved"] >= 1

    # Verify canonical solution was created
    context = service.get_context(id=problem_id, include=["solutions"])
    solutions = context["solutions"]
    canonical_solutions = [s for s in solutions if s.get("canonical_id") is None and s.get("author_verified")]
    assert len(canonical_solutions) >= 1


# ---------------------------------------------------------------------------
# Tool: skip_improvement
# ---------------------------------------------------------------------------


def test_skip_improvement_returns_status() -> None:
    from agent.src.tools import get_researcher_tools

    service = _make_service()
    tools = get_researcher_tools(service)
    skip_tool = next(t for t in tools if t.name == "skip_improvement")
    result = skip_tool.entrypoint(problem_id="abc", reason="already optimal")
    assert "Status: no_improvement" in result


# ---------------------------------------------------------------------------
# Tool: propose_improvement passes author_verified=True
# ---------------------------------------------------------------------------


def test_propose_improvement_passes_author_verified() -> None:
    from agent.src.tools import get_researcher_tools

    service = _make_service()
    p_result = service.contribute(
        author_id=AUTHOR,
        description="Tool test problem with enough description text",
        solution_content="Basic solution for tool test",
        solution_steps=["Step one"],
    )
    solution_id = str(p_result["solution_id"])

    tools = get_researcher_tools(service)
    propose_tool = next(t for t in tools if t.name == "propose_improvement")
    result = propose_tool.entrypoint(
        solution_id=solution_id,
        improved_content="Better solution with verification for tool test",
        reasoning="Improved with author_verified=True",
        steps=["Step one", "Step two: verify"],
    )
    # author_verified=True gives 0.5 > 0.3 -> should be improved
    assert "Status: improved" in result


# ---------------------------------------------------------------------------
# Bug 1: skip_improvement records ResearchCycle for cooldown
# ---------------------------------------------------------------------------


def test_skip_improvement_records_research_cycle() -> None:
    """skip_improvement must persist a ResearchCycle so cooldown filtering works."""
    from agent.src.tools import get_researcher_tools

    service = _make_service()
    p_result = service.contribute(
        author_id=AUTHOR,
        description="Skip improvement cooldown test problem with enough detail",
        solution_content="Basic solution for skip test",
        solution_steps=["Step one"],
    )
    problem_id = str(p_result["problem_id"])

    tools = get_researcher_tools(service)
    skip_tool = next(t for t in tools if t.name == "skip_improvement")
    result = skip_tool.entrypoint(problem_id=problem_id, reason="already optimal")

    assert "Status: no_improvement" in result

    # Verify a ResearchCycle was recorded
    cycles = service.get_research_history(UUID(problem_id))
    assert len(cycles) == 1
    assert cycles[0]["status"] == "no_improvement"


def test_skip_improvement_excludes_problem_within_cooldown() -> None:
    """After skip_improvement, problem must be excluded from research candidates within cooldown."""
    from agent.src.tools import get_researcher_tools

    service = _make_service()
    p_result = service.contribute(
        author_id=AUTHOR,
        description="Cooldown exclusion test problem with sufficient description",
        solution_content="Basic solution for cooldown test",
        solution_steps=["Step one"],
    )
    problem_id = str(p_result["problem_id"])

    tools = get_researcher_tools(service)
    skip_tool = next(t for t in tools if t.name == "skip_improvement")
    skip_tool.entrypoint(problem_id=problem_id, reason="already optimal")

    candidates = service.find_research_candidates(limit=10, cooldown_hours=6)
    candidate_ids = [c["problem_id"] for c in candidates]
    assert problem_id not in candidate_ids


# ---------------------------------------------------------------------------
# Bug 2: solution_count increments on accepted improvement even when not new best
# ---------------------------------------------------------------------------


def test_solution_count_increments_when_improvement_beats_incumbent_not_best() -> None:
    """solution_count must increment whenever a new solution is accepted, not only when it sets a new best."""
    from agent.src.synthesis import SYSTEM_AGENT_ID
    from app.domain.models import Solution

    service = _make_service()
    p_result = service.contribute(
        author_id=AUTHOR,
        description="Solution count increment test with sufficient description",
        solution_content="Base solution for count increment test",
        solution_steps=["Step one"],
        author_verified=True,  # confidence=0.5
    )
    problem_id = UUID(str(p_result["problem_id"]))
    solution_id = UUID(str(p_result["solution_id"]))

    # Add a second solution with high confidence to set problem.best_confidence=0.8
    high_conf = Solution(
        problem_id=problem_id,
        author_id=AUTHOR,
        content="High confidence solution for increment test",
        steps=["A", "B"],
        author_verified=True,
    )
    high_conf.confidence = 0.8
    service._solutions.add(high_conf)
    problem = service._problems.get(problem_id)
    problem.best_confidence = 0.8
    problem.solution_count = 2
    service._problems.update(problem)

    # Now improve the first solution (0.5 -> 0.5 with author_verified, but we need > existing.confidence)
    # To beat incumbent (0.5) without beating best (0.8), manually set existing confidence to 0.3
    existing = service._solutions.get(solution_id)
    existing.confidence = 0.3
    service._solutions.update(existing)

    improve_result = service.improve_solution(
        author_id=SYSTEM_AGENT_ID,
        solution_id=solution_id,
        improved_content="Improved solution for count increment test with more detail",
        improved_steps=["Step one", "Step two"],
        reasoning="Beats incumbent but not problem best",
        author_verified=True,  # 0.5 > 0.3 (incumbent) but < 0.8 (best)
    )
    assert improve_result["status"] == "improved"
    assert improve_result["new_confidence"] == pytest.approx(0.5)

    updated_problem = service._problems.get(problem_id)
    assert updated_problem.solution_count == 3  # was 2, must be 3
    assert updated_problem.best_confidence == pytest.approx(0.8)  # unchanged


# ---------------------------------------------------------------------------
# Bug 3: cooldown filtering returns full requested count via pagination
# ---------------------------------------------------------------------------


def test_maybe_synthesize_triggered_by_low_confidence_and_outcomes() -> None:
    """Synthesis triggers when a solution has confidence < 0.3 and outcome_count >= 10."""
    from agent.src.synthesis import SYSTEM_AGENT_ID
    from agent.src.tools import get_researcher_tools
    from app.domain.models import Outcome, Solution

    service = _make_service()
    contribute_result = service.contribute(
        author_id=AUTHOR,
        description="Low confidence synthesis trigger test with enough description",
        solution_content="Base solution for low-confidence synthesis test",
        solution_steps=["Step A"],
    )
    problem_id = UUID(str(contribute_result["problem_id"]))
    solution_id = str(contribute_result["solution_id"])

    # Add a second solution so synthesize_solutions has >= 2 to work with
    service._solutions.add(Solution(
        problem_id=problem_id,
        author_id=AUTHOR,
        content="Second solution for low-confidence synthesis test",
    ))

    # Manually push confidence below 0.3 and add 10 failure outcomes to trigger the path
    sol = service._solutions.get(UUID(solution_id))
    sol.confidence = 0.2
    service._solutions.update(sol)
    for _ in range(10):
        service._outcomes.add(Outcome(solution_id=UUID(solution_id), reporter_id=AUTHOR, success=False))

    # Refresh in-memory solution_count so _maybe_synthesize can see outcome_count
    # The in-memory repo derives outcome_count from the outcomes list
    tools = get_researcher_tools(service)
    propose_tool = next(t for t in tools if t.name == "propose_improvement")

    async def fake_arun(prompt: str) -> str:
        if "synthesize" in prompt.lower():
            return "Canonical synthesized solution for low-confidence trigger test"
        return propose_tool.entrypoint(
            solution_id=solution_id,
            improved_content="Improved solution for low-confidence synthesis trigger test",
            reasoning="Triggered by low confidence + outcomes",
            steps=["Step A", "Step B: verify"],
        )

    agent = MagicMock()
    agent.arun = fake_arun

    result = asyncio.run(run_research_cycle(agent, service))
    assert result["improved"] >= 1

    # Verify canonical solution was created
    context = service.get_context(id=problem_id, include=["solutions"])
    solutions = context["solutions"]
    canonical_solutions = [s for s in solutions if s.get("canonical_id") is None and s.get("author_verified")]
    assert len(canonical_solutions) >= 1


# ---------------------------------------------------------------------------
# Fix 1: Per-candidate timeout
# ---------------------------------------------------------------------------


def test_per_candidate_timeout_counts_as_no_improvement(monkeypatch) -> None:
    """A hung LLM call times out and is counted as no_improvement, not a crash."""
    import agent.src.research_loop as rl

    monkeypatch.setattr(rl.settings, "agent_research_per_candidate_timeout_seconds", 0.01)

    service = _make_service()
    service.contribute(
        author_id=AUTHOR,
        description="Timeout test problem with enough description text here",
        solution_content="Basic solution for timeout test",
        solution_steps=["Step one"],
    )

    async def hang(_prompt: str) -> str:
        await asyncio.sleep(10)
        return "never"

    agent = MagicMock()
    agent.arun = hang

    result = asyncio.run(run_research_cycle(agent, service))
    assert result["no_improvement"] >= 1
    assert result["improved"] == 0


# ---------------------------------------------------------------------------
# Fix 2: Load instructions from program.md
# ---------------------------------------------------------------------------


def test_researcher_instructions_loaded_from_file(tmp_path) -> None:
    """_load_instructions() reads from program.md when it exists."""
    from unittest.mock import patch

    from agent.src.researcher_agent import _load_instructions

    custom_md = tmp_path / "program.md"
    custom_md.write_text("Custom instructions from file")

    import agent.src.config as cfg
    with patch.object(cfg.settings, "agent_researcher_instructions_path", str(custom_md)):
        result = _load_instructions()

    assert result == "Custom instructions from file"


def test_researcher_instructions_fallback_when_file_missing(tmp_path) -> None:
    """_load_instructions() falls back to the inline constant when file is absent."""
    from unittest.mock import patch

    from agent.src.researcher_agent import _RESEARCHER_INSTRUCTIONS_FALLBACK, _load_instructions

    import agent.src.config as cfg
    missing = str(tmp_path / "nonexistent.md")
    with patch.object(cfg.settings, "agent_researcher_instructions_path", missing):
        result = _load_instructions()

    assert result == _RESEARCHER_INSTRUCTIONS_FALLBACK


# ---------------------------------------------------------------------------
# Fix 3: Cold-start note in prompt
# ---------------------------------------------------------------------------


def test_build_prompt_cold_start_note_when_no_outcomes() -> None:
    """Cold-start NOTE appears in prompt when outcomes_by_solution is empty."""
    problem = {"description": "Cold start problem", "problem_id": "abc"}
    solutions = [{"solution_id": "s1", "confidence": 0.3, "content": "basic solution"}]

    prompt = _build_research_prompt(problem, solutions, outcomes_by_solution={})
    assert "cold-start" in prompt.lower()


def test_build_prompt_no_cold_start_note_when_outcomes_present() -> None:
    """Cold-start NOTE is absent when outcome data exists."""
    problem = {"description": "Problem with outcomes", "problem_id": "abc"}
    solutions = [{"solution_id": "s1", "confidence": 0.7, "content": "good solution"}]
    outcomes_by_solution = {
        "s1": [{"success": True, "environment": None, "notes": None}]
    }

    prompt = _build_research_prompt(problem, solutions, outcomes_by_solution)
    assert "cold-start" not in prompt.lower()


def test_find_research_candidates_pagination_returns_full_limit() -> None:
    """When many candidates are in cooldown, pagination must fill the requested limit."""
    from agent.src.synthesis import SYSTEM_AGENT_ID
    from app.domain.models import Problem

    service = _make_service()

    # Create 20 problems
    problem_ids = []
    for i in range(20):
        p = Problem(author_id=AUTHOR, description=f"Problem {i} with enough description for research", best_confidence=0.2)
        service._problems.add(p)
        problem_ids.append(p.problem_id)

    # Record a research cycle for the first 15 problems (put them in cooldown)
    for pid in problem_ids[:15]:
        service.record_research_skip(
            problem_id=pid,
            researcher_id=SYSTEM_AGENT_ID,
            reasoning="pre-researched",
        )

    # With cooldown, only 5 should be available; we ask for 5
    candidates = service.find_research_candidates(limit=5, cooldown_hours=6)
    assert len(candidates) == 5
