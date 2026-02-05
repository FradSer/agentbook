import importlib
import sys
import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4


class DummyService:
    def __init__(self) -> None:
        self.thread_updates = []

    def get_unreviewed_threads(self, limit: int):
        return [
            SimpleNamespace(
                thread_id=uuid4(),
                title="valid title",
                body="valid thread body",
            )
        ]

    def update_thread_review(self, **kwargs):
        self.thread_updates.append(kwargs)

    def delete_thread(self, _thread_id):
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

        self.assertEqual(len(tool_builders), 4)
        result = tool_builders[0].entrypoint(
            thread_id=str(uuid4()),
            score=6.0,
            reason="ok",
        )

        self.assertIn("approved", result)

    def test_review_threads_marks_error_status_when_agent_run_fails(self) -> None:
        main_module = importlib.import_module("agent.src.main")
        service = DummyService()

        asyncio.run(main_module.review_threads(DummyErrorAgent(), service))

        self.assertEqual(len(service.thread_updates), 1)
        self.assertEqual(service.thread_updates[0]["status"], "error")

    def test_pgvector_is_available_in_agent_runtime(self) -> None:
        sqlalchemy_models = importlib.import_module("app.infrastructure.persistence.sqlalchemy_models")
        self.assertIsNotNone(sqlalchemy_models.Vector)


if __name__ == "__main__":
    unittest.main()
