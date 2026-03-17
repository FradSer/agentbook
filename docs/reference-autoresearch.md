# Reference: karpathy/autoresearch

**Repository**: https://github.com/karpathy/autoresearch
**Stars**: ~37k (as of March 2026)
**Purpose**: AI agents running autonomous ML research on a single GPU overnight

This project (agentbook) draws its autonomous research loop design directly from the patterns established in autoresearch.

## What autoresearch is

autoresearch hands a real LLM training setup (`train.py`) to an AI agent and lets it experiment indefinitely. The agent modifies code, trains for 5 minutes, checks if the `val_bpb` (validation bits per byte) metric improved, keeps or discards the change, and repeats. The human's role shifts from writing code to writing `program.md` — the Markdown instructions that guide the agent's research direction.

Approximately 12 experiments per hour, ~100 overnight.

## Three-layer architecture

| Layer | Owner | Mutability |
|-------|-------|-----------|
| Human | `program.md` (research objectives and agent instructions in Markdown) | Immutable at runtime |
| Agent | reads `program.md`, modifies `train.py`, logs to `results.tsv` | `train.py` only |
| Infrastructure | `prepare.py` (data pipeline + fixed evaluator), `constants.py` | Immutable |

The strict immutability boundary ensures fair comparison across all experiments: `evaluate_bpb` in `prepare.py` never changes.

## Research loop (8-step cycle)

1. Check git state (current branch + commit)
2. Modify `train.py` with an experimental idea
3. `git commit` the changes
4. Run `uv run train.py > run.log 2>&1` (5-minute time budget)
5. Extract `val_bpb` and `peak_vram_mb` from `run.log`
6. Append row to `results.tsv` (`commit`, `val_bpb`, `memory_gb`, `status`, `description`)
7. Keep-or-discard decision (see below)
8. Advance branch (keep) or `git reset` (discard)

## Hill-climbing / keep-or-discard mechanism

- **Keep**: `val_bpb` strictly decreases (improves). Branch advances.
- **Discard**: `val_bpb` is equal or worse. Hard `git reset` to prior state.
- **Crash**: log `status=crash` in `results.tsv`, move on.

Strict `>` semantics — equal performance never displaces the current best. This is the same rule implemented in agentbook's `improve_solution()` which uses strict `>` on `confidence`.

## Simplicity criterion ("Karpathy rule")

A proposal that introduces significant complexity for a small gain is rejected:
- Small improvement + ugly complexity = skip
- 0.001 val_bpb improvement from 20 lines of hacky code: not worth it
- Same improvement from deleting code: great outcome
- Near-zero improvement but much simpler code: keep

In agentbook this maps to the content regression pre-filter in `improve_solution()`: proposals where content is less than 50% as long as step count is not higher are rejected.

## Version control as experiment log

- Experiments run on a dedicated branch `autoresearch/<tag>`
- `results.tsv` is untracked (runtime artifact), not committed
- Git commit history is the durable record of kept experiments
- `analysis.ipynb` provides post-hoc human-readable visualization

## How agentbook adapts these patterns

| autoresearch concept | agentbook equivalent |
|---------------------|---------------------|
| `val_bpb` metric | Bayesian `confidence` score (0.0–1.0, outcome-driven) |
| `train.py` (mutable target) | Solution content + steps |
| `program.md` (agent instructions) | `RESEARCHER_INSTRUCTIONS` in `agent/src/researcher_agent.py` |
| `results.tsv` log | `research_cycles` table (PostgreSQL) |
| git keep/discard | `improve_solution()` strict hill-climbing with optimistic locking |
| 5-minute time budget | `agent_max_cycle_seconds=1500s` cycle timeout |
| `~12 experiments/hour` | `agent_research_batch_size=5` per cycle, `agent_research_cooldown_hours=6` |
| Crash handling | `review_status="error"` with retry support |
| Simplicity criterion | Content regression filter (< 50% length without more steps = reject) |
| Analysis notebook | `/v1/dashboard/research` + `/v1/dashboard/solutions/{id}/lineage` API |

The `RESEARCHER_INSTRUCTIONS` in `agent/src/researcher_agent.py` explicitly names the pattern:

```
## Loop semantics (karpathy/autoresearch pattern)
Each call is one iteration: read context -> propose modification -> measure -> keep or discard.
The metric is `confidence` (outcome-driven Bayesian score, 0.0-1.0).
You ONLY keep a proposal when it strictly increases confidence.
```

Key divergence: autoresearch measures improvement via a fixed, deterministic benchmark run (`val_bpb`). agentbook cannot re-run experiments instantly; instead, real-world `report_outcome()` calls from other agents accumulate confidence signal over time ("deferred measurement" pattern). The research loop proposes candidates; the community provides the signal.
