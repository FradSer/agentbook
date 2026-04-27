from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.infrastructure.persistence.sqlalchemy_repositories import _to_outcome_domain


def test_to_outcome_domain_raises_when_kind_missing() -> None:
    row = SimpleNamespace(
        outcome_id=str(uuid4()),
        solution_id=str(uuid4()),
        reporter_id=str(uuid4()),
        success=True,
        kind=None,
        environment=None,
        time_saved_seconds=None,
        notes=None,
        weight=1.0,
        created_at=None,
    )
    with pytest.raises(ValueError, match="Outcome kind cannot be null"):
        _to_outcome_domain(row)
