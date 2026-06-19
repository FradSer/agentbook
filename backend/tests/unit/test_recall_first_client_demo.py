"""The recall_first_client self-demo entrypoint stays runnable and readable.

The read-only `python examples/recall_first_client.py "<error>"` demo is the
fastest adoption check (anonymous recall, no key). These tests pin that it
exits cleanly and prints an actionable hit / an honest miss, so the "adopt in
minutes" path cannot silently regress.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_EXAMPLES = Path(__file__).resolve().parents[3] / "examples" / "recall_first_client.py"


def _load_client_module():
    spec = importlib.util.spec_from_file_location("_recall_first_client", _EXAMPLES)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_recall_first_client"] = module
    spec.loader.exec_module(module)
    return module


def _capture(capsys):
    captured = capsys.readouterr()
    return captured.out


def test_demo_prints_actionable_hit(capsys, monkeypatch):
    module = _load_client_module()

    class _FakeRecalled:
        match_quality = "strong"
        confidence = 0.3
        solution_id = "sol-123"
        root_cause_pattern = "musl libc missing C-extension build deps"
        localization_cues = ["Dockerfile FROM line", "apk add output"]
        verification = [{"command": "docker build .", "expected": "succeeds"}]
        steps = ["switch base to python:3.11-slim", "or apk add gcc musl-dev"]
        content = "Switch FROM python:3.11-alpine to python:3.11-slim."

    monkeypatch.setattr(
        module.AgentbookClient,
        "recall",
        lambda self, q, **kw: _FakeRecalled(),
    )
    rc = module._demo(["prog", "ModuleNotFoundError uvicorn alpine"])
    out = _capture(capsys)
    assert rc == 0
    assert "strong-match" in out
    assert "sol-123" in out
    assert "musl libc" in out
    assert "1. switch base to python:3.11-slim" in out


def test_demo_prints_honest_miss(capsys, monkeypatch):
    module = _load_client_module()
    monkeypatch.setattr(module.AgentbookClient, "recall", lambda self, q, **kw: None)
    rc = module._demo(["prog", "some novel error nobody hit yet"])
    out = _capture(capsys)
    assert rc == 0
    assert "no actionable match" in out
    assert "miss" in out.lower()


def test_demo_default_query_when_none_given(capsys, monkeypatch):
    module = _load_client_module()
    seen = {}

    def _recall(self, q, **kw):
        seen["q"] = q
        return None

    monkeypatch.setattr(module.AgentbookClient, "recall", _recall)
    module._demo(["prog"])
    assert seen["q"]  # fell back to the default demo query, not empty
