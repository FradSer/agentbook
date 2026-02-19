# Task 026 — Implement: Solution Synthesis Pipeline

**Type:** Green (implementation)
**Depends-on:** task-025
**BDD refs:** Feature 4 all scenarios

## Goal

Implement the synthesis pipeline and update the ReviewerAgent to use it instead of approve/reject gating.

## What to implement

### In `agent/src/synthesis.py` (extend task-024 file)

**`synthesize_solutions(solutions, problem, llm_fn) -> Solution`**

1. Build prompt for `llm_fn`: include `problem.description`, all solution `content` values numbered, instruction to produce one canonical unified solution
2. Call `llm_fn(prompt)` — gets synthesized content string
3. Aggregate outcome stats from source solutions: `total_outcomes = sum(s.outcome_count)`, `total_successes = sum(s.success_count)`
4. Compute inherited confidence: `total_successes / total_outcomes` (or 0.5 if zero outcomes)
5. Create new `Solution(problem_id=problem.problem_id, author_id=SYSTEM_AGENT_ID, content=llm_result, confidence=inherited, outcome_count=total_outcomes, success_count=total_successes, author_verified=True)`
6. Return new solution (caller is responsible for persisting)

**`_mark_superseded(solutions, canonical_id) -> list[Solution]`**

Sets `solution.canonical_id = canonical_id` on all source solutions. Returns modified list (caller persists).

**`run_synthesis_cycle(service_v2, similarity_fn, llm_fn) -> dict`**

1. Fetch all problems via `service_v2` (or directly via repo)
2. For each problem, fetch its solutions
3. Call `find_synthesis_candidates` to get clusters
4. For each cluster: call `synthesize_solutions`, add canonical to repo, call `_mark_superseded` and update sources in repo
5. Return `{"synthesized": count, "skipped": skipped_count}`

### Update `agent/src/reviewer_agent.py`

Remove approve/reject tools. Add `run_synthesis` tool that calls `run_synthesis_cycle`. Remove the polling-based `review_threads` and `review_comments` loops from `agent/src/main.py`. Replace with an event-driven check: run synthesis cycle once per poll interval IF `find_synthesis_candidates` returns non-empty results.

### System agent ID

Define `SYSTEM_AGENT_ID` constant (a fixed UUID) for solutions created by the synthesis system — not a real registered agent.

## Files to modify

- `agent/src/synthesis.py` — extend with `synthesize_solutions`, `_mark_superseded`, `run_synthesis_cycle`
- `agent/src/reviewer_agent.py` — remove approve/reject, add synthesis tool
- `agent/src/main.py` — replace review loops with synthesis cycle call

## Verification

```bash
uv run pytest tests/unit/test_solution_synthesis.py -v
```

All tests from task-025 must pass (green).
