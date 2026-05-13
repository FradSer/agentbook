"""Verifies the contract in features/search_mode_disclosure.feature.

The historical failure mode: pgvector silently unavailable on Railway,
``SQLAlchemyProblemRepository.find_hybrid`` returns ``[]``,
``AgentbookService._search_problems`` falls through to an in-process
keyword scan, and the response shape is identical to a fully-vector
ranked one. Calling agents and monitoring see no signal.

These tests pin:
- ``ProblemRepository.find_hybrid_with_diagnostics`` returning a
  ``SearchDiagnostics`` carrier alongside the rows.
- ``AgentbookService.search_problems`` deriving a ``search_mode`` field
  on the response from those diagnostics + the keyword-fallback path.
- ``MCP recall`` propagating the same field.
- ``GET /v1/health-metrics`` exposing ``pgvector_available`` /
  ``search_backend`` so operators can correlate degraded modes with
  infrastructure state.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from mcp.server import Server

from backend.application.service import AgentbookService
from backend.domain.models import Problem
from backend.domain.search import SearchDiagnostics
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)
from backend.presentation.mcp.context import current_remote_addr
from backend.presentation.mcp.tools import dispatch_tool


def _problem(description: str, embedding: list[float] | None = None) -> Problem:
    return Problem(
        problem_id=uuid4(),
        author_id=uuid4(),
        description=description,
        embedding=embedding,
        created_at=datetime.now(UTC),
        last_activity_at=datetime.now(UTC),
        review_status="approved",
    )


def _service_with(problems: InMemoryProblemRepository) -> AgentbookService:
    return AgentbookService(
        agents=InMemoryAgentRepository(),
        problems=problems,
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )


# ---------------------------------------------------------------------------
# Repo-layer diagnostics carrier.
# ---------------------------------------------------------------------------


class TestSearchDiagnosticsCarrier:
    def test_in_memory_repo_reports_memory_backend(self) -> None:
        repo = InMemoryProblemRepository()
        repo.add(_problem("alpha bravo", embedding=[1.0, 0.0]))
        results, diag = repo.find_hybrid_with_diagnostics(
            query_embedding=[1.0, 0.0],
            query_text="alpha",
            limit=5,
        )
        assert results
        assert isinstance(diag, SearchDiagnostics)
        assert diag.backend == "memory"
        assert diag.pgvector_available is False
        assert diag.dense_hits >= 1
        assert diag.sparse_hits >= 1

    def test_in_memory_repo_reports_zero_dense_when_no_embedding_query(self) -> None:
        repo = InMemoryProblemRepository()
        repo.add(_problem("only lexical token here"))
        _, diag = repo.find_hybrid_with_diagnostics(
            query_embedding=None,
            query_text="lexical",
            limit=5,
        )
        assert diag.dense_hits == 0
        assert diag.sparse_hits >= 1


# ---------------------------------------------------------------------------
# Service-layer search_mode derivation on the response payload.
# ---------------------------------------------------------------------------


class TestServiceSearchModeOnResponse:
    def test_in_memory_corpus_returns_in_memory_scan(self) -> None:
        problems = InMemoryProblemRepository()
        problems.add(_problem("docker python module not found"))
        service = _service_with(problems)
        payload = service.search_problems(query="docker", limit=5)
        assert payload["search_mode"] == "in_memory_scan"

    def test_no_match_anywhere_returns_no_match(self) -> None:
        problems = InMemoryProblemRepository()
        problems.add(_problem("alpha bravo charlie"))
        service = _service_with(problems)
        payload = service.search_problems(query="zzz_nothing_matches_zzz", limit=5)
        assert payload["results"] == []
        assert payload["search_mode"] == "no_match"

    def test_keyword_fallback_path_labels_correctly(self) -> None:
        """Scenario: hybrid + vector return empty, but the in-process
        keyword scan in service._search_problems still finds a substring match.

        We force this by stubbing find_hybrid_with_diagnostics + find_similar_scored
        to return empty so the fallback fires.
        """
        problems = InMemoryProblemRepository()
        target = _problem("substring matches only via fallback scan")
        problems.add(target)
        service = _service_with(problems)

        # Stub the hybrid + scored calls so the in-process keyword scan is
        # the only branch that can recover the row.
        problems.find_hybrid_with_diagnostics = lambda **kw: (  # type: ignore[method-assign]
            [],
            SearchDiagnostics(
                backend="postgres",
                pgvector_available=True,
                dense_hits=0,
                sparse_hits=0,
            ),
        )
        problems.find_similar_scored = lambda **kw: []  # type: ignore[method-assign]
        # find_similar_scored signature is positional in service: pass-through
        problems.find_similar_scored = lambda emb: []  # type: ignore[method-assign]

        payload = service.search_problems(query="substring", limit=5)
        assert payload["results"], "keyword-fallback scan should still find the row"
        assert payload["search_mode"] == "keyword_fallback"


# ---------------------------------------------------------------------------
# Presentation: MCP recall and /v1/health-metrics expose the signal too.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mcp_recall_payload_includes_search_mode() -> None:
    service = MagicMock()
    service.search_problems.return_value = {
        "results": [],
        "total": 0,
        "no_good_match": True,
        "search_mode": "in_memory_scan",
    }
    server = Server("search-mode-test")
    server._service = service
    current_remote_addr.set("198.51.100.1")

    result = await dispatch_tool(server, "recall", {"query": "x"})
    payload = json.loads(result[0]["text"])
    assert payload["search_mode"] == "in_memory_scan"


def test_health_metrics_exposes_pgvector_availability_and_backend() -> None:
    from backend.tests.conftest import _build_client

    client, _ = _build_client()
    resp = client.get("/v1/health-metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert "pgvector_available" in body
    assert isinstance(body["pgvector_available"], bool)
    assert body["search_backend"] in {"postgres", "memory"}
