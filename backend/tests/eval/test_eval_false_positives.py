"""Offline retrieval-quality eval against frozen FP/TP fixtures.

Purpose
-------
The 22-Coding-Agent simulation against production agentbook surfaced 6 cases
(27%) where ``similarity_score=1.0`` / ``match_quality="exact"`` was returned
for unrelated problems because ``_score_problem_relevance`` short-circuits on
any single distinctive token overlap with ``error_signature``.

This eval freezes those 6 false positives + 2 true positives as a fixture
and runs each case end-to-end against ``AgentbookService.search_problems``
with an in-memory corpus seeded with both the legitimate target and the
misleading collider. Each phase of the fix must satisfy the same invariants:

* For false-positive cases: the legitimate target must outrank every collider,
  the top result must NOT be tagged ``match_quality == "exact"``, and the top
  ``similarity_score`` must be strictly less than 1.0.
* For true-positive substring cases: the target ranks first and is tagged
  ``"exact"`` because the query is a true substring of its ``error_signature``.

Designed to FAIL on the broken pre-fix code (proving the bug reproduces) and
PASS once Phase 1 lands. The same harness re-runs unchanged after Phase 2
ships the Voyage reranker, where the assertions tighten to "target ranks #1".
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

FIXTURE_PATH = Path(__file__).parent / "false_positives.json"


def _load_cases() -> list[dict]:
    return json.loads(FIXTURE_PATH.read_text())["cases"]


def _make_service():
    from backend.application.service import AgentbookService
    from backend.domain.models import Agent
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
        Agent(api_key_hash="eval-hash", model_type="eval", agent_id=author_id),
    )
    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    return service, author_id


def _seed_problem(service, author_id, payload: dict):
    return service.create_problem(
        author_id=author_id,
        description=payload["description"],
        error_signature=payload["error_signature"],
    )


def _ranks_by_problem_id(results: list[dict]) -> dict[str, int]:
    return {row["problem_id"]: idx for idx, row in enumerate(results)}


@pytest.mark.eval
@pytest.mark.parametrize(
    "case",
    _load_cases(),
    ids=lambda c: c["name"],
)
def test_retrieval_quality(case: dict) -> None:
    service, author_id = _make_service()

    # Insert collider FIRST so the broken candidate-injection path locks the
    # collider's row at similarity_score=1.0 before the target arrives.
    # Under the bug, ``add_candidate`` only overwrites on strict greater-than,
    # so the collider stays on top in the broken code path.
    collider = None
    if case["collider"] is not None:
        collider = _seed_problem(service, author_id, case["collider"])

    target = _seed_problem(service, author_id, case["target"])

    payload = service.search_problems(query=case["query"], limit=10)
    results = payload["results"]
    assert results, f"No results returned for case {case['name']!r}"

    ranks = _ranks_by_problem_id(results)
    assert str(target.problem_id) in ranks, (
        f"Target not found in results for {case['name']!r}: "
        f"got problem_ids {list(ranks)}"
    )

    if case["kind"] == "false_positive":
        assert collider is not None, "false_positive cases must include a collider"
        target_rank = ranks[str(target.problem_id)]
        collider_rank = ranks.get(str(collider.problem_id))
        # Either the collider is suppressed below ``_MIN_SEARCH_RELEVANCE``
        # (the stronger outcome) or it appears below the target. Both are
        # acceptable; the bug we're guarding against is the collider ranking
        # AT or ABOVE the target with similarity_score=1.0.
        if collider_rank is not None:
            assert target_rank < collider_rank, (
                f"FP regression for {case['name']!r}: target ranked at "
                f"{target_rank} but collider ranked higher at {collider_rank}"
            )
        top = results[0]
        # The top result may legitimately be tagged ``"exact"`` only when it
        # IS the target and the query happens to substring-match its signature.
        if top["match_quality"] == "exact":
            assert top["problem_id"] == str(target.problem_id), (
                f"FP for {case['name']!r}: a non-target result earned "
                f"match_quality=exact ({top['problem_id']}). exact must be "
                f"reserved for true substring matches against the legitimate "
                f"target."
            )
        else:
            assert top["similarity_score"] < 1.0, (
                f"Top result for {case['name']!r} is non-exact yet "
                f"similarity_score={top['similarity_score']} >= 1.0 — score "
                f"must be capped below 1.0 for non-substring matches."
            )

    elif case["kind"] == "true_positive_substring":
        top = results[0]
        assert top["problem_id"] == str(target.problem_id), (
            f"TP {case['name']!r}: expected target {target.problem_id} at rank 0, "
            f"got {top['problem_id']}"
        )
        assert top["match_quality"] == "exact", (
            f"TP {case['name']!r}: expected match_quality=exact for substring "
            f"match, got {top['match_quality']}"
        )
        assert "error_signature" in top["match_reasons"], (
            f"TP {case['name']!r}: expected error_signature in match_reasons, "
            f"got {top['match_reasons']}"
        )

    else:
        pytest.fail(f"Unknown case kind {case['kind']!r} in {case['name']!r}")
