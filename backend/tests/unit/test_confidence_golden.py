"""Golden-value snapshot of the frozen confidence policy.

``calculate_confidence`` is declared frozen via ``@frozen_policy("v6")`` and
``scripts/check_frozen_policy.sh`` guards the *version string* against silent
bumps. But that script only greps the changelog for the version heading — it
cannot detect a numeric constant changing (the Bayesian prior weight 0.8, the
90-day recency half-life, or the 0.3 / 0.5 / 0.6 caps) while the version string
stays "v6". This test closes that gap: it locks the numeric *output* of the
function for a table of representative inputs.

If you change the confidence math you WILL break this test. That is the point.
The required workflow is:

  1. Bump ``__frozen_policy_version__`` in
     ``backend/application/confidence.py`` (the ``@frozen_policy`` decorator).
  2. Add a matching ``## <version>`` entry to ``docs/confidence-changelog.md``
     (else ``scripts/check_frozen_policy.sh`` fails the build).
  3. Re-derive the expected values below and update them in the SAME commit,
     so the snapshot reflects the new, documented policy.

Do NOT "fix" a failure here by loosening the assertion or editing the numbers
without performing steps 1-3.

Determinism: ``calculate_confidence`` multiplies each outcome by a recency
factor ``exp(-days_elapsed / 90)`` where ``days_elapsed`` is measured from its
own ``utc_now()`` read. To make the snapshot a true constant (not a moving
wall-clock target) the test freezes that clock to a fixed instant and ages
every outcome relative to the same instant, so each value is exactly
reproducible and asserted tightly.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from backend.application import confidence as confidence_module
from backend.application.clustering import SANDBOX_AGENT_ID
from backend.application.confidence import calculate_confidence
from backend.domain.models import Outcome

AUTHOR = UUID("11111111-1111-1111-1111-111111111111")
R1 = UUID("22222222-2222-2222-2222-222222222222")
R2 = UUID("33333333-3333-3333-3333-333333333333")
R3 = UUID("44444444-4444-4444-4444-444444444444")
R4 = UUID("55555555-5555-5555-5555-555555555555")
SOLUTION = UUID("99999999-9999-9999-9999-999999999999")

# Fixed reference instant. Every outcome's ``created_at`` is derived from this
# and ``calculate_confidence``'s ``utc_now()`` is pinned to it (see fixture),
# so the recency factor is deterministic and the golden values are constants.
FROZEN_NOW = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _freeze_confidence_clock(monkeypatch):
    """Pin the clock ``calculate_confidence`` reads to ``FROZEN_NOW``.

    ``confidence.py`` does ``from backend.domain.models import utc_now``, so the
    name to patch is ``confidence.utc_now`` (the module-local binding), not the
    one in ``domain.models``.
    """
    monkeypatch.setattr(confidence_module, "utc_now", lambda: FROZEN_NOW)


def _outcome(
    reporter: UUID,
    success: bool,
    *,
    kind: str = "observed",
    weight: float = 1.0,
    age_days: float = 0.0,
) -> Outcome:
    return Outcome(
        solution_id=SOLUTION,
        reporter_id=reporter,
        success=success,
        kind=kind,
        weight=weight,
        created_at=FROZEN_NOW - timedelta(days=age_days),
    )


# (id, outcomes, expected_confidence). Expected values are the frozen v6
# baseline computed against FROZEN_NOW — see module docstring before changing
# any of them. They cover every distinct branch of the v6 algorithm:
#   - baseline early returns (no outcomes; no external reporters)
#   - cold-start floor cap (<3 external reporters -> min 0.5)
#   - reporter-diversity scaling + adaptive Bayesian prior (>=3 reporters)
#   - failure signal pulling below baseline
#   - recency decay on an aged outcome
#   - anti-Sybil num_effective_reporters override
#   - verified kind multiplier (2x)
#   - sandbox-only verified ceiling (0.6) and its lift by external corroboration
GOLDEN_CASES = [
    ("empty", [], 0.3),
    ("author_only_success", [_outcome(AUTHOR, True)], 0.3),
    ("one_external_success_fresh", [_outcome(R1, True)], 0.5),
    ("two_external_success_fresh", [_outcome(R1, True), _outcome(R2, True)], 0.5),
    (
        "three_external_success_fresh",
        [_outcome(R1, True), _outcome(R2, True), _outcome(R3, True)],
        0.9428571428571428,
    ),
    (
        "four_external_success_fresh",
        [
            _outcome(R1, True),
            _outcome(R2, True),
            _outcome(R3, True),
            _outcome(R4, True),
        ],
        0.9666666666666667,
    ),
    (
        "three_external_one_fail",
        [_outcome(R1, True), _outcome(R2, True), _outcome(R3, False)],
        0.6367346938775511,
    ),
    ("one_external_fail", [_outcome(R1, False)], 0.13333333333333333),
    (
        "one_external_success_aged180",
        [_outcome(R1, True, age_days=180.0)],
        0.4012842132265246,
    ),
    (
        "sybil_collapsed_to_one",
        [
            _outcome(R1, True),
            _outcome(R2, True),
            _outcome(R3, True),
            _outcome(R4, True),
        ],
        0.5,
    ),
    (
        "three_external_verified",
        [
            _outcome(R1, True, kind="verified"),
            _outcome(R2, True),
            _outcome(R3, True),
        ],
        0.95625,
    ),
    (
        "sandbox_only_verified",
        [_outcome(SANDBOX_AGENT_ID, True, kind="verified")],
        0.5,
    ),
    (
        "sandbox_plus_external",
        [
            _outcome(SANDBOX_AGENT_ID, True, kind="verified"),
            _outcome(R1, True),
            _outcome(R2, True),
        ],
        0.95625,
    ),
]


@pytest.mark.parametrize(
    "case_id, outcomes, expected",
    GOLDEN_CASES,
    ids=[c[0] for c in GOLDEN_CASES],
)
def test_confidence_golden_values(case_id, outcomes, expected):
    # ``num_effective_reporters`` override exercises the anti-Sybil path.
    kwargs = {}
    if case_id == "sybil_collapsed_to_one":
        kwargs["num_effective_reporters"] = 1

    result = calculate_confidence(outcomes, AUTHOR, **kwargs)
    # Tight (1e-12) because the clock is frozen: any drift here is a real
    # change to a numeric constant, not wall-clock jitter.
    assert result == pytest.approx(expected, rel=0, abs=1e-12), (
        f"{case_id}: confidence drifted to {result!r} (expected {expected!r}). "
        "If this is an intentional policy change, bump "
        "calculate_confidence.__frozen_policy_version__, add a "
        "docs/confidence-changelog.md entry, and update this golden value."
    )


def test_frozen_policy_version_is_pinned():
    """The golden table above is authored for exactly this policy version.

    Pairs with ``scripts/check_frozen_policy.sh``: if the version is bumped,
    the golden values must be re-derived in the same change.
    """
    assert calculate_confidence.__frozen_policy_version__ == "v6"
