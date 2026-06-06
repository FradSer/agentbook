"""Simulation tests: multi-agent Agentbook usage against a real database."""

from __future__ import annotations

import os

import pytest

from backend.presentation.mcp.context import (
    current_agent as _current_agent_ctx,
    current_remote_addr as _current_remote_addr_ctx,
)

pytest_plugins = ["backend.tests.postgres_fixtures"]


@pytest.fixture(autouse=True)
def _reset_mcp_context():
    agent_token = _current_agent_ctx.set(None)
    addr_token = _current_remote_addr_ctx.set(None)
    try:
        yield
    finally:
        _current_remote_addr_ctx.reset(addr_token)
        _current_agent_ctx.reset(agent_token)


@pytest.fixture(autouse=True)
def _integration_database_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore DATABASE_URL when Postgres simulation tests opt in via skipif."""
    if not os.getenv("RUN_DOCKER_TESTS"):
        return
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL must be set for simulation tests")
    from backend.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "database_url", url)


@pytest.fixture()
def postgres_service_client(postgres_service_bundle):
    """Alias used by simulation tests: ``(TestClient, AgentbookService)``."""
    return postgres_service_bundle
