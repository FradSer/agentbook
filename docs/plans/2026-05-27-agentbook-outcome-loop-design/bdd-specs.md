# BDD specifications: agentbook outcome-feedback loop

36 scenarios across five features (10 refinement + 10 parser-lenient + 5 parser-feedback + 8 rotation + 3 rotation-offline-eval). Test placement:
- Refinement scenarios → new `experiments/agentbook-ab/memory/tests/test_refine_from_outcomes.py` (Opus subprocess monkeypatched).
- Lenient Edit Parser scenarios → extend `experiments/agentbook-ab/harness/tests/test_search_replace.py`.
- Adaptive Sample Rotation scenarios → new `experiments/agentbook-ab/pipeline/tests/test_router.py` (extends what's already there) + offline-eval scenarios verified by `pipeline.router.evaluate_offline_rotate`.

## Feature 1: Outcome-Driven Cue Refinement

```gherkin
Feature: refine_from_outcomes appends a new cue revision for stuck tasks

Background:
  Given _oracle/synth_cache.json carries a revision-0 entry for "sympy__sympy-15976"
  And _oracle/outcomes_log.json contains gemma4_e4b s0..s2 across 5 arms on sympy__sympy-15976 with resolved=false
  And runs_v2/sympy__sympy-15976__*gemma4_e4b__s*/transcript.json files exist for those failing runs
  And min_failure_count is 3

Scenario: Happy path -- one stuck task refined and versioned
  Given gold_added_lines("sympy__sympy-15976") returns a non-empty set
  And refine_from_outcomes is invoked with --only sympy__sympy-15976 --workers 1
  When the script runs
  Then a subprocess.run call is made to claude -p with the refinement prompt
  And the prompt body includes the existing root_cause_pattern, localization_cues, verification_method
  And the prompt body includes a digest of failing-turn observations and parse-failure notes
  And the prompt body does NOT include any line from gold_added_lines("sympy__sympy-15976")
  And the prompt body does NOT include any path under tests/ or matching test_*.py
  And the refined JSON is parsed, normalized, and scrubbed
  And synth_cache["sympy__sympy-15976"]["revisions"][0] equals the prior entry's knowledge fields with rev=0
  And synth_cache["sympy__sympy-15976"]["revisions"][1] is the new refined entry with rev=1, parent_revision=0
  And synth_cache["sympy__sympy-15976"]["revisions"][1]["refined_from"] lists the harvested run identifiers
  And synth_cache["sympy__sympy-15976"]["revisions"][1]["change_rationale"] is a non-empty string
  And synth_cache["sympy__sympy-15976"]["root_cause_pattern"] equals revisions[-1].root_cause_pattern
  And synth_cache["sympy__sympy-15976"]["localization_cues"] equals revisions[-1].localization_cues
  And synth_cache["sympy__sympy-15976"]["verification_method"] equals revisions[-1].verification_method

Scenario: Under-evidenced stuck task is skipped with reason logged
  Given runs_v2 contains only 1 failing transcript for "sympy__sympy-16450"
  And min_failure_count is 3
  When refine_from_outcomes runs over sympy__sympy-16450
  Then no Opus subprocess call is made for sympy__sympy-16450
  And the log records "skip sympy__sympy-16450: under-evidenced (1<3)"
  And synth_cache["sympy__sympy-16450"] is byte-for-byte unchanged

Scenario: Gold-leaked content in refinement output is scrubbed
  Given gold_added_lines("sympy__sympy-15976") includes "return Integer(1)"
  And Opus returns refined cues containing the verbatim line "return Integer(1)"
  When refine_from_outcomes processes the entry
  Then scrub_leak rewrites the verbatim line to "…"
  And revisions[-1]["leak_lines_removed"] is at least 1
  And no revision field contains the verbatim gold line

Scenario: Malformed JSON from Opus leaves prior revisions untouched
  Given Opus returns a string with neither a ```json fenced block nor a parsable {...} substring
  When refine_from_outcomes processes "sympy__sympy-16766"
  Then a single ERROR line is logged including the iid and exception class
  And synth_cache["sympy__sympy-16766"]["revisions"] has the same length as before
  And other tasks in the same batch still succeed (per-task isolation)

Scenario: Refinement that empties root_cause_pattern is rejected before write
  Given Opus returns refined fields with root_cause_pattern="" (empty after strip)
  When refine_from_outcomes validates the refined entry
  Then ValueError is raised inside the per-task worker
  And the entry is left at its prior revisions length
  And the rejection is logged with iid and reason="empty_root_cause_pattern"

Scenario: Empty outcomes log is a no-op
  Given _oracle/outcomes_log.json is "[]"
  When refine_from_outcomes runs with no --only filter
  Then no tasks are selected
  And the log prints "refining 0/0 stuck tasks"
  And synth_cache.json is byte-for-byte unchanged

Scenario: Re-running refinement is idempotent without --redo
  Given refine_from_outcomes already produced revision 1 for "sympy__sympy-15976"
  When refine_from_outcomes is invoked a second time without --redo
  Then no Opus subprocess call is issued for "sympy__sympy-15976"
  And the log records "skip sympy__sympy-15976: already refined (revisions=2)"
  And synth_cache["sympy__sympy-15976"]["revisions"] is unchanged

Scenario: --redo forces a new revision even if one exists
  Given refine_from_outcomes already produced revision 1 for "sympy__sympy-15976"
  When refine_from_outcomes is invoked with --redo --only sympy__sympy-15976
  Then Opus is called once
  And synth_cache["sympy__sympy-15976"]["revisions"] has length 3
  And revisions[2]["parent_revision"] equals 1

Scenario: One task's failure does not poison sibling tasks
  Given two stuck tasks "sympy__sympy-15976" and "sympy__sympy-16766" are eligible
  And the Opus subprocess for "sympy__sympy-16766" raises subprocess.TimeoutExpired
  When refine_from_outcomes runs with --workers 2
  Then "sympy__sympy-15976" advances to revision 1
  And "sympy__sympy-16766" stays at its prior revision count
  And the failure line names "sympy__sympy-16766" and the exception class

Scenario: Stuck-task selection prefers full-failure tasks deterministically
  Given gemma4_e4b has 0/3 resolved on every arm for sympy__sympy-15976 (15 failures)
  And gemma4_e4b has 2/3 resolved for sympy__sympy-15875 on good_loop (4 failures)
  When refine_from_outcomes selects candidates with require_zero_wins=True, min_failure_count=3
  Then sympy__sympy-15976 is selected
  And sympy__sympy-15875 is NOT selected
  And selection order on ties is alphabetical
```

## Feature 2: Lenient Edit Parser

```gherkin
Feature: extract_edits recovers truncated or off-fence SEARCH/REPLACE blocks

Background:
  Given the strict _EDIT_RE / _SR_RE patterns remain the fast path
  And every test currently in harness/tests/test_search_replace.py is in the suite

Scenario: Closing fence missing because the model hit max_tokens
  Given an assistant message opening with "```edit\npath/x.py\n<<<<<<< SEARCH\na = 1\n=======\na = 2\n>>>>>>> REPLACE\n"
  And the message has no closing triple-backtick
  When extract_edits parses the message
  Then it returns exactly one tuple
  And the path equals "path/x.py"
  And the search equals "a = 1"
  And the replace equals "a = 2"

Scenario: Fence tagged ```python instead of ```edit is still parsed
  Given an assistant message with a fenced ```python block containing a valid SEARCH/REPLACE pair
  When extract_edits parses the message
  Then it returns exactly one tuple
  And the path comes from the first non-empty pre-SEARCH line inside the block

Scenario: Raw SEARCH/REPLACE markers with no opening fence are recovered when a path precedes them
  Given an assistant message "Here is the fix.\n\npath/x.py\n<<<<<<< SEARCH\nx = 1\n=======\nx = 2\n>>>>>>> REPLACE\n"
  When extract_edits parses the message
  Then it returns exactly one tuple ("path/x.py", "x = 1", "x = 2")

Scenario: Reply with neither SR markers nor ```edit returns empty list
  Given an assistant message "Let me think. I will grep next.\n\n```bash\nls\n```\n"
  When extract_edits parses the message
  Then it returns []
  And the lenient fallback is NOT entered (no _INTENT_RE match)

Scenario: Carets-and-equals whitespace tolerance
  Given an assistant message with "<<<<< SEARCH", trailing spaces on the ======= line, and ">>>>>>>> REPLACE" (mixed caret counts)
  When extract_edits parses the message
  Then it returns exactly one tuple
  And the search and replace bodies are stripped of leading/trailing whitespace correctly

Scenario: Path-on-fence-line ("```edit path/x.py")
  Given an assistant message "```edit path/x.py\n<<<<<<< SEARCH\nold\n=======\nnew\n>>>>>>> REPLACE\n```"
  When extract_edits parses the message
  Then it returns exactly one tuple ("path/x.py", "old", "new")

Scenario: Two complete SEARCH/REPLACE pairs in one unfenced block both recover
  Given an unclosed ```edit block under one path with two complete SEARCH/REPLACE pairs
  When extract_edits parses the message
  Then it returns 2 tuples sharing the same path

Scenario: Truncated final pair is dropped, prior complete pairs kept
  Given an unclosed ```edit block with one complete SEARCH/REPLACE pair followed by "<<<<<<< SEARCH\na = 1\n=====<truncated>"
  When extract_edits parses the message
  Then it returns exactly 1 tuple (the complete pair)
  And the incomplete pair is silently discarded

Scenario: End-to-end -- truncated edit block parses AND applies to a real file
  Given a tmp_path repo containing mod.py with "def f():\n    return 0\n"
  And an assistant message that opens a ```edit block targeting mod.py with SEARCH "return 0" / REPLACE "return 1" but no closing fence
  When extract_edits then apply_search_replace runs
  Then mod.py is rewritten to "def f():\n    return 1\n"

Scenario: Test-file edit refusal still fires for a recovered (unfenced) block
  Given the lenient fallback recovers a tuple ("tests/test_x.py", "old", "new")
  When apply_search_replace receives that tuple
  Then it returns (False, msg) where msg contains "test file"
  And the working tree is unchanged
```

## Feature 3: Lenient Edit Parser — malformed-block feedback

```gherkin
Feature: agent_loop breaks the doom-loop on unparseable edit intent

Scenario: looks_like_edit_intent detects partial markers
  Given the assistant message "```edit\n...\n"
  When looks_like_edit_intent is called
  Then it returns true
  Given the assistant message "<<<<<<< SEARCH\nfoo\n"
  Then looks_like_edit_intent returns true
  Given the assistant message "just bash\n```bash\nls\n```\n"
  Then looks_like_edit_intent returns false

Scenario: diagnose_edit_block classifies the missing closing fence
  Given the assistant message "```edit\nmod.py\n<<<<<<< SEARCH\nold\n=======\nnew\n>>>>>>> REPLACE\n" (no closing fence)
  When diagnose_edit_block is called
  Then the returned string contains "closing triple-backtick"

Scenario: diagnose_edit_block classifies missing separator
  Given the assistant message "```edit\nmod.py\n<<<<<<< SEARCH\nold\n>>>>>>> REPLACE\n```\n"
  When diagnose_edit_block is called
  Then the returned string contains "=======" or "separator"

Scenario: diagnose_edit_block classifies truncated mid-block
  Given the assistant message "```edit\nmod.py\n<<<<<<< SEARCH\nold\n=======\nnew\n"
  When diagnose_edit_block is called
  Then the returned string contains "REPLACE"

Scenario: agent_loop emits _EDIT_MALFORMED_HINT instead of _NO_BLOCK_HINT
  Given an episode in progress where the model emits a truncated ```edit block
  And extract_edits returns []
  And looks_like_edit_intent(reply) returns true
  When agent_loop processes the turn
  Then the next user message contains the malformed-block diagnosis
  And the next user message does NOT contain "Respond with EXACTLY ONE ```bash"
  And consecutive_parse_failures increments by 1
  And the episode does NOT abort yet (assuming this is below the 6-strike cap)
```

## Feature 4: Adaptive Sample Rotation

```gherkin
Feature: select_arm_for_sample rotates arms across samples within a task

Background:
  Given RUNTIME_ARMS is ("good", "good_synth", "good_loop", "good_multi_loop")
  And the outcomes log records (model_slug, iid, arm, sample_idx, resolved)
  And LOO exclusion of the held-out iid is honored for KNNRouter

Scenario: First sample picks the router's top-ranked arm (FRESH_ARM, empty history)
  Given a RuleRouter and multisite gemma features
  When select_arm_for_sample(features, "gemma4_e4b", sample_idx=0, tried_arms_results={}) is called
  Then it returns "good_multi_loop" (rule's top pick for multisite gemma)

Scenario: After a failed top pick, sample 1 advances to rank-2 (FRESH_ARM after failure)
  Given a RuleRouter, multisite gemma features
  And tried_arms_results = {"good_multi_loop": [False]}
  When select_arm_for_sample(..., sample_idx=1, tried_arms_results=...) is called
  Then the returned arm is NOT "good_multi_loop"
  And the returned arm is the next-best by rule ranking among RUNTIME_ARMS
  And the returned arm is in RUNTIME_ARMS

Scenario: A prior win short-circuits to REPLAY_WIN
  Given tried_arms_results = {"good_multi_loop": [False], "good_loop": [True]}
  When select_arm_for_sample(..., sample_idx=2, tried_arms_results=...) is called
  Then it returns "good_loop"

Scenario: All RUNTIME_ARMS tried, all failed -- BURN_REPLAY returns the top-ranked arm
  Given a KNNRouter and tried_arms_results that records resolved=False for every arm in RUNTIME_ARMS
  When select_arm_for_sample(features, "gemma4_e4b", sample_idx=4, tried_arms_results=..., exclude_iid="sympy__sympy-15017") is called
  Then it returns ranking[0]
  And the returned arm is in RUNTIME_ARMS

Scenario: Rule and KNN disagree on the fresh arm at sample 1
  Given multisite gemma features, tried_arms_results = {"good_multi_loop": [False]}
  When RuleRouter.select_arm_for_sample is called
  Then it returns "good_loop" (rule's #2 for multisite)
  When KNNRouter.select_arm_for_sample is called against an outcomes log where
    "good" resolves 3/3 nearest neighbours and "good_loop" resolves 1/3
  Then it returns "good"

Scenario: Existing select_arms callers are unaffected (no signature change)
  Given existing call sites use select_arms(iid, model_slug, k=1)
  When the new select_arm_for_sample method is shipped
  Then no caller of select_arms breaks
  And select_arms returns the same arm it returned before this change

Scenario: good_rotate cell records the routing decision in arm_meta
  Given an orchestrator runs a good_rotate cell at sample_idx=1 for sympy__sympy-15017 on gemma4_e4b
  And the prior sample at sample_idx=0 has a result.json with arm_meta.routed_to="good_multi_loop" and resolved=False
  When build_prompt(iid, "good_rotate", ...) executes
  Then _load_prior_sample_outcomes returns {"good_multi_loop": [False]}
  And select_arm_for_sample is consulted with that history
  And the returned arm_meta carries routed_from="good_rotate", routed_to=<the chosen sub-arm>, rotate_sample_idx=1, rotate_tried_history={"good_multi_loop": [False]}

Scenario: Orchestrator schedules good_rotate samples serially within (iid, model) chain (R6)
  Given the orchestrator enumerates 3 good_rotate cells for (sympy__sympy-15017, gemma4:e4b) at sample_idx=0/1/2
  And the run_chain function dispatches them as a single chain
  When the chain executes under args.workers=12
  Then sample_idx=1 starts only after sample_idx=0's result.json has been written to runs_v2/
  And sample_idx=2 starts only after sample_idx=1's result.json has been written
  And other tasks' chains may execute in parallel (chain-level parallelism preserved)
  And no two cells in the SAME chain ever overlap in wall time
```

## Feature 5: Adaptive Sample Rotation -- offline simulator

```gherkin
Feature: evaluate_offline_rotate simulates good_rotate against the existing outcomes log (R7)

Scenario: rotate coverage at k=3 is >= the best static single arm under LOO
  Given the outcomes log contains gemma4_e4b s=0..s=2 data for all 5 arms × 17 tasks
  And the best static arm for gemma4_e4b at pass@3 is good_multi_loop (13/17)
  When evaluate_offline_rotate(RuleRouter(), k=3, models=("gemma4_e4b",)) runs under LOO
  Then the reported coverage_rotate is >= 13/17
  And the reported coverage_rotate is <= ceiling_all_arms_union (15/17)
  And the per-model report carries arms_used_count showing >= 2 distinct arms were dispatched across tasks

Scenario: rotate consumes sample slots in order and falls back when a slot is missing
  Given an outcomes log where (gemma4_e4b, sympy__sympy-15017, good_multi_loop) has s=0 resolved=False and no s=1 row
  When evaluate_offline_rotate processes sympy__sympy-15017 at sample_idx=1
  And select_arm_for_sample returns good_multi_loop a second time (after a hypothetical earlier failure)
  Then the simulator falls back to sample s=0's outcome
  And unmet_samples counter records the gap
  And the simulation does NOT raise

Scenario: LOO safety in rotate simulation
  Given evaluate_offline_rotate runs with KNNRouter and held-out iid sympy__sympy-15017
  When KNNRouter.select_arm_for_sample is consulted at each sample
  Then no row with iid="sympy__sympy-15017" enters the router's score computation (exclude_iid honored)
  And the in-trial tried_arms_results only contains in-simulation samples for sympy__sympy-15017
```
