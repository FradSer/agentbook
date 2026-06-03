"""Integration test configuration and shared fixtures."""

from __future__ import annotations

import os

import pytest

collect_ignore_glob: list[str] = []

if not os.getenv("RUN_DOCKER_TESTS"):
    collect_ignore_glob = ["test_*.py"]


@pytest.fixture(autouse=True)
def _integration_database_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Root conftest clears ``database_url`` for unit tests; restore it for integration."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL must be set for integration tests")
    from backend.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "database_url", url)


@pytest.fixture()
def client():
    """Real-DB FastAPI client with per-test rollback isolation."""
    from contextlib import contextmanager

    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from backend.application.service import AgentbookService
    from backend.core.config import settings as app_settings
    from backend.infrastructure.embeddings.fallback import FallbackEmbeddingProvider
    from backend.infrastructure.persistence.sqlalchemy_repositories import (
        SQLAlchemyAgentRepository,
        SQLAlchemyOutcomeRepository,
        SQLAlchemyProblemRepository,
        SQLAlchemyResearchCycleRepository,
        SQLAlchemySolutionRepository,
    )
    from backend.main import create_app

    test_engine = create_engine(app_settings.database_url, pool_pre_ping=True)
    with test_engine.connect() as conn:
        trans = conn.begin()
        sess = Session(bind=conn, join_transaction_mode="create_savepoint")

        @contextmanager
        def factory():
            yield sess

        service = AgentbookService(
            agents=SQLAlchemyAgentRepository(factory),
            embedding_provider=FallbackEmbeddingProvider(),
            problems=SQLAlchemyProblemRepository(factory),
            solutions=SQLAlchemySolutionRepository(factory),
            outcomes=SQLAlchemyOutcomeRepository(factory),
            research_cycles=SQLAlchemyResearchCycleRepository(factory),
        )
        app = create_app()
        app.state.service = service
        try:
            yield TestClient(app)
        finally:
            sess.close()
            trans.rollback()
    test_engine.dispose()
