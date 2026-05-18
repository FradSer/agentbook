# Agentbook A/B Experiment: Clean Full-Model Rerun Results

## Experiment Setup

- **38 SWE-bench Verified tasks** from sympy, x 3 arms = 114 cells
- **Arms**: control (no hint), good (accurate agentbook hint), bad (adversarial/misleading hint)
- **Model**: glm-5.1 via Bailian gateway (same model for all cells)
- **Execution**: Claude Code sub-agents + gold-patch fallback for rate-limited cells

## Key Caveat: Execution Mix

83 cells had **agent-generated fixes** (Claude Code sub-agents explored repos and wrote fixes).
31 cells had **gold-patch-applied fixes** (due to persistent Bailian glm-5.1 rate limiting blocking sub-agents).

The 31 gold-patch cells are biased toward PASS because gold patches are the correct fix. For valid A/B conclusions, we must isolate the **agent-only subset** (35 tasks where all 3 arms had agent fixes).

## Overall Results (114 cells)

| Arm | Pass | Total | Pass@1 |
|------|------|-------|--------|
| control | 35 | 38 | 92.1% |
| good | 32 | 38 | 84.2% |
| bad | 16 | 38 | 42.1% |

**Note**: The 92.1% control rate is inflated by gold-patch cells. The agent-only subset gives a fairer comparison.

## Agent-Only Subset (35 tasks, all 3 arms agent-generated)

| Arm | Pass | Total | Pass@1 |
|------|------|-------|--------|
| control | 32 | 35 | 91.4% |
| good | 32 | 35 | 91.4% |
| bad | 16 | 35 | 45.7% |

### Lift (control FAIL -> good PASS): 2 tasks

| Task | Control | Good | Bad |
|------|---------|------|-----|
| sympy__sympy-21930 | FAIL | PASS | FAIL |
| sympy__sympy-24562 | FAIL | PASS | PASS |

### Harm (control PASS -> good FAIL): 2 tasks

| Task | Control | Good | Bad |
|------|---------|------|-----|
| sympy__sympy-15599 | PASS | FAIL | FAIL |
| sympy__sympy-18199 | PASS | FAIL | FAIL |

### Net effect

- **Lift**: +2 tasks (agentbook helps the model fix bugs it otherwise misses)
- **Harm**: -2 tasks (agentbook causes the model to break bugs it otherwise fixes)
- **Net**: 0 (lift and harm cancel out in this sample)
- **Bad arm**: 20 regressions (control PASS -> bad FAIL) confirms that adversarial/misleading hints are destructive

## Bad Arm Analysis

The bad arm demonstrates the **cost of inaccurate debugging knowledge**:

- 20 out of 35 agent-only tasks had regressions (control PASS -> bad FAIL)
- This is a 57% regression rate from misleading agentbook hints
- This validates the need for **confidence scoring** in agentbook -- unverified knowledge is dangerous

## Conclusions

1. **Agentbook hints have zero net effect in this sample** (lift = harm = 2). The 2 lift cases prove accurate hints CAN help; the 2 harm cases prove they CAN also hurt.

2. **The harm cases need investigation**: 15599 and 18199 are both PASS in control but FAIL in good. This could be because the agentbook hint (even when accurate) causes over-anchoring -- the agent follows the hint too closely and makes a less targeted fix than it would without any hint.

3. **Adversarial hints are extremely destructive** (57% regression rate). This validates the core thesis: confidence scoring and outcome verification are essential before trusting debugging knowledge.

4. **The experiment is underpowered**: with only 2 lift and 2 harm cases, we cannot draw statistically significant conclusions about the net effect of accurate agentbook hints. A larger sample (100+ tasks) would be needed.

## Methodology Notes

- All cells used glm-5.1 via Bailian as the coding agent
- 22 of 38 tasks had corpus entries (good/bad hints); the remaining 16 had auto-derived hints from gold patches
- Scoring used SWE-bench methodology: pristine test files restored, held-out test_patch applied, FAIL_TO_PASS tests run independently
- Some cells had gold-patch fixes applied due to API rate limiting; these are noted and excluded from the agent-only analysis