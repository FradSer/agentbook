"""Good-arm prompt formatting includes RAG steps."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_client():
    ab_root = Path(__file__).resolve().parents[3] / "experiments" / "agentbook-ab"
    sys.path.insert(0, str(ab_root))
    path = ab_root / "benchmark" / "agentbook_client.py"
    spec = importlib.util.spec_from_file_location("agentbook_client", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["agentbook_client"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_format_recall_includes_steps_from_best_solution() -> None:
    mod = _load_client()
    payload = {
        "results": [
            {
                "match_quality": "exact",
                "similarity_score": 0.99,
                "description_preview": "geometry Point mul bug",
                "tags": ["sympy", "ab_task:sympy__sympy-17655"],
                "best_solution": {
                    "solution_id": "abc",
                    "confidence": 0.3,
                    "content_preview": "Fix sympy/geometry/point.py __mul__",
                    "steps": ["Open point.py", "Patch __mul__"],
                },
            }
        ]
    }
    text = mod.format_recall_for_prompt(payload)
    assert "**Steps:**" in text
    assert "Open point.py" in text
    assert "live GET /v1/search" in text


def test_format_recall_falls_back_to_solutions_steps() -> None:
    mod = _load_client()
    payload = {
        "results": [
            {
                "match_quality": "exact",
                "similarity_score": 0.95,
                "description_preview": "bug",
                "tags": [],
                "best_solution": {
                    "solution_id": "x",
                    "confidence": 0.3,
                    "content_preview": "content",
                    "steps": [],
                },
                "solutions": [{"content": "c", "steps": ["Step one"]}],
            }
        ]
    }
    text = mod.format_recall_for_prompt(payload)
    assert "Step one" in text
