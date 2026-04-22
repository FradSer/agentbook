"""Red tests for Outcome.kind weighting in calculate_confidence.

Verified outcomes multiply the base weight by 2.0; observed by 1.0.
SANDBOX_AGENT_ID counts as an external reporter so a verified-only
history passes the external-reporter diversity check.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.application.confidence import calculate_confidence
from backend.domain.models import Outcome

SANDBOX_AGENT_ID = UUID("00000000-0000-0000-0000-000000000003")


def _outcome(
    *,
    reporter_id: UUID,
    kind: str,
    success: bool = True,
    created_at: datetime | None = None,
) -> Outcome:
    return Outcome(
        solution_id=uuid4(),
        reporter_id=reporter_id,
        success=success,
        kind=kind,
        created_at=created_at or datetime.now(tz=UTC),
    )


def test_given_single_external_success_when_kind_changes_then_verified_scores_higher() -> None:
    author = uuid4()
    external = uuid4()

    verified_outcomes = [_outcome(reporter_id=external, kind="verified")]
    observed_outcomes = [_outcome(reporter_id=external, kind="observed")]

    c_verified = calculate_confidence(verified_outcomes, author_id=author)
    c_observed = calculate_confidence(observed_outcomes, author_id=author)

    assert c_verified > c_observed, (
        f"expected verified > observed, got {c_verified} vs {c_observed}"
    )
    assert c_observed > 0.3, "observed history should still lift above baseline"


def test_given_verified_outcomes_from_sandbox_agent_when_calculating_then_diversity_guard_passes() -> None:
    author = uuid4()
    outcomes = [
        _outcome(reporter_id=SANDBOX_AGENT_ID, kind="verified") for _ in range(3)
    ]
    c = calculate_confidence(outcomes, author_id=author)
    assert c > 0.3
