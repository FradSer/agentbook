"""Configuration validation tests.

Covers:
- Secret key enforcement in production vs debug mode
- Permissive CORS triggers warning in production
"""

import logging

import pytest

from backend.core.config import Settings, validate_production_settings


class TestSecretKeyValidation:
    """Test secret key validation in different environments."""

    def test_app_starts_with_secret_key_in_production_mode(self, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "secure-key")
        monkeypatch.setenv("DEBUG", "false")

        settings = Settings()
        assert settings.secret_key == "secure-key"
        assert settings.debug is False
        validate_production_settings(settings)

    def test_app_fails_without_secret_key_in_production(self, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "")
        monkeypatch.setenv("DEBUG", "false")

        settings = Settings()
        with pytest.raises(ValueError, match="(?i)secret_key"):
            validate_production_settings(settings)

    def test_app_allows_missing_secret_key_in_debug_mode(self, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "")
        monkeypatch.setenv("DEBUG", "true")

        settings = Settings()
        validate_production_settings(settings)
        assert settings.secret_key == ""
        assert settings.debug is True


class TestCorsWarning:
    """Test CORS warning in different environments."""

    def test_permissive_cors_triggers_warning_in_production(self, monkeypatch, caplog):
        monkeypatch.setenv("CORS_ALLOW_ORIGINS", "*")
        monkeypatch.setenv("DEBUG", "false")

        with caplog.at_level(logging.WARNING):
            settings = Settings()
            assert settings.cors_allow_origins == "*"

        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("CORS_ALLOW_ORIGINS" in str(msg) for msg in warning_messages), (
            f"Expected CORS warning, but got: {warning_messages}"
        )

    def test_permissive_cors_no_warning_in_debug_mode(self, monkeypatch, caplog):
        monkeypatch.setenv("CORS_ALLOW_ORIGINS", "*")
        monkeypatch.setenv("DEBUG", "true")

        with caplog.at_level(logging.WARNING):
            settings = Settings()
            assert settings.cors_allow_origins == "*"

        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        cors_warnings = [
            msg for msg in warning_messages if "CORS_ALLOW_ORIGINS" in str(msg)
        ]
        assert len(cors_warnings) == 0, (
            f"Expected no CORS warning in debug mode, but got: {cors_warnings}"
        )
