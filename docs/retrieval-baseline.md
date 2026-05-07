# Retrieval Quality Baseline (Frozen)

This document is the **frozen reference** for `backend/tests/eval/test_retrieval_quality.py`. The harness reads the JSON block below in `EVAL_BASELINE_MODE=guard` (the default) and asserts that current numbers have not regressed.

| Field | Value |
|---|---|
| Dataset | `backend/tests/eval/retrieval_quality_dataset.json` |
| Dataset version | `2026-05-07.v1` |
| Corpus | `backend/tests/simulation/stress_agents.PROBLEM_TEMPLATES` (15 problems, list-index order) |
| Mode | fallback embedding + noop reranker (the default test environment, forced by `backend/tests/conftest.py:isolate_runtime_settings_for_tests`) |
| Tolerance | 5 absolute points on `recall@{1,5,10}`, `mrr`, `ndcg@10_binary` (drops only — gains are unrestricted but should be re-frozen in the same PR). `no_false_exact_rate` must not regress at all. `latency_p95_ms` may grow up to 2× before it fails. |
| Captured | 2026-05-07, `EVAL_BASELINE_MODE=collect uv run pytest backend/tests/eval/test_retrieval_quality.py -v -s` |

## Frozen aggregate (machine-readable; do not edit by hand)

```json
{
  "dataset_version": "2026-05-07.v1",
  "latency_p50_ms": 0.2536250394769013,
  "latency_p95_ms": 0.471667037345469,
  "no_false_exact_rate": 1.0,
  "overall": {
    "mrr": 1.0,
    "n": 58,
    "ndcg@10_binary": 0.9986158756749688,
    "ndcg@10_graded": 0.8620689655172413,
    "recall@1": 0.9741379310344828,
    "recall@10": 1.0,
    "recall@5": 1.0
  }
}
```

## By-category (informational, not asserted)

| Category | n | recall@1 | recall@5 | recall@10 | MRR | nDCG@10 binary |
|---|---|---|---|---|---|---|
| `exact_signature` | 15 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| `signature_substring` | 10 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| `paraphrase_natural` | 15 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| `keyword_partial` | 10 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| `cross_topic_confusion` | 8 | 0.812 | 1.000 | 1.000 | 1.000 | 0.990 |

The 0.812 R@1 in `cross_topic_confusion` is structural, not a defect: three of those queries (q051, q055, q056) declare two legitimate targets each — only one of the two can occupy rank 0, so R@1 = 0.5 for those rows by construction.

## top1 match-quality distribution (n=65)

```
exact:    25
strong:   32
partial:   2
none:      6   ← out_of_corpus (4) + empty/short edge queries (2)
```

## Update procedure

Updating the frozen numbers is a deliberate act, not a routine:

1. Run `EVAL_BASELINE_MODE=collect uv run pytest backend/tests/eval/test_retrieval_quality.py -v -s` and inspect the printed per-query report.
2. Confirm the drift is intended (a retrieval-logic change is in the same diff) — silent shifts in fallback-mode numbers usually indicate a regression, not an improvement.
3. Replace the JSON block above with the freshly printed `--- machine-readable JSON ---` block.
4. Update the by-category and top1-quality tables for human readers.
5. Bump `dataset_version` only if the queries themselves changed; service-side improvements that re-rank the same queries leave the version alone.
6. Reviewers: question any drop greater than 2 percentage points without a corresponding `service.py` / retrieval-stack change in the same PR.

## What this baseline does not measure

- **Real Voyage embeddings + cross-encoder rerank** — the conftest forces fallback. Real-mode numbers belong in a follow-up PR that adds an `RUN_REAL_EVAL=1` opt-in fixture and a separate JSON block here.
- **Solution-aware retrieval (`format="full"`)** — this baseline only exercises `format="concise"`. A solution-aware eval needs the corpus seeded with solutions and outcomes.
- **Cold-start / cache-miss latency** — `service._search_cache` is empty per `service_and_author` fixture, so all numbers reflect a cold cache, but they do not reflect the first request after `service` startup in production.
