"""Unit tests for backend.application._frozen_policy.

The decorator is a runtime no-op whose contract is:
- the wrapped function still runs unchanged
- ``__frozen_policy_version__`` is attached and matches the supplied version

This invariant is what the CI grep check relies on.
"""

from __future__ import annotations

from backend.application._frozen_policy import frozen_policy


def test_decorator_attaches_version_attribute_and_passes_through_calls() -> None:
    @frozen_policy("v1.0")
    def add(a: int, b: int) -> int:
        return a + b

    assert add(2, 3) == 5
    assert add.__frozen_policy_version__ == "v1.0"


def test_decorator_returns_same_function_object() -> None:
    def fn() -> int:
        return 42

    decorated = frozen_policy("v9")(fn)
    # The decorator must NOT wrap; it must return the original callable so
    # downstream `inspect.signature(...)` and stack traces stay clean.
    assert decorated is fn


def test_each_decoration_overwrites_prior_version() -> None:
    @frozen_policy("v1")
    def fn(x: int) -> int:
        return x

    assert fn.__frozen_policy_version__ == "v1"

    re_decorated = frozen_policy("v2")(fn)
    assert re_decorated.__frozen_policy_version__ == "v2"
