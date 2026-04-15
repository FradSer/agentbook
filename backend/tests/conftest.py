from __future__ import annotations

from contextlib import contextmanager

import pytest

from backend.core.config import settings as app_settings
from backend.core.mcp_rate_limit import mcp_search_limiter, mcp_search_limiter_auth
from backend.core.rate_limit import limiter


@contextmanager
def _disabled(lim):
    original = lim.enabled
    lim.enabled = False
    lim.reset()
    try:
        yield
    finally:
        lim.enabled = original
        lim.reset()


@pytest.fixture(autouse=True)
def isolate_runtime_settings_for_tests() -> None:
    """Run tests against in-memory repositories unless a test overrides settings."""
    original_database_url = app_settings.database_url
    original_openrouter_api_key = app_settings.openrouter_api_key
    original_debug = app_settings.debug
    original_secret_key = app_settings.secret_key

    app_settings.database_url = None
    app_settings.openrouter_api_key = None
    app_settings.debug = True
    app_settings.secret_key = "test-secret-key-for-testing"

    try:
        yield
    finally:
        app_settings.database_url = original_database_url
        app_settings.openrouter_api_key = original_openrouter_api_key
        app_settings.debug = original_debug
        app_settings.secret_key = original_secret_key


@pytest.fixture(autouse=True)
def disable_rate_limiter_by_default():
    """Rate limiter is disabled in tests; tests that exercise it opt in via a fixture."""
    with (
        _disabled(limiter),
        _disabled(mcp_search_limiter),
        _disabled(mcp_search_limiter_auth),
    ):
        yield
