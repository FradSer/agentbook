import importlib
import unittest
from types import SimpleNamespace
from uuid import uuid4


class DummySyncAgent:
    def __init__(self) -> None:
        self.run_calls = 0

    def run(self, _prompt: str):
        self.run_calls += 1
        return SimpleNamespace(status="COMPLETED", content="ok")


class DrainService:
    def __init__(self) -> None:
        self.problem_fetches = 0

    def get_unreviewed_problems(self, limit: int):
        self.problem_fetches += 1
        if self.problem_fetches == 1:
            return [
                SimpleNamespace(
                    problem_id=uuid4(),
                    description="valid problem description that is long enough",
                )
            ]
        return []

    def get_unreviewed_solutions(self, limit: int):
        return []

    def update_review(self, **kwargs):
        return None


class TestAsyncCycle(unittest.IsolatedAsyncioTestCase):
    async def test_cycle_drains_backlog_before_sleep_boundary(self) -> None:
        main_module = importlib.import_module("agent.src.main")
        service = DrainService()
        agent = DummySyncAgent()

        metrics = await main_module.run_cycle_until_idle(
            agent, service, max_cycle_seconds=10, continue_delay_seconds=0
        )

        self.assertGreaterEqual(service.problem_fetches, 2)
        self.assertEqual(metrics["processed"], 1)
