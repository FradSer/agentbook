"""seed_book is idempotent: a 409 duplicate_problem is skipped, not fatal.

REST surfaces an exact-signature duplicate as HTTP 409 (an error envelope),
not a 200 with existing_problems. Before this fix one pre-existing entry
aborted the whole load before the rest landed.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

_EXAMPLES = Path(__file__).resolve().parents[3] / "examples"


@pytest.fixture(autouse=True)
def _examples_on_path(monkeypatch):
    monkeypatch.syspath_prepend(str(_EXAMPLES))
    yield


class _FakeClient:
    """remember() pops the next canned response or raises it."""

    def __init__(self, responses, agentbook_error_cls):
        self._responses = list(responses)
        self._i = 0
        self.AgentbookError = agentbook_error_cls

    def remember(self, **kw):
        item = self._responses[self._i]
        self._i += 1
        if isinstance(item, self.AgentbookError):
            raise item
        return item


def _entry(description):
    return SimpleNamespace(
        description=description,
        error_signature="ModuleNotFoundError: No module named",
        solution_content="Install deps then pip install",
        solution_steps=["apk add build-base"],
        root_cause_pattern="Alpine musl lacks C build deps",
        localization_cues=["Dockerfile FROM line"],
        verification=[{"command": "docker build .", "expected": "ok"}],
        tags=["python"],
    )


def test_duplicate_409_is_skipped_and_loading_continues(monkeypatch):
    import seed_book
    from recall_first_client import AgentbookError

    responses = [
        AgentbookError(
            "POST /v1/problems -> HTTP 409: duplicate_problem already exists"
        ),
        {"problem_id": "p1", "solution_id": "s1"},
        {"problem_id": "p2", "solution_id": "s2"},
    ]
    client = _FakeClient(responses, AgentbookError)
    monkeypatch.setattr(seed_book, "CORPUS", [_entry("d0"), _entry("d1"), _entry("d2")])
    stats = seed_book.seed(client)
    assert stats == {"contributed": 2, "already_present": 1, "total": 3}


def test_non_duplicate_error_is_not_swallowed(monkeypatch):
    import seed_book
    from recall_first_client import AgentbookError

    responses = [AgentbookError("POST /v1/problems -> HTTP 500: internal server error")]
    client = _FakeClient(responses, AgentbookError)
    monkeypatch.setattr(seed_book, "CORPUS", [_entry("d0")])
    with pytest.raises(AgentbookError):
        seed_book.seed(client)
