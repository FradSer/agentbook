# Task 004 (write-dedup) — Impl (Green)

**type:** impl
**theme:** P0-B
**closes:** PR-6, PR-17
**depends-on:** [004-write-dedup-test]

## Goal

Make the Red tests from 004-write-dedup-test pass. Populate `existing_problems` without depending on embeddings: add an exact `error_signature` match leg (via the existing `ProblemRepository.find_by_error_signature`) to `service.contribute`, folded into the similarity advisory, and surface `existing_problems` on the REST `ProblemCreateResponse`. Prepend recall-first / improve-on-match guidance to the MCP `remember` tool description (PR-17).

Clean Architecture discipline: keep business logic in `AgentbookService`; Presentation layers only serialize. Do NOT bump `confidence.py:__frozen_policy_version__` — every confidence-related change here only *surfaces* values the frozen math already computes.

## BDD Scenarios (target behavior)

```gherkin
Feature: Write-time dedup advisory on the contribute write contract

  A unified memory layer's value is one evolving agentbook per problem
  accumulating outcomes and confidence. The write path must not let agents
  silently fork duplicates of an already-known problem. When a contributed
  problem's description or error_signature matches an existing one, the write
  response must populate existing_problems so the agent can switch to
  improve-mode instead of creating a duplicate. This feeds the canonical /
  synthesis flow, which needs >= 2 active solutions on ONE problem.

  Scenario: Identical error_signature surfaces the existing problem
    Given a problem already exists with error_signature "RuntimeError: Event loop is closed"
    When an authenticated agent contributes a new problem with the same error_signature
    Then the response populates existing_problems with the prior problem_id
    And the response advises improve-mode (provide solution_id) over creating a fork

  Scenario: Near-identical description surfaces the existing problem
    Given a problem already exists describing an asyncpg pool-close RuntimeError on shutdown
    When an agent contributes a paraphrased description of the same failure
    Then existing_problems is non-empty
    And the top entry's match_quality is "strong" or "exact"

  Scenario: A genuinely novel problem reports no existing match
    Given no problem matches the contributed description or error_signature
    When an agent contributes the novel problem
    Then existing_problems is empty
    And a new problem is created

  Scenario: remember tool description steers recall-first
    When an MCP client lists tools
    Then the "remember" tool description instructs the agent to recall first and use improve-mode on a match

---
```

## Files

- `backend/application/service.py`
- `backend/presentation/api/schemas.py`
- `backend/presentation/mcp/tools.py`

## Interface contract (signatures only — no implementation bodies)

```python
# Application: dedup advisory independent of embedding availability
def contribute(self, ...) -> dict: ...  # returns {problem_id, solution_id, status, existing_problems}
# existing_problems folds find_by_error_signature(error_signature) ∪ find_similar(embedding) when present
```

## Steps

1. Implement the change described above across the listed files, matching surrounding code style (Ruff, 88 cols, double quotes).
2. Keep both transports calling shared Application logic where applicable (no per-transport business logic).
3. Run the paired test file; confirm GREEN. Run `make fast` to confirm no regressions.

## Verification

```bash
uv run pytest backend/tests/unit/test_write_dedup.py -q   # expect PASS (Green)
make fast                                                   # no regressions
```
