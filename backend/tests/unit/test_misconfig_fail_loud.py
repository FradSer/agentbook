"""Unit tests for the misconfig-fail-loud contract.

Feature: backend/tests/features/misconfig-fail-loud.feature

A Voyage key with EMBEDDING_VERSION=v1 is a 1024-vs-1536 dimension mismatch.
In production it must refuse to boot; in EVERY mode it must emit a loud boot
WARN naming the mismatch instead of silently degrading. And once degraded to a
keyword scan, the per-query response must not keep advertising the
boot-configured dense provider ("voyage") — embedding_provider has to reflect
the mechanism that actually ranked the row.

Tests are hermetic: in-memory repos only, settings mutated under a try/finally
so the autouse isolation fixture's restore still holds.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from uuid import uuid4

import pytest

from backend.application.service import AgentbookService
from backend.core.config import Settings, validate_production_settings
from backend.domain.models import Agent
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)


@contextmanager
def _settings(**overrides):
    """A Settings instance with the given overrides, isolated from env."""
    base = dict(
        debug=False,
        cors_allow_origins="https://app.example.com",
        database_url="postgresql://user:pass@localhost/db",
    )
    base.update(overrides)
    yield Settings(**base)


def _service_with_provider_name(name: str) -> AgentbookService:
    agents = InMemoryAgentRepository()
    agents.add(Agent(api_key_hash="h", model_type="test", agent_id=uuid4()))
    return AgentbookService(
        agents=agents,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
        embedding_provider_name=name,
        rerank_provider_name=name,
    )


# Scenario: v1 plus a Voyage key refuses to boot


def test_v1_plus_voyage_refuses_to_boot_naming_dimension_mismatch() -> None:
    with (
        _settings(voyage_api_key="va-secret", embedding_version="v1") as settings,
        pytest.raises(ValueError) as exc_info,
    ):
        validate_production_settings(settings)
    message = str(exc_info.value)
    assert "1024" in message
    assert "1536" in message


def test_v1_plus_voyage_warns_loud_in_every_mode(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Even outside production (debug=True), the mismatch must WARN loudly.

    Current `main` only hard-raises in production and is silent in debug —
    this assertion is the Red-state failure for the boot-warning contract.
    """
    with (
        caplog.at_level(logging.WARNING),
        _settings(
            debug=True,
            cors_allow_origins="*",
            database_url=None,
            voyage_api_key="va-secret",
            embedding_version="v1",
        ),
    ):
        # Instantiating Settings runs its validators; the loud WARN about
        # the 1024/1536 mismatch must fire even when debug short-circuits
        # the production hard-raise.
        pass
    warned = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.WARNING
    )
    assert "1024" in warned and "1536" in warned, (
        "expected a loud v1+voyage dimension-mismatch WARN in every mode, "
        f"got: {warned!r}"
    )


# Scenario: Provider field reflects the per-query mechanism, not boot config


def test_in_memory_scan_provider_field_is_not_voyage() -> None:
    service = _service_with_provider_name("voyage")
    payload = service.search_problems(query="some unmatched query text", limit=5)
    assert payload["search_mode"] in {"in_memory_scan", "no_match"}
    provider = payload["embedding_provider"]
    assert provider != "voyage", (
        "embedding_provider must reflect the actual ranking mechanism under "
        f"keyword fallback, not the boot-configured name; got {provider!r}"
    )
    assert provider in {"keyword", None}
    assert payload["rerank_provider"] != "voyage"


def test_no_match_provider_field_is_not_voyage() -> None:
    service = _service_with_provider_name("voyage")
    payload = service.search_problems(query="zzz-no-such-problem-anywhere", limit=5)
    assert payload["search_mode"] in {"in_memory_scan", "no_match"}
    assert payload["embedding_provider"] != "voyage"


# Scenario: A consistent v2 / Voyage config boots cleanly


def test_v2_plus_voyage_boots_cleanly() -> None:
    with _settings(voyage_api_key="va-secret", embedding_version="v2") as settings:
        validate_production_settings(settings)  # must not raise
