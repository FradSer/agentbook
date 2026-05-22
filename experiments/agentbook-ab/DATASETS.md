# Coding-agent benchmark datasets (survey)

Survey for refactoring agentbook A/B. **Primary substrate today:** SWE-bench Verified (no-Docker sympy slice). **Multi-repo pilot:** sklearn + pytest via `setup_bench.sh --multirepo`.

## Tier 1 — Issue resolution (pass@1, our current task shape)

| Dataset | Scale | Langs | Grading | Agentbook fit | Access |
|---------|-------|-------|---------|---------------|--------|
| [SWE-bench Verified](https://huggingface.co/datasets/SWE-bench/SWE-bench_Verified) | 500 instances | Mostly Python | Fail→pass tests | **In use** — sympy 54 RED-verified | HF `SWE-bench/SWE-bench_Verified` |
| **Multi-repo pilot** | sklearn 2 RED-verified (+ pytest blocked no-Docker) | Python | Same no-Docker harness | `tasks/manifest.multirepo.json` (27 tasks) | `build_benchmark.py --multirepo` |
| [SWE-bench Full](https://www.swebench.com/) | 2.3k | Python | Docker harness | Same pipeline, heavier infra | HF + Docker |
| [SWE-bench-Live](https://github.com/microsoft/SWE-bench-Live) | +50/mo | Multi | Fresh issues | Anti-contamination longitudinal | GitHub + HF |
| [SWE-Bench Pro](https://arxiv.org/html/2509.16941) | 1,865 | Multi | Enterprise/long-horizon | Harder lift surface; license/partners | Separate release |
| [SWE-rebench / V2](https://arxiv.org/html/2602.23866) | 32k+ | 20 langs | Automated decontam | Scale + multilingual; not sympy-only | Paper + pipeline |

## Tier 2 — Context / memory (retrieval metrics, complements pass@1)

| Dataset | Scale | Focus | Agentbook fit | Notes |
|---------|-------|-------|---------------|-------|
| [ContextBench](https://contextbench.github.io/) | 1,136 tasks, 66 repos | Gold context recall/precision | **Best match** for recall@k on hints | 8 languages; process-oriented |
| [SWE-ContextBench](https://arxiv.org/pdf/2602.08316) | 1,100 + 376 related | Cross-issue experience reuse | Good for sequential agentbook sessions | Dependency-linked tasks |
| [SWE-Bench-CL](https://arxiv.org/html/2507.00014v1) | Verified-based streams | Continual learning | Stability/plasticity of memory | Chronological splits |
| AMA-Bench | Trajectory QA | Long-horizon agent memory | Orthogonal to code fix | arXiv:2602.22769 |

## Tier 3 — Beyond bugfix (not v1 A/B)

| Dataset | Focus |
|---------|--------|
| [SWE Atlas](https://arxiv.org/html/2605.08366v1) | Q&A, test writing, refactor (284 tasks) |

## Selection for agentbook-ab v2

1. **Keep** `tasks/manifest.json` as the 54-task sympy regression baseline.
2. **Multi-repo pilot:** `./setup_bench.sh --multirepo` RED-verifies sklearn 1.3 (2/7 passed) and attempts pytest (0/12 — version lock-in needs Docker or per-task venv). Writes `tasks/manifest.multirepo.json` (25 sympy hard + 2 sklearn = **27 tasks**).
3. **Retrieval gate (required before A/B):** `MANIFEST=tasks/manifest.multirepo.json ./run_retrieval_gate.sh` — asserts Voyage embed/rerank and recall@3 on `ab_task` tags.
4. **Manifest presets:** `uv run python filter_manifest.py hard|multirepo -o tasks/manifest.*.json`
5. **Hard tier rules:** drop sympy 1.4–1.6; drop `<15 min` unless control-failed; keep control-fail tasks.

## Local data layout

```
_data/verified.parquet        # fetch_verified.py
_data/red_verify_report.json  # build failures by repo
_repo/<name>/                 # clone_repos.py (--multirepo)
tasks/manifest.json           # sympy regression (54)
tasks/manifest.hard.json      # sympy hard tier (~25)
tasks/manifest.multirepo.json # hard + sklearn/pytest pilot
tasks/<id>/                   # BUG.md, META.json, repo/ (gitignored)
_oracle/<id>/                 # gold.patch, test.patch (never agent-visible)
recalls/                      # per-task GET /v1/search audit JSON
retrieval_gate_report.json    # gate metrics
```
