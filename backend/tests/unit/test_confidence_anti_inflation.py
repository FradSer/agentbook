"""Verifies features/confidence_anti_inflation.feature.

Pins the three v6 invariants:
- Outcome upsert (same reporter cannot vote twice on the same solution)
- Cold-start floor (< 3 external reporters caps confidence at 0.5)
- Sandbox-only ceiling (no external observed corroboration caps at 0.6)

Plus the frozen-policy/changelog handshake and the
``confidence_provenance`` field on search responses.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from backend.application.confidence import calculate_confidence
from backend.application.service import (
    SANDBOX_AGENT_ID,
    AgentbookService,
)
from backend.domain.models import Agent, Outcome, Problem, Solution, utc_now
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)


def _make_outcome(
    reporter_id: UUID,
    solution_id: UUID,
    *,
    success: bool = True,
    kind: str = "observed",
    weight: float = 1.0,
    age_days: float = 0.0,
) -> Outcome:
    return Outcome(
        outcome_id=uuid4(),
        solution_id=solution_id,
        reporter_id=reporter_id,
        success=success,
        kind=kind,
        weight=weight,
        created_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Invariant 1 — outcome dedup: same reporter, same solution → upsert.
# ---------------------------------------------------------------------------


class TestOutcomeUpsert:
    def test_in_memory_upsert_replaces_existing_row(self) -> None:
        repo = InMemoryOutcomeRepository()
        sid = uuid4()
        rid = uuid4()
        first = _make_outcome(rid, sid, success=False)
        repo.add(first)

        second = _make_outcome(rid, sid, success=True, weight=0.5)
        repo.upsert(second)

        rows = repo.list_by_solution(sid)
        assert len(rows) == 1
        # Most-recent wins: success and weight should match `second`.
        assert rows[0].success is True
        assert rows[0].weight == 0.5

    def test_upsert_inserts_when_pair_is_new(self) -> None:
        repo = InMemoryOutcomeRepository()
        sid = uuid4()
        rid = uuid4()
        repo.upsert(_make_outcome(rid, sid))
        rows = repo.list_by_solution(sid)
        assert len(rows) == 1

    def test_upsert_keeps_separate_rows_for_distinct_reporters(self) -> None:
        repo = InMemoryOutcomeRepository()
        sid = uuid4()
        repo.upsert(_make_outcome(uuid4(), sid))
        repo.upsert(_make_outcome(uuid4(), sid))
        rows = repo.list_by_solution(sid)
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# Invariant 2 — cold-start floor: < 3 unique external reporters ⇒ ≤ 0.5.
# ---------------------------------------------------------------------------


class TestColdStartFloor:
    def test_one_external_success_is_capped_at_0_5(self) -> None:
        author = uuid4()
        sid = uuid4()
        outcomes = [_make_outcome(uuid4(), sid, success=True)]
        conf = calculate_confidence(outcomes, author)
        assert conf <= 0.5, (
            "A single external success must not push confidence past 0.5; "
            f"got {conf:.3f}. The pre-v6 math jumped to 0.689 here."
        )

    def test_two_external_successes_still_capped_at_0_5(self) -> None:
        author = uuid4()
        sid = uuid4()
        outcomes = [
            _make_outcome(uuid4(), sid, success=True),
            _make_outcome(uuid4(), sid, success=True),
        ]
        conf = calculate_confidence(outcomes, author)
        assert conf <= 0.5, (
            f"Two distinct external successes must remain ≤ 0.5; got {conf:.3f}"
        )

    def test_three_external_successes_release_the_floor(self) -> None:
        author = uuid4()
        sid = uuid4()
        outcomes = [_make_outcome(uuid4(), sid, success=True) for _ in range(3)]
        conf = calculate_confidence(outcomes, author)
        assert conf > 0.5, (
            f"Three distinct external successes should clear the floor; got {conf:.3f}"
        )

    def test_floor_does_not_invert_failure_signal(self) -> None:
        """The cap is on positive momentum; a single failure should not rise to 0.5."""
        author = uuid4()
        sid = uuid4()
        outcomes = [_make_outcome(uuid4(), sid, success=False)]
        conf = calculate_confidence(outcomes, author)
        # Floor caps the *upper* bound; a failure should be below baseline.
        assert conf <= 0.5


# ---------------------------------------------------------------------------
# Invariant 3 — sandbox-only ceiling: no external observed ⇒ ≤ 0.6.
# ---------------------------------------------------------------------------


class TestSandboxOnlyCeiling:
    def test_single_sandbox_verified_pass_capped_at_0_6(self) -> None:
        author = uuid4()
        sid = uuid4()
        outcomes = [
            _make_outcome(SANDBOX_AGENT_ID, sid, success=True, kind="verified"),
        ]
        conf = calculate_confidence(outcomes, author)
        assert conf <= 0.6, (
            "A sandbox-only verified pass must not exceed 0.6 — without "
            "external corroboration the agent cannot tell whether the "
            "fix only works in the sandbox's narrow Python image. "
            f"Got {conf:.3f}."
        )

    def test_external_observed_corroboration_releases_ceiling(self) -> None:
        author = uuid4()
        sid = uuid4()
        outcomes = [
            _make_outcome(SANDBOX_AGENT_ID, sid, success=True, kind="verified"),
            _make_outcome(uuid4(), sid, success=True),
            _make_outcome(uuid4(), sid, success=True),
            _make_outcome(uuid4(), sid, success=True),
        ]
        conf = calculate_confidence(outcomes, author)
        assert conf > 0.6, (
            f"Sandbox + 3 external observed should clear 0.6; got {conf:.3f}"
        )


# ---------------------------------------------------------------------------
# Frozen policy version + changelog.
# ---------------------------------------------------------------------------


class TestFrozenPolicyV6:
    def test_calculate_confidence_carries_v6(self) -> None:
        version = getattr(calculate_confidence, "__frozen_policy_version__", None)
        assert version == "v6", (
            f"Expected frozen policy v6 after the cold-start + sandbox "
            f"ceiling change; got {version!r}"
        )

    def test_changelog_has_v6_entry(self) -> None:
        changelog = (
            Path(__file__).resolve().parents[3] / "docs" / "confidence-changelog.md"
        )
        text = changelog.read_text()
        assert re.search(r"^## v6\b", text, flags=re.MULTILINE), (
            "Bumping the frozen policy without a matching ## v6 entry "
            "in docs/confidence-changelog.md will fail "
            "scripts/check_frozen_policy.sh in CI."
        )


# ---------------------------------------------------------------------------
# Provenance field on search response.
# ---------------------------------------------------------------------------


def _seeded_service() -> tuple[AgentbookService, UUID, UUID]:
    """Build a service with one approved problem and one solution + outcome."""
    agents = InMemoryAgentRepository()
    problems = InMemoryProblemRepository()
    solutions = InMemorySolutionRepository()
    outcomes = InMemoryOutcomeRepository()

    author_id = uuid4()
    agents.add(Agent(api_key_hash="hash", model_type="m", agent_id=author_id))

    problem = Problem(
        problem_id=uuid4(),
        author_id=author_id,
        description="docker python module not found on alpine image",
        created_at=utc_now(),
        last_activity_at=utc_now(),
        review_status="approved",
    )
    problems.add(problem)

    solution = Solution(
        solution_id=uuid4(),
        problem_id=problem.problem_id,
        author_id=author_id,
        content="Use python:3.11-slim instead of alpine.",
        steps=["Switch base image", "Rebuild"],
        confidence=0.45,
        outcome_count=1,
        created_at=utc_now(),
        updated_at=utc_now(),
        review_status="approved",
    )
    solutions.add(solution)
    problem.canonical_solution_id = solution.solution_id
    problems.update(problem)

    outcomes.add(
        Outcome(
            outcome_id=uuid4(),
            solution_id=solution.solution_id,
            reporter_id=uuid4(),
            success=True,
            kind="observed",
            weight=1.0,
            created_at=utc_now(),
        )
    )

    service = AgentbookService(
        agents=agents,
        problems=problems,
        solutions=solutions,
        outcomes=outcomes,
        research_cycles=InMemoryResearchCycleRepository(),
    )
    return service, problem.problem_id, solution.solution_id


class TestConfidenceProvenanceOnResponse:
    def test_search_response_best_solution_carries_provenance(self) -> None:
        service, _, _ = _seeded_service()
        payload = service.search_problems(query="docker python", limit=5)
        assert payload["results"], "expected the seeded problem to surface"
        best = payload["results"][0]["best_solution"]
        assert best is not None
        provenance = best.get("confidence_provenance")
        assert provenance is not None, (
            "Every confidence number in a response must come with a "
            "provenance carrier so agents can distinguish a real "
            "Bayesian estimate from a seed-override."
        )
        assert isinstance(provenance.get("outcomes_n"), int)
        assert isinstance(provenance.get("unique_reporters"), int)
        assert isinstance(provenance.get("verified_n"), int)
        assert isinstance(provenance.get("has_seed_override"), bool)
        assert provenance["outcomes_n"] >= 1
        assert provenance["unique_reporters"] >= 1
