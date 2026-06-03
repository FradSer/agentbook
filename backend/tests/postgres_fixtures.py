"""Shared PostgreSQL test fixtures for integration and simulation suites."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from backend.application.service import AgentbookService


def require_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL must be set for Postgres tests")
    return url


@pytest.fixture()
def postgres_service_bundle() -> tuple[TestClient, AgentbookService]:
    """FastAPI client and service sharing one rolled-back Postgres transaction."""
    from backend.application.service import AgentbookService
    from backend.infrastructure.embeddings.fallback import FallbackEmbeddingProvider
    from backend.infrastructure.persistence.sqlalchemy_repositories import (
        SQLAlchemyAgentRepository,
        SQLAlchemyOutcomeRepository,
        SQLAlchemyProblemRepository,
        SQLAlchemyResearchCycleRepository,
        SQLAlchemySolutionRepository,
    )
    from backend.main import create_app

    database_url = require_database_url()
    test_engine = create_engine(database_url, pool_pre_ping=True)
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
            yield TestClient(app), service
        finally:
            sess.close()
            trans.rollback()
    test_engine.dispose()
