# Agentbook A/B Evaluation Protocol (v3 final)

Two-layer protocol separating **retrieval quality** from **end-to-end fix quality**.
**Headline conclusions** use the **lift manifest** — tasks where strong control did not pass.

## Why v3?

v1/v2 measured good vs control on the full 54-task sympy slice. Many tasks were
already solvable without hints (control PASS), compressing `rag_gain` toward zero.
Good-arm prompts also omitted **steps** that oracle received, inflating
`retrieval_loss` even when tag recall was 100%.

v3 fixes both: **lift task selection** + **good/oracle prompt parity** (steps +
apply-first instructions).

---

## Layer 1 — Retrieval (agentbook internal)

1. Seed from `_oracle/corpus.seed.json` (hand corpus + gold excerpts).
2. Good arm uses live `GET /v1/search` (Voyage embed + rerank when keyed).
3. Gate (`eval_retrieval_gate.py`) must pass before agent runs:

| Metric | Threshold |
|--------|-----------|
| `recall@3` on `ab_task:{instance_id}` | 100% |
| `content_sufficient@1` | top-1 mentions gold primary file |
| `steps_present@1` | top-1 payload includes ≥1 step |
| Stack audit | matches live API stack (typically `embedding=voyage`, `rerank=voyage`) |

Gate probes the running API for expected providers (not client-side env alone).

---

## Layer 2 — End-to-end (external fix model)

### Manifests

| Manifest | Role |
|----------|------|
| **`tasks/manifest.lift.json`** | **Primary headline** — 16 hard tasks where control ≠ PASS |
| `tasks/manifest.lift.multirepo.json` | Primary multirepo (16 sympy + 2 sklearn) |
| `tasks/manifest.json` | Full sympy slice (54) — regression only |
| `tasks/manifest.hard.json` | Hard sympy without lift filter |

Generate:

```bash
uv run python filter_manifest.py lift -o tasks/manifest.lift.json
uv run python filter_manifest.py lift-multirepo -o tasks/manifest.lift.multirepo.json
```

Lift eligibility comes from strong control scores (`results.sympy.json`), then
weak OpenRouter, then static fallback (`benchmark/eligibility.py`).

### Three arms

| Arm | Hint source |
|-----|-------------|
| **control** | Bug description only |
| **good** | Live RAG (`GET /v1/search`) — content **and steps** |
| **oracle** | Direct verified corpus injection (upper bound) |

Good and oracle share **apply-first** instructions; only provenance differs.

### Fix models

| Track | Model | Arms | Role |
|-------|-------|------|------|
| **Strong** (headline) | Cursor sub-agent | control, good, oracle | Primary conclusions |
| **Weak** (appendix) | OpenRouter **`openai/gpt-oss-20b:free` only** | control, good | Directional only |

OpenRouter **hard constraint:** only `openai/gpt-oss-20b:free` is allowed
(`run_openrouter_cells.py` allowlist). No paid fallback on 429 — exponential
backoff on free, then `api_error` + `retry-errors`.

### Success metrics

Report full-manifest and lift-eligible subsets:

| Metric | Definition |
|--------|------------|
| **rag_gain_eligible** | `good_pass − control_pass` on lift-eligible tasks (headline) |
| **paired lift (control FAIL)** | control FAIL → good PASS on eligible subset |
| **retrieval_loss_eligible** | `oracle_pass − good_pass` on eligible subset |
| **submit_rate** | submitted / tasks per arm — headline underpowered if strong &lt; 80% |

Weak OpenRouter single-shot runs are **not** primary evidence for RAG value.

---

## Commands

```bash
# API (repo root)
DEMO_MODE=1 uv run uvicorn backend.main:app --host 127.0.0.1 --port 8078

cd experiments/agentbook-ab

# Regenerate lift manifests (after strong scores update)
uv run python filter_manifest.py lift -o tasks/manifest.lift.json
uv run python filter_manifest.py lift-multirepo -o tasks/manifest.lift.multirepo.json

# Prep lift manifest (gate + cells)
MODEL_TRACK=prep MANIFEST=tasks/manifest.lift.json ./run_full_eval.sh

# Strong three-arm: Cursor per AGENT_CELL_RULES.md, then score
MODEL_TRACK=score-only MANIFEST=tasks/manifest.lift.json ./run_full_eval.sh

# Weak appendix (free only)
MODEL_TRACK=weak-cells MANIFEST=tasks/manifest.lift.json ./run_full_eval.sh
./run_openrouter_benchmark.sh retry-errors   # api_error cells

# Cell progress
MODEL_TRACK=status MANIFEST=tasks/manifest.lift.json ./run_full_eval.sh
```

---

## Outputs

| File | Content |
|------|---------|
| `retrieval_gate_report.json` | Layer 1 metrics |
| `results.lift.json` | Layer 2 strong three-arm scores (headline) |
| `summary.lift.json` | rag_gain_eligible, retrieval_loss_eligible, submit_rate |
| `results.openrouter.lift.json` | Weak appendix (not headline) |

Filter prior full-manifest strong scores to lift subset:

```bash
uv run python filter_results.py results.sympy.json \
  --manifest tasks/manifest.lift.json -o results.lift.json
uv run python summarize_ab.py results.lift.json \
  --manifest tasks/manifest.lift.json -o summary.lift.json
```
