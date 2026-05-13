from __future__ import annotations

import math
from uuid import UUID

from backend.application._frozen_policy import frozen_policy
from backend.application.clustering import SANDBOX_AGENT_ID
from backend.domain.models import Outcome, Solution, utc_now

# v6 caps. See docs/confidence-changelog.md ## v6 for the rationale.
BASELINE_CONFIDENCE = 0.3
COLD_START_MIN_REPORTERS = 3
COLD_START_FLOOR = 0.5
SANDBOX_ONLY_CEILING = 0.6


def external_reporter_ids(outcomes: list[Outcome], author_id: UUID) -> set[UUID]:
    """Reporter IDs that count toward external corroboration.

    Excludes the solution author (self-reports don't add diversity).
    Shared across the confidence math, the candidate-promotion gate,
    and the search-response provenance carrier — keeping them in sync
    means a sandbox agent's status flip lands in all three at once.
    """
    return {o.reporter_id for o in outcomes if o.reporter_id != author_id}


@frozen_policy("v6")
def calculate_confidence(
    outcomes: list[Outcome],
    author_id: UUID,
    *,
    num_effective_reporters: int | None = None,
) -> float:
    if not outcomes:
        return BASELINE_CONFIDENCE

    total = len(outcomes)
    now = utc_now()

    # Step 2-3: compute final_weight and success_value per outcome.
    final_weights: list[float] = []
    success_values: list[float] = []

    for outcome in outcomes:
        base_weight = 0.5 if outcome.reporter_id == author_id else 1.0
        kind_multiplier = 2.0 if outcome.kind == "verified" else 1.0
        days_elapsed = (now - outcome.created_at).total_seconds() / 86400
        recency_factor = math.exp(-days_elapsed / 90.0)
        env_factor = outcome.weight
        final_weight = base_weight * kind_multiplier * recency_factor * env_factor
        final_weights.append(final_weight)
        success_values.append(1.0 if outcome.success else 0.0)

    # Step 4: reporter diversity penalty. ``num_effective_reporters``
    # (pre-computed from anti-Sybil clustering) wins when supplied;
    # otherwise fall back to the naive unique external count.
    if num_effective_reporters is not None:
        unique_ext_reporters = num_effective_reporters
    else:
        unique_ext_reporters = len(external_reporter_ids(outcomes, author_id))

    if unique_ext_reporters == 0:
        return BASELINE_CONFIDENCE

    effective_count = unique_ext_reporters * math.log2(total + 1)
    if effective_count < total:
        scale = effective_count / total
        final_weights = [w * scale for w in final_weights]

    # Step 5: weighted ratio with adaptive Bayesian prior P = P0 / total.
    # The adaptive prior pulls a single aged outcome (tiny weight) strongly
    # toward baseline while leaving a batch of fresh outcomes mostly free.
    sum_w = sum(final_weights)
    sum_sv_w = sum(sv * w for sv, w in zip(success_values, final_weights, strict=False))

    if sum_w == 0.0:
        return BASELINE_CONFIDENCE

    prior_weight = 0.8 / total
    confidence = (sum_sv_w + BASELINE_CONFIDENCE * prior_weight) / (
        sum_w + prior_weight
    )

    # v6 caps applied last so they can't be circumvented by feeding an
    # inflated num_effective_reporters in. Both caps are upper bounds
    # only — failure signals stay free to drive confidence below 0.5.
    if unique_ext_reporters < COLD_START_MIN_REPORTERS:
        confidence = min(confidence, COLD_START_FLOOR)

    has_sandbox_verified = False
    external_observed_corroboration = False
    for o in outcomes:
        if o.reporter_id == SANDBOX_AGENT_ID:
            if o.kind == "verified":
                has_sandbox_verified = True
        elif o.reporter_id != author_id and o.kind == "observed" and o.success:
            external_observed_corroboration = True
        if has_sandbox_verified and external_observed_corroboration:
            break
    if has_sandbox_verified and not external_observed_corroboration:
        confidence = min(confidence, SANDBOX_ONLY_CEILING)

    return max(0.0, min(1.0, confidence))


# Unified evaluation – single entry point for hill-climbing decisions.
# Analogous to autoresearch's immutable prepare.py:evaluate_bpb().

_SPECIFICITY_MARKERS = ("```", "$ ", "sudo ", "pip ", "npm ", "apt ", "brew ")


def _content_quality_score(solution: Solution) -> float:
    """Heuristic quality score for a solution with no outcome data.

    Factors:
    - Step completeness (structured steps indicate actionable solutions)
    - Content substantiveness (reasonable length, diminishing returns)
    - Specificity markers (code blocks, commands, paths)
    """
    score = 0.0

    step_count = len(solution.steps) if solution.steps else 0
    score += min(step_count, 10) * 0.05  # max 0.5

    content_len = len(solution.content)
    if content_len >= 50:
        score += min(content_len / 500, 1.0) * 0.3  # max 0.3

    marker_count = sum(1 for m in _SPECIFICITY_MARKERS if m in solution.content)
    score += min(marker_count, 4) * 0.05  # max 0.2

    return score


def is_content_regression(
    existing: Solution,
    proposed: Solution,
) -> bool:
    """Content <50% of original length without extra steps."""
    new_steps = len(proposed.steps) if proposed.steps else 0
    old_steps = len(existing.steps) if existing.steps else 0
    return (
        len(proposed.content) < len(existing.content) * 0.5 and new_steps <= old_steps
    )


def evaluate_improvement(
    existing: Solution,
    proposed: Solution,
    evaluator_score: float | None = None,
    sandbox_score: float | None = None,
    *,
    problem_has_error_signature: bool = False,
    sandbox_available: bool = False,
) -> tuple[bool, str]:
    """Single decision function: should proposed replace existing?

    Like autoresearch's ``new_val_bpb < old_val_bpb`` but multi-factor.
    When ``problem_has_error_signature`` and ``sandbox_available`` are both
    true and ``sandbox_score`` is supplied, the sandbox verdict is
    decisive — pass accepts, fail rejects, tie (0.5 < score < 1.0) routes
    through the Karpathy simplicity rule. Otherwise the legacy tree runs:
    content regression, content bloat, cold-start heuristics, strict
    hill-climbing, and simplification reward.

    Args:
        evaluator_score: Optional LLM A/B comparison result (0.0-1.0, >0.5
            means proposed is better).  Used during cold-start as a proxy
            for autoresearch's deterministic ``prepare.py`` measurement.
        sandbox_score: Optional sandbox execution result (0.0-1.0).
            Semantics vary by flag combination — see below.
        problem_has_error_signature: True when the parent problem has an
            ``error_signature`` that makes reproduction codifiable.
        sandbox_available: True when a non-Noop SandboxProvider is
            configured AND circuit breaker / gates permit a real run.

    sandbox_score encoding (set by the orchestrator in service.py):
        - 0.0: both solutions fail, or proposed fails while existing passes
        - 0.6: tie (both pass) — defers to simplicity rule
        - 1.0: proposed passes while existing fails

    Returns ``(accepted, reason_code)`` for auditability.

    This function is immutable evaluation infrastructure — agents must not
    attempt to bypass, override, or negotiate with the scoring system.
    """
    new_steps = len(proposed.steps) if proposed.steps else 0
    old_steps = len(existing.steps) if existing.steps else 0

    # 0. Sandbox-primary dispatch: decisive when error_signature + sandbox.
    if problem_has_error_signature and sandbox_available and sandbox_score is not None:
        if sandbox_score >= 0.99:
            return True, "sandbox_verified_pass"
        if sandbox_score <= 0.5:
            return False, "sandbox_verified_fail"
        # Tie: both passed. Fall through to simplicity rule with tied reason.
        if (
            len(proposed.content) < len(existing.content) * 0.8
            and new_steps >= old_steps
        ):
            return True, "sandbox_tied_simplification"
        return False, "sandbox_tied_no_improvement"

    # 1. Content regression: <50% length without extra steps
    if is_content_regression(existing, proposed):
        return False, "content_regression"

    # 2. Content bloat: >2x length, no extra steps, negligible confidence gain
    if (
        len(proposed.content) > len(existing.content) * 2.0
        and new_steps <= old_steps
        and proposed.confidence <= existing.confidence + 0.05
    ):
        return False, "content_bloat"

    # 3. Cold-start: both at baseline with no outcomes
    if existing.outcome_count == 0 and proposed.confidence == existing.confidence:
        # 3a. Simplification wins even during cold-start (Karpathy rule)
        if (
            len(proposed.content) < len(existing.content) * 0.8
            and new_steps >= old_steps
        ):
            return True, "cold_start_simplification"

        # 3b. LLM evaluator signal (proxy for prepare.py)
        if evaluator_score is not None:
            if evaluator_score > 0.5:
                return True, "cold_start_evaluator_better"
            return False, "cold_start_evaluator_no_improvement"

        # 3b.5. Sandbox execution signal
        if sandbox_score is not None:
            if sandbox_score > 0.5:
                return True, "cold_start_sandbox_better"
            return False, "cold_start_sandbox_no_improvement"

        # 3c. Content quality heuristic fallback
        proposed_score = _content_quality_score(proposed)
        existing_score = _content_quality_score(existing)
        if proposed_score > existing_score:
            return True, "cold_start_better"
        return False, "cold_start_no_improvement"

    # 4. Strict hill-climbing on Bayesian confidence
    if proposed.confidence > existing.confidence:
        return True, "confidence_improved"

    # 5. Simplification reward (Karpathy rule): shorter + same steps + same confidence
    if (
        len(proposed.content) < len(existing.content) * 0.8
        and new_steps >= old_steps
        and proposed.confidence >= existing.confidence
    ):
        return True, "simplification"

    # 6. No improvement
    return False, "no_improvement"


# Environment-aware scoring
