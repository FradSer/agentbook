from __future__ import annotations

import pytest

from app.core.config import settings as app_settings


@pytest.fixture(autouse=True)
def isolate_runtime_settings_for_tests() -> None:
    """Run tests against in-memory repositories unless a test overrides settings."""
    original_database_url = app_settings.database_url
    original_openrouter_api_key = app_settings.openrouter_api_key

    app_settings.database_url = None
    app_settings.openrouter_api_key = None

    try:
        yield
    finally:
        app_settings.database_url = original_database_url
        app_settings.openrouter_api_key = original_openrouter_api_key
