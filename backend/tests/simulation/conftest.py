"""Simulation tests: multi-agent Agentbook usage against a real database."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from backend.presentation.mcp.context import current_agent as _current_agent_ctx
from backend.presentation.mcp.context import (
    current_remote_addr as _current_remote_addr_ctx,
)

collect_ignore_glob: list[str] = []

if not os.getenv("RUN_DOCKER_TESTS"):
    collect_ignore_glob = ["test_*.py"]


@pytest.fixture(autouse=True)
def _reset_mcp_context():
    agent_token = _current_agent_ctx.set(None)
    addr_token = _current_remote_addr_ctx.set(None)
    try:
        yield
    finally:
        _current_remote_addr_ctx.reset(addr_token)
        _current_agent_ctx.reset(agent_token)


@pytest.fixture()
def postgres_service_client():
    """HTTP client backed by an isolated Postgres transaction (savepoint mode)."""
    from contextlib import contextmanager

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

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

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is not set")

    # Root unit-test conftest forces ``settings.database_url = None`` before
    # fixtures run, so the module-level ``database.engine`` may be ``None`` even
    # when DATABASE_URL is exported for integration runs.
    engine = create_engine(database_url, pool_pre_ping=True)

    with engine.connect() as conn:
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
