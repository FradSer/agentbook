from __future__ import annotations

import math


Z_SCORE_95 = 1.96


def calculate_wilson_score(upvotes: int, downvotes: int) -> float:
    total_votes = upvotes + downvotes
    if total_votes == 0:
        return 0.0

    positive_ratio = float(upvotes) / total_votes
    z_squared = Z_SCORE_95 * Z_SCORE_95
    margin = math.sqrt(
        (positive_ratio * (1 - positive_ratio) + z_squared / (4 * total_votes))
        / total_votes
    )
    numerator = positive_ratio + z_squared / (2 * total_votes) - Z_SCORE_95 * margin
    denominator = 1 + z_squared / total_votes
    return numerator / denominator
