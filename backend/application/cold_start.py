"""Cold-start content quality comparison for hill-climbing.

When no outcomes exist, Bayesian confidence is identical for all solutions
(baseline 0.3). This module provides a heuristic quality score to enable
hill-climbing during cold-start, analogous to autoresearch's instant val_bpb.
"""

from __future__ import annotations

from backend.domain.models import Solution


def cold_start_compare(existing: Solution, proposed: Solution) -> bool:
    """Return True if proposed solution is better than existing during cold-start."""
    existing_score = _content_quality_score(existing)
    proposed_score = _content_quality_score(proposed)
    return proposed_score > existing_score


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

    specificity_markers = ["```", "$ ", "sudo ", "pip ", "npm ", "apt ", "brew "]
    marker_count = sum(1 for m in specificity_markers if m in solution.content)
    score += min(marker_count, 4) * 0.05  # max 0.2

    return score
