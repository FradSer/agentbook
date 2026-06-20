"""Pyodide WASM sandbox runner: key-free, self-hosted isolation.

The pyodide backend runs untrusted Python in a WASM linear-memory boundary via
a Node subprocess — no Docker daemon, no privileged container, no third-party
API key. These tests pin the runner's stdin/stdout JSON protocol (the Python
server `_run_pyodide` shells out to it), without requiring the actual WASM
runtime (mocked subprocess).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

_SVC = Path(__file__).resolve().parents[3] / "sandbox_service" / "server.py"


def _load():
    spec = importlib.util.spec_from_file_location("_sandbox_svc_pyodide", _SVC)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_sandbox_svc_pyodide"] = module
    spec.loader.exec_module(module)
    return module


_MODULE = _load()


def test_run_pyodide_parses_runner_json_output():
    fake_runner_out = json.dumps(
        {
            "success": True,
            "exit_code": 0,
            "stdout": "42\n",
            "stderr": "",
            "duration_seconds": 0.5,
        }
    )

    class _FakeProc:
        def communicate(self, input=None, timeout=None):
            return (fake_runner_out, "")

    with patch("subprocess.Popen", return_value=_FakeProc()):
        result = _MODULE._run_pyodide("print(6*7)", 30)

    assert result["success"] is True
    assert result["exit_code"] == 0
    assert result["stdout"] == "42\n"
    assert "duration_seconds" in result


def test_run_pyodide_empty_runner_output_returns_failure():
    class _FakeProc:
        returncode = 1

        def communicate(self, input=None, timeout=None):
            return ("", "node blew up")

    with patch("subprocess.Popen", return_value=_FakeProc()):
        result = _MODULE._run_pyodide("x", 30)

    assert result["success"] is False
    assert "node blew up" in result["stderr"]


def test_run_pyodide_timeout_returns_failure():
    import subprocess

    def _raise(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="node", timeout=45)

    class _FakeProc:
        def kill(self):
            pass

        def communicate(self, input=None, timeout=None):
            raise subprocess.TimeoutExpired(cmd="node", timeout=45)

    with patch("subprocess.Popen", return_value=_FakeProc()):
        result = _MODULE._run_pyodide("while True: pass", 30)

    assert result["success"] is False
    assert "timeout" in result["stderr"].lower()


def test_run_pyodide_no_node_returns_failure():

    with patch("subprocess.Popen", side_effect=FileNotFoundError("node")):
        result = _MODULE._run_pyodide("x", 30)

    assert result["success"] is False
    assert "node" in result["stderr"].lower()


def test_run_resolution_prefers_pyodide_when_no_e2b_key(monkeypatch):
    # The key-free path: with no E2B_API_KEY, _run uses pyodide (not DinD),
    # so the sandbox works with zero operator setup.
    called = {}

    def _pyodide(code, timeout):
        called["pyodide"] = True
        return {"success": True, "exit_code": 0}

    monkeypatch.setattr(_MODULE, "_E2B_KEY", "")
    monkeypatch.setattr(_MODULE, "_run_pyodide", _pyodide)
    monkeypatch.delenv("SANDBOX_DISABLE_PYODIDE", raising=False)
    result = _MODULE._run("x", None, 5)
    assert called.get("pyodide") is True
    assert result["success"] is True
