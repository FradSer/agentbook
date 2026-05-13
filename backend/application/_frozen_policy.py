"""Frozen-policy decorator for confidence scoring.

This decorator is a runtime no-op. Its sole purpose is to attach a
version string to functions whose output must not drift without an
entry in ``docs/confidence-changelog.md``. A CI grep check enforces
the invariant.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

F = TypeVar("F", bound=Callable[..., object])


def frozen_policy(version: str) -> Callable[[F], F]:
    def _decorator(fn: F) -> F:
        fn.__frozen_policy_version__ = version  # type: ignore[attr-defined]
        return fn

    return _decorator
