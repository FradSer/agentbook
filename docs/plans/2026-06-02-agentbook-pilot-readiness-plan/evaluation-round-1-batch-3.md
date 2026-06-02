# Evaluation Report — Round 1, Batch 3

**Mode:** code (independent superpowers-evaluator pass, spawned by main agent)
**Sprint contract:** `sprint-contract-batch-3.md`
**Checklist:** `docs/retros/checklists/code-v2.md`
**Verdict:** PASS

## Verification Commands (run independently)

| Command | Exit | Evidence |
|---|---|---|
| `uv run pytest backend/tests/unit/test_honest_match_labeling.py -q` | 0 | 5 passed |
| `uv run pytest backend/tests/unit/test_recall_latency.py -q` | 0 | 7 passed |
| `make fast` | 0 | 685 passed, 1 skipped, 13 deselected in 24.43s |
| `bash scripts/check_frozen_policy.sh` | 0 | "frozen_policy v6 is documented." |
| `git diff --stat backend/application/confidence.py` | empty | untouched |
| ruff (7 Python batch files) | 0 | All checks passed! |

## Result

Both Red-Green pairs sound.

**005 honest-labeling:** `service.py:709-717` caps `best_solution is None` rows to `_NO_SOLUTION_TIER` (`service.py:95`, outside `_GOOD_MATCH_TIERS` `service.py:89`) and stamps `has_help` per row. `no_good_match` derives from `_GOOD_MATCH_TIERS` membership (`service.py:544-546`), so a zero-solution sole candidate yields `no_good_match=True`. The Batch-2 `_dedup_advisory` (`service.py:1652-1705`) is a separate path — untouched, no regression. Labeling computed once in `_search_problems` and flows through both transports (orphan test exercises both `mcp_recall` and `rest_search`).

**006 latency — scope deviation verified correct:** coordinator changed ONLY `voyage.py`, not the listed `service.py`. Confirmed valid: the retry storm lived entirely in `voyage._embed_batch_with_retry` (below the `EmbeddingProvider` Protocol boundary). Live `embed()` now passes `retry_delays=_LIVE_RETRY_DELAYS_SECONDS=()` (single attempt, no sleep); client built `timeout=2.0, max_retries=0`; full `(1,2,4)` retained ONLY on offline `embed_documents` backfill. `service._safe_embed` (`service.py:1099-1103`) already swallows failures → keyword fallback; a miss already returns `no_good_match=True`/`search_mode="no_match"`. The request path genuinely cannot trigger a multi-second storm without a service.py change.

**No fake timing:** decisive assertions are structural (`_LIVE_RETRY_DELAYS_SECONDS == ()`, `max_retries == 0`, `embed.call_count == 1` live vs `len(_RETRY_DELAYS_SECONDS)` backfill), driving the REAL `VoyageEmbeddingProvider` with a stubbed `voyageai.Client` (`_StormClient`). Using the generic `embedding_fault` double would have bypassed the real retry code — the author's deviation is the stronger choice.

**Peer-test edits (CODE-SCOPE-01 exception b):** all three (`test_response_transparency`, `test_search_rerank_integration`, `test_voyage_embedding_provider`) are legitimate invalidated-test fixes, not regression-masking.

## Rework Items

None.

## Recurring patterns

CODE-EDIT-02 ruff-strips-import watch from Batch 2 did NOT recur (006/005 added no new imports). Drop from watch.

## Pivot

false.
