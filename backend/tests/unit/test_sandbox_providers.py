"""Unit tests for sandbox providers.

These cover the shared ``run_sandboxed`` helper and the three providers
that delegate to it. We mock ``subprocess.run`` so the suite stays
hermetic (no Docker, no shell, no network).
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from backend.domain.models import SandboxResult
from backend.infrastructure.sandbox import run_sandboxed
from backend.infrastructure.sandbox.docker_sandbox import DockerSandboxProvider
from backend.infrastructure.sandbox.noop_sandbox import NoopSandboxProvider
from backend.infrastructure.sandbox.subprocess_sandbox import SubprocessSandboxProvider


def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


# ---------------------------------------------------------------------------
# NoopSandboxProvider
# ---------------------------------------------------------------------------


def test_noop_provider_always_succeeds() -> None:
    result = NoopSandboxProvider().execute("anything")
    assert isinstance(result, SandboxResult)
    assert result.success is True
    assert result.exit_code == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_noop_provider_threads_environment_through() -> None:
    env = {"os": "linux"}
    result = NoopSandboxProvider().execute("code", environment=env)
    assert result.environment == env


# ---------------------------------------------------------------------------
# run_sandboxed -- shared helper
# ---------------------------------------------------------------------------


def test_run_sandboxed_returns_success_when_exit_zero() -> None:
    with patch("backend.infrastructure.sandbox.subprocess.run") as mock_run:
        mock_run.return_value = _completed(returncode=0, stdout="ok")
        result = run_sandboxed(lambda _t, s: ["python3", str(s)], "print('ok')")
    assert result.success is True
    assert result.exit_code == 0
    assert result.stdout == "ok"


def test_run_sandboxed_marks_failure_when_exit_nonzero() -> None:
    with patch("backend.infrastructure.sandbox.subprocess.run") as mock_run:
        mock_run.return_value = _completed(returncode=1, stderr="boom")
        result = run_sandboxed(lambda _t, s: ["python3", str(s)], "raise SystemExit(1)")
    assert result.success is False
    assert result.exit_code == 1


def test_run_sandboxed_treats_error_signature_as_failure_even_on_exit_zero() -> None:
    """If the stderr contains the expected error_signature, success must be False
    even when the process exited zero. This is the "did the bug reproduce?" gate.
    """
    with patch("backend.infrastructure.sandbox.subprocess.run") as mock_run:
        mock_run.return_value = _completed(
            returncode=0, stderr="ImportError: cannot import name X"
        )
        result = run_sandboxed(
            lambda _t, s: ["python3", str(s)],
            "code",
            error_signature="ImportError",
        )
    assert result.success is False


def test_run_sandboxed_truncates_long_stdout_and_stderr_to_4kb() -> None:
    big = "x" * 8000
    with patch("backend.infrastructure.sandbox.subprocess.run") as mock_run:
        mock_run.return_value = _completed(returncode=0, stdout=big, stderr=big)
        result = run_sandboxed(lambda _t, s: ["python3", str(s)], "code")
    assert len(result.stdout) == 4096
    assert len(result.stderr) == 4096


def test_run_sandboxed_returns_failure_on_timeout() -> None:
    with patch("backend.infrastructure.sandbox.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="python3", timeout=1)
        result = run_sandboxed(lambda _t, s: ["python3", str(s)], "code", timeout=1)
    assert result.success is False
    assert result.exit_code == -1
    assert "Timeout" in result.stderr


def test_run_sandboxed_returns_failure_on_unexpected_exception() -> None:
    with patch("backend.infrastructure.sandbox.subprocess.run") as mock_run:
        mock_run.side_effect = OSError("docker daemon down")
        result = run_sandboxed(lambda _t, s: ["python3", str(s)], "code")
    assert result.success is False
    assert result.exit_code == -1
    assert result.stderr == "Sandbox execution error"


# ---------------------------------------------------------------------------
# SubprocessSandboxProvider
# ---------------------------------------------------------------------------


def test_subprocess_provider_delegates_to_run_sandboxed_with_python3_command() -> None:
    captured: dict[str, list[str]] = {}

    def _fake_run_sandboxed(build_cmd, code, **kwargs):
        captured["cmd"] = build_cmd("/tmp", "/tmp/solution.py")
        captured["timeout"] = kwargs.get("timeout")
        return SandboxResult(True, 0, "", "", 0.0, {})

    with patch(
        "backend.infrastructure.sandbox.subprocess_sandbox.run_sandboxed",
        side_effect=_fake_run_sandboxed,
    ):
        SubprocessSandboxProvider(timeout_seconds=7).execute("print(1)")

    assert captured["cmd"] == ["python3", "/tmp/solution.py"]
    assert captured["timeout"] == 7


def test_subprocess_provider_per_call_timeout_overrides_default() -> None:
    captured: dict[str, int] = {}

    def _fake_run_sandboxed(build_cmd, code, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        return SandboxResult(True, 0, "", "", 0.0, {})

    with patch(
        "backend.infrastructure.sandbox.subprocess_sandbox.run_sandboxed",
        side_effect=_fake_run_sandboxed,
    ):
        SubprocessSandboxProvider(timeout_seconds=30).execute(
            "print(1)", timeout_seconds=99
        )

    assert captured["timeout"] == 99


# ---------------------------------------------------------------------------
# DockerSandboxProvider
# ---------------------------------------------------------------------------


def test_docker_provider_builds_isolated_container_command() -> None:
    captured: dict[str, list[str]] = {}

    def _fake_run_sandboxed(build_cmd, code, **kwargs):
        captured["cmd"] = build_cmd("/tmp/abc", "/tmp/abc/solution.py")
        return SandboxResult(True, 0, "", "", 0.0, {})

    with patch(
        "backend.infrastructure.sandbox.docker_sandbox.run_sandboxed",
        side_effect=_fake_run_sandboxed,
    ):
        DockerSandboxProvider(image="python:3.11-slim", memory_mb=256).execute(
            "print(1)"
        )

    cmd = captured["cmd"]
    # Critical security flags must be present.
    assert cmd[0] == "docker"
    assert "run" in cmd
    assert "--rm" in cmd
    assert "--network=none" in cmd
    assert "--memory=256m" in cmd
    assert "--cpus=0.5" in cmd
    assert "python:3.11-slim" in cmd


@pytest.mark.parametrize("memory_mb", [64, 128, 512, 1024])
def test_docker_provider_threads_memory_limit_into_flag(memory_mb: int) -> None:
    captured: dict[str, list[str]] = {}

    def _fake_run_sandboxed(build_cmd, code, **kwargs):
        captured["cmd"] = build_cmd("/tmp/abc", "/tmp/abc/solution.py")
        return SandboxResult(True, 0, "", "", 0.0, {})

    with patch(
        "backend.infrastructure.sandbox.docker_sandbox.run_sandboxed",
        side_effect=_fake_run_sandboxed,
    ):
        DockerSandboxProvider(memory_mb=memory_mb).execute("code")

    assert f"--memory={memory_mb}m" in captured["cmd"]
