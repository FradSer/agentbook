"""Integration test configuration and shared fixtures."""

from __future__ import annotations

import os

import pytest

pytest_plugins = ["backend.tests.postgres_fixtures"]

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
def client(postgres_service_bundle):
    """Real-DB FastAPI client with per-test rollback isolation."""
    test_client, _service = postgres_service_bundle
    return test_client
