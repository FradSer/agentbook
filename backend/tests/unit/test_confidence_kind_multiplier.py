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


def test_verified_outcome_confidence_exceeds_equivalent_observed() -> None:
    author = uuid4()
    external = uuid4()

    verified_outcomes = [_outcome(reporter_id=external, kind="verified")]
    observed_outcomes = [_outcome(reporter_id=external, kind="observed")]

    c_verified = calculate_confidence(verified_outcomes, author_id=author)
    c_observed = calculate_confidence(observed_outcomes, author_id=author)

    # Both are single successful outcomes; verified must rank strictly
    # higher because its kind multiplier is 2.0 vs 1.0.
    assert c_verified > c_observed, (
        f"expected verified > observed, got {c_verified} vs {c_observed}"
    )


def test_observed_outcome_preserves_legacy_weight() -> None:
    """An observed-only dataset must match today's Bayesian behaviour.

    Legacy tests in test_confidence_scoring.py pin today's numbers for
    observed outcomes; this test guards against drift when kind_multiplier
    is added.
    """
    author = uuid4()
    external = uuid4()
    outcomes = [_outcome(reporter_id=external, kind="observed") for _ in range(3)]
    c = calculate_confidence(outcomes, author_id=author)
    # Three fresh external successes should land comfortably above baseline.
    assert 0.5 < c <= 1.0


def test_verified_only_from_sandbox_agent_passes_diversity() -> None:
    """Sandbox reporter is trusted-external; a verified-only history lifts."""
    author = uuid4()
    outcomes = [
        _outcome(reporter_id=SANDBOX_AGENT_ID, kind="verified") for _ in range(3)
    ]
    c = calculate_confidence(outcomes, author_id=author)
    # Must exceed the 0.3 baseline rather than collapsing to it.
    assert c > 0.3
