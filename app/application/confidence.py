from __future__ import annotations

import math
from datetime import UTC, datetime
from uuid import UUID

from app.domain.models import Outcome


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def calculate_confidence(
    outcomes: list[Outcome],
    author_id: UUID,
    author_verified: bool = False,
) -> float:
    baseline = 0.5 if author_verified else 0.3

    if not outcomes:
        return baseline

    total = len(outcomes)
    now = utc_now()

    # Step 2-3: compute final_weight and success_value per outcome.
    final_weights: list[float] = []
    success_values: list[float] = []

    for outcome in outcomes:
        base_weight = 0.5 if outcome.reporter_id == author_id else 1.0
        days_elapsed = (now - outcome.created_at).total_seconds() / 86400
        recency_factor = math.exp(-days_elapsed / 90.0)
        env_factor = outcome.weight
        final_weight = base_weight * recency_factor * env_factor
        final_weights.append(final_weight)
        success_values.append(1.0 if outcome.success else 0.0)

    # Step 4: reporter diversity penalty.
    # Count only external unique reporters (excluding author_id).  Self-reports
    # do not increase reporter diversity, so a purely self-reported dataset has
    # zero external unique reporters and its weights collapse to zero.
    unique_ext_reporters = len(
        {o.reporter_id for o in outcomes if o.reporter_id != author_id}
    )

    if unique_ext_reporters == 0:
        # No external corroboration: treat as no usable data, return baseline.
        return baseline

    effective_count = unique_ext_reporters * math.log2(total + 1)
    if effective_count < total:
        scale = effective_count / total
        final_weights = [w * scale for w in final_weights]

    # Step 5: weighted ratio with adaptive Bayesian prior P = P0 / total.
    # The adaptive prior ensures a single aged outcome (tiny weight) is pulled
    # strongly toward the baseline, while a batch of fresh outcomes is pulled
    # only weakly.
    sum_w = sum(final_weights)
    sum_sv_w = sum(sv * w for sv, w in zip(success_values, final_weights, strict=False))

    if sum_w == 0.0:
        return baseline

    prior_weight = 0.8 / total
    confidence = (sum_sv_w + baseline * prior_weight) / (sum_w + prior_weight)

    return max(0.0, min(1.0, confidence))
