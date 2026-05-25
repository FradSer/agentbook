"""Paired control-vs-good analysis with the exact-binomial McNemar test.

Exact (not chi-squared) because discordant counts are small in this regime.
"""

from __future__ import annotations

from math import comb


def paired_table(pairs: list[tuple[bool, bool]]) -> dict:
    """pairs = (control_bool, good_bool). Returns the 2x2 outcome counts."""
    both_pass = sum(1 for c, g in pairs if c and g)
    both_fail = sum(1 for c, g in pairs if not c and not g)
    lift = sum(1 for c, g in pairs if not c and g)  # control FAIL -> good PASS
    harm = sum(1 for c, g in pairs if c and not g)  # control PASS -> good FAIL
    return {
        "n": len(pairs),
        "both_pass": both_pass,
        "both_fail": both_fail,
        "lift": lift,
        "harm": harm,
    }


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact-binomial McNemar p-value for discordant counts b, c."""
    n = b + c
    if n == 0:
        return 1.0
    x = min(b, c)
    tail = sum(comb(n, i) for i in range(x + 1)) * (0.5**n)
    return min(2.0 * tail, 1.0)


def mcnemar(pairs: list[tuple[bool, bool]]) -> dict:
    table = paired_table(pairs)
    p = mcnemar_exact(table["lift"], table["harm"])
    return {**table, "p_value": p}
