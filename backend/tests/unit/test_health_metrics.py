from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from backend.application.service import SANDBOX_AGENT_ID
from backend.domain.models import Outcome
from backend.infrastructure.persistence.in_memory import InMemoryOutcomeRepository
from backend.presentation.api.routes.health import _sandbox_pass_rate


class _ServiceStub:
    def __init__(self, outcomes: InMemoryOutcomeRepository) -> None:
        self._outcomes = outcomes


def test_sandbox_pass_rate_uses_reporter_filtered_outcomes_with_24h_window() -> None:
    repo = InMemoryOutcomeRepository()
    now = datetime.now(tz=UTC)
    repo.add(
        Outcome(
            solution_id=uuid4(),
            reporter_id=SANDBOX_AGENT_ID,
            success=True,
            kind="verified",
            created_at=now - timedelta(hours=1),
        )
    )
    repo.add(
        Outcome(
            solution_id=uuid4(),
            reporter_id=SANDBOX_AGENT_ID,
            success=False,
            kind="verified",
            created_at=now - timedelta(hours=2),
        )
    )
    repo.add(
        Outcome(
            solution_id=uuid4(),
            reporter_id=SANDBOX_AGENT_ID,
            success=True,
            kind="verified",
            created_at=now - timedelta(hours=30),
        )
    )
    repo.add(
        Outcome(
            solution_id=uuid4(),
            reporter_id=uuid4(),
            success=True,
            kind="observed",
            created_at=now - timedelta(hours=1),
        )
    )

    rate, total = _sandbox_pass_rate(_ServiceStub(repo))
    assert total == 2
    assert rate == 0.5
