"""Unit tests for Outcome.kind domain field and repository hydration."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

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


@pytest.mark.parametrize(
    ("given_kind", "expected_kind"),
    [
        (None, "observed"),
        ("verified", "verified"),
    ],
)
def test_given_outcome_kind_when_constructing_then_kind_matches_contract(
    given_kind: str | None, expected_kind: str
) -> None:
    kwargs: dict[str, object] = {
        "solution_id": uuid4(),
        "reporter_id": uuid4(),
        "success": True,
    }
    if given_kind is not None:
        kwargs["kind"] = given_kind
    outcome = Outcome(**kwargs)
    assert outcome.kind == expected_kind


@pytest.mark.parametrize(
    ("row", "expected_kind"),
    [
        (_minimal_row(kind="verified"), "verified"),
        (_minimal_row(kind=None), "observed"),
    ],
)
def test_given_row_kind_when_hydrating_then_kind_is_normalized(
    row: SimpleNamespace, expected_kind: str
) -> None:
    outcome = _to_outcome_domain(row)
    assert outcome.kind == expected_kind


def test_given_legacy_row_without_kind_when_hydrating_then_defaults_to_observed() -> (
    None
):
    # Simulate a legacy row loaded before the additive column existed —
    # defensive ``getattr`` must yield "observed" in the migration window.
    row = _minimal_row()  # no `kind` attribute at all
    outcome = _to_outcome_domain(row)
    assert outcome.kind == "observed"
