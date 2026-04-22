"""Tests for agent session management (SQLAlchemy context managers)."""

import importlib
from types import SimpleNamespace
from unittest import mock
from unittest.mock import AsyncMock, MagicMock


class DummyAgent:
    """Mock agent for testing."""

    def run(self, _prompt: str):
        return SimpleNamespace(status="OK", content="Approved")


class TestSessionManagement:
    """Test SQLAlchemy session management in agent main loop."""

    def test_main_loop_session_management(self) -> None:
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
                mock.patch("agent.src.main.create_service") as mock_create_service,
                mock.patch("agent.src.main.create_reviewer_agent") as mock_agent,
                mock.patch("agent.src.main.create_researcher_agent"),
                mock.patch(
                    "agent.src.main.run_research_cycle",
                    new=AsyncMock(
                        return_value={
                            "candidates": 0,
                            "improved": 0,
                            "no_improvement": 0,
                        }
                    ),
                ),
                mock.patch(
                    "agent.src.main.run_cycle_until_idle",
                    new=AsyncMock(
                        return_value={
                            "processed": 0,
                            "iterations": 1,
                            "elapsed_seconds": 0.1,
                            "drained": True,
                        }
                    ),
                ),
            ):
                # Setup mocks
                mock_maker.return_value = mock_session_factory
                mock_agent.return_value = DummyAgent()
                mock_engine.return_value = MagicMock()
                mock_create_service.return_value = MagicMock()
                mock_create_service.return_value._agents.get.return_value = None

                # Patch time.sleep to exit immediately after one cycle
                with mock.patch(
                    "agent.src.main.time.sleep", side_effect=KeyboardInterrupt
                ):
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
