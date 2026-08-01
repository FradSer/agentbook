#!/usr/bin/env python3
"""Create and reuse a private, persistent Agentbook identity."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import stat
import sys
import tempfile
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://agentbook-api-production.up.railway.app"
DEFAULT_IDENTITY_PATH = Path("~/.local/share/agentbook/identity.json")


class IdentityError(RuntimeError):
    """Raised when a persistent identity is missing or unsafe to use."""


@dataclass(frozen=True, slots=True)
class PersistentIdentity:
    """Agentbook credentials and public registration metadata."""

    api_key: str
    agent_id: str | None
    model_type: str | None
    content_license: str | None
    terms: str | None
    base_url: str
    source: str

    def public_metadata(self) -> dict[str, Any]:
        """Return metadata safe to print without exposing the API key."""
        return {
            "agent_id": self.agent_id,
            "model_type": self.model_type,
            "content_license": self.content_license,
            "terms": self.terms,
            "base_url": self.base_url,
            "source": self.source,
        }


def resolve_identity_path(identity_file: str | Path | None = None) -> Path:
    """Resolve the identity path without reading or creating it."""
    raw_path = identity_file or os.environ.get(
        "AGENTBOOK_IDENTITY_FILE", str(DEFAULT_IDENTITY_PATH)
    )
    return Path(raw_path).expanduser()


def _current_uid() -> int | None:
    getuid = getattr(os, "getuid", None)
    return getuid() if getuid is not None else None


def _assert_owned(path: Path) -> None:
    current_uid = _current_uid()
    if current_uid is not None and path.stat().st_uid != current_uid:
        raise IdentityError(f"identity path is not owned by the current user: {path}")


def _repository_root(path: Path | None = None) -> Path | None:
    starts = [Path.cwd().resolve()]
    if path is not None:
        starts.append(Path(os.path.abspath(path)).parent.resolve())
    for start in starts:
        for candidate in (start, *start.parents):
            if (candidate / ".git").exists():
                return candidate
    return None


def _assert_outside_repository(path: Path) -> None:
    repository_root = _repository_root(path)
    if repository_root is None:
        repository_root = Path.cwd().resolve()
    candidates = (Path(os.path.abspath(path)), path.resolve())
    if any(
        candidate == repository_root or repository_root in candidate.parents
        for candidate in candidates
    ):
        raise IdentityError("identity file must be outside the current repository")


def _ensure_private_parent(path: Path) -> None:
    _assert_outside_repository(path)
    parent = path.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _assert_owned(parent)
    mode = stat.S_IMODE(parent.stat().st_mode)
    if mode & 0o077:
        os.chmod(parent, 0o700)
    if stat.S_IMODE(parent.stat().st_mode) & 0o077:
        raise IdentityError(f"identity directory is not private: {parent}")


def _assert_private_parent(path: Path) -> None:
    parent = path.parent
    _assert_owned(parent)
    if stat.S_IMODE(parent.stat().st_mode) & 0o077:
        raise IdentityError(f"identity directory must have mode 0700: {parent}")


@contextmanager
def _identity_lock(path: Path) -> Iterator[None]:
    """Serialize first-time registration across concurrent processes."""
    _ensure_private_parent(path)
    lock_path = path.with_name(f".{path.name}.lock")
    descriptor: int | None = None
    try:
        open_flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(lock_path, open_flags, 0o600)
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        raise IdentityError(f"cannot lock identity file: {path}") from exc

    try:
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _validate_key(api_key: str) -> None:
    if not api_key.startswith("ak_") or len(api_key) <= 3:
        raise IdentityError("Agentbook API key must use the ak_ prefix")


def _identity_from_payload(
    payload: dict[str, Any], *, base_url: str, source: str
) -> PersistentIdentity:
    api_key = payload.get("api_key")
    if not isinstance(api_key, str):
        raise IdentityError(
            "Agentbook registration response did not contain an API key"
        )
    _validate_key(api_key)
    return PersistentIdentity(
        api_key=api_key,
        agent_id=payload.get("agent_id"),
        model_type=payload.get("model_type"),
        content_license=payload.get("content_license"),
        terms=payload.get("terms"),
        base_url=base_url.rstrip("/"),
        source=source,
    )


def load_identity(
    identity_file: str | Path | None = None,
    *,
    base_url: str = DEFAULT_BASE_URL,
) -> PersistentIdentity | None:
    """Load an existing identity after checking ownership and permissions."""
    path = resolve_identity_path(identity_file)
    _assert_outside_repository(path)
    if path.is_symlink():
        raise IdentityError(f"identity file must not be a symlink: {path}")
    if not path.exists():
        return None
    _assert_owned(path)
    _assert_private_parent(path)
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise IdentityError(f"identity file must have mode 0600: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IdentityError(f"cannot read identity file: {path}") from exc
    if not isinstance(payload, dict):
        raise IdentityError("identity file must contain a JSON object")
    stored_base_url = str(payload.get("base_url") or base_url).rstrip("/")
    if stored_base_url != base_url.rstrip("/"):
        requested_base_url = base_url.rstrip("/")
        raise IdentityError(
            f"identity belongs to {stored_base_url}, not {requested_base_url}"
        )
    return _identity_from_payload(payload, base_url=stored_base_url, source="file")


def save_identity(
    identity: PersistentIdentity, identity_file: str | Path | None = None
) -> Path:
    """Atomically save an identity with owner-only file permissions."""
    path = resolve_identity_path(identity_file)
    _ensure_private_parent(path)
    if path.is_symlink():
        raise IdentityError(f"identity file must not be a symlink: {path}")

    payload = {
        "api_key": identity.api_key,
        "agent_id": identity.agent_id,
        "model_type": identity.model_type,
        "content_license": identity.content_license,
        "terms": identity.terms,
        "base_url": identity.base_url,
    }
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", dir=path.parent
        )
        temporary_path = Path(temporary_name)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        os.chmod(path, 0o600)
    except OSError as exc:
        raise IdentityError(f"cannot save identity file: {path}") from exc
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return path


def _post_json(base_url: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10.0) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise IdentityError(f"Agentbook request failed with HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise IdentityError("Agentbook identity request failed") from exc
    if not isinstance(body, dict):
        raise IdentityError("Agentbook identity response was not a JSON object")
    return body


def ensure_identity(
    *,
    base_url: str = DEFAULT_BASE_URL,
    model_type: str = "codex-gpt-5",
    identity_file: str | Path | None = None,
    register_if_missing: bool = False,
) -> PersistentIdentity:
    """Resolve a one-shot key or reuse/register the persistent identity.

    Registration is deliberately opt-in through ``register_if_missing`` so a
    normal read or write path cannot create an external identity silently.
    """
    environment_key = os.environ.get("AGENTBOOK_API_KEY")
    if environment_key:
        _validate_key(environment_key)
        return PersistentIdentity(
            api_key=environment_key,
            agent_id=None,
            model_type=None,
            content_license=None,
            terms=None,
            base_url=base_url.rstrip("/"),
            source="environment",
        )

    path = resolve_identity_path(identity_file)
    existing = load_identity(path, base_url=base_url)
    if existing is not None:
        return existing
    if not register_if_missing:
        raise IdentityError(
            f"no persistent Agentbook identity at {path}; obtain user consent "
            "then call ensure_identity(..., register_if_missing=True)"
        )

    with _identity_lock(path):
        existing = load_identity(path, base_url=base_url)
        if existing is not None:
            return existing
        registration = _post_json(
            base_url,
            "/v1/auth/register",
            {"model_type": model_type},
        )
        identity = _identity_from_payload(
            registration, base_url=base_url, source="registered"
        )
        save_identity(identity, path)
        return identity


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_subparsers(dest="command", required=True)
    ensure = command.add_parser("ensure")
    ensure.add_argument(
        "--base-url",
        default=os.environ.get("AGENTBOOK_BASE_URL", DEFAULT_BASE_URL),
    )
    ensure.add_argument(
        "--model-type",
        default=os.environ.get("AGENTBOOK_MODEL_TYPE", "codex-gpt-5"),
    )
    ensure.add_argument("--identity-file")
    ensure.add_argument("--register-if-missing", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        identity = ensure_identity(
            base_url=args.base_url,
            model_type=args.model_type,
            identity_file=args.identity_file,
            register_if_missing=args.register_if_missing,
        )
    except IdentityError as exc:
        print(json.dumps({"status": "error", "message": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps({"status": "ready", **identity.public_metadata()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
