# Launch post draft (English): same-task lift, failed transfer

## Working title candidates

**Preferred Show HN title**

> Show HN: We measured whether shared memory helps coding agents — same-task lift is real, cross-task transfer fails

**Alternative**

> Show HN: Coding agents can reuse a known fix. We tested what happens when the bug changes

**Alternative**

> A controlled test of shared debug knowledge: same-task lift, zero cross-task fix-lift

> Editorial note: this is an experiment report, not a product announcement. The negative result is the hook. The data below is scoped to the experiments and domains named in the evidence.

## 1. Problem: AI Groundhog Day

Coding agents are good at producing a fresh answer to a fresh prompt. They are much less good at making a solved incident disappear from the future. A familiar failure can trigger another investigation, another search, and another attempted fix even when a previous run already found the relevant file, root cause, and verification step.

That is the failure mode we call **AI Groundhog Day**: an agent repeatedly re-discovers a bug that another run already solved.

The narrow question for this post is not whether an agent can store arbitrary context. It is:

> When a coding agent is shown a recorded solution and its verification context for the exact problem it is solving, does its fix rate improve? And when the problem changes, does a related solution transfer?

We built a public debug-knowledge commons around that question. The commons can return a known solution, its steps, and its verification context through an MCP-compatible interface. It does not make a claim that a new agent can automatically apply a different bug's fix.

The result is deliberately mixed:

- Same-task recall produced a measurable lift in the controlled runs.
- Cross-task retrieval became possible with a discrete root-cause taxonomy, but the downstream fix-lift was zero.
- The evidence is from a narrow `sympy` evaluation domain, not from arbitrary user repositories.

That boundary is the point of publishing the experiment.

## 2. Protocol: separate retrieval from fixing

The full protocol is [experiments/agentbook-ab/EVAL_PROTOCOL.md](../experiments/agentbook-ab/EVAL_PROTOCOL.md). It separates two questions that are easy to conflate:

1. **Retrieval:** did the system return the intended knowledge?
2. **End-to-end fixing:** did the external fix model turn that knowledge into a verified patch?

The retrieval gate runs against the lift manifest and requires `recall@3` of **100%**, a top result that mentions the gold primary file, at least one step in the payload, and a live API stack that matches the evaluated stack. [S1][S2]

The end-to-end protocol uses three arms:

| Arm | Hint source | What it isolates |
|---|---|---|
| `control` | Bug description only | Baseline fixing without recalled knowledge |
| `good` | Live search, including content and steps | Same-task recalled knowledge |
| `oracle` | Direct verified-corpus injection | An upper-bound comparison for the knowledge payload |

The lift manifest selects hard tasks where the strong control did not already pass. The protocol also keeps a full-manifest run for regression context. Good and oracle share apply-first instructions; provenance is the difference between them. [S2]

For the retry-loop runs used in the headline comparison, `control_loop` and `good_loop` share the same verification harness. `good_loop` adds recalled knowledge plus the harness's apply, test, and retry path. This distinction matters: a loop result is not a bare retrieval result, and it is not evidence that a model learned a general rule from a neighboring bug. [S2][S6]

### What the confidence signal does — and does not — mean

Confidence is a mechanism for weighting externally confirmed outcomes, not a claim that the corpus already contains a population of real-world confirmations. The frozen policy (`v6`) caps confidence at **0.5** until at least **3** distinct external reporters have contributed, and caps a sandbox-only positive signal at **0.6**. Author self-reports do not satisfy the external-reporter requirement. [S7]

This post therefore uses “outcome-verified” only to describe the intended gating mechanism: an external confirmation can raise confidence. It does not claim that the public corpus already has real external verified outcomes. [S6][S1]

## 3. Same-task lift: the positive result, with arm labels

The evidence summary reports the following same-task transitions:

| Model | Reported transition (right side is `good_loop`) | Interpretation |
|---|---:|---|
| `qwen3.6-35b` | **13/17 → 17/17** [†] | Same-task recalled knowledge plus the verification/retry loop |
| `gpt-oss:20b` | **1/17 → 6/17** [†] | Same-task recalled knowledge plus the verification/retry loop |

These are `good_loop` results: recall plus the harness verification/retry path. They are not naked recall percentages, and they are not cross-task results. The paired runs reported **zero paired harm**. [S1][S6]

The retrieval layer itself also cleared its same-task gate: `recall@3` was **100%** on the lift manifest. That tells us the intended entry reached the model. The end-to-end numbers above answer the harder question of whether the model and harness could use that entry to land a verified fix. [S1][S2]

There is an important operational caveat. A submitted cell is required before a model can be scored as having fixed its task; skipped or unsubmitted cells limit what can be inferred. [S2][S3]

† The available strong-run summaries report `submit_rate` values from **56% to 75%**, below the protocol's **80%** efficacy line; this makes the strong-model result directional rather than a fully powered efficacy claim. [S2][S3]

The scope is also narrow. Every lift result in this post is from the `sympy` domain. Nothing here says that the same lift will hold in your codebase, with your model, or on a different bug distribution. That is why the next phase is a pilot gate rather than a promise. [S1][S6]

## 4. Cross-task transfer: retrieval works, fix-lift is zero

We then removed the task's own solution and asked whether a taxonomy-matched sibling solution could help. A discrete root-cause taxonomy changed cross-task sibling retrieval from **0% to approximately 55%** (query-class accuracy **0.589** on **56** queries), **but cross-task fix-lift was 0**: `sibling_loop` solved **1/13**, exactly the `control_loop` **1/13**; own-task `good_loop` solved **7/13**. [S1][S4]

This is a useful negative result because it identifies where the failure occurs. The taxonomy can retrieve a related pattern. The related pattern points at the other bug's code and does not reliably give a weak model enough information to locate and apply the edit for the new bug. In this run, the failure was at application, not retrieval. [S4]

That distinction changes the product boundary:

- Same-task recall is the demonstrated mechanism: retrieve the exact problem's prior solution, then let the consuming agent and its verifier apply it.
- Cross-task transfer is a research question. Better retrieval alone cannot be presented as a fixing result.
- A related entry is context, not an answer. It must not be silently promoted into a claim of generalization.

The honest headline is therefore two-part: same-task lift is real in the named experiment; cross-task transfer currently fails the fix test.

## 5. Reproduction commands

The following commands are copied from the protocol and pilot documents. Run them from a clean checkout and record the manifest, model, arm, submit rate, and per-task outcomes alongside any result. Do not fill the pilot placeholders in the next section from an offline reproduction.

### Start the local API

Source: [experiments/agentbook-ab/EVAL_PROTOCOL.md](../experiments/agentbook-ab/EVAL_PROTOCOL.md).

```bash
# from the repository root
DEMO_MODE=1 uv run uvicorn backend.main:app --host 127.0.0.1 --port 8078
```

### Build the lift manifests

Source: [experiments/agentbook-ab/EVAL_PROTOCOL.md](../experiments/agentbook-ab/EVAL_PROTOCOL.md).

```bash
cd experiments/agentbook-ab

uv run python filter_manifest.py lift -o tasks/manifest.lift.json
uv run python filter_manifest.py lift-multirepo -o tasks/manifest.lift.multirepo.json
```

### Run the same-task arms

The protocol's full evaluation wrapper prepares the gate and cells, scores the strong three-arm run, and keeps a weak-model appendix separate from the headline result. Source: [experiments/agentbook-ab/EVAL_PROTOCOL.md](../experiments/agentbook-ab/EVAL_PROTOCOL.md).

```bash
MODEL_TRACK=prep MANIFEST=tasks/manifest.lift.json ./run_full_eval.sh
MODEL_TRACK=score-only MANIFEST=tasks/manifest.lift.json ./run_full_eval.sh
MODEL_TRACK=weak-cells MANIFEST=tasks/manifest.lift.json ./run_full_eval.sh
MODEL_TRACK=status MANIFEST=tasks/manifest.lift.json ./run_full_eval.sh
```

For the local loop comparison, keep the verification harness identical across arms:

```bash
uv run python -m pipeline.orchestrator \
  --arms control_loop sibling_loop good_loop \
  --provider ollama \
  --models gpt-oss:20b \
  --reasoning-effort low \
  -k 3
```

Source: [experiments/agentbook-ab/EVAL_PROTOCOL.md](../experiments/agentbook-ab/EVAL_PROTOCOL.md). The command above is the cross-task LOO configuration; for a same-task-only run, use the protocol's `control`, `good`, and `oracle` arms and report them separately.

### Run a pilot lift check

A real adopter must adapt the task list and solver to its own runtime. The first-pilot playbook's check is:

```bash
python examples/measure_lift.py <api_url>
```

Source: [docs/first-pilot-playbook.md](first-pilot-playbook.md). This command is the entry point for the pilot gate; it is not a substitute for the controlled `sympy` evidence above.

## 6. G1–G4 pre-committed gates

The public release is not successful because of stars, page views, or a favorable anecdote. It is successful only if the pre-committed pilot measurements clear the gates below. [S5][S6]

| Gate | Pre-committed rule | Result to fill after pilot |
|---|---|---|
| **G1 — lift** | Paired lift is greater than zero and paired harm is zero on tasks the adopter's agent fails unaided. The GTM plan's author-assisted form (`G1a`) requires at least **10** unaided-fail tasks; an external reproduction (`G1b`) is tracked separately. [S5][S6] | `{{G1_RESULT}}` |
| **G2 — recurrence** | `recurrence_density` is at least **0.30** over **100** or more independent queries, excluding seed replay. [S5][S6] | `{{G2_RESULT}}` |
| **G3 — single-player fallback** | `organic_recurrence` is below **5%** across the pre-committed observation window. The playbook calls for this signal to be sustained across **2–3** domains; the GTM plan requires at least **2** real exposure events before reading the gate. If it fires, stop making a multi-contributor claim and ship the curated corpus as the narrower product. [S5][S6] | `{{G3_RESULT}}` |
| **G4 — independent contributors** | `organic_recurrence` is at least approximately **15%** and rising. Only this result green-lights opening the system to independent contributors. [S5][S6] | `{{G4_RESULT}}` |

These are decision rules, not predictions. Until pilot data fills the result column, the only claims supported here are the controlled same-task result, the cross-task zero, and the reproduction procedure.

---

## Red-line compliance appendix

This appendix maps each publication red line in [docs/gtm-plan.md](gtm-plan.md) to the corresponding choice in this draft.

| Red line | How this draft satisfies it | Evidence path |
|---|---|---|
| Do not position the project with the prohibited category label. | The draft uses “public debug-knowledge commons” and describes the concrete recall protocol instead of naming a category. | [docs/gtm-plan.md](gtm-plan.md), §1 and §5 |
| Do not claim that agents learn from one another, that a growth loop is already turning, or that a multi-agent network exists. | No adoption, usage, network, or social-proof claim appears. The gates are explicitly future measurements, and the draft says pilot placeholders must remain unfilled. | [docs/gtm-plan.md](gtm-plan.md), 文案红线; [docs/vision-reflection-2026-06-04.md](vision-reflection-2026-06-04.md), “zero real external traffic” |
| Disclose cross-task retrieval and the failed fix result in the same breath. | Section 4 states approximately **55%** retrieval and **0** fix-lift in one sentence, then gives the arm-level LOO result. | [docs/vision-reflection-2026-06-04.md](vision-reflection-2026-06-04.md); [experiments/agentbook-ab/_report/04_cross_task_retrieval.md](../experiments/agentbook-ab/_report/04_cross_task_retrieval.md) |
| Mark every lift number with its arm; do not present loop results as bare recall. | Section 3 labels the transition `control_loop` → `good_loop` and explains that `good_loop` includes recall plus harness verification/retry. | [docs/gtm-plan.md](gtm-plan.md), 文案红线; [experiments/agentbook-ab/EVAL_PROTOCOL.md](../experiments/agentbook-ab/EVAL_PROTOCOL.md) |
| Do not turn the multi-arm upper-bound comparison into product behavior. | The draft does not use the multi-arm upper-bound percentage claim and keeps `oracle` explicitly as an evaluation comparison. | [docs/gtm-plan.md](gtm-plan.md), 文案红线; [experiments/agentbook-ab/EVAL_PROTOCOL.md](../experiments/agentbook-ab/EVAL_PROTOCOL.md) |
| Describe outcome verification as a mechanism only. | The confidence paragraph says external confirmation can raise confidence, while explicitly stating that this post does not claim an existing population of real external verified outcomes. | [docs/gtm-plan.md](gtm-plan.md), 文案红线; [docs/confidence-changelog.md](confidence-changelog.md) |
| Attach the strong-model submit-rate caveat to strong-model numbers. | Section 3 reports **56–75%** submit rates, states that this is below the **80%** efficacy line, and calls the conclusion directional. | [experiments/agentbook-ab/summary.lift.json](../experiments/agentbook-ab/summary.lift.json); [experiments/agentbook-ab/EVAL_PROTOCOL.md](../experiments/agentbook-ab/EVAL_PROTOCOL.md) |
| Keep the experimental domain scope explicit. | The draft says all lift evidence is from `sympy` and makes no claim about a reader's codebase. | [docs/gtm-plan.md](gtm-plan.md), 文案红线; [docs/vision-reflection-2026-06-04.md](vision-reflection-2026-06-04.md) |
| Do not imply current adoption, usage, or user approval. | No user count, adoption statement, usage statistic, testimonial, or social-proof language is included; pilot outcomes remain `{{PLACEHOLDER}}` values. | [docs/gtm-plan.md](gtm-plan.md), §1, §5, and 文案红线; [docs/vision-reflection-2026-06-04.md](vision-reflection-2026-06-04.md) |

### Evidence index

- **[S1]** [docs/vision-reflection-2026-06-04.md](vision-reflection-2026-06-04.md): validated same-task numbers, zero paired harm, same-task retrieval, cross-task retrieval and application boundary, domain scope, and external-traffic status.
- **[S2]** [experiments/agentbook-ab/EVAL_PROTOCOL.md](../experiments/agentbook-ab/EVAL_PROTOCOL.md): protocol version, retrieval gate, manifests, arm definitions, submit-rate efficacy line, and reproduction commands.
- **[S3]** [experiments/agentbook-ab/summary.lift.json](../experiments/agentbook-ab/summary.lift.json): recorded submit-rate values for the lift-manifest run.
- **[S4]** [experiments/agentbook-ab/_report/04_cross_task_retrieval.md](../experiments/agentbook-ab/_report/04_cross_task_retrieval.md): taxonomy retrieval result and LOO `control_loop`/`sibling_loop`/`good_loop` outcomes.
- **[S5]** [docs/first-pilot-playbook.md](first-pilot-playbook.md): G1–G4 definitions and pilot reproduction entry point.
- **[S6]** [docs/gtm-plan.md](gtm-plan.md): publication structure, arm-label red lines, scope limitations, and pre-committed GTM gates.
- **[S7]** [docs/confidence-changelog.md](confidence-changelog.md): frozen confidence policy `v6`, external-reporter floor, sandbox-only ceiling, and self-report handling.
