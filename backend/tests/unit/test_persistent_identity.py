"""Regression tests for the Agentbook persistent identity helper."""

from __future__ import annotations

import importlib.util
import stat
import sys
import threading
import time
from pathlib import Path

import pytest

_SCRIPT = (
    Path(__file__).resolve().parents[3]
    / "skills"
    / "using-agentbook"
    / "scripts"
    / "persistent_identity.py"
)


def _load_identity_module():
    spec = importlib.util.spec_from_file_location("persistent_identity_test", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_registration_is_persisted_and_reused(tmp_path: Path, monkeypatch) -> None:
    module = _load_identity_module()
    identity_file = tmp_path / "private" / "identity.json"
    registrations = []

    def fake_register(base_url, path, payload):
        registrations.append((base_url, path, payload))
        return {
            "agent_id": "agent-test",
            "api_key": "ak_persistent_test",
            "content_license": "CC0-1.0",
            "terms": "https://example.invalid/terms",
        }

    monkeypatch.setattr(module, "_post_json", fake_register)

    registered = module.ensure_identity(
        base_url="https://example.invalid",
        model_type="codex-test",
        identity_file=identity_file,
        register_if_missing=True,
    )
    reused = module.ensure_identity(
        base_url="https://example.invalid",
        identity_file=identity_file,
    )

    assert registered.source == "registered"
    assert reused.source == "file"
    assert reused.api_key == registered.api_key
    assert len(registrations) == 1
    assert stat.S_IMODE(identity_file.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(identity_file.stat().st_mode) == 0o600
    assert "api_key" not in reused.public_metadata()


def test_broken_identity_symlink_is_rejected_before_registration(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_identity_module()
    identity_file = tmp_path / "identity.json"
    identity_file.symlink_to(tmp_path / "missing-target")
    registrations = []

    def fake_register(*args):
        registrations.append(args)
        return {"api_key": "ak_should_not_be_used"}

    monkeypatch.setattr(module, "_post_json", fake_register)

    with pytest.raises(module.IdentityError, match="symlink"):
        module.ensure_identity(
            identity_file=identity_file,
            register_if_missing=True,
        )

    assert registrations == []


def test_concurrent_registration_creates_one_identity(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_identity_module()
    identity_file = tmp_path / "private" / "identity.json"
    registrations = []
    registration_started = threading.Event()
    release_registration = threading.Event()

    def fake_register(*args):
        registrations.append(args)
        registration_started.set()
        release_registration.wait(timeout=2)
        return {
            "agent_id": "agent-test",
            "api_key": "ak_concurrent_test",
            "content_license": "CC0-1.0",
            "terms": "https://example.invalid/terms",
        }

    monkeypatch.setattr(module, "_post_json", fake_register)
    results = []
    errors = []

    def resolve() -> None:
        try:
            results.append(
                module.ensure_identity(
                    base_url="https://example.invalid",
                    identity_file=identity_file,
                    register_if_missing=True,
                )
            )
        except Exception as error:  # pragma: no cover - assertion aid
            errors.append(error)

    threads = [threading.Thread(target=resolve) for _ in range(2)]
    for thread in threads:
        thread.start()
    assert registration_started.wait(timeout=2)
    time.sleep(0.05)
    release_registration.set()
    for thread in threads:
        thread.join(timeout=2)

    assert errors == []
    assert len(results) == 2
    assert len(registrations) == 1
    assert {result.api_key for result in results} == {"ak_concurrent_test"}


def test_identity_path_inside_repository_is_rejected_from_nested_cwd(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_identity_module()
    repository = tmp_path / "repository"
    nested_directory = repository / "nested"
    nested_directory.mkdir(parents=True)
    (repository / ".git").mkdir()
    monkeypatch.chdir(nested_directory)

    with pytest.raises(module.IdentityError, match="outside the current repository"):
        module.ensure_identity(
            identity_file=repository / "identity.json",
            register_if_missing=True,
        )
