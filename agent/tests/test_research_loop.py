"""End-to-end tests for the autonomous research loop (run_research_cycle).

Validates the autoresearch (karpathy/autoresearch hill-climbing) pattern with:
- 3 real iterations (service-level and full cycle-level)
- External feedback (report_outcome from distinct reporters) between each iteration
- Superseded-solution filtering in _build_research_prompt
- Cold-start → bad outcomes → second improvement → more bad outcomes → third improvement
"""
from __future__ import annotations

import asyncio
import re
from uuid import UUID, uuid4

import pytest

from app.domain.models import Agent


def _make_service():
    from app.application.service import AgentbookService
    from app.infrastructure.persistence.in_memory import (
        InMemoryAgentRepository,
        InMemoryOutcomeRepository,
        InMemoryProblemRepository,
        InMemoryResearchCycleRepository,
        InMemorySolutionRepository,
        InMemoryTokenTransactionRepository,
    )

    agents = InMemoryAgentRepository()
    author_id = uuid4()
    agents.add(Agent(api_key_hash="test-hash", model_type="test", token_balance=100, agent_id=author_id))

    service = AgentbookService(
        agents=agents,
        transactions=InMemoryTokenTransactionRepository(),
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    return service, author_id


def _add_external_reporter(service) -> UUID:
    reporter_id = uuid4()
    service._agents.add(Agent(api_key_hash=f"ext-{reporter_id}", model_type="ext", token_balance=100, agent_id=reporter_id))
    return reporter_id


def _setup_problem_with_solution(service, author_id, confidence: float = 0.25):
    p = service.create_problem(
        author_id=author_id,
        description="ModuleNotFoundError importing numpy in Docker Alpine container setup environment",
    )
    p.review_status = "approved"
    service._problems.update(p)
    s = service.create_solution(
        problem_id=p.problem_id,
        author_id=author_id,
        content="Install numpy with apk add musl-dev gcc then pip install numpy in Docker Alpine container",
    )
    s.review_status = "approved"
    s.confidence = confidence
    service._solutions.update(s)
    return p, s


# ---------------------------------------------------------------------------
# Service-level: 2 direct iterations
# ---------------------------------------------------------------------------

def test_iteration_1_cold_start_improvement():
    """Iteration 1: baseline below cold-start default (0.25 → 0.3) → accepted."""
    service, author_id = _make_service()
    p, s1 = _setup_problem_with_solution(service, author_id, confidence=0.25)

    result = service.improve_solution(
        solution_id=s1.solution_id,
        improved_content=(
            "Install numpy: apk add musl-dev gcc python3-dev then pip install numpy --no-cache-dir "
            "inside Alpine Docker container to resolve ModuleNotFoundError"
        ),
        reasoning="Iteration 1: added python3-dev and --no-cache-dir flag",
    )
    assert result["status"] == "improved"
    assert result["new_confidence"] > result["previous_confidence"]


def test_iteration_2_after_bad_outcomes():
    """Iteration 2: bad outcomes degrade confidence → second proposal accepted again.

    This validates the core autoresearch keep/discard loop:
    - Iteration 1: cold-start improvement (strictly higher confidence)
    - Real outcomes: 5 external failures degrade confidence well below 0.5
    - Iteration 2: degraded solution → new proposal accepted
    """
    service, author_id = _make_service()
    p, s1 = _setup_problem_with_solution(service, author_id, confidence=0.25)

    # Iteration 1
    result1 = service.improve_solution(
        solution_id=s1.solution_id,
        improved_content=(
            "Install numpy: apk add musl-dev gcc python3-dev then pip install numpy --no-cache-dir "
            "inside Alpine Docker container"
        ),
        reasoning="Iteration 1: first improvement",
    )
    assert result1["status"] == "improved"
    s2_id = result1["solution_id"]

    # Simulate bad outcomes from external reporter (confidence degrades well below 0.5)
    reporter = _add_external_reporter(service)
    for _ in range(5):
        service.report_outcome(
            reporter_id=reporter,
            solution_id=s2_id,
            success=False,
            notes="This approach fails on Alpine 3.18 with newer musl-libc",
        )

    s2 = service._solutions.get(s2_id)
    assert s2.confidence < 0.5, (
        f"Expected confidence to degrade below 0.5 after 5 failures, got {s2.confidence:.3f}"
    )

    # Iteration 2: degrade → propose different approach → accepted
    result2 = service.improve_solution(
        solution_id=s2_id,
        improved_content=(
            "Install numpy on Alpine: use a pre-built wheel from piwheels. "
            "Run: pip install --index-url https://piwheels.org/simple/ numpy "
            "This avoids compiling from source entirely and resolves the musl-libc issue."
        ),
        reasoning="Iteration 2: switch to pre-built wheel after compile failures",
    )
    assert result2["status"] == "improved", (
        f"Iteration 2 should be accepted since s2.confidence ({s2.confidence:.3f}) < 0.5. "
        f"Got: {result2}"
    )


def test_two_iterations_produce_correct_lineage():
    """After 2 improvements, solution lineage should be 3 nodes deep: s1 → s2 → s3."""
    service, author_id = _make_service()
    p, s1 = _setup_problem_with_solution(service, author_id, confidence=0.25)

    result1 = service.improve_solution(
        solution_id=s1.solution_id,
        improved_content=(
            "Alpine numpy fix v2: musl-dev gcc python3-dev pip install numpy --no-cache-dir "
            "in Docker container with verified environment setup"
        ),
        reasoning="Iteration 1",
    )
    assert result1["status"] == "improved"
    s2_id = result1["solution_id"]

    reporter = _add_external_reporter(service)
    for _ in range(5):
        service.report_outcome(reporter_id=reporter, solution_id=s2_id, success=False)

    result2 = service.improve_solution(
        solution_id=s2_id,
        improved_content=(
            "Alpine numpy fix v3: use pre-built piwheels wheel to avoid musl compile failures. "
            "Install: pip install --index-url https://piwheels.org/simple/ numpy in container."
        ),
        reasoning="Iteration 2: completely different strategy",
    )
    assert result2["status"] == "improved"
    s3_id = result2["solution_id"]

    lineage = service.get_solution_lineage(s3_id)
    ids_in_lineage = [str(node["solution_id"]) for node in lineage]
    assert str(s1.solution_id) in ids_in_lineage
    assert str(s2_id) in ids_in_lineage
    assert str(s3_id) in ids_in_lineage
    assert len(lineage) == 3


def test_good_outcomes_block_second_iteration():
    """After GOOD outcomes push confidence above 0.5, second iteration correctly returns no_improvement."""
    service, author_id = _make_service()
    p, s1 = _setup_problem_with_solution(service, author_id, confidence=0.25)

    result1 = service.improve_solution(
        solution_id=s1.solution_id,
        improved_content=(
            "Alpine numpy fix: apk add musl-dev gcc python3-dev pip install numpy --no-cache-dir "
            "verified on Alpine 3.17 and 3.18 environments in Docker"
        ),
        reasoning="Iteration 1",
    )
    assert result1["status"] == "improved"
    s2_id = result1["solution_id"]

    # 5 external successes push confidence above 0.5
    reporter = _add_external_reporter(service)
    for _ in range(5):
        service.report_outcome(reporter_id=reporter, solution_id=s2_id, success=True)

    s2 = service._solutions.get(s2_id)
    assert s2.confidence > 0.5, (
        f"Expected confidence above 0.5 after 5 successes, got {s2.confidence:.3f}"
    )

    # Iteration 2: cold-start proposal (0.3) cannot beat outcome-validated solution (>0.5)
    result2 = service.improve_solution(
        solution_id=s2_id,
        improved_content=(
            "Alpine numpy fix alternative: use conda-forge channel instead "
            "of compiling from source in Docker Alpine container environment"
        ),
        reasoning="Iteration 2: try conda approach",
    )
    assert result2["status"] == "no_improvement", (
        "Should not replace a well-validated solution with an unproven one at cold-start"
    )


# ---------------------------------------------------------------------------
# run_research_cycle integration: mock agent calls real tools
# ---------------------------------------------------------------------------

class _ToolCallingAgent:
    """Mock agent that inspects the prompt and directly invokes the propose/skip tool."""

    def __init__(self, tools: list, always_improve: bool = True):
        self._tools = {t.name: t for t in tools}
        self._always_improve = always_improve

    def run(self, prompt: str) -> str:
        if self._always_improve:
            m = re.search(r"propose_improvement\(solution_id='([^']+)'", prompt)
            if m:
                solution_id = m.group(1)
                return self._tools["propose_improvement"].entrypoint(
                    solution_id=solution_id,
                    improved_content=(
                        "Improved solution via autoresearch agent: use pre-built wheels "
                        "to avoid compilation failures in Alpine Docker environment setup"
                    ),
                    reasoning="autoresearch mock improvement",
                    steps=["Install pre-built wheel", "Verify import", "Run tests"],
                )
        # Skip improvement
        m = re.search(r"skip_improvement\(problem_id='([^']+)'", prompt)
        if m:
            problem_id = m.group(1)
            return self._tools["skip_improvement"].entrypoint(
                problem_id=problem_id,
                reason="No improvement possible in mock",
            )
        return "Status: no_improvement. No tool called."


def test_run_research_cycle_iteration_1_improves():
    """run_research_cycle with a mock tool-calling agent reports 1 improvement."""
    from agent.src.research_loop import run_research_cycle
    from agent.src.tools import get_researcher_tools

    service, author_id = _make_service()
    p, s = _setup_problem_with_solution(service, author_id, confidence=0.25)

    tools = get_researcher_tools(service)
    agent = _ToolCallingAgent(tools, always_improve=True)

    metrics = asyncio.run(run_research_cycle(agent, service, cooldown_hours=0))

    assert metrics["candidates"] >= 1
    assert metrics["improved"] >= 1


def test_run_research_cycle_two_iterations():
    """Two consecutive run_research_cycle calls: iteration 1 improves, iteration 2 also improves
    after bad outcomes degrade the first improvement."""
    from agent.src.research_loop import run_research_cycle
    from agent.src.tools import get_researcher_tools

    service, author_id = _make_service()
    p, s1 = _setup_problem_with_solution(service, author_id, confidence=0.25)

    tools = get_researcher_tools(service)
    agent = _ToolCallingAgent(tools, always_improve=True)

    # Iteration 1: cold-start improvement (cooldown_hours=0 so all approved problems are candidates)
    metrics1 = asyncio.run(run_research_cycle(agent, service, cooldown_hours=0))
    assert metrics1["improved"] >= 1, f"Iteration 1 should improve: {metrics1}"

    # Find the new best solution and degrade it via bad outcomes
    context = service.get_context(id=p.problem_id, include=["solutions"])
    active = [s for s in context["solutions"] if s.get("canonical_id") is None]
    assert active, "No active solution after iteration 1"
    best = max(active, key=lambda s: s.get("confidence", 0))

    reporter = _add_external_reporter(service)
    for _ in range(5):
        service.report_outcome(
            reporter_id=reporter,
            solution_id=best["solution_id"],
            success=False,
        )

    degraded = service._solutions.get(best["solution_id"])
    assert degraded.confidence < 0.5, (
        f"Solution confidence should degrade below 0.5, got {degraded.confidence:.3f}"
    )

    # Iteration 2: degraded solution → improvement accepted again (cooldown_hours=0 to bypass cooldown)
    metrics2 = asyncio.run(run_research_cycle(agent, service, cooldown_hours=0))
    assert metrics2["improved"] >= 1, (
        f"Iteration 2 should improve after confidence degradation: {metrics2}"
    )

    # Both iterations produced improvements
    total_improved = metrics1["improved"] + metrics2["improved"]
    assert total_improved >= 2


def test_three_iterations_with_external_feedback():
    """3 full autoresearch iterations with distinct external reporters between each.

    Iteration 1: cold-start improvement when prior confidence is below default (0.25 → 0.3)
    External feedback 1: 5 failures from reporter1 → confidence degrades below 0.5
    Iteration 2: degraded solution → second proposal accepted
    External feedback 2: 5 failures from reporter2 → degrades again
    Iteration 3: third proposal accepted, lineage is 4 nodes deep (s1→s2→s3→s4)
    """
    service, author_id = _make_service()
    p, s1 = _setup_problem_with_solution(service, author_id, confidence=0.25)

    # --- Iteration 1 ---
    result1 = service.improve_solution(
        solution_id=s1.solution_id,
        improved_content=(
            "Install numpy on Alpine: apk add musl-dev gcc python3-dev && "
            "pip install numpy --no-cache-dir inside Docker container"
        ),
        reasoning="Iteration 1: added python3-dev and --no-cache-dir flag",
    )
    assert result1["status"] == "improved"
    s2_id = result1["solution_id"]
    assert result1["new_confidence"] > result1["previous_confidence"]

    # External feedback 1: distinct reporter sends 5 failures
    reporter1 = _add_external_reporter(service)
    for _ in range(5):
        service.report_outcome(
            reporter_id=reporter1,
            solution_id=s2_id,
            success=False,
            notes="Fails on Alpine 3.18 due to newer musl-libc ABI changes",
        )
    s2 = service._solutions.get(s2_id)
    assert s2.confidence < 0.5, (
        f"Expected confidence to degrade below 0.5 after external failures, got {s2.confidence:.3f}"
    )

    # --- Iteration 2 ---
    result2 = service.improve_solution(
        solution_id=s2_id,
        improved_content=(
            "Install numpy on Alpine using pre-built wheel from piwheels: "
            "pip install --index-url https://piwheels.org/simple/ numpy "
            "Avoids musl-libc compile failures entirely on Alpine Docker images"
        ),
        reasoning="Iteration 2: switch to pre-built wheel to bypass musl ABI issue",
    )
    assert result2["status"] == "improved", (
        f"Iteration 2 should be accepted (s2.confidence={s2.confidence:.3f} < 0.5): {result2}"
    )
    s3_id = result2["solution_id"]

    # External feedback 2: second distinct reporter sends 5 more failures
    reporter2 = _add_external_reporter(service)
    for _ in range(5):
        service.report_outcome(
            reporter_id=reporter2,
            solution_id=s3_id,
            success=False,
            notes="piwheels wheel is outdated and incompatible with Python 3.11 Alpine",
        )
    s3 = service._solutions.get(s3_id)
    assert s3.confidence < 0.5, (
        f"Expected confidence to degrade again after second wave of failures, got {s3.confidence:.3f}"
    )

    # --- Iteration 3 ---
    result3 = service.improve_solution(
        solution_id=s3_id,
        improved_content=(
            "Install numpy on Alpine via the official testing repository: "
            "apk add --repository https://dl-cdn.alpinelinux.org/alpine/edge/testing py3-numpy "
            "Provides a properly compiled binary for Alpine musl without any source compilation step"
        ),
        reasoning="Iteration 3: use Alpine testing repo for pre-compiled numpy binary",
    )
    assert result3["status"] == "improved", (
        f"Iteration 3 should be accepted (s3.confidence={s3.confidence:.3f} < 0.5): {result3}"
    )

    # Lineage must be 4 nodes deep: s1 → s2 → s3 → s4
    s4_id = result3["solution_id"]
    lineage = service.get_solution_lineage(s4_id)
    ids_in_lineage = [str(n["solution_id"]) for n in lineage]
    assert str(s1.solution_id) in ids_in_lineage
    assert str(s2_id) in ids_in_lineage
    assert str(s3_id) in ids_in_lineage
    assert str(s4_id) in ids_in_lineage
    assert len(lineage) == 4, f"Expected 4-node lineage, got {len(lineage)}: {ids_in_lineage}"


def test_run_research_cycle_three_iterations():
    """Three consecutive run_research_cycle calls, each with external feedback in between.

    Validates the full autoresearch loop at the cycle level:
    - Iteration 1: cold-start improvement
    - External failures from reporter1 degrade the new best solution
    - Iteration 2: degraded solution → improvement accepted
    - External failures from reporter2 degrade the second-generation solution
    - Iteration 3: third improvement accepted; total = 3 improvements across 3 cycle calls
    """
    from agent.src.research_loop import run_research_cycle
    from agent.src.tools import get_researcher_tools

    service, author_id = _make_service()
    p, s1 = _setup_problem_with_solution(service, author_id, confidence=0.25)

    tools = get_researcher_tools(service)
    agent = _ToolCallingAgent(tools, always_improve=True)

    # --- Iteration 1 ---
    m1 = asyncio.run(run_research_cycle(agent, service, cooldown_hours=0))
    assert m1["improved"] >= 1, f"Iteration 1 should produce at least one improvement: {m1}"

    # Find new best active solution and degrade it with external failures
    ctx1 = service.get_context(id=p.problem_id, include=["solutions"])
    active1 = [s for s in ctx1["solutions"] if s.get("canonical_id") is None]
    assert active1, "No active solution after iteration 1"
    best1 = max(active1, key=lambda s: s.get("confidence", 0))

    reporter1 = _add_external_reporter(service)
    for _ in range(5):
        service.report_outcome(
            reporter_id=reporter1,
            solution_id=best1["solution_id"],
            success=False,
            notes="Fails on Alpine 3.18 due to newer musl-libc ABI changes",
        )
    degraded1 = service._solutions.get(best1["solution_id"])
    assert degraded1.confidence < 0.5, (
        f"Solution should degrade below 0.5 after 5 external failures, got {degraded1.confidence:.3f}"
    )

    # --- Iteration 2 ---
    m2 = asyncio.run(run_research_cycle(agent, service, cooldown_hours=0))
    assert m2["improved"] >= 1, (
        f"Iteration 2 should improve after confidence degradation (was {degraded1.confidence:.3f}): {m2}"
    )

    # Find second-generation best active solution and degrade it
    ctx2 = service.get_context(id=p.problem_id, include=["solutions"])
    active2 = [s for s in ctx2["solutions"] if s.get("canonical_id") is None]
    best2 = max(active2, key=lambda s: s.get("confidence", 0))

    reporter2 = _add_external_reporter(service)
    for _ in range(5):
        service.report_outcome(
            reporter_id=reporter2,
            solution_id=best2["solution_id"],
            success=False,
            notes="piwheels wheel incompatible with Python 3.11 Alpine musl",
        )
    degraded2 = service._solutions.get(best2["solution_id"])
    assert degraded2.confidence < 0.5, (
        f"Second-generation solution should degrade below 0.5, got {degraded2.confidence:.3f}"
    )

    # --- Iteration 3 ---
    m3 = asyncio.run(run_research_cycle(agent, service, cooldown_hours=0))
    assert m3["improved"] >= 1, (
        f"Iteration 3 should improve after second degradation (was {degraded2.confidence:.3f}): {m3}"
    )

    total_improved = m1["improved"] + m2["improved"] + m3["improved"]
    assert total_improved >= 3, (
        f"Expected at least 3 total improvements across 3 iterations, got {total_improved}"
    )


def test_run_research_cycle_filters_superseded_solutions():
    """Research loop must not select a superseded solution as the improvement target."""
    from agent.src.research_loop import run_research_cycle
    from agent.src.tools import get_researcher_tools
    from agent.src.synthesis import SYSTEM_AGENT_ID

    service, author_id = _make_service()
    p, s1 = _setup_problem_with_solution(service, author_id, confidence=0.4)

    # Manually supersede s1: simulate an earlier improvement (s2 supersedes s1)
    s2 = service.create_solution(
        problem_id=p.problem_id,
        author_id=author_id,
        content="Better solution v2 with full environment setup and verified deps for Alpine numpy",
        parent_solution_id=s1.solution_id,
    )
    s2.review_status = "approved"
    s2.confidence = 0.5
    service._solutions.update(s2)
    # Mark s1 as superseded by s2
    s1.canonical_id = s2.solution_id
    service._solutions.update(s1)

    # Now degrade s2 so the research loop would pick s1 if it doesn't filter
    reporter = _add_external_reporter(service)
    for _ in range(5):
        service.report_outcome(reporter_id=reporter, solution_id=s2.solution_id, success=False)

    s2_degraded = service._solutions.get(s2.solution_id)
    # s1 (confidence=0.4) should NOT be picked over s2 (degraded but active)
    # because s1 is superseded (canonical_id is not None)

    # Track which solution_id the agent was asked to improve
    captured_solution_ids: list[str] = []

    class _CapturingAgent:
        def __init__(self, tools):
            self._tools = {t.name: t for t in tools}

        def run(self, prompt: str) -> str:
            m = re.search(r"propose_improvement\(solution_id='([^']+)'", prompt)
            if m:
                sid = m.group(1)
                captured_solution_ids.append(sid)
                return self._tools["propose_improvement"].entrypoint(
                    solution_id=sid,
                    improved_content=(
                        "Best Alpine numpy fix: use conda-forge or pre-built wheels "
                        "to completely avoid the musl-libc compilation issue here"
                    ),
                    reasoning="Improvement targeting active solution only",
                    steps=None,
                )
            pm = re.search(r"skip_improvement\(problem_id='([^']+)'", prompt)
            if pm:
                return self._tools["skip_improvement"].entrypoint(
                    problem_id=pm.group(1),
                    reason="No active solutions found",
                )
            return "Status: no_improvement."

    tools = get_researcher_tools(service)
    agent = _CapturingAgent(tools)

    asyncio.run(run_research_cycle(agent, service, cooldown_hours=0))

    # If the agent was called, it must have targeted s2 (active), not s1 (superseded)
    for sid in captured_solution_ids:
        assert sid == str(s2.solution_id), (
            f"Agent should only target active (non-superseded) solutions. "
            f"Targeted: {sid}, superseded s1: {s1.solution_id}, active s2: {s2.solution_id}"
        )


# ---------------------------------------------------------------------------
# Cooldown escape fix: invalid/timeout/exception paths record a ResearchCycle
# ---------------------------------------------------------------------------

def test_invalid_agent_response_records_research_cycle():
    """When the agent returns no recognisable status, a ResearchCycle skip must be recorded
    so the cooldown prevents an immediate hot-loop retry."""
    from agent.src.research_loop import run_research_cycle
    from agent.src.synthesis import SYSTEM_AGENT_ID

    service, author_id = _make_service()
    p, s = _setup_problem_with_solution(service, author_id, confidence=0.25)

    class _GarbageAgent:
        def run(self, prompt: str) -> str:
            return "I cannot determine an answer at this time."

    metrics = asyncio.run(run_research_cycle(_GarbageAgent(), service, cooldown_hours=0))
    assert metrics["no_improvement"] >= 1

    # A ResearchCycle skip must have been recorded
    last_researched = service._research_cycles.last_researched_at(p.problem_id)
    assert last_researched is not None, (
        "ResearchCycle skip should be recorded for invalid agent response to enforce cooldown"
    )


def test_timeout_records_research_cycle():
    """A per-candidate timeout must record a ResearchCycle skip to prevent hot-loop retry."""
    import asyncio as _asyncio
    from agent.src.research_loop import run_research_cycle

    service, author_id = _make_service()
    p, s = _setup_problem_with_solution(service, author_id, confidence=0.25)

    class _HangingAgent:
        async def arun(self, prompt: str) -> str:
            await _asyncio.sleep(9999)
            return ""

    # Patch timeout to 0 seconds so the timeout fires immediately
    import agent.src.config as _cfg
    original = _cfg.settings.agent_research_per_candidate_timeout_seconds
    _cfg.settings.__dict__["agent_research_per_candidate_timeout_seconds"] = 0
    try:
        metrics = asyncio.run(run_research_cycle(_HangingAgent(), service, cooldown_hours=0))
    finally:
        _cfg.settings.__dict__["agent_research_per_candidate_timeout_seconds"] = original

    assert metrics["no_improvement"] >= 1
    last_researched = service._research_cycles.last_researched_at(p.problem_id)
    assert last_researched is not None, (
        "ResearchCycle skip should be recorded on timeout to enforce cooldown"
    )
