# Task 006: refine_from_outcomes implementation + _synth_entry revision-aware reader

**depends-on**: task-005

## Description

Implement the `memory/refine_from_outcomes.py` CLI script and the small `_synth_entry` update in `pipeline/arm_context.py` so refined cues take effect on the next eval run. Make the 10 Red tests from task-005 Green. The script must mirror `memory/synthesize.py`'s style (CLI flags, `ThreadPoolExecutor`, single `threading.Lock` around `SYNTH_CACHE.write_text`, `_extract_json` reuse). The `_synth_entry` change is two extra lines: when `revisions` is present, merge `revisions[-1]` into the returned dict.

Anti-leak is load-bearing: Opus input MUST exclude `gold_added_lines(iid)`, hidden test paths, and any `tests/`/`test_*.py` substring. `scrub_leak` runs over the refined output as defense in depth; `leak_lines_removed` is recorded on the new revision.

## Execution Context

**Task Number**: 006 of 016
**Phase**: Batch 2 — Outcome-Driven Cue Refinement (GREEN)
**Prerequisites**:
- task-005 complete: 10 Red tests failing as expected.

## BDD Scenario

```gherkin
# This task is the Green pair for task-005. The 10 Feature 1 scenarios from
# bdd-specs.md (quoted verbatim in task-005) are the acceptance contract.
# A representative scenario is reproduced below.

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
```

**Spec Source**: [bdd-specs.md Feature 1](../2026-05-27-agentbook-outcome-loop-design/bdd-specs.md) (10 scenarios, all quoted in task-005).

## Files to Modify/Create

- Create: `experiments/agentbook-ab/memory/refine_from_outcomes.py` — full CLI script.
- Modify: `experiments/agentbook-ab/pipeline/arm_context.py:_synth_entry` — return merged view when `revisions` is present (4-line change per [architecture.md § `_synth_entry` update](../2026-05-27-agentbook-outcome-loop-design/architecture.md)).
- Possibly modify (refactor option): `experiments/agentbook-ab/memory/_claude_io.py` (new) hosting `_extract_json` and `_synth_env` shared with `memory/synthesize.py`. Acceptable to keep them duplicated for now and refactor later — choose the path that keeps `synthesize.py`'s 26 existing tests green.

## Steps

### Step 1: Skeleton CLI signatures
- Add `argparse` flags per [architecture.md § CLI flags](../2026-05-27-agentbook-outcome-loop-design/architecture.md):
  - `--only`, `--model-slug`, `--min-failure-count`, `--redo`, `--workers`, `--model`, `--timeout`, `--dry-run`, `--max-tasks`, `--cues-version`, `--require-no-regression` (default ON), `--allow-regression`, `--reason`, `--rollback-to-rev`.
- Function signatures (signatures only — no bodies — to define the contract):

```python
def select_stuck(
    outcomes: list[dict], model_slug: str, *,
    min_failure_count: int = 3, require_zero_wins: bool = True,
) -> list[str]: ...

def harvest_failing_transcripts(
    iid: str, runs_dir: Path, model_slug: str, *,
    arms: tuple[str, ...] = RUNTIME_ARMS, max_turns_per_run: int = 4,
) -> list[dict]: ...

def build_refine_prompt(entry: dict, fails: list[dict]) -> str: ...

def call_opus(prompt: str, *, model: str, timeout: int) -> dict: ...

def write_revision(
    cache: dict, iid: str, refined: dict, *,
    source_tag: str, cache_path: Path, lock: threading.Lock,
    failure_evidence_count: int, stuck_criterion: str, refined_from: list[str],
) -> None: ...

def main() -> int: ...
```

### Step 2: Implement `select_stuck`
- Walk `outcomes`, restrict to `model_slug` and `arm in RUNTIME_ARMS`, count wins/fails per iid.
- Return iids with `fails ≥ min_failure_count` and (when `require_zero_wins`) `wins == 0`.
- Sort by `(-fails, iid)` for determinism.

### Step 3: Implement `harvest_failing_transcripts`
- For each `runs_v2/<iid>__<arm>__<model_slug>__s*/` directory, read sibling `result.json`; skip when `resolved` is true.
- Extract `stop_reason`, `verification_passed`, `turns_used`, last 2 turns' `stdout_tail`/`stderr_tail`, first 2 notes truncated to 200 chars.
- Filter: drop any tail or note referencing `**/tests/**` or `test_*.py`.
- Filter: drop any line whose stripped form is in `gold_added_lines(iid)` (defense in depth — `gold_added_lines` is the canonical anti-leak primitive from `memory/to_memory_entry.py`).

### Step 4: Implement `build_refine_prompt`
- Compose the prompt body per [architecture.md § Prompt assembly](../2026-05-27-agentbook-outcome-loop-design/architecture.md).
- Append `## Hard rules: no diffs, no verbatim source lines, no test file paths.` verbatim.
- Validate before returning: assert no line in the prompt body matches any `gold_added_lines(iid)` entry; assert no `tests/` or `test_*.py` substring.

### Step 5: Implement `call_opus`
- `subprocess.run` with `claude -p`, `--output-format json`, `--no-session-persistence`, `--model`, `--disallowedTools WebSearch WebFetch Bash Read Edit Write`, `cwd=tempfile.TemporaryDirectory(prefix="agentbook-refine-")`, `env=_synth_env()`, `timeout=...`.
- Parse via shared `_extract_json` (import from `memory/synthesize.py` or move to `memory/_claude_io.py`).
- `_normalize` ensures `root_cause_pattern`, `localization_cues`, `verification_method`, `change_rationale` exist (default empty).

### Step 6: Implement `write_revision`
- Holds the shared `threading.Lock`.
- Lazy-init `revisions[0]` from current top-level fields on first write per iid (matches alias contract from [architecture.md § Schema](../2026-05-27-agentbook-outcome-loop-design/architecture.md)).
- Validate `refined["root_cause_pattern"].strip()` is non-empty → else raise `ValueError("empty_root_cause_pattern")`.
- Run `scrub_leak(refined, gold_added_lines(iid))`; record `leak_lines_removed`.
- Append the new revision with `rev`, `parent_revision`, `created_at` (ISO UTC), `source`, `model`, `leak_lines_removed`, `failure_evidence_count`, `stuck_criterion`, `refined_from`, `change_rationale`.
- Mirror the knowledge fields to top-level aliases UNLESS the new revision would regress an iid (per `--require-no-regression`); when regression check is enabled and `regression_count > 0`, write the revision but **leave top-level aliases pointing at the prior revision**.
- Persist `cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n")` while holding the lock.

### Step 7: Implement `main`
- Resolve outcomes log path; load; call `select_stuck` (or restrict to `--only`); cap at `--max-tasks`.
- Print "refining {selected}/{eligible} stuck tasks".
- `ThreadPoolExecutor(max_workers=args.workers)`; per-task `try/except` wraps `harvest → build_refine_prompt → call_opus → write_revision`.
- Per-task isolation: failures log a single ERROR line with iid + exception class; siblings continue.
- Idempotency: skip when `len(revisions) >= 2` unless `--redo`; log `skip {iid}: already refined (revisions={N})`.
- Under-evidence skip: `len(fails) < min_failure_count` → log `skip {iid}: under-evidenced ({N}<{min})`.
- Exit code: non-zero when `--require-no-regression` and any iid regresses.

### Step 8: Update `pipeline/arm_context.py:_synth_entry`
- Add the merged-view branch from [architecture.md § `_synth_entry` update](../2026-05-27-agentbook-outcome-loop-design/architecture.md):

```python
def _synth_entry(iid: str) -> dict | None:
    # ... existing cache load unchanged ...
    entry = _synth_data.get(iid)
    if entry is None:
        return None
    revisions = entry.get("revisions")
    if revisions:
        merged = dict(entry)
        for field in ("root_cause_pattern", "localization_cues", "verification_method",
                      "verifications", "leak_lines_removed"):
            if field in revisions[-1]:
                merged[field] = revisions[-1][field]
        return merged
    return entry
```

- Backwards-compat: entries without `revisions` return unchanged.

### Step 9: Re-run the 10 Red tests; confirm all Green
- Plus the full regression sweep.

## Verification Commands

```bash
# All 10 refinement tests pass
cd experiments/agentbook-ab && \
  uv run python -m pytest memory/tests/test_refine_from_outcomes.py -q

# Full experiment-wide regression sweep
cd experiments/agentbook-ab && \
  uv run python -m pytest -q

# --dry-run smoke against real fixtures (no Opus call)
cd experiments/agentbook-ab && \
  uv run python -m memory.refine_from_outcomes --dry-run --min-failure-count 3

# --help shows all flags
cd experiments/agentbook-ab && \
  uv run python -m memory.refine_from_outcomes --help

# Ruff lint
uv run ruff check --fix experiments/agentbook-ab/memory/refine_from_outcomes.py \
  experiments/agentbook-ab/pipeline/arm_context.py
```

## Success Criteria

- All 10 tests in `memory/tests/test_refine_from_outcomes.py` PASS.
- Full `experiments/agentbook-ab/` pytest suite stays green; in particular, `memory/synthesize.py`'s existing tests do not regress whether `_extract_json` is duplicated or moved to `memory/_claude_io.py`.
- `--dry-run` prints the planned tasks and the assembled prompt for one task without any `subprocess.run` call.
- `--help` lists every documented flag.
- `_synth_entry` returns the merged view when `revisions` is present and the unchanged entry otherwise.
- Ruff passes on both modified files.
- No new external Python dependencies.
- Default behaviour: `--require-no-regression` ON; when ON, regressing iids leave top-level aliases pointing at the prior revision (the new revision is still persisted under `revisions` for inspection).
- `--rollback-to-rev N` flag exists and reverts top-level aliases to `revisions[N].<field>` for the given iid.
