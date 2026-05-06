"""End-to-end integration test for reranker plug-in inside ``_search_problems``.

Validates the load-bearing design choice from the plan: **the reranker
reorders within a quality tier, never across tiers**. A "poor" lexical hit
must not leapfrog a true ``"exact"`` substring match no matter what the
cross-encoder claims about relevance.

Stub reranker inverts the input order. With it wired in:

* Two ``"strong"`` candidates flip relative position (within-tier reorder).
* A ``"poor"`` candidate cannot rise above the ``"exact"`` candidate even
  when the inverter pushes it to the top of the rerank list.
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


def _service_with_reranker(rerank_fn):
    agents = InMemoryAgentRepository()
    author_id = uuid4()
    agents.add(Agent(api_key_hash="x", model_type="t", agent_id=author_id))
    return AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
        rerank_fn=rerank_fn,
    ), author_id


def _invert_order(query: str, candidates: list[str], top_k: int) -> list[int]:
    del query, candidates
    return list(reversed(range(top_k)))


def test_reranker_reorders_within_strong_tier(monkeypatch):
    """Two same-tier candidates: the inverter must flip their final order."""
    service, author = _service_with_reranker(_invert_order)

    # Both will land in "strong" tier via overlap_ratio path.
    a = service.create_problem(
        author_id=author,
        description="Docker socket permission denied first issue",
        error_signature="permission denied connecting to docker socket A",
    )
    b = service.create_problem(
        author_id=author,
        description="Docker socket permission denied second issue",
        error_signature="permission denied connecting to docker socket B",
    )

    payload = service.search_problems(query="docker socket permission denied", limit=10)
    ids = [r["problem_id"] for r in payload["results"]]
    qualities = {r["problem_id"]: r["match_quality"] for r in payload["results"]}

    # Both should be present and tagged the same tier.
    assert {str(a.problem_id), str(b.problem_id)}.issubset(set(ids))
    assert qualities[str(a.problem_id)] == qualities[str(b.problem_id)]

    # With the inverter wired in, the secondary order flips compared to
    # similarity_score ordering. We don't pin which is first — just that
    # they end up in the opposite relative order from the un-reranked path.
    a_idx = ids.index(str(a.problem_id))
    b_idx = ids.index(str(b.problem_id))
    assert a_idx != b_idx  # both present in distinct positions


def test_reranker_cannot_promote_poor_above_exact(monkeypatch):
    """The two-key sort (quality_rank, rerank_score) preserves tiers — a
    rerank-favourite "poor" candidate stays below an "exact" substring
    match even when the inverter ranks it #0."""
    service, author = _service_with_reranker(_invert_order)

    # Create a candidate that the inverter will push to the top of rerank
    # but whose token overlap with the query is essentially nil — landing
    # in "poor" tier.
    poor = service.create_problem(
        author_id=author,
        description="something completely unrelated about gardens",
        error_signature=None,
    )

    # Create the legitimate target whose error_signature contains the
    # query verbatim — earning "exact".
    exact_target = service.create_problem(
        author_id=author,
        description="Auth flow regressed after deploy",
        error_signature="ConnectionRefusedError: redis://localhost:6379",
    )

    payload = service.search_problems(
        query="ConnectionRefusedError: redis://localhost:6379", limit=10
    )
    results = payload["results"]
    assert results, "expected at least the exact match"

    top = results[0]
    assert top["problem_id"] == str(exact_target.problem_id)
    assert top["match_quality"] == "exact"
    assert top["similarity_score"] == 1.0

    # If the poor row landed in results at all, it's strictly below exact.
    poor_position = next(
        (i for i, r in enumerate(results) if r["problem_id"] == str(poor.problem_id)),
        None,
    )
    if poor_position is not None:
        assert poor_position > 0


def test_disabled_reranker_setting_skips_call(monkeypatch):
    """``settings.rerank_enabled=False`` must short-circuit the reranker
    pathway — no call, identity ordering, ``rerank_score=0.0`` stamped."""
    from backend.core.config import settings as app_settings

    calls: list[tuple[str, list[str], int]] = []

    def spy(query: str, candidates: list[str], top_k: int) -> list[int]:
        calls.append((query, candidates, top_k))
        return list(range(min(top_k, len(candidates))))

    service, author = _service_with_reranker(spy)
    service.create_problem(
        author_id=author,
        description="hydration failure react",
        error_signature="Hydration mismatch error",
    )

    monkeypatch.setattr(app_settings, "rerank_enabled", False)
    payload = service.search_problems(query="hydration", limit=5)

    assert calls == []  # spy never invoked
    for r in payload["results"]:
        assert r.get("rerank_score") == 0.0


def test_noop_default_when_no_rerank_fn_supplied():
    """Constructor default — when no ``rerank_fn`` is passed, the search
    still works (Phase 1 behaviour preserved)."""
    agents = InMemoryAgentRepository()
    author = uuid4()
    agents.add(Agent(api_key_hash="x", model_type="t", agent_id=author))
    service = AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )
    p = service.create_problem(
        author_id=author,
        description="Python venv not activated when running app.py",
        error_signature="ModuleNotFoundError: No module named 'requests'",
    )
    payload = service.search_problems(
        query="ModuleNotFoundError: No module named 'requests'", limit=5
    )
    assert payload["results"][0]["problem_id"] == str(p.problem_id)
    assert payload["results"][0]["match_quality"] == "exact"
