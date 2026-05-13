# Task 024: Autoresearch reference re-verification

**depends-on**: (none)

## Description

Re-verify that karpathy/autoresearch (https://github.com/karpathy/autoresearch) has not drifted from the 15-day-old mapping recorded in `reference_autoresearch.md`. Specifically confirm: `val_bpb` is still the metric; `prepare.py` is still the immutable evaluation harness; the 5-minute training budget per experiment is unchanged; the binary keep/discard (`git commit` vs `git reset`) loop semantics are unchanged. Update the design reference memory with any drift.

## Execution Context

**Task Number**: 024 of 41
**Phase**: Reference hygiene
**Prerequisites**: none (research task).

## BDD Scenario

No BDD scenario. This is a plan-phase prerequisite flagged in `_index.md` Discovery Results (task 000 of the design). It unblocks confident promotion of the sandbox-primary branch.

**Spec Source**: design `_index.md` Discovery Results — "Autoresearch reference integrity".

## Files to Modify/Create

- Modify: `/Users/FradSer/.claude/projects/-Users-FradSer-Developer-FradSer-agentbook/memory/reference_autoresearch.md` — update with any drift findings.

## Steps

### Step 1: Fetch current repo state
- Use WebFetch or Context7 on the autoresearch README and top-level files. Alternative: `git clone --depth 1 https://github.com/karpathy/autoresearch /tmp/autoresearch` and inspect locally.

### Step 2: Confirm invariants
Check each claim from the memory file:
- `prepare.py` computes `val_bpb` (val bits-per-byte). Still true?
- `train.py` is the single mutable file. Still true?
- `program.md` is the agent's instruction file. Still true?
- 5-minute budget per training run. Still true?
- Binary keep/discard via git. Still true?
- Simplicity criterion is agent-judged (qualitative). Still true?
- No reporter-diversity concept (single-agent loop). Still true?

### Step 3: Record findings
- If all invariants hold: append one line to `reference_autoresearch.md` at the top: `Verified 2026-04-xx — all claims hold.`
- If any drift: update the mapping section + document the divergence in the agentbook `_index.md` Discovery Results amendment.

### Step 4: Flag downstream impact
- If drift changes the mapping (e.g., autoresearch introduced multi-agent support), open an issue or append to this plan's `_index.md` Risk Log.

## Verification Commands

```bash
# Ad-hoc research — no test runner.
cat /Users/FradSer/.claude/projects/-Users-FradSer-Developer-FradSer-agentbook/memory/reference_autoresearch.md | head
```

## Success Criteria

- `reference_autoresearch.md` has a verification timestamp within the last 24 hours.
- Any drift documented inline with explicit before/after values.
- If drift affects the sandbox-primary rationale, `_index.md` Rationale section is amended with a link to this task.
