import asyncio
import importlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4


class DummyAsyncAgent:
    def __init__(self) -> None:
        self.arun_calls = 0

    async def arun(self, _prompt: str):
        self.arun_calls += 1
        return SimpleNamespace(status="COMPLETED", content="ok")


class DrainService:
    def __init__(self) -> None:
        self.thread_fetches = 0

    def get_unreviewed_threads(self, limit: int):
        self.thread_fetches += 1
        if self.thread_fetches == 1:
            return [SimpleNamespace(thread_id=uuid4(), title="valid title", body="valid thread body")]
        return []

    def get_unreviewed_comments(self, limit: int):
        return []

    def update_thread_review(self, **kwargs):
        return None

    def update_comment_review(self, **kwargs):
        return None

    def delete_thread(self, _thread_id):
        return None

    def delete_comment(self, _comment_id):
        return None


class TestAsyncCycle(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

    async def test_review_threads_uses_async_agent(self) -> None:
        main_module = importlib.import_module("agent.src.main")
        service = DrainService()
        agent = DummyAsyncAgent()

        reviewed = await main_module.review_threads(agent, service)

        self.assertEqual(reviewed, 1)
        self.assertEqual(agent.arun_calls, 1)

    async def test_cycle_drains_backlog_before_sleep_boundary(self) -> None:
        main_module = importlib.import_module("agent.src.main")
        service = DrainService()
        agent = DummyAsyncAgent()

        metrics = await main_module.run_cycle_until_idle(agent, service, max_cycle_seconds=10, continue_delay_seconds=0)

        self.assertGreaterEqual(service.thread_fetches, 2)
        self.assertEqual(metrics["processed"], 1)


if __name__ == "__main__":
    unittest.main()
