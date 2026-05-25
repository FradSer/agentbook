"""Provenance helpers: prompt hashing and the agentbook repo commit at run time."""

from __future__ import annotations

import hashlib
import subprocess
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def prompt_hash(system: str, user: str) -> str:
    h = hashlib.sha256()
    h.update(system.encode())
    h.update(b"\x00")
    h.update(user.encode())
    return h.hexdigest()[:16]


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


@lru_cache(maxsize=1)
def harness_git_commit() -> str:
    r = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return r.stdout.strip() or "unknown"
