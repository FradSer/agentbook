"""resolve_sandbox_provider prefers the remote microservice when its URL is set.

On hosts with no Docker daemon (a Railway app container), setting
SANDBOX_ENABLED=true crashed boot because the local-Docker path raised. The
remote path (SANDBOX_SERVICE_URL) is the fix: it is chosen FIRST, before the
``docker info`` probe, so a sandbox microservice unblocks verify without a local
daemon.
"""

from __future__ import annotations

from unittest.mock import patch

from backend.infrastructure.sandbox import resolve_sandbox_provider


def test_remote_service_url_is_chosen_before_docker_probe(monkeypatch):
    # Even with no Docker daemon reachable, the remote URL short-circuits the
    # ``docker info`` probe — so a container without Docker still gets a provider.
    monkeypatch.setattr(
        "backend.infrastructure.sandbox.settings.sandbox_service_url",
        "https://sandbox.example.com",
    )
    monkeypatch.setattr(
        "backend.infrastructure.sandbox.settings.sandbox_service_token", "tok"
    )
    provider = resolve_sandbox_provider()
    from backend.infrastructure.sandbox.remote_sandbox import RemoteSandboxProvider

    assert isinstance(provider, RemoteSandboxProvider)


def test_no_remote_url_and_no_docker_raises_in_production(monkeypatch):
    # debug=False, no remote URL, no Docker -> must refuse (the original crash
    # behavior, preserved so an operator never silently runs unsandboxed).
    monkeypatch.setattr(
        "backend.infrastructure.sandbox.settings.sandbox_service_url", None
    )
    monkeypatch.setattr("backend.infrastructure.sandbox.settings.debug", False)

    def fake_run(*a, **kw):
        raise FileNotFoundError("docker not found")

    with (
        patch("backend.infrastructure.sandbox.subprocess.run", side_effect=fake_run),
        __import__("pytest").raises(RuntimeError, match="SANDBOX_ENABLED=true"),
    ):
        resolve_sandbox_provider()
