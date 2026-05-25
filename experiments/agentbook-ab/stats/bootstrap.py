"""Paired bootstrap CI for the resolved-rate lift (good - control)."""

from __future__ import annotations

import random


def bootstrap_delta(
    pairs: list[tuple[bool, bool]], *, b: int = 10000, seed: int = 0
) -> dict:
    """pairs = (control_bool, good_bool). Statistic: mean(good) - mean(control).

    Resamples tasks (paired) with replacement; returns point delta and 95% CI.
    """
    n = len(pairs)
    if n == 0:
        return {"delta": 0.0, "ci_low": 0.0, "ci_high": 0.0, "n": 0}
    point = (sum(g for _, g in pairs) - sum(c for c, _ in pairs)) / n
    rng = random.Random(seed)
    deltas: list[float] = []
    for _ in range(b):
        sc = sg = 0
        for _ in range(n):
            c, g = pairs[rng.randrange(n)]
            sc += c
            sg += g
        deltas.append((sg - sc) / n)
    deltas.sort()
    lo = deltas[int(0.025 * b)]
    hi = deltas[min(int(0.975 * b), b - 1)]
    return {
        "delta": round(point, 4),
        "ci_low": round(lo, 4),
        "ci_high": round(hi, 4),
        "n": n,
    }
