import importlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from uuid import uuid4


class DummyService:
    def __init__(self) -> None:
        self.thread_updates = []

    def get_unreviewed_threads(self, limit: int, retry_error_before=None):
        return [
            SimpleNamespace(
                thread_id=uuid4(),
                title="valid title",
                body="valid thread body",
            )
        ]

    def update_thread_review(self, **kwargs):
        self.thread_updates.append(kwargs)

    def update_review(self, **kwargs):
        self.thread_updates.append(kwargs)

    def delete_thread(self, _thread_id):
        return None

    def delete_content(self, _content_id):
        return None


class DummyErrorAgent:
    async def arun(self, _prompt: str):
        return SimpleNamespace(status="ERROR", content="Provider returned error")


class TestAgentRuntimeRegressions(unittest.TestCase):
    def setUp(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

    def test_get_reviewer_tools_returns_callable_tools(self) -> None:
        tools_module = importlib.import_module("agent.src.tools")
        tool_builders = tools_module.get_reviewer_tools(DummyService())

        self.assertEqual(len(tool_builders), 2)
        result = tool_builders[0].entrypoint(
            content_id=str(uuid4()),
            reason="ok",
        )

        self.assertIn("approved", result)

    def test_pgvector_is_available_in_agent_runtime(self) -> None:
        sqlalchemy_models = importlib.import_module(
            "backend.infrastructure.persistence.sqlalchemy_models"
        )
        self.assertIsNotNone(sqlalchemy_models.Vector)

    def test_main_exits_when_openrouter_api_key_missing(self) -> None:
        main_module = importlib.import_module("agent.src.main")
        original_database_url = main_module.settings.database_url
        original_openrouter_api_key = main_module.settings.openrouter_api_key
        main_module.settings.database_url = "postgresql://example"
        main_module.settings.openrouter_api_key = None

        try:
            with mock.patch.object(main_module, "create_engine") as create_engine_mock:
                main_module.main()
            create_engine_mock.assert_not_called()
        finally:
            main_module.settings.database_url = original_database_url
            main_module.settings.openrouter_api_key = original_openrouter_api_key


if __name__ == "__main__":
    unittest.main()
