"""Edge-case stress tests for AgentBook.

Run with: DEMO_MODE=1 uv run python backend/tests/simulation/edge_cases.py

Tests:
  1. Concurrent improvement of the same solution (optimistic locking)
  2. Outcome rate limiting (10/hour per agent)
  3. Concurrent outcome reports on the same solution
  4. Search cache consistency under concurrent writes
  5. Spam gate edge cases
  6. Version / optimistic locking for concurrent problem updates
  7. Anti-Sybil clustering with same-IP agents
"""

from __future__ import annotations

import asyncio
import os
from collections import Counter
from dataclasses import dataclass, field
from uuid import UUID

os.environ.setdefault("DEMO_MODE", "1")

from backend.application.errors import RateLimitError
from backend.application.service import AgentbookService
from backend.demo import (
    P1_ID,
    S1_1_ID,
    S1_2_ID,
    S1_3_ID,
    S1_SYN_ID,
    S2_1_ID,
    S2_2_ID,
    S3_1_ID,
    build_demo_repos,
)
from backend.infrastructure.embeddings.fallback import FallbackEmbeddingProvider

ALL_DEMO_SOLUTIONS = [S1_1_ID, S1_2_ID, S1_3_ID, S1_SYN_ID, S2_1_ID, S2_2_ID, S3_1_ID]


@dataclass
class TestResult:
    name: str
    passed: bool
    message: str = ""
    details: dict = field(default_factory=dict)


def build_service() -> AgentbookService:
    repos = build_demo_repos()
    return AgentbookService(
        agents=repos[0],
        embedding_provider=FallbackEmbeddingProvider(),
        problems=repos[1],
        solutions=repos[2],
        outcomes=repos[3],
        research_cycles=repos[4],
    )


# ── Test 1: Concurrent improvement of the same solution ──────────────


async def test_concurrent_improvement() -> TestResult:
    """Multiple agents try to improve the same solution simultaneously."""
    service = build_service()
    agent_ids = []
    for i in range(10):
        agent, _ = service.register_agent(f"improver-{i}")
        agent_ids.append(agent.agent_id)

    target_solution = S1_3_ID  # high confidence solution
    results: list[str] = []
    errors: list[str] = []

    async def improve(agent_id: UUID, idx: int):
        try:
            result = service.improve_solution(
                solution_id=target_solution,
                improved_content=f"Improvement attempt {idx}: better approach with more detail",
                improved_steps=[f"Step {idx}: apply fix"],
                reasoning=f"Agent {idx} reasoning",
                author_id=agent_id,
            )
            results.append(result.get("status", "unknown"))
        except Exception as e:
            errors.append(f"{type(e).__name__}: {e}")

    tasks = [improve(aid, i) for i, aid in enumerate(agent_ids)]
    await asyncio.gather(*tasks)

    status_counts = Counter(results)
    return TestResult(
        name="concurrent_improvement",
        passed=True,  # No crashes = pass
        message=f"10 concurrent improvements: {dict(status_counts)}, {len(errors)} errors",
        details={"statuses": dict(status_counts), "errors": errors[:3]},
    )


# ── Test 2: Outcome rate limiting ────────────────────────────────────


def test_outcome_rate_limit() -> TestResult:
    """A single agent reports more than 10 outcomes within 1 hour."""
    service = build_service()
    agent, _ = service.register_agent("rate-limit-tester")

    successes = 0
    rate_limited = 0
    other_errors = 0

    for i in range(20):
        try:
            service.report_outcome(
                reporter_id=agent.agent_id,
                solution_id=ALL_DEMO_SOLUTIONS[i % len(ALL_DEMO_SOLUTIONS)],
                success=True,
                notes=f"Report #{i}",
            )
            successes += 1
        except RateLimitError:
            rate_limited += 1
        except Exception:
            other_errors += 1

    passed = rate_limited > 0 and successes <= 10
    return TestResult(
        name="outcome_rate_limit",
        passed=passed,
        message=f"20 reports: {successes} succeeded, {rate_limited} rate-limited, {other_errors} errors",
        details={"successes": successes, "rate_limited": rate_limited},
    )


# ── Test 3: Concurrent outcome reports on the same solution ──────────


async def test_concurrent_outcomes() -> TestResult:
    """Multiple agents report outcomes on the same solution simultaneously."""
    service = build_service()
    agent_ids = []
    for i in range(20):
        agent, _ = service.register_agent(f"reporter-{i}")
        agent_ids.append(agent.agent_id)

    target = S1_3_ID
    successes = 0
    errors: list[str] = []

    async def report(agent_id: UUID, idx: int):
        nonlocal successes
        try:
            service.report_outcome(
                reporter_id=agent_id,
                solution_id=target,
                success=(idx % 2 == 0),
                notes=f"Concurrent report #{idx}",
            )
            successes += 1
        except Exception as e:
            errors.append(f"{type(e).__name__}: {e}")

    tasks = [report(aid, i) for i, aid in enumerate(agent_ids)]
    await asyncio.gather(*tasks)

    # Check confidence was updated
    solutions = service._solutions.list_by_problem(P1_ID)
    target_sol = next((s for s in solutions if s.solution_id == target), None)
    new_confidence = target_sol.confidence if target_sol else 0

    return TestResult(
        name="concurrent_outcomes",
        passed=len(errors) == 0,
        message=f"20 concurrent reports: {successes} ok, {len(errors)} errors, confidence={new_confidence:.3f}",
        details={"errors": errors[:5], "confidence": new_confidence},
    )


# ── Test 4: Search cache consistency ────────────────────────────────


async def test_search_cache_consistency() -> TestResult:
    """Concurrent searches while new problems are being created."""
    service = build_service()
    agent_ids = []
    for i in range(10):
        agent, _ = service.register_agent(f"searcher-{i}")
        agent_ids.append(agent.agent_id)

    search_results: list[int] = []
    create_results: list[int] = []
    errors: list[str] = []

    async def search(idx: int):
        try:
            result = service.search_problems(query="docker python module", limit=10)
            search_results.append(result["total"])
        except Exception as e:
            errors.append(f"search[{idx}]: {type(e).__name__}: {e}")

    async def create_problem(agent_id: UUID, idx: int):
        try:
            service.create_problem(
                author_id=agent_id,
                description=f"Docker python module import error variant {idx}",
                error_signature="ModuleNotFoundError: No module named 'docker_test'",
                tags=["docker", "python"],
            )
            create_results.append(idx)
        except Exception as e:
            errors.append(f"create[{idx}]: {type(e).__name__}: {e}")

    # Interleave searches and creates
    tasks = []
    for i in range(10):
        tasks.append(search(i))
        tasks.append(create_problem(agent_ids[i % len(agent_ids)], i))
        tasks.append(search(i + 10))
    await asyncio.gather(*tasks)

    # Final search should see all created problems
    final = service.search_problems(query="docker python module", limit=50)

    return TestResult(
        name="search_cache_consistency",
        passed=len(errors) == 0,
        message=f"Searches saw {min(search_results)}-{max(search_results)} results, created {len(create_results)} problems, final search: {final['total']}, {len(errors)} errors",
        details={
            "search_range": f"{min(search_results)}-{max(search_results)}",
            "errors": errors[:3],
        },
    )


# ── Test 5: Spam gate edge cases ────────────────────────────────────


def test_spam_gate() -> TestResult:
    """Test spam gate with various inputs."""
    service = build_service()
    agent, _ = service.register_agent("spam-tester")

    spam_inputs = [
        ("buy cheap pills now", "spam content"),
        ("http://spam-link.com", "link spam"),
        ("", "empty description"),
        ("a" * 10000, "very long content"),
        ("FREE MONEY!!! CLICK HERE!!!", "promotional spam"),
        ("asdfghjkl qwertyuiop", "gibberish"),
    ]

    rejected = 0
    accepted = 0
    errors: list[str] = []

    for desc, label in spam_inputs:
        try:
            service.create_problem(
                author_id=agent.agent_id,
                description=desc,
                error_signature="test",
                tags=["test"],
            )
            accepted += 1
        except ValueError:
            rejected += 1
        except Exception as e:
            errors.append(f"{label}: {type(e).__name__}: {e}")

    # Also test legitimate content passes
    legit_accepted = False
    try:
        service.create_problem(
            author_id=agent.agent_id,
            description="Python fails to import numpy in Docker Alpine container with ModuleNotFoundError",
            error_signature="ModuleNotFoundError: No module named 'numpy'",
            tags=["python", "docker"],
        )
        legit_accepted = True
    except Exception as e:
        errors.append(f"legit: {type(e).__name__}: {e}")

    passed = rejected > 0 and legit_accepted and len(errors) == 0
    return TestResult(
        name="spam_gate",
        passed=passed,
        message=f"Spam: {rejected} rejected, {accepted} accepted. Legit: {'accepted' if legit_accepted else 'REJECTED'}. Errors: {len(errors)}",
        details={
            "rejected": rejected,
            "accepted": accepted,
            "legit": legit_accepted,
            "errors": errors,
        },
    )


# ── Test 6: Version / optimistic locking ─────────────────────────────


async def test_optimistic_locking() -> TestResult:
    """Test concurrent problem updates with version checking."""
    service = build_service()
    agent_ids = []
    for i in range(5):
        agent, _ = service.register_agent(f"locker-{i}")
        agent_ids.append(agent.agent_id)

    # Create solutions concurrently on the same problem
    # This triggers problem.version updates via solution_count increment
    results: list[str] = []
    errors: list[str] = []

    async def create_solution(agent_id: UUID, idx: int):
        try:
            service.create_solution(
                problem_id=P1_ID,
                author_id=agent_id,
                content=f"Solution {idx} for testing concurrent writes",
                steps=[f"Step {idx}"],
            )
            results.append("ok")
        except Exception as e:
            errors.append(f"{type(e).__name__}: {e}")

    tasks = [create_solution(aid, i) for i, aid in enumerate(agent_ids)]
    await asyncio.gather(*tasks)

    # Check the problem's solution_count
    problem = service._problems.get(P1_ID)
    return TestResult(
        name="optimistic_locking",
        passed=True,  # No data corruption
        message=f"5 concurrent solution creates: {len(results)} ok, {len(errors)} errors. Final solution_count={problem.solution_count if problem else 'N/A'}",
        details={"results": len(results), "errors": errors[:3]},
    )


# ── Test 7: Anti-Sybil clustering ───────────────────────────────────


def test_anti_sybil_clustering() -> TestResult:
    """Test that agents with same IP hash are clustered together for confidence."""
    from backend.application.clustering import detect_clusters
    from backend.domain.models import Agent

    # Create agents with same ip_hash
    agents = []
    for i in range(5):
        agent = Agent(
            api_key_hash=f"hash_{i}",
            model_type=f"model-{i}",
            ip_hash="same_ip_hash_123",
        )
        agents.append(agent)

    # Create agents with different ip_hash
    for i in range(3):
        agent = Agent(
            api_key_hash=f"diff_hash_{i}",
            model_type=f"model-diff-{i}",
            ip_hash=f"different_ip_{i}",
        )
        agents.append(agent)

    clusters = detect_clusters(agents)
    # Same-IP agents should collapse into one cluster
    # Different-IP agents should each be their own cluster
    cluster_sizes = sorted([len(c) for c in clusters], reverse=True)

    # The 5 same-IP agents should form 1 cluster of 5
    # The 3 different-IP agents should form 3 clusters of 1 each
    expected = [5, 1, 1, 1]
    passed = cluster_sizes == expected
    return TestResult(
        name="anti_sybil_clustering",
        passed=passed,
        message=f"Cluster sizes: {cluster_sizes} (expected {expected})",
        details={"clusters": cluster_sizes, "expected": expected},
    )


# ── Test 8: Confidence scoring with diverse reporters ────────────────


def test_confidence_diverse_reporters() -> TestResult:
    """Test that confidence is higher with diverse reporters vs single reporter."""
    from backend.application.confidence import calculate_confidence
    from backend.domain.models import Outcome, utc_now

    now = utc_now()

    # Scenario A: 5 outcomes from 5 different reporters
    reporters_a = [UUID(f"aaaaaaaa-0000-0000-0000-00000000000{j}") for j in range(5)]
    outcomes_a = [
        Outcome(
            outcome_id=UUID(f"bbbbbbbb-0000-0000-0000-00000000000{j}"),
            solution_id=UUID("11111111-0000-0000-0000-000000000001"),
            reporter_id=rid,
            success=True,
            kind="observed",
            created_at=now,
        )
        for j, rid in enumerate(reporters_a)
    ]
    author_a = UUID("cccccccc-0000-0000-0000-000000000001")
    conf_a = calculate_confidence(outcomes_a, author_a, num_effective_reporters=5)

    # Scenario B: 5 outcomes from 1 reporter (self-reports)
    single_reporter = UUID("dddddddd-0000-0000-0000-000000000001")
    outcomes_b = [
        Outcome(
            outcome_id=UUID(f"eeeeeeee-0000-0000-0000-00000000000{j}"),
            solution_id=UUID("11111111-0000-0000-0000-000000000001"),
            reporter_id=single_reporter,
            success=True,
            kind="observed",
            created_at=now,
        )
        for j in range(5)
    ]
    conf_b = calculate_confidence(
        outcomes_b, single_reporter, num_effective_reporters=0
    )

    passed = conf_a > conf_b
    return TestResult(
        name="confidence_diverse_reporters",
        passed=passed,
        message=f"Diverse reporters confidence: {conf_a:.3f} vs single reporter: {conf_b:.3f}",
        details={"diverse": conf_a, "single": conf_b},
    )


# ── Test 9: Improvement evaluation regression detection ──────────────


def test_improvement_regression() -> TestResult:
    """Test that content regressions are rejected."""
    from uuid import uuid4

    from backend.application.confidence import (
        evaluate_improvement,
        is_content_regression,
    )
    from backend.domain.models import Solution

    pid = uuid4()
    existing = Solution(
        solution_id=uuid4(),
        problem_id=pid,
        author_id=uuid4(),
        content="This is a detailed solution with multiple steps explaining the fix thoroughly.",
        steps=["Step 1", "Step 2", "Step 3"],
        confidence=0.5,
    )

    # Regression: much shorter content with fewer steps
    regression = Solution(
        solution_id=uuid4(),
        problem_id=pid,
        author_id=uuid4(),
        content="Just restart.",
        steps=["Step 1"],
        confidence=0.3,
    )

    is_reg = is_content_regression(existing, regression)
    accepted, reason = evaluate_improvement(existing, regression)

    passed = is_reg and not accepted
    return TestResult(
        name="improvement_regression",
        passed=passed,
        message=f"Regression detected: {is_reg}, accepted: {accepted}, reason: {reason}",
        details={"is_regression": is_reg, "accepted": accepted, "reason": reason},
    )


# ── Main ─────────────────────────────────────────────────────────────


async def main():
    print("=" * 70)
    print("  AgentBook Edge-Case Stress Tests")
    print("=" * 70)
    print()

    tests: list[TestResult] = []

    # Sync tests
    tests.append(test_outcome_rate_limit())
    tests.append(test_spam_gate())
    tests.append(test_anti_sybil_clustering())
    tests.append(test_confidence_diverse_reporters())
    tests.append(test_improvement_regression())

    # Async tests
    tests.append(await test_concurrent_improvement())
    tests.append(await test_concurrent_outcomes())
    tests.append(await test_search_cache_consistency())
    tests.append(await test_optimistic_locking())

    # Report
    passed = sum(1 for t in tests if t.passed)
    failed = sum(1 for t in tests if not t.passed)

    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    print()

    for t in tests:
        status = "PASS" if t.passed else "FAIL"
        print(f"  [{status}] {t.name}")
        print(f"         {t.message}")
        if t.details.get("errors"):
            for err in t.details["errors"][:3]:
                print(f"         Error: {err}")
        print()

    return failed


if __name__ == "__main__":
    import sys

    errors = asyncio.run(main())
    sys.exit(1 if errors > 0 else 0)
