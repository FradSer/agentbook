# Agentbook A/B cell rules (three arms: control + good + oracle)

**Harness:** Good-arm hints come only from the **agentbook API** (`GET /v1/search`).
Oracle-arm hints are **direct verified corpus injection** (upper bound, no search).
Problems/solutions are seeded via `seed_agentbook.py` before runs.

**Primary manifest:** `tasks/manifest.lift.json` (16 tasks where strong control ≠ PASS).
Full 54-task sympy slice is regression only.

**Search stack (server-side only):** Voyage embed + rerank inside agentbook for good arm.
The external fix model must **not** re-call search — use the recall in `prompt.md`.

**Retrieval gate:** `./run_retrieval_gate.sh` must pass before agent runs:

| Metric | Threshold |
|--------|-----------|
| `recall@3` | 100% |
| `content_sufficient@1` | 100% |
| `steps_present@1` | 100% (good-arm steps in search payload) |

You are fixing **one** benchmark cell: `runs/<instance_id>__<arm>/`.

## Arms

| Arm | Agentbook |
|-----|-----------|
| **control** | No agentbook; fix from bug description only |
| **good** | Hint from live `GET /v1/search` (RAG) in `prompt.md` — content **and steps** |
| **oracle** | Verified accurate hint injected directly (upper bound) |

Good and oracle share **apply-first** instructions; only provenance differs.

## Allowed reads

- `runs/<instance_id>__<arm>/prompt.md`
- Source under `runs/<instance_id>__<arm>/repo/`

## Forbidden

- `_oracle/` (gold.patch, test.patch, corpus files)
- `META.json`, `recalls/` for gold paths
- Other arms' workspaces
- Re-calling agentbook on good arm (use baked recall)

## Finish

```bash
cd runs/<instance_id>__<arm>/repo
git add -A
git commit -m "agent fix"
```

Do not run `score.py` or grading pytest.

## Orchestration

```bash
# Prep (gate + cells)
MODEL_TRACK=prep MANIFEST=tasks/manifest.lift.json ./run_full_eval.sh

# Progress
MODEL_TRACK=status MANIFEST=tasks/manifest.lift.json ./run_full_eval.sh

# After all cells committed
MODEL_TRACK=score-only MANIFEST=tasks/manifest.lift.json ./run_full_eval.sh
```

Strong track uses **Cursor sub-agents only** (not OpenRouter). OpenRouter
`openai/gpt-oss-20b:free` is weak appendix (control + good) via
`MODEL_TRACK=weak-cells`.
