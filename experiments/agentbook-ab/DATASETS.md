# Coding-agent benchmark datasets (survey)

Survey for refactoring agentbook A/B. **Primary substrate today:** SWE-bench Verified (no-Docker sympy slice). **Recommended additions** for memory/retrieval eval are marked.

## Tier 1 — Issue resolution (pass@1, our current task shape)

| Dataset | Scale | Langs | Grading | Agentbook fit | Access |
|---------|-------|-------|---------|---------------|--------|
| [SWE-bench Verified](https://huggingface.co/datasets/SWE-bench/SWE-bench_Verified) | 500 instances | Mostly Python | Fail→pass tests | **In use** — sympy 54 RED-verified | HF `SWE-bench/SWE-bench_Verified` |
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

1. **Keep** SWE-bench Verified as sole *fix* substrate until RED-verify works for more repos (`probe_substrate.py`).
2. **Manifest tiers** use static difficulty/patch/version rules — not prior `results.json` (avoids circular eval).
3. **Eval slice `eval-v2`:** drop sympy 1.4–1.6 expansion, drop `<15 min fix`, require gold patch ≥ 15 lines → maximizes control/good/bad separation.
4. **Full slice `full`:** all 54 RED-verified sympy tasks (regression / headline number).
5. **Future:** add ContextBench subset for recall@1 on injected hints without pass@1 confound.

## Local data layout

```
_data/verified.parquet     # fetch_verified.py
_repo/<name>/              # clone_repos.py
tasks/<id>/                # BUG.md, META.json, repo/ (gitignored)
_oracle/<id>/             # gold.patch, test.patch (never agent-visible)
```
