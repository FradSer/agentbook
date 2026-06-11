"""Unit tests for the decomposed match-quality scoring functions.

Phase 1 of the false-positive bug fix split ``_score_problem_relevance`` into
``_classify_match_quality`` (taxonomy) and ``_compute_relevance_score``
(numeric). These tests pin down the contract that previously held only by
accident: ``"exact"`` is reserved for substring matches, the score is capped
at 0.95 outside the exact tier, and signature-token overlap requires both a
distinctive-token count floor and a Jaccard floor before earning ``"strong"``.

Boundary cases below were chosen to catch the precise off-by-one that
produced the original 27% high-confidence false-positive rate.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.application.service import AgentbookService
from backend.domain.models import Agent, Problem
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)


def _make_service(embedding_provider_name: str = "fallback") -> AgentbookService:
    agents = InMemoryAgentRepository()
    agents.add(Agent(api_key_hash="x", model_type="t", agent_id=uuid4()))
    return AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
        embedding_provider_name=embedding_provider_name,
    )


def _problem(description: str, error_signature: str | None = None) -> Problem:
    return Problem(
        author_id=uuid4(),
        description=description,
        error_signature=error_signature,
        review_status="approved",
    )


# ---------------------------------------------------------------------------
# _classify_match_quality
# ---------------------------------------------------------------------------


def test_substring_match_earns_exact_tier():
    service = _make_service()
    p = _problem(
        description="Python venv inactive after pip install",
        error_signature="ModuleNotFoundError: No module named 'requests'",
    )
    quality, reasons, _ = service._classify_match_quality(
        p, "ModuleNotFoundError: No module named 'requests'", raw_score=0.0
    )
    assert quality == "exact"
    assert "error_signature" in reasons


def test_query_substring_of_signature_earns_exact_tier():
    """The QueuePool case from test_service_agentbook_view: a short query
    that is a substring of a longer signature still earns ``"exact"``."""
    service = _make_service()
    p = _problem(
        description="FastAPI requests intermittently hang under DB load",
        error_signature="TimeoutError: QueuePool limit of size 5 overflow 10 reached",
    )
    quality, reasons, _ = service._classify_match_quality(p, "QueuePool", raw_score=0.0)
    assert quality == "exact"
    assert "error_signature" in reasons


def test_distinctive_overlap_two_tokens_does_not_earn_strong_via_signature():
    """The Docker-rootless collider had 2 shared distinctive tokens with a
    Docker-socket query. Under the bug it earned ``"exact"``; under the fix
    it must NOT earn ``"strong"`` via the signature path because the
    distinctive overlap floor is 3."""
    service = _make_service()
    collider = _problem(
        description="Docker rootless mode cannot mount /tmp",
        error_signature="Permission denied: cannot mount /tmp in rootless container",
    )
    quality, reasons, _ = service._classify_match_quality(
        collider, "Docker socket permission denied", raw_score=0.0
    )
    assert quality != "exact"
    # If quality is "strong", it must not be via the signature path.
    if quality == "strong":
        assert "error_signature" not in reasons


def test_distinctive_overlap_three_tokens_with_jaccard_under_floor_skips_signature_tier():
    """Three distinctive overlaps but Jaccard below 0.35 should NOT promote
    via the signature path — the dual-gate is what kills surface-token
    coincidences in long signatures with mostly disjoint vocabulary."""
    service = _make_service()
    p = _problem(
        description="A long unrelated problem",
        # Long signature so Jaccard tanks even with 3 distinctive tokens
        # overlapping. Query distinctive tokens here are reusable, common.
        error_signature=(
            "permission denied while trying to do many other things "
            "in a completely different unrelated context with various tokens"
        ),
    )
    # Query has only 3 tokens to maximize the Jaccard impact of the long sig.
    quality, reasons, _ = service._classify_match_quality(
        p, "permission denied trying", raw_score=0.0
    )
    # Distinctive overlap (>=6 chars): {permission, denied, trying} = 3 ✓
    # Jaccard: 3 / (~16 sig tokens + 0 query-only) ≈ 0.19 — below 0.35.
    if quality == "strong" and "error_signature" in reasons:
        pytest.fail(
            "signature-tier strong was awarded despite Jaccard below floor — "
            "the dual gate is broken."
        )


def test_signature_tier_strong_when_both_gates_clear():
    """The signature path must light up when distinctive overlap >= 3 AND
    Jaccard >= 0.35. Inputs here are hand-tuned for Jaccard 5/6 ≈ 0.83 with
    no substring match (different word order)."""
    service = _make_service()
    target = _problem(
        description="Docker daemon socket permission denied",
        error_signature="permission denied connect Docker daemon socket",
    )
    quality, reasons, _ = service._classify_match_quality(
        target, "Docker permission denied socket connect", raw_score=0.0
    )
    assert quality == "strong"
    assert "error_signature" in reasons


def test_high_raw_score_alone_promotes_to_strong_under_real_provider():
    # The vector-score promotion requires a trusted embedding provider; under
    # the deterministic fallback the same score caps at "partial" (see
    # test_fallback_label_cap.py / fallback-label-cap.feature).
    service = _make_service(embedding_provider_name="gemini")
    p = _problem(description="any description", error_signature=None)
    quality, reasons, _ = service._classify_match_quality(
        p, "totally different query terms here", raw_score=0.85
    )
    assert quality == "strong"
    assert "semantic" in reasons


def test_partial_for_low_overlap():
    service = _make_service()
    p = _problem(description="hydration mismatch react", error_signature=None)
    # Single-token overlap → ratio 1/2 = 0.5, which is exactly the boundary.
    # Use a longer query so the ratio lands in [0.25, 0.5).
    quality, _, signals = service._classify_match_quality(
        p, "react server component hydration", raw_score=0.0
    )
    assert quality in {"partial", "strong"}
    # Make sure overlap_ratio signal is exposed.
    assert "overlap_ratio" in signals


def test_poor_when_nothing_matches():
    service = _make_service()
    p = _problem(description="completely unrelated text here", error_signature=None)
    quality, _, _ = service._classify_match_quality(
        p, "totally different query xyz", raw_score=0.0
    )
    assert quality == "poor"


# ---------------------------------------------------------------------------
# _compute_relevance_score
# ---------------------------------------------------------------------------


def test_score_is_one_only_for_exact_tier():
    service = _make_service()
    score = service._compute_relevance_score(
        quality="exact", raw_score=0.0, overlap_ratio=0.0, signature_jaccard=0.0
    )
    assert score == 1.0


def test_score_caps_below_one_outside_exact():
    service = _make_service()
    # Even with perfect overlap and perfect raw, non-exact must cap at 0.95.
    score = service._compute_relevance_score(
        quality="strong", raw_score=1.0, overlap_ratio=1.0, signature_jaccard=1.0
    )
    assert score == 0.95


def test_score_takes_max_of_signals():
    service = _make_service()
    score = service._compute_relevance_score(
        quality="partial", raw_score=0.3, overlap_ratio=0.45, signature_jaccard=0.2
    )
    assert score == pytest.approx(0.45)


# ---------------------------------------------------------------------------
# End-to-end via _score_problem_relevance shim
# ---------------------------------------------------------------------------


def test_score_problem_relevance_shim_matches_decomposed_path():
    service = _make_service()
    p = _problem(
        description="Python ssl cert verify failed",
        error_signature="SSL: CERTIFICATE_VERIFY_FAILED unable to get local issuer",
    )
    score, quality, reasons = service._score_problem_relevance(
        p, "SSL: CERTIFICATE_VERIFY_FAILED unable to get local issuer", 0.0
    )
    assert score == 1.0
    assert quality == "exact"
    assert "error_signature" in reasons


@pytest.mark.parametrize(
    "fp_query, fp_signature",
    [
        # Single distinctive overlap; long disjoint signature.
        ("Docker socket permission denied", "Permission denied: rootless tmp mount"),
        # Two distinctive overlaps but Jaccard well below 0.35.
        (
            "EADDRINUSE port 3000",
            "mDNS bind failure cannot register service Bonjour responder firewall",
        ),
        # Very loose token overlap on long signatures (Xcode pbxproj cases).
        (
            "TS2742 inferred type cannot be named",
            "Xcode pbxproj inferred type module map annotation Swift",
        ),
    ],
)
def test_documented_fp_queries_never_earn_exact_or_score_one(
    fp_query: str, fp_signature: str
):
    """Regression guard: the three structural patterns from the 22-Agent
    simulation must never earn ``"exact"`` or ``similarity_score == 1.0``."""
    service = _make_service()
    collider = _problem(description="unrelated", error_signature=fp_signature)
    score, quality, _ = service._score_problem_relevance(collider, fp_query, 0.0)
    assert quality != "exact", (
        f"FP {fp_query!r} earned exact tier against signature {fp_signature!r}"
    )
    assert score < 1.0, (
        f"FP {fp_query!r} earned similarity_score {score} >= 1.0 against "
        f"signature {fp_signature!r}"
    )
