"""Retrieval-quality baseline eval.

Runs the 65-query fixture against ``AgentbookService.search_problems`` over
the in-memory ``PROBLEM_TEMPLATES`` corpus, computes recall@k / MRR / nDCG /
latency / match_quality distribution, and either:

* ``EVAL_BASELINE_MODE=collect`` -- prints the report and skips assertions
  (use this to capture a fresh baseline for ``docs/retrieval-baseline.md``).
* ``EVAL_BASELINE_MODE=guard`` (default) -- parses the JSON fenced block
  beneath the active mode's heading in ``docs/retrieval-baseline.md`` and
  asserts that

    * ``dataset_version`` matches the current fixture exactly,
    * ``recall@{1,5,10}``, MRR, and binary nDCG@10 have not regressed
      beyond a 5-absolute-point tolerance,
    * ``no_false_exact_rate`` has not regressed at all,
    * p95 latency has not exceeded ``max(2x baseline, 50ms)`` — the
      absolute floor avoids spurious flakes when the fallback baseline is
      sub-millisecond.

The harness has two modes selected by the ``RUN_REAL_EVAL`` environment
variable:

* **fallback** (``RUN_REAL_EVAL`` unset, the default) — runs in the
  conftest-forced fallback environment (no Voyage, no OpenRouter, no DB),
  which makes the numbers deterministic and offline. The frozen baseline
  for this mode lives under ``## Frozen aggregate`` in
  ``docs/retrieval-baseline.md``. ``make eval`` and ``make fast`` exercise
  this path on every CI run.
* **real** (``RUN_REAL_EVAL=1`` plus ``VOYAGE_API_KEY`` set) — uses the
  production retrieval stack: Voyage 3-large embeddings + Voyage
  rerank-2.5-lite cross-encoder, still backed by in-memory repositories.
  The frozen baseline for this mode lives under
  ``## Frozen aggregate (real-mode)`` in ``docs/retrieval-baseline.md``.
  ``make eval-real`` exercises this path; it is deliberately excluded from
  ``make full`` because real-mode burns Voyage API quota.
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

_REGRESSION_DROP_TOLERANCE = 0.05
_LATENCY_P95_FACTOR = 2.0
# Absolute floor on the p95 latency assertion. The fallback baseline is
# sub-millisecond, so 2x of it is comparable to a single CI runner stall —
# we'd rather miss noise than red-flag clean PRs. Real regressions
# (accidental sync I/O, N+1 query) sit well above this floor anyway.
_LATENCY_P95_ABSOLUTE_FLOOR_MS = 50.0
_GUARDED_METRICS = ("recall@1", "recall@5", "recall@10", "mrr", "ndcg@10_binary")
_AGGREGATE_CATEGORIES = {
    "exact_signature",
    "signature_substring",
    "paraphrase_natural",
    "keyword_partial",
    "cross_topic_confusion",
}

# Heading anchors in docs/retrieval-baseline.md keyed by active mode. The
# parser uses these as exact section anchors so future per-environment
# blocks can co-exist without the regex picking the wrong JSON fence.
_BASELINE_ANCHORS = {
    "fallback": "## Frozen aggregate",
    "real": "## Frozen aggregate (real-mode)",
}


def _active_mode() -> str:
    """Return ``"real"`` when ``RUN_REAL_EVAL`` is set, otherwise ``"fallback"``.

    Anchored on ``RUN_REAL_EVAL`` rather than ``EVAL_BASELINE_MODE`` because
    mode selection is orthogonal to collect/guard: a real-mode run can be in
    either collect or guard, and so can fallback.
    """
    return "real" if os.environ.get("RUN_REAL_EVAL") else "fallback"


def _baseline_anchor(mode: str) -> str:
    """Return the markdown heading that anchors the JSON block for ``mode``."""
    try:
        return _BASELINE_ANCHORS[mode]
    except KeyError as exc:
        raise ValueError(f"unknown eval mode: {mode!r}") from exc


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

    # Graded nDCG was removed because the fixture only carries one
    # ``expected_match_quality`` per query — every ``expected_id`` ends up
    # with the same grade, so graded DCG/IDCG reduces to binary scaled by
    # a constant. Re-introduce per-target grades in the dataset before
    # adding it back.
    if contributes:
        metrics.update(
            {
                "recall@1": recall_at_k(result_ids, expected_ids, 1),
                "recall@5": recall_at_k(result_ids, expected_ids, 5),
                "recall@10": recall_at_k(result_ids, expected_ids, 10),
                "rr": reciprocal_rank(result_ids, expected_ids),
                "ndcg@10_binary": ndcg_at_k(
                    result_ids, expected_ids, 10, mode="binary"
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
    keys = ("recall@1", "recall@5", "recall@10", "rr", "ndcg@10_binary")
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


def print_report(
    per_query: list[dict], aggregate: dict, dataset: dict, mode: str
) -> None:
    stack_label = (
        "Voyage 3-large embedding + Voyage rerank-2.5-lite"
        if mode == "real"
        else "fallback embedding + noop rerank"
    )
    lines: list[str] = []
    lines.append("")
    lines.append("=" * 78)
    lines.append(f"RETRIEVAL QUALITY EVAL  (mode={mode}; {stack_label})")
    lines.append(f"dataset_version = {dataset['dataset_version']}")
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
        "mode": mode,
        "dataset_version": dataset["dataset_version"],
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


def _parse_baseline_from_md(path: Path, anchor: str) -> dict | None:
    """Extract the JSON block beneath ``anchor`` in ``path``.

    ``anchor`` is the literal markdown heading (e.g. ``"## Frozen aggregate"``
    or ``"## Frozen aggregate (real-mode)"``); it is regex-escaped before
    being inserted into the parser. The match is line-anchored (``MULTILINE``
    + ``^``) so the inline reference to ``## Frozen aggregate (real-mode)``
    in the document's intro paragraph is not mistaken for the actual heading
    — that bug would have silently aimed the real-mode parser at the
    fallback JSON fence.
    """
    if not path.exists():
        return None
    text = path.read_text()
    pattern = r"^" + re.escape(anchor) + r"[^\n]*\n.*?```json\s*\n(.*?)\n```"
    m = re.search(pattern, text, re.DOTALL | re.MULTILINE)
    if m is None:
        return None
    return json.loads(m.group(1))


def _assert_against_baseline(
    aggregate: dict, baseline: dict, dataset_version: str
) -> None:
    base_version = baseline.get("dataset_version")
    if base_version != dataset_version:
        raise AssertionError(
            f"\nDataset version mismatch:\n"
            f"  current dataset = {dataset_version!r}\n"
            f"  frozen baseline = {base_version!r}\n"
            f"\nGuard mode refuses to compare metrics across dataset versions. "
            f"Re-run EVAL_BASELINE_MODE=collect make eval and update "
            f"{BASELINE_MD_PATH}."
        )

    failures: list[str] = []
    overall = aggregate["overall"]
    base_overall = baseline["overall"]

    for metric in _GUARDED_METRICS:
        cur = overall.get(metric)
        base = base_overall.get(metric)
        if cur is None or base is None:
            continue
        drift = cur - base
        if drift < -_REGRESSION_DROP_TOLERANCE:
            failures.append(
                f"  {metric:18s} current={cur:.4f}  baseline={base:.4f}  "
                f"drift={drift:+.4f}  (tolerance -{_REGRESSION_DROP_TOLERANCE:.2f})"
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
    p95_threshold = max(base_p95 * _LATENCY_P95_FACTOR, _LATENCY_P95_ABSOLUTE_FLOOR_MS)
    if cur_p95 > p95_threshold:
        failures.append(
            f"  latency_p95_ms      current={cur_p95:.2f}  baseline={base_p95:.2f}  "
            f"threshold={p95_threshold:.2f}  "
            f"(max(baseline x {_LATENCY_P95_FACTOR}, "
            f"{_LATENCY_P95_ABSOLUTE_FLOOR_MS:.0f}ms))"
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


def _build_real_mode_service():
    """Build an in-memory ``AgentbookService`` wired to real Voyage providers.

    Mirrors the precedence chain in ``backend/main.py:_build_service`` but
    skips the OpenRouter/Fallback fallthrough — real-mode must use Voyage or
    not run at all, otherwise the printed metrics would silently describe
    the wrong stack. Caller is responsible for ensuring ``VOYAGE_API_KEY`` is
    present in the environment via the conftest ``RUN_REAL_EVAL`` carve-out.
    """
    from uuid import uuid4

    from backend.application.service import AgentbookService
    from backend.domain.models import Agent
    from backend.infrastructure.embeddings.voyage import (
        resolve_embedding_provider as resolve_voyage_embedding,
    )
    from backend.infrastructure.persistence.in_memory import (
        InMemoryAgentRepository,
        InMemoryOutcomeRepository,
        InMemoryProblemRepository,
        InMemoryResearchCycleRepository,
        InMemorySolutionRepository,
    )
    from backend.infrastructure.reranking import resolve_rerank_fn

    embedding_provider = resolve_voyage_embedding()
    if embedding_provider is None:
        raise RuntimeError(
            "real-mode eval requires a working Voyage embedding provider; "
            "resolve_embedding_provider returned None despite VOYAGE_API_KEY "
            "being set — check that the voyageai package is installed."
        )
    rerank_fn = resolve_rerank_fn()

    agents = InMemoryAgentRepository()
    author_id = uuid4()
    agents.add(Agent(api_key_hash="test-hash", model_type="test", agent_id=author_id))
    service = AgentbookService(
        agents=agents,
        embedding_provider=embedding_provider,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
        rerank_fn=rerank_fn,
    )
    return service, author_id


@pytest.mark.eval
def test_retrieval_quality_baseline(service_and_author) -> None:
    active_mode = _active_mode()
    if active_mode == "real" and not os.environ.get("VOYAGE_API_KEY"):
        # Skip BEFORE seeding the corpus so we don't waste time on a 65-query
        # run that has nowhere meaningful to land.
        pytest.skip("RUN_REAL_EVAL=1 requires VOYAGE_API_KEY in env (real-mode eval)")

    if active_mode == "real":
        service, author_id = _build_real_mode_service()
    else:
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
    print_report(per_query, aggregate, dataset, active_mode)

    baseline_mode = os.environ.get("EVAL_BASELINE_MODE", "guard")
    anchor = _baseline_anchor(active_mode)
    if baseline_mode == "collect":
        pytest.skip(
            f"EVAL_BASELINE_MODE=collect (mode={active_mode}): report printed, "
            f"skipping regression assertions. Paste the JSON block above under "
            f"the {anchor!r} heading in docs/retrieval-baseline.md."
        )

    baseline = _parse_baseline_from_md(BASELINE_MD_PATH, anchor)
    if baseline is None:
        pytest.fail(
            f"Frozen baseline ({active_mode} mode) not found beneath the "
            f"{anchor!r} heading at {BASELINE_MD_PATH}. Run "
            f"EVAL_BASELINE_MODE=collect "
            f"{'RUN_REAL_EVAL=1 ' if active_mode == 'real' else ''}"
            f"make {'eval-real' if active_mode == 'real' else 'eval'} "
            f"to populate it."
        )
    if baseline.get("placeholder") is True:
        pytest.fail(
            f"Frozen baseline ({active_mode} mode) is still the placeholder "
            f"under the {anchor!r} heading at {BASELINE_MD_PATH}. Run "
            f"EVAL_BASELINE_MODE=collect "
            f"{'RUN_REAL_EVAL=1 ' if active_mode == 'real' else ''}"
            f"VOYAGE_API_KEY=... uv run pytest "
            f"backend/tests/eval/test_retrieval_quality.py -v -s "
            f"and replace the placeholder JSON with the printed "
            f"`--- machine-readable JSON ---` block."
        )
    _assert_against_baseline(aggregate, baseline, dataset["dataset_version"])
