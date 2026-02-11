"""Tests for agent session management.

BDD Scenarios:
- Session is closed after successful cycle
- Session is closed on error (context manager behavior)
- Session is committed on success

This tests the main loop's session management using SQLAlchemy context managers.
"""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from unittest.mock import MagicMock


def _setup_path() -> None:
    """Add project root to sys.path."""
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


class DummyAgent:
    """Mock agent for testing."""

    def run(self, _prompt: str):
        return SimpleNamespace(status="OK", content="Approved")


class TestSessionManagement:
    """Test SQLAlchemy session management in agent main loop.

    BDD: SQLAlchemy sessions are properly managed

    Tests verify:
    1. Session is created and committed per cycle
    2. Session context manager properly closes sessions
    """

    def setup_method(self) -> None:
        """Set up test environment."""
        _setup_path()

    def test_main_loop_session_management(self) -> None:
        """Test main loop properly creates and manages sessions per cycle.

        BDD: Session is closed after successful cycle

        Verifies that:
        - Session.__enter__ is called (context manager enters)
        - Session.__exit__ is called (context manager exits)
        - Session.close is called (via __exit__)
        - Session.commit is called (after successful cycle)
        """
        main_module = importlib.import_module("agent.src.main")

        # Mock settings to avoid database URL errors
        original_db_url = main_module.settings.database_url
        original_api_key = main_module.settings.openrouter_api_key
        main_module.settings.database_url = "postgresql://test"
        main_module.settings.openrouter_api_key = "test-key"

        try:
            # Track session creation and closure
            session_instances = []

            def mock_session_factory():
                session = MagicMock()
                session.commit = MagicMock()
                session.close = MagicMock()
                session.__enter__ = MagicMock(return_value=session)

                def mock_exit(*args):
                    session.close()

                session.__exit__.side_effect = mock_exit
                session_instances.append(session)
                return session

            with (
                mock.patch("agent.src.main.create_engine") as mock_engine,
                mock.patch("agent.src.main.sessionmaker") as mock_maker,
                mock.patch("agent.src.main.create_reviewer_agent") as mock_agent,
            ):
                # Setup mocks
                mock_maker.return_value = mock_session_factory
                mock_agent.return_value = DummyAgent()
                mock_engine.return_value = MagicMock()

                # Run one cycle then exit
                with mock.patch("agent.src.main.run_cycle_until_idle") as mock_cycle:
                            mock_cycle.return_value = {
                                "processed": 0,
                                "iterations": 1,
                                "elapsed_seconds": 0.1,
                                "drained": True,
                            }

                            # Patch time.sleep to exit immediately
                            with mock.patch("agent.src.main.time.sleep", side_effect=KeyboardInterrupt):
                                main_module.main()

            # Verify session lifecycle
            assert len(session_instances) >= 1, (
                "At least one session should be created per cycle"
            )
            for session in session_instances:
                session.__enter__.assert_called()
                session.__exit__.assert_called()
                session.close.assert_called()
                session.commit.assert_called()

        finally:
            main_module.settings.database_url = original_db_url
            main_module.settings.openrouter_api_key = original_api_key


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])