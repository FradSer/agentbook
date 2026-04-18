"""Unit tests for Outcome.kind domain field and repository hydration.

Red tests authored before task 002b lands `kind` in the Outcome dataclass
and the repository hydration helper. When these fail before 002b, the
failure mode is either ``AttributeError`` on ``Outcome.kind`` or a
``TypeError`` because the constructor rejects an unknown keyword.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from backend.domain.models import Outcome
from backend.infrastructure.persistence.sqlalchemy_repositories import (
    _to_outcome_domain,
)


def _minimal_row(**overrides: object) -> SimpleNamespace:
    """Build a duck-typed OutcomeORM row for hydration tests."""
    now = datetime.now(tz=UTC)
    defaults = {
        "outcome_id": str(uuid4()),
        "solution_id": str(uuid4()),
        "reporter_id": str(uuid4()),
        "success": True,
        "environment": None,
        "time_saved_seconds": None,
        "notes": None,
        "weight": 1.0,
        "created_at": now,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_outcome_kind_defaults_to_observed() -> None:
    o = Outcome(solution_id=uuid4(), reporter_id=uuid4(), success=True)
    assert o.kind == "observed"


def test_outcome_accepts_kind_verified() -> None:
    o = Outcome(
        solution_id=uuid4(),
        reporter_id=uuid4(),
        success=True,
        kind="verified",
    )
    assert o.kind == "verified"


def test_repository_hydrates_kind_from_row() -> None:
    row = _minimal_row(kind="verified")
    outcome = _to_outcome_domain(row)
    assert outcome.kind == "verified"


def test_repository_hydrates_missing_kind_as_observed() -> None:
    # Simulate a legacy row loaded before the additive column existed —
    # defensive ``getattr`` must yield "observed" in the migration window.
    row = _minimal_row()  # no `kind` attribute at all
    outcome = _to_outcome_domain(row)
    assert outcome.kind == "observed"


def test_repository_hydrates_null_kind_as_observed() -> None:
    row = _minimal_row(kind=None)
    outcome = _to_outcome_domain(row)
    assert outcome.kind == "observed"
