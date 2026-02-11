from __future__ import annotations

import pytest

from app.core.config import settings as app_settings


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
