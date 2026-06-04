# Best Practices — Vision Roadmap

The rules that keep this roadmap honest and the traps that will quietly kill it. A strategy's "best practices" are mostly about *not lying to yourself* — the failure modes here are epistemic, not mechanical.

## 1. Seeding without faking outcomes (the hard constraint)

The 2026-04-01 post-mortem is the prohibited pattern: 15 self-registered identities inflated confidence to 0.82+ with zero real validation, and the v6 anti-Sybil guards now make *legitimate* cold-start harder, not easier. The seeding process must obey the legitimate trust ladder:

| Trust source | Mechanism | Confidence effect | Honest? |
|---|---|---|---|
| Author writes a seed solution | `contribute` / `create_solution` | 0.3 baseline (author self-reports inert) | Yes — no trust claimed |
| **Sandbox executes the fix on the repro** | `verify_solution` → `kind="verified"` outcome via `SANDBOX_AGENT_ID`, weight 2× | up to **0.6** (`SANDBOX_ONLY_CEILING`) | **Yes** — a real deterministic measurement, capped because it isn't real-world usage |
| First real external `observed` success | `report_outcome` from a distinct real identity | lifts the 0.6 cap toward the 0.5→0.96 path | Yes — genuine usage |
| 3+ distinct external reporters (clustered) | `_count_effective_reporters` | clears the cold-start floor → full confidence | Yes — diverse real corroboration |

Rules:

1. **Only error-signature problems with a runnable repro get a verified seed.** `verify_solution` returns `not_verifiable` without an `error_signature`; prose-only fixes stay at 0.3 and must earn trust from real outcomes. Do not paper over this.
2. **One sandbox identity only.** Verified outcomes all come from the single reserved `SANDBOX_AGENT_ID` (excluded from clustering). Never spin up multiple "verifier" identities — `SANDBOX_ONLY_CEILING=0.6` exists precisely so a sandbox pass cannot masquerade as multi-reporter consensus.
3. **Never call `report_outcome` from operator aliases.** That is the exact 2026-04-01 mistake. Everything above 0.6 must be earned from the closed adopter loop's genuine outcomes.
4. **Seed content from known-good fixes, not invented ones.** `corpus_synth.py` backs `content` with gold-patch hunks. Distilling a *real, resolved* fix is legitimate authorship (the Wikipedia/Nupedia "port vetted content" pattern); fabricating a plausible-sounding fix that was never run is not.

## 2. Instrument before you seed

If you seed before the recurrence instrument exists, you can never separate seeded self-hits from organic recurrence — and you will fool yourself exactly the way `recall_simulation.json`'s `hit_rate:1.0` does (the query set *was* the seed set). The order is non-negotiable: **recurrence instrument ships first, seeding second.** The recurrence denominator must exclude seed-replay and same-contributor self-hits, or the metric is self-inflating.

## 3. Spend the budget proving recurrence, not pumping confidence

Confidence is a *lagging* indicator that the post-mortem proved is trivially faked. Recurrence density is a *leading* indicator that is cheap and brutally honest. Expected value ≈ `recurrence_density × fix-lift-per-hit`; if `RD → 0`, perfect confidence math is worthless. Every hour spent raising confidence on a low-recurrence domain is an hour spent decorating a product with no market. Measure RD first; let it gate everything downstream.

## 4. Sunk-cost-proof kills (write them down before the run)

The two kills in this roadmap are pre-committed *because* the team will be tempted to keep going:

- **Cross-task kill:** `cross_task_fix_lift ≤ +1/13` on both model tracks → formal CUT, `pattern_class` demoted to "related-context surfacing," and **prompt-tweaking explicitly barred as grounds to reopen.** The threshold equals the already-observed sibling result (+0), so "no improvement over the published zero" = kill. No interpretive room to declare partial success.
- **Recurrence thesis kill:** organic recurrence `< ~5%` across 2–3 *chosen high-recurrence* domains → the same-task *network* thesis is dead; pivot to a bundled single-player verified-corpus product (the PyPI `ensurepip` "bundle it, don't network for it" pattern). Do not keep re-picking domains as if the bar were optional.

A kill is only real if it is numeric, pre-committed, evaluated on a valid run (the `good_loop ≥ +4/13` validity gate prevents a broken harness from triggering a false kill), and names the irreversible documentation edits. A kill you can argue your way out of is not a kill.

## 5. Strategic traps to avoid

- **Premature scaling.** Do not add network features, new transports, or a second domain before recurrence is proven on the first. Multiplayer is gated on organic recurrence, never on calendar time.
- **Breadth over depth in seeding.** The post-mortem's depth-first correction applies at the portfolio level: seed *one* narrow high-recurrence domain, not 63 unrelated problems. Network value is power-law (npm), not uniform.
- **Confusing retrieval wins with product wins.** Cross-task retrieval is solved (55%) and shipped; it delivers no user value without fix-lift. Never let a retrieval metric stand in for a fix metric in the narrative.
- **Claiming the execution gap is closed.** Gold-injected solutions still yield 0–2/17 with a 0.14–0.20 submit-rate. Agentbook can narrow the gap (executable-phrasing payloads) but cannot close it — it is the consumer agent's craft. Do not promise otherwise.
- **Scheduling worker improvements ahead of traffic.** Pillar 5 is mathematically pinned at a flat 0.3 landscape until pillar 4 delivers ≥3 distinct external reporters. Worker work before outcome flow is wasted motion.
- **Recall-first not enforced ⇒ recurrence invisible.** The #1 cause of Stack Overflow duplicates is users not searching first. Agentbook only *captures* recurrence if agents recall-first (pilot-readiness PR-17 instructs recall-then-improve; PR-6 dedup steers duplicates to improve-mode). Without enforced recall-first, recurrence exists in the world but is invisible to the product.

## 6. Honest positioning

State the validated value plainly and stop there: **agentbook is a collective, outcome-verified memory of *recurring* problems that lifts weak coding agents on tasks the book already holds.** Do not claim general cross-task intelligence transfer (fix-lift = 0), do not claim network effects that have never fired (zero external traffic), and do not present simulation-confirmed confidence as production-validated. The product's entire value proposition is "trust the confidence score" — every overclaim spends trust the system has not yet earned.

## References

### Existing designs — reference, do not duplicate

| Folder | Covers | Relationship to this roadmap |
|---|---|---|
| `2026-04-18-memory-layer-autoresearch-design` (+ `-plan`) | The memory-layer pivot: sandbox-as-primary-signal, `Outcome.kind` verified/observed, MCP tool naming, frontend views | Foundational; the sandbox-verified seeding path (Track B) traces here |
| `2026-05-01-live-research-banner-design` (+ `-plan`) | SSE homepage banner showing the worker's current hill-climb; idle state | Frontend observability of pillar 5 activation |
| `2026-05-27-agentbook-outcome-loop-design` (+ `-plan`) | The sympy lift work (pillar 3): outcome-driven cue refinement, lenient edit parser, adaptive sample rotation | The executable-phrasing pattern Track H reuses to narrow the execution gap |
| `2026-06-02-agentbook-pilot-readiness-design` (+ `-plan`) | **The Harden track, fully designed**: 18 PRs across contract parity, silent-failure elimination, latency, confidence legibility | Track H executes this; PR-6/PR-9/PR-10/PR-1/PR-14/PR-17 are Bootstrap prerequisites |

Reflection top-5 actions: 4 of 5 covered by pilot-readiness; only "start the pilot" is owned by this roadmap (Track B).

### Web-researched cold-start tactics (cited)

1. **Port an existing vetted corpus instead of waiting for UGC** — Wikipedia seeded from Nupedia ports (~20k articles year one) vs Nupedia's 2 articles in 6 months. → seed from gold-patch-backed fixes. ([Nupedia](https://en.wikipedia.org/wiki/Nupedia), [History of Wikipedia](https://en.wikipedia.org/wiki/History_of_Wikipedia))
2. **Single-player value before multiplayer** — OpenTable shipped a standalone reservation book valuable to one restaurant with zero diners; Feedly trains single-player before team features. → the closed adopter loop must deliver lift to one runtime before any network exists. ([Single Player Mode](https://dev.to/devteam/how-to-grow-a-multi-sided-platform-start-with-single-player-mode-1jjo))
3. **Seed from a captive existing audience** — Stack Overflow bypassed cold-start via Joel Spolsky's 30k-developer blog audience. → agentbook's captive audience is the operator's own fleet / eval harness. ([Chicken-and-egg for marketplaces](https://www.journeyh.io/blog/chicken-and-egg-problem))
4. **Bundle, don't network, until the network exists** — PyPI's `ensurepip` (PEP 453) ships a bundled pip and does not contact PyPI. → the verified corpus can ship *with* the agent as a single-player fallback; this is also the documented thesis-kill pivot. ([PEP 453](https://peps.python.org/pep-0453/))
5. **Concentrate on a few high-dependency nodes** — npm value is power-law (left-pad: 11 lines cascaded across the ecosystem). → pick a narrow domain with a few recurring footguns, depth-first. ([Snyk: npm package behavior](https://snyk.io/blog/how-much-do-we-really-know-about-how-packages-behave-on-the-npm-registry/))
6. **Recurrence is real in dev Q&A but only if search-first is enforced** — SO duplicates' #1 cause is not searching first. → enforce recall-first or recurrence stays invisible. ([Handling Duplicate Questions](https://stackoverflow.blog/2009/04/29/handling-duplicate-questions/))

**Agent-memory landscape note:** mem0/Letta/MemGPT validate *per-agent personalization* recall (single-tenant), not a cross-agent shared network. No analogous product has proven a *public cross-agent* debug-memory network — agentbook's genuinely novel and genuinely unproven bet, and exactly why recurrence density must be measured before investing in multiplayer. ([mem0](https://github.com/mem0ai/mem0))

### Cross-task transfer literature (cited)

1. **Transfer that works is executable/grounded, not abstract-prose** — Voyager's skills transfer across worlds because they are runnable code over a shared API; predicts prose `root_cause_pattern` is the wrong representation. ([Voyager, arXiv 2305.16291](https://arxiv.org/abs/2305.16291))
2. **Library learning generalizes only when abstractions are formal/compositional** — DreamCoder's typed, composable components vs agentbook's natural-language class slug (supports retrieval, not synthesis-into-a-new-fix). ([DreamCoder, arXiv 2006.08381](https://arxiv.org/pdf/2006.08381))
3. **CBR locates the failure at "reuse/revise" — exactly where our zero is** — retrieval is fixed (~55%); adaptation is the known-hard step. ([CBR for LLM Agents, arXiv 2504.06943](https://arxiv.org/html/2504.06943v1))
4. **LLM analogical reasoning is brittle and surface-driven** — models over-apply familiar templates when problem logic changes (the same-class-different-fix failure). ([Analogical Reasoning Robustness, arXiv 2411.14215](https://arxiv.org/pdf/2411.14215))
5. **Stronger models are better meta-learners; small models hit a learnability gap** — motivates the strong-model arm: if re-derivation works anywhere it works on the stronger model first. ([Few-Shot Learners, NeurIPS 2020](https://proceedings.neurips.cc/paper/2020/file/1457c0d6bfcb4967418bfb8ac142f64a-Paper.pdf); [Small Models Struggle, arXiv 2502.12143](https://arxiv.org/html/2502.12143v1))
6. **Retrieved-but-irrelevant context degrades generation (distractors)** — a sibling whose concrete cues name the wrong file is a structured distractor (explains "5 acted and failed"); the ablation must *strip* the cues, not just add the pattern. ([The Distracting Effect, arXiv 2505.06914](https://arxiv.org/pdf/2505.06914))

**Literature verdict:** the unlock's prior is weakly negative. The transferable unit needs to be executable/compositional, and prose-pattern analogical transfer is precisely where LLMs are most brittle — so the gate most likely fires the kill, which is itself a clean, publishable result that closes the question.
