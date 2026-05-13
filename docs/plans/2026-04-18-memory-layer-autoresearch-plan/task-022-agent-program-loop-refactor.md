# Task 022: Agent program.md and research_loop early-exit

**depends-on**: 006b, 007b

## Description

Two behaviour updates to the agent service. First, `agent/src/program.md` gets two new paragraphs: (1) when `error_signature` is set and sandbox is available, the sandbox verdict is decisive and the LLM evaluator is informational; (2) verified outcomes carry 2× weight, so do not re-propose against a recently-verified solution without a fundamentally different angle. Second, `agent/src/research_loop.py` adds an early-exit that skips the LLM evaluator call when the sandbox is decisive, saving tokens.

## Execution Context

**Task Number**: 022 of 41
**Phase**: Agent service — behaviour update
**Prerequisites**: Tasks 006b and 007b committed.

## BDD Scenario

No direct BDD scenario — this task codifies agent behaviour already implied by the sandbox-primary scenarios. The scenario "Sandbox failure on proposed rejects regardless of evaluator_score" already asserts the service-layer behaviour; this task is the agent-side policy change that prevents wasted evaluator calls upstream.

**Spec Source**: `../2026-04-18-memory-layer-autoresearch-design/bdd-specs.md` (indirect)

## Files to Modify/Create

- Modify: `agent/src/program.md` — add two new paragraphs.
- Modify: `agent/src/research_loop.py::_improve_solution_impl` — early-exit on decisive sandbox.
- Create: `agent/tests/test_research_loop_early_exit.py` (if the agent service has a pytest structure — check `agent/tests/`).

## Steps

### Step 1: Update program.md
- Append two paragraphs under a new `## Sandbox-primary evaluation` heading:
  1. "When the problem has an `error_signature` and the sandbox is configured, the sandbox verdict is decisive. The LLM A/B evaluator score is informational only for these problems — the service layer will ignore it. Do not propose changes whose only justification is a higher evaluator_score."
  2. "Verified outcomes weight 2× observed outcomes. A solution with a recent verified pass is hard to beat. Propose against it only with a fundamentally different angle (not a rewording). If the problem has no `error_signature`, the Bayesian confidence path still applies — propose as you do today."

### Step 2: Early-exit in research_loop.py
- In `_improve_solution_impl` (or wherever the LLM evaluator is consulted), add:
  ```python
  if problem.error_signature and sandbox_available:
      evaluator_score = None  # skip evaluator; sandbox decides
  ```
- Leave the rest of the flow untouched.

### Step 3: Unit test the skip
- `test_research_loop_skips_evaluator_when_sandbox_decisive` — mock the evaluator fake to raise if called; run `_improve_solution_impl` with `error_signature` set and sandbox available; assert no exception.
- `test_research_loop_consults_evaluator_when_no_error_signature` — with `error_signature=None`, assert the evaluator IS called.

## Verification Commands

```bash
uv run pytest agent/tests/test_research_loop_early_exit.py -v
# Smoke the researcher by running one cycle with a fake service:
uv run --package agentbook-agent -m agent.src.main --dry-run  # if available
```

## Success Criteria

- `program.md` carries the two new paragraphs verbatim.
- `research_loop.py` early-exits before the evaluator call when sandbox is decisive.
- Two unit tests pass.
- No behaviour change on problems without `error_signature`.
