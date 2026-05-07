"""Retrieval-quality baseline eval.

Runs the 65-query fixture against ``AgentbookService.search_problems`` over
the in-memory ``PROBLEM_TEMPLATES`` corpus, computes recall@k / MRR / nDCG /
latency / match_quality distribution, and either:

* ``EVAL_BASELINE_MODE=collect`` -- prints the report and skips assertions
  (use this to capture a fresh baseline for ``docs/retrieval-baseline.md``).
* ``EVAL_BASELINE_MODE=guard`` (default) -- parses the JSON fenced block in
  ``docs/retrieval-baseline.md`` and asserts that ``recall@{1,5,10}``, MRR,
  binary nDCG@10, and ``no_false_exact_rate`` have not regressed beyond a
  5-absolute-point tolerance, and that p95 latency has not regressed beyond
  2x the frozen baseline.

The harness runs in the conftest-forced fallback environment (no Voyage,
no OpenRouter, no DB), which makes the numbers deterministic and offline.
A real-Voyage variant is out of scope for this PR.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path

import pytest

from backend.tests.eval._retrieval_corpus import seed_corpus
from backend.tests.eval._retrieval_metrics import (
    mean,
    ndcg_at_k,
    percentile,
    recall_at_k,
    reciprocal_rank,
)

DATASET_PATH = Path(__file__).parent / "retrieval_quality_dataset.json"
BASELINE_MD_PATH = (
    Path(__file__).parent.parent.parent.parent / "docs" / "retrieval-baseline.md"
)

_QUALITY_GRADE = {"exact": 3, "strong": 2, "partial": 1, "poor": 0}
_AGGREGATE_TOLERANCE = 0.05
_LATENCY_P95_FACTOR = 2.0
_GUARDED_METRICS = ("recall@1", "recall@5", "recall@10", "mrr", "ndcg@10_binary")
_AGGREGATE_CATEGORIES = {
    "exact_signature",
    "signature_substring",
    "paraphrase_natural",
    "keyword_partial",
    "cross_topic_confusion",
}


def _grades_for(query: dict, expected_ids: list[str]) -> dict[str, int]:
    quality = query.get("expected_match_quality")
    grade = _QUALITY_GRADE.get(quality, 0) if quality else 0
    return {pid: grade for pid in expected_ids}


def _score_query(
    q: dict,
    results: list[dict],
    expected_ids: list[str],
    latency_ms: float,
) -> dict:
    result_ids = [r["problem_id"] for r in results]
    contributes = q["expected_in_top_k"] > 0

    metrics: dict = {
        "id": q["id"],
        "category": q["category"],
        "expected_ids": expected_ids,
        "result_ids_top10": result_ids[:10],
        "expected_in_top_k": q["expected_in_top_k"],
        "top1_match_quality": results[0]["match_quality"] if results else None,
        "top1_similarity": results[0]["similarity_score"] if results else None,
        "latency_ms": latency_ms,
    }

    if contributes:
        grades = _grades_for(q, expected_ids)
        metrics.update(
            {
                "recall@1": recall_at_k(result_ids, expected_ids, 1),
                "recall@5": recall_at_k(result_ids, expected_ids, 5),
                "recall@10": recall_at_k(result_ids, expected_ids, 10),
                "rr": reciprocal_rank(result_ids, expected_ids),
                "ndcg@10_binary": ndcg_at_k(
                    result_ids, expected_ids, 10, mode="binary"
                ),
                "ndcg@10_graded": ndcg_at_k(
                    result_ids,
                    expected_ids,
                    10,
                    mode="graded",
                    grades_by_id=grades,
                ),
            }
        )
    else:
        metrics.update(
            {
                "recall@1": None,
                "recall@5": None,
                "recall@10": None,
                "rr": None,
                "ndcg@10_binary": None,
                "ndcg@10_graded": None,
            }
        )

    metrics["no_false_exact_ok"] = _no_false_exact(q, results, expected_ids)
    return metrics


def _no_false_exact(
    q: dict, results: list[dict], expected_ids: list[str]
) -> bool | None:
    """Category-driven success check.

    * out_of_corpus: no result may carry quality in {exact, strong}
    * cross_topic_confusion: no NON-target may carry quality == exact
    * other categories: not applicable
    """
    if q["category"] == "out_of_corpus":
        return not any(r["match_quality"] in {"exact", "strong"} for r in results)
    if q["category"] == "cross_topic_confusion":
        target_set = set(expected_ids)
        return not any(
            r["match_quality"] == "exact" and r["problem_id"] not in target_set
            for r in results
        )
    return None


def _aggregate_subset(rows: list[dict]) -> dict[str, float]:
    keys = (
        "recall@1",
        "recall@5",
        "recall@10",
        "rr",
        "ndcg@10_binary",
        "ndcg@10_graded",
    )
    out: dict = {"n": len(rows)}
    for k in keys:
        vals = [r[k] for r in rows if r.get(k) is not None]
        out["mrr" if k == "rr" else k] = mean(vals)
    return out


def aggregate_metrics(per_query: list[dict]) -> dict:
    contributing = [q for q in per_query if q["category"] in _AGGREGATE_CATEGORIES]
    overall = _aggregate_subset(contributing)

    by_category: dict[str, dict] = {}
    for cat in sorted({q["category"] for q in per_query}):
        in_cat = [q for q in per_query if q["category"] == cat]
        if cat in _AGGREGATE_CATEGORIES:
            by_category[cat] = _aggregate_subset(in_cat)

    nfe_rows = [q for q in per_query if q["no_false_exact_ok"] is not None]
    no_false_exact_rate = (
        mean([1.0 if q["no_false_exact_ok"] else 0.0 for q in nfe_rows])
        if nfe_rows
        else 1.0
    )

    quality_hist: dict[str, int] = defaultdict(int)
    for q in per_query:
        quality_hist[q["top1_match_quality"] or "none"] += 1

    latencies = [q["latency_ms"] for q in per_query]
    return {
        "overall": overall,
        "by_category": by_category,
        "no_false_exact_rate": no_false_exact_rate,
        "no_false_exact_n": len(nfe_rows),
        "match_quality_distribution": dict(quality_hist),
        "latency_p50_ms": percentile(latencies, 50),
        "latency_p95_ms": percentile(latencies, 95),
        "n_queries": len(per_query),
    }


def _fmt(x) -> str:
    if x is None:
        return "  -  "
    if isinstance(x, float):
        return f"{x:.3f}"
    return str(x)


def print_report(per_query: list[dict], aggregate: dict) -> None:
    lines: list[str] = []
    lines.append("")
    lines.append("=" * 78)
    lines.append("RETRIEVAL QUALITY EVAL  (fallback embedding + noop rerank)")
    lines.append("=" * 78)

    lines.append("")
    lines.append("--- contributing queries (excluding perfect R@1=R@10=1.0) ---")
    shown = 0
    for q in per_query:
        if q["category"] not in _AGGREGATE_CATEGORIES:
            continue
        if (
            q["recall@1"] is not None
            and q["recall@10"] is not None
            and q["recall@1"] >= 1.0
            and q["recall@10"] >= 1.0
        ):
            continue
        shown += 1
        lines.append(
            f"  [{q['id']}] {q['category']:24s} "
            f"R@1={_fmt(q['recall@1'])}  R@5={_fmt(q['recall@5'])}  "
            f"R@10={_fmt(q['recall@10'])}  RR={_fmt(q['rr'])}  "
            f"top1={q['top1_match_quality']}"
        )
    if shown == 0:
        lines.append("  (all contributing queries scored R@1=R@10=1.0)")

    lines.append("")
    lines.append("--- no-false-exact checks (confusion + out_of_corpus) ---")
    for q in per_query:
        if q["no_false_exact_ok"] is None:
            continue
        flag = "OK  " if q["no_false_exact_ok"] else "FAIL"
        lines.append(
            f"  [{q['id']}] {q['category']:24s} {flag}  "
            f"top1_quality={q['top1_match_quality']}  "
            f"top1_sim={_fmt(q['top1_similarity'])}"
        )

    overall = aggregate["overall"]
    lines.append("")
    lines.append(f"--- aggregate (n={overall['n']} contributing) ---")
    for k in (
        "recall@1",
        "recall@5",
        "recall@10",
        "mrr",
        "ndcg@10_binary",
        "ndcg@10_graded",
    ):
        lines.append(f"  {k:18s} = {overall[k]:.4f}")
    lines.append(
        f"  no_false_exact     = {aggregate['no_false_exact_rate']:.4f}  "
        f"(n={aggregate['no_false_exact_n']})"
    )
    lines.append(f"  latency_p50_ms     = {aggregate['latency_p50_ms']:.2f}")
    lines.append(f"  latency_p95_ms     = {aggregate['latency_p95_ms']:.2f}")
    lines.append(
        f"  top1_quality_dist  = {dict(sorted(aggregate['match_quality_distribution'].items()))}"
    )

    lines.append("")
    lines.append("--- by category (contributing categories only) ---")
    for cat, m in aggregate["by_category"].items():
        lines.append(
            f"  {cat:24s} n={m['n']:2d}  "
            f"R@1={m['recall@1']:.3f}  R@5={m['recall@5']:.3f}  "
            f"R@10={m['recall@10']:.3f}  MRR={m['mrr']:.3f}  "
            f"nDCG@10b={m['ndcg@10_binary']:.3f}"
        )

    lines.append("")
    lines.append(
        "--- machine-readable JSON (paste into docs/retrieval-baseline.md) ---"
    )
    payload = {
        "dataset_version": _load_dataset()["dataset_version"],
        "overall": overall,
        "no_false_exact_rate": aggregate["no_false_exact_rate"],
        "latency_p50_ms": aggregate["latency_p50_ms"],
        "latency_p95_ms": aggregate["latency_p95_ms"],
    }
    lines.append(json.dumps(payload, indent=2, sort_keys=True))

    lines.append("=" * 78)
    print("\n".join(lines))


def _load_dataset() -> dict:
    return json.loads(DATASET_PATH.read_text())


def _parse_baseline_from_md(path: Path) -> dict | None:
    """Extract the first ```json fenced block from the baseline markdown."""
    if not path.exists():
        return None
    text = path.read_text()
    m = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if m is None:
        return None
    return json.loads(m.group(1))


def _assert_against_baseline(aggregate: dict, baseline: dict) -> None:
    failures: list[str] = []
    overall = aggregate["overall"]
    base_overall = baseline["overall"]

    for metric in _GUARDED_METRICS:
        cur = overall.get(metric)
        base = base_overall.get(metric)
        if cur is None or base is None:
            continue
        drift = cur - base
        if drift < -_AGGREGATE_TOLERANCE:
            failures.append(
                f"  {metric:18s} current={cur:.4f}  baseline={base:.4f}  "
                f"drift={drift:+.4f}  (tolerance -{_AGGREGATE_TOLERANCE:.2f})"
            )

    cur_nfe = aggregate["no_false_exact_rate"]
    base_nfe = baseline.get("no_false_exact_rate", 0.0)
    if cur_nfe < base_nfe:
        failures.append(
            f"  no_false_exact_rate current={cur_nfe:.4f}  baseline={base_nfe:.4f}  "
            f"(must not regress)"
        )

    cur_p95 = aggregate["latency_p95_ms"]
    base_p95 = baseline.get("latency_p95_ms", 0.0)
    if base_p95 > 0 and cur_p95 > base_p95 * _LATENCY_P95_FACTOR:
        failures.append(
            f"  latency_p95_ms      current={cur_p95:.2f}  baseline={base_p95:.2f}  "
            f"(>{_LATENCY_P95_FACTOR}x)"
        )

    if failures:
        msg = (
            "\nRetrieval quality regression detected:\n"
            + "\n".join(failures)
            + f"\n\nIf this drift is intended, run "
            f"EVAL_BASELINE_MODE=collect make eval and update {BASELINE_MD_PATH} "
            f"with the new numbers in the same PR."
        )
        raise AssertionError(msg)


@pytest.mark.eval
def test_retrieval_quality_baseline(service_and_author) -> None:
    service, author_id = service_and_author
    template_to_pid = seed_corpus(service, author_id)
    dataset = _load_dataset()

    per_query: list[dict] = []
    for q in dataset["queries"]:
        expected_ids = [template_to_pid[i] for i in q["expected_template_indices"]]
        t0 = time.perf_counter()
        payload = service.search_problems(query=q["query"], limit=10)
        latency_ms = (time.perf_counter() - t0) * 1000
        per_query.append(_score_query(q, payload["results"], expected_ids, latency_ms))

    aggregate = aggregate_metrics(per_query)
    print_report(per_query, aggregate)

    mode = os.environ.get("EVAL_BASELINE_MODE", "guard")
    if mode == "collect":
        pytest.skip(
            "EVAL_BASELINE_MODE=collect: report printed, skipping regression "
            "assertions. Paste the JSON block above into docs/retrieval-baseline.md."
        )

    baseline = _parse_baseline_from_md(BASELINE_MD_PATH)
    if baseline is None:
        pytest.fail(
            f"Frozen baseline not found at {BASELINE_MD_PATH}. "
            f"Run EVAL_BASELINE_MODE=collect make eval to populate it."
        )
    _assert_against_baseline(aggregate, baseline)
