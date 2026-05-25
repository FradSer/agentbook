"""Resolved-rate / pass@k / pass^k metrics. SKIP/empty/parse-failure => FAIL.

A "task outcome" for a (model, arm) cell is derived from its k sample booleans:
  - pass@k  (any-of-k): task resolved if >=1 sample resolved.
  - pass^k  (all-of-k): task resolved only if ALL k samples resolved.
"""

from __future__ import annotations

from collections import defaultdict
from math import comb


def pass_at_k(n: int, c: int, k: int) -> float:
    """Unbiased pass@k estimator for n samples with c successes (n>=k)."""
    if k <= 0 or n <= 0:
        return 0.0
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


def build_outcomes(records: list[dict]) -> dict[tuple[str, str], dict[str, list[bool]]]:
    """(model, arm) -> {instance_id: [resolved_bool per sample]}."""
    out: dict[tuple[str, str], dict[str, list[bool]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in records:
        model, arm, iid = r.get("model"), r.get("arm"), r.get("instance_id")
        if not (model and arm and iid):
            continue
        out[(model, arm)][iid].append(bool(r.get("resolved")))
    return out


def task_bool(samples: list[bool], criterion: str) -> bool:
    if not samples:
        return False
    if criterion == "strict":
        return all(samples)
    return any(samples)  # pass@k


def arm_rate(tasks: dict[str, list[bool]], criterion: str) -> tuple[float, int, int]:
    """Return (rate, resolved_tasks, total_tasks) for one (model, arm)."""
    total = len(tasks)
    resolved = sum(task_bool(s, criterion) for s in tasks.values())
    rate = resolved / total if total else 0.0
    return rate, resolved, total


def diagnostics(records: list[dict]) -> dict[tuple[str, str], dict]:
    """Per (model, arm): submit rate, skip rate, mean turns, stop-reason mix."""
    by: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in records:
        if r.get("model") and r.get("arm"):
            by[(r["model"], r["arm"])].append(r)
    out = {}
    for key, rows in by.items():
        n = len(rows)
        submitted = sum(1 for x in rows if x.get("submitted"))
        turns = [x.get("turns_used") or 0 for x in rows]
        stops: dict[str, int] = defaultdict(int)
        for x in rows:
            stops[x.get("stop_reason") or "unknown"] += 1
        out[key] = {
            "samples": n,
            "submit_rate": round(submitted / n, 3) if n else 0,
            "skip_rate": round((n - submitted) / n, 3) if n else 0,
            "mean_turns": round(sum(turns) / n, 1) if n else 0,
            "stop_reasons": dict(stops),
        }
    return out


def paired_units(
    outcomes: dict[tuple[str, str], dict[str, list[bool]]],
    model: str,
    arm_a: str,
    arm_b: str,
    criterion: str,
) -> list[tuple[bool, bool]]:
    """Paired (arm_a_bool, arm_b_bool) over tasks present in both arms."""
    a = outcomes.get((model, arm_a), {})
    b = outcomes.get((model, arm_b), {})
    shared = sorted(set(a) & set(b))
    return [(task_bool(a[i], criterion), task_bool(b[i], criterion)) for i in shared]


def pooled_units(
    outcomes: dict[tuple[str, str], dict[str, list[bool]]],
    models: list[str],
    arm_a: str,
    arm_b: str,
    criterion: str,
) -> list[tuple[bool, bool]]:
    """Pool paired units across the panel (each model-task is one paired unit)."""
    units: list[tuple[bool, bool]] = []
    for m in models:
        units.extend(paired_units(outcomes, m, arm_a, arm_b, criterion))
    return units
