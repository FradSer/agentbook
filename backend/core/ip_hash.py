"""Shared remote-address hashing for caller identity.

Used by both presentation transports (MCP ``recall`` and REST ``/v1/search``) to
stamp a recurrence-density ``QueryEvent`` with a dedup-capable ``ip_hash`` for an
anonymous caller. Kept in ``core`` so neither transport imports the other.
"""

from __future__ import annotations

import hashlib


def hash_remote_addr(addr: str | None) -> str | None:
    """SHA256 a remote address into an anonymous, dedup-capable ``ip_hash``.

    Mirrors the ``Agent.ip_hash`` scheme (a stored SHA256 hex digest) so an
    anonymous caller's recurrence events collapse on a shared address the same
    way an authenticated agent's do.
    """
    if not addr:
        return None
    return hashlib.sha256(addr.encode("utf-8")).hexdigest()
