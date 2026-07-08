"""Unit tests for AgentbookService.compile_campaign_book.

Covers the two paths: (1) LLM synthesizer returns distilled markdown ->
``refined=True`` with the model name; (2) synthesizer unavailable or returns
None -> mechanical fallback labelled "unrefined" with model
"mechanical-fallback". The bundle is a stub; the service just forwards it.
"""

from __future__ import annotations

from backend.application.service import AgentbookService
from backend.domain.models import BookArtifact
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)


class _StubSynthesizer:
    """Minimal BookSynthesizer double."""

    def __init__(self, markdown: str | None, model: str = "stub-model") -> None:
        self._markdown = markdown
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def synthesize(self, bundle: dict) -> str | None:
        return self._markdown


def _service(book_synthesizer=None) -> AgentbookService:
    return AgentbookService(
        agents=InMemoryAgentRepository(),
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(solutions=InMemorySolutionRepository()),
        research_cycles=InMemoryResearchCycleRepository(),
        book_synthesizer=book_synthesizer,
    )


def _bundle() -> dict:
    return {
        "campaign_id": "test-campaign",
        "agents": {"spawned": 3, "completed": 3, "skipped": 0},
        "grounding": [{"_kind": "grounding_confidence", "levers": ["x"]}],
        "published": [
            {
                "problem_id": "p1",
                "title": "a bug",
                "final_content": "the fix",
                "prod_url": "https://example/memories/p1",
                "review_changes_made": "fixed a claim",
            }
        ],
        "verifications": [
            {"solution_id": "s1", "verdict": "confirmed_success", "summary": "ok"}
        ],
        "incidents": ["06:00 RATE_LIMITED at s1"],
    }


def test_compile_book_refined_when_llm_returns_markdown():
    synth = _StubSynthesizer(markdown="# distilled book\n...")
    service = _service(book_synthesizer=synth)
    artifact = service.compile_campaign_book(_bundle())
    assert isinstance(artifact, BookArtifact)
    assert artifact.refined is True
    assert artifact.markdown == "# distilled book\n..."
    assert artifact.model == "stub-model"
    assert artifact.campaign_id == "test-campaign"
    assert artifact.source_count == 3


def test_compile_book_mechanical_fallback_when_llm_returns_none():
    synth = _StubSynthesizer(markdown=None)
    service = _service(book_synthesizer=synth)
    artifact = service.compile_campaign_book(_bundle())
    assert artifact.refined is False
    assert artifact.model == "mechanical-fallback"
    assert "UNREFINED" in artifact.markdown
    assert "the fix" in artifact.markdown  # final_content rendered
    assert "confirmed_success" in artifact.markdown  # verification rendered


def test_compile_book_mechanical_fallback_when_no_synthesizer():
    service = _service(book_synthesizer=None)
    artifact = service.compile_campaign_book(_bundle())
    assert artifact.refined is False
    assert artifact.model == "mechanical-fallback"
    assert "UNREFINED" in artifact.markdown


def test_compile_book_malformed_bundle_does_not_crash_mechanical_fallback():
    """The mechanical fallback must never crash on None/missing fields —
    it is the error-recovery path, so a malformed bundle degrades honestly."""
    service = _service(book_synthesizer=None)
    artifact = service.compile_campaign_book(
        {
            "campaign_id": "malformed",
            "agents": None,  # None, not a dict
            "grounding": [None, "not a dict", {"_kind": "g", "levers": None}],
            "published": [
                {"title": None, "problem_id": "p1"},  # title present but None
                "not a dict",
                {"final_content": None, "review_changes_made": None},
            ],
            "verifications": [{"solution_id": None, "verdict": None, "summary": None}],
            "incidents": None,
        }
    )
    assert artifact.refined is False
    assert "UNREFINED" in artifact.markdown
    assert "p1" in artifact.markdown  # fell through None title -> problem_id
    assert artifact.source_count == 0  # agents=None -> 0, no crash
