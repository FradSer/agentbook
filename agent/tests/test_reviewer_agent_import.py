import importlib
import sys
import unittest
from pathlib import Path


class TestReviewerAgentImport(unittest.TestCase):
    def test_module_imports(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        module = importlib.import_module("agent.src.reviewer_agent")
        self.assertTrue(hasattr(module, "create_reviewer_agent"))

    def test_main_module_imports(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        module = importlib.import_module("agent.src.main")
        self.assertTrue(hasattr(module, "main"))

    def test_create_reviewer_agent_builds_agent(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        module = importlib.import_module("agent.src.reviewer_agent")

        class DummyService:
            pass

        agent = module.create_reviewer_agent(DummyService())
        self.assertEqual(agent.name, "ReviewerAgent")


if __name__ == "__main__":
    unittest.main()
