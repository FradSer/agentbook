"""Tests for configuration validation.

BDD Scenarios:
- Application starts with secret key in production mode
- Application fails without secret key in production
- Application allows missing secret key in debug mode
- Application starts with specific secret key
- Permissive CORS triggers warning in production
"""

import logging
import os

import pytest

from backend.core.config import Settings, validate_production_settings


class TestSecretKeyValidation:
    """Test secret key validation in different environments."""

    def test_app_starts_with_secret_key_in_production_mode(self):
        """Test app starts with secret key in production mode.

        BDD: Given SECRET_KEY=secure-key and DEBUG=false
              When Settings is initialized and validated
              Then it initializes without error

        RED PHASE: This test FAILS because "secure-key" is only 10 chars,
        but production requires 32+ characters.
        """
        original_key = os.environ.get("SECRET_KEY")
        original_debug = os.environ.get("DEBUG")

        os.environ["SECRET_KEY"] = "secure-key"
        os.environ["DEBUG"] = "false"

        try:
            settings = Settings()
            assert settings.secret_key == "secure-key"
            assert settings.debug is False
            # This should fail due to insufficient key length
            validate_production_settings(settings)
        finally:
            if original_key is None:
                os.environ.pop("SECRET_KEY", None)
            else:
                os.environ["SECRET_KEY"] = original_key

            if original_debug is None:
                os.environ.pop("DEBUG", None)
            else:
                os.environ["DEBUG"] = original_debug

    def test_app_fails_without_secret_key_in_production(self):
        """Test app fails without secret key in production.

        BDD: Given SECRET_KEY="" and DEBUG=false
              When Settings is initialized and validated
              Then it raises ValueError with message containing "SECRET_KEY"
        """
        original_key = os.environ.get("SECRET_KEY")
        original_debug = os.environ.get("DEBUG")

        os.environ["SECRET_KEY"] = ""
        os.environ["DEBUG"] = "false"

        try:
            settings = Settings()
            with pytest.raises(ValueError) as exc_info:
                validate_production_settings(settings)

            assert "secret_key" in str(exc_info.value).lower()
        finally:
            if original_key is None:
                os.environ.pop("SECRET_KEY", None)
            else:
                os.environ["SECRET_KEY"] = original_key

            if original_debug is None:
                os.environ.pop("DEBUG", None)
            else:
                os.environ["DEBUG"] = original_debug

    def test_app_allows_missing_secret_key_in_debug_mode(self):
        """Test app allows missing secret key in debug mode.

        BDD: Given SECRET_KEY="" and DEBUG=true
              When Settings is initialized and validated
              Then it initializes without error
        """
        original_key = os.environ.get("SECRET_KEY")
        original_debug = os.environ.get("DEBUG")

        os.environ["SECRET_KEY"] = ""
        os.environ["DEBUG"] = "true"

        try:
            settings = Settings()
            validate_production_settings(settings)
            assert settings.secret_key == ""
            assert settings.debug is True
        finally:
            if original_key is None:
                os.environ.pop("SECRET_KEY", None)
            else:
                os.environ["SECRET_KEY"] = original_key

            if original_debug is None:
                os.environ.pop("DEBUG", None)
            else:
                os.environ["DEBUG"] = original_debug

    def test_app_starts_with_specific_secret_key(self):
        """Test app starts with specific secret key.

        BDD: Given SECRET_KEY=my-custom-key
              When Settings is initialized and validated in production
              Then settings.secret_key == "my-custom-key"

        RED PHASE: This test FAILS because "my-custom-key" is only 13 chars,
        but production requires 32+ characters.
        """
        original_key = os.environ.get("SECRET_KEY")
        original_debug = os.environ.get("DEBUG")

        os.environ["SECRET_KEY"] = "my-custom-key"
        os.environ["DEBUG"] = "false"

        try:
            settings = Settings()
            assert settings.secret_key == "my-custom-key"
            # This should fail due to insufficient key length
            validate_production_settings(settings)
        finally:
            if original_key is None:
                os.environ.pop("SECRET_KEY", None)
            else:
                os.environ["SECRET_KEY"] = original_key

            if original_debug is None:
                os.environ.pop("DEBUG", None)
            else:
                os.environ["DEBUG"] = original_debug


class TestCorsWarning:
    """Test CORS warning in different environments."""

    def test_permissive_cors_triggers_warning_in_production(self, caplog):
        """Test permissive CORS triggers warning in production.

        BDD: Given CORS_ALLOW_ORIGINS='*' and DEBUG=false
              When Settings is initialized
              Then it logs a warning about permissive CORS

        GREEN PHASE: The model_validator emits a warning via logger.warning.
        This test uses caplog fixture to capture and verify the warning.
        """
        original_cors = os.environ.get("CORS_ALLOW_ORIGINS")
        original_debug = os.environ.get("DEBUG")

        os.environ["CORS_ALLOW_ORIGINS"] = "*"
        os.environ["DEBUG"] = "false"

        try:
            from backend.core.config import Settings

            with caplog.at_level(logging.WARNING):
                settings = Settings()
                assert settings.cors_allow_origins == "*"

            # Verify warning was logged
            warning_messages = [
                r.message for r in caplog.records if r.levelno == logging.WARNING
            ]
            assert any("CORS_ALLOW_ORIGINS" in str(msg) for msg in warning_messages), (
                f"Expected CORS warning, but got: {warning_messages}"
            )
        finally:
            if original_cors is None:
                os.environ.pop("CORS_ALLOW_ORIGINS", None)
            else:
                os.environ["CORS_ALLOW_ORIGINS"] = original_cors

            if original_debug is None:
                os.environ.pop("DEBUG", None)
            else:
                os.environ["DEBUG"] = original_debug

    def test_permissive_cors_no_warning_in_debug_mode(self, caplog):
        """Test permissive CORS does not trigger warning in debug mode.

        BDD: Given CORS_ALLOW_ORIGINS='*' and DEBUG=true
              When Settings is initialized
              Then it does NOT log a warning about permissive CORS
        """
        original_cors = os.environ.get("CORS_ALLOW_ORIGINS")
        original_debug = os.environ.get("DEBUG")

        os.environ["CORS_ALLOW_ORIGINS"] = "*"
        os.environ["DEBUG"] = "true"

        try:
            from backend.core.config import Settings

            with caplog.at_level(logging.WARNING):
                settings = Settings()
                assert settings.cors_allow_origins == "*"

            # Verify no CORS warning was logged
            warning_messages = [
                r.message for r in caplog.records if r.levelno == logging.WARNING
            ]
            cors_warnings = [
                msg for msg in warning_messages if "CORS_ALLOW_ORIGINS" in str(msg)
            ]
            assert len(cors_warnings) == 0, (
                f"Expected no CORS warning in debug mode, but got: {cors_warnings}"
            )
        finally:
            if original_cors is None:
                os.environ.pop("CORS_ALLOW_ORIGINS", None)
            else:
                os.environ["CORS_ALLOW_ORIGINS"] = original_cors

            if original_debug is None:
                os.environ.pop("DEBUG", None)
            else:
                os.environ["DEBUG"] = original_debug
