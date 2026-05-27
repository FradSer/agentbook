# Architecture: agentbook Outcome-Feedback Loop

Scope: three coupled subsystems inside `experiments/agentbook-ab/`. No code outside the experiment is touched.

## File Map

**New files**

| Path | Purpose |
|---|---|
| `memory/refine_from_outcomes.py` | CLI: select stuck tasks, harvest failing transcripts, call Opus with the existing cue entry + leak-scrubbed failure evidence, append a new revision to `synth_cache.json`. |
| `pipeline/tests/__init__.py` | New empty test package for the router. |
| `pipeline/tests/test_router.py` | Unit tests for `select_arm_for_sample` (5 scenarios mapped to decision branches). |

**Modified files**

| Path | Change |
|---|---|
| `harness/prompts.py` | Add `_INTENT_RE`, `_EDIT_RE_LENIENT`, `_SR_RE_LENIENT`, `_extract_path()`, `looks_like_edit_intent()`, `diagnose_edit_block()`. Extend `extract_edits` with a fallback branch that fires only when `_INTENT_RE` matches and the fast path returned []. |
| `harness/agent_loop.py` | Add a third dispatch branch (between diff and command) that fires on `looks_like_edit_intent(text)` when no edit parsed; emit `_EDIT_MALFORMED_HINT` (template defined here). Increment `consecutive_parse_failures` so the 6-strike abort still fires. |
| `harness/tests/test_search_replace.py` | Add 11 new tests (truncated-fence recovery, fence-tag tolerance, raw-marker recovery, intent detection, malformed-block diagnosis, end-to-end recovery-and-apply). Existing 15 tests unchanged. |
| `pipeline/arm_context.py` | Add `good_rotate` branch (peer to `good_router` at lines 211-226). Add `sample_idx: int | None = None` to `build_prompt`. Update `_synth_entry` to return a merged view of latest revision + base entry metadata when `revisions` is present. |
| `pipeline/orchestrator.py` | Split scheduling: parallel pool for non-rotate cells, per-`(iid, model)` chain pool for `good_rotate`. Pass `cell.sample_idx` to `build_prompt`. Extend `_has_memory` gate for `good_rotate` (= union of all sub-arm requirements). Extend `bootstrap_outcomes_log` harvest to include `runs_v2.cues_v1/` etc. when present. |
| `pipeline/router.py` | Add module-level `_pick_unexplored(ranking, tried)` helper. Add `select_arm_for_sample` method on `RuleRouter` and `KNNRouter` (3-line bodies, each calling the shared helper after fetching the ranking). Add `evaluate_offline_rotate(router, k=3)` parallel to `evaluate_offline`. Extend `main()` CLI to print rotation results alongside k=1/k=2/k=3. |
| `_oracle/synth_cache.json` | Schema-extended at runtime by `refine_from_outcomes.py`. No schema migration script; refinement writes the first `revisions[0]` (constructed from existing top-level fields) lazily on first refinement. |

## Schema: `synth_cache.json` per-entry diff

**Before** (current shape, 14 top-level fields per entry):

```json
{
  "sympy__sympy-15976": {
    "root_cause_pattern": "...",
    "localization_cues": ["...", "..."],
    "verification_method": "...",
    "verifications": [...],
    "instance_id": "sympy__sympy-15976",
    "leak_lines_removed": 0,
    "model": "opus",
    "source": "claude -p synthesis of leak-free memory",
    "elapsed_s": 16.2,
    "verification_command": "...",
    "verification_expected": "...",
    "verification_buggy": "...",
    "verification_feasible": true,
    "verification_leak_removed": 0
  }
}
```

**After first refinement** (revisions list added; top-level fields now alias `revisions[-1]`):

```json
{
  "sympy__sympy-15976": {
    "root_cause_pattern": "<aliased from revisions[-1]>",
    "localization_cues": ["<aliased>"],
    "verification_method": "<aliased>",
    "verifications": ["<aliased>"],
    "instance_id": "sympy__sympy-15976",
    "leak_lines_removed": 0,
    "model": "opus",
    "source": "claude -p synthesis of leak-free memory",
    "elapsed_s": 16.2,
    "verification_command": "<aliased>",
    "verification_expected": "<aliased>",
    "verification_buggy": "<aliased>",
    "verification_feasible": true,
    "verification_leak_removed": 0,
    "revisions": [
      {
        "rev": 0,
        "parent_revision": null,
        "root_cause_pattern": "<original>",
        "localization_cues": ["<original>"],
        "verification_method": "<original>",
        "verifications": [...],
        "leak_lines_removed": 0,
        "source": "claude -p synthesis of leak-free memory",
        "model": "opus",
        "created_at": null
      },
      {
        "rev": 1,
        "parent_revision": 0,
        "root_cause_pattern": "<refined>",
        "localization_cues": ["<refined, with verification sites enumerated>"],
        "verification_method": "<refined>",
        "leak_lines_removed": 0,
        "source": "refine_from_outcomes failure-evidence batch 2026-05-27",
        "model": "opus",
        "created_at": "2026-05-27T...",
        "failure_evidence_count": 8,
        "stuck_criterion": "zero_wins_gemma4_e4b_all_arms",
        "refined_from": [
          "sympy__sympy-15976__good_synth__gemma4_e4b__s0",
          "sympy__sympy-15976__good_loop__gemma4_e4b__s2",
          "..."
        ],
        "change_rationale": "Lifted verifications' enumeration of 4 print sites into cues so the model has an explicit checklist."
      }
    ]
  }
}
```

Properties of the alias contract:
- `revisions[-1].<knowledge_field>` is the source of truth.
- Top-level `<knowledge_field>` is a copy maintained by `refine_from_outcomes.py` after every append. `extract_features` (which reads top-level keys directly) needs no change.
- Entries without `revisions` are unchanged on disk and read identically to today.
- Rollback to revision N = copy `revisions[N].<knowledge_field>` to top level (one-line jq or a future `--rollback-to-rev N` flag on `refine_from_outcomes.py`).

## Component-by-component spec

### `memory/refine_from_outcomes.py`

**CLI flags** (mirrors `memory/synthesize.py` exactly where possible):

```
--only <iid> [<iid> ...]    # limit to specific instance_ids; default: all stuck
--model-slug <slug>         # which model's failures to learn from; default "gemma4_e4b"
--min-failure-count <N>     # min number of failing runs before refining; default 3
--redo                      # re-refine even if a refinement revision exists
--workers <N>               # default 2 (Opus calls are slow; 4+ risks rate limits)
--model <alias>             # default "opus"
--timeout <seconds>         # default 360
--dry-run                   # print plan + prompt; no Opus calls, no writes
--max-tasks <N>             # batch cap; default 10
--cues-version <label>      # tag for revision.source; default auto: "refine_from_outcomes <date>"
```

**Stuck-task selection** (`select_stuck(outcomes, model_slug, *, min_failure_count, require_zero_wins=True)`):

```python
def select_stuck(outcomes, model_slug, *, min_failure_count=3, require_zero_wins=True):
    """Return iids meeting the stuck criterion, sorted by (failures desc, iid asc) for determinism."""
    by_iid = defaultdict(lambda: {"wins": 0, "fails": 0})
    for r in outcomes:
        if r["model_slug"] != model_slug: continue
        if r["arm"] not in RUNTIME_ARMS: continue
        if r["resolved"]: by_iid[r["iid"]]["wins"] += 1
        else: by_iid[r["iid"]]["fails"] += 1
    return sorted(
        [iid for iid, c in by_iid.items()
         if c["fails"] >= min_failure_count
         and (not require_zero_wins or c["wins"] == 0)],
        key=lambda i: (-by_iid[i]["fails"], i),
    )
```

**Transcript harvest** (`harvest_failing_transcripts(iid, runs_dir, model_slug, *, arms=RUNTIME_ARMS, max_turns_per_run=4)`):

For each `runs_v2/<iid>__<arm>__<model_slug>__s*/transcript.json`:
- include only failing runs (no `resolved=True` in result.json — read sibling result.json).
- extract: `stop_reason`, `verification_passed`, `turns_used`, last 2 turns' `stdout_tail`+`stderr_tail`, first 2 `notes` entries truncated to 200 chars.
- filter: drop any `stdout_tail`/`stderr_tail`/note containing `/tests/` or `test_*.py` substrings (no hidden-test leak).
- filter: drop any line whose stripped form is in `gold_added_lines(iid)`.
- return list of dicts: `[{run_id, arm, sample_idx, stop_reason, verification_passed, turns_used, last_turn_observations, parse_failure_notes}, ...]`.

**Prompt assembly** (`build_refine_prompt(entry, fails)`):

```
You are revising a knowledge-synthesis entry for a shared memory layer.

The entry below was given to a weak 4B-parameter Python model. Across N runs it FAILED every time.

## Current knowledge entry

Root-cause pattern: {root_cause_pattern}

Where to look:
{cues}

How to verify: {verification_method}

## Failure evidence (N failing runs)

{per_run_evidence_block}

## Most common failure pattern
{aggregate_summary}

## Your task
Revise the entry so a weak model is more likely to land the fix. The model must
derive the edit itself — never give a patch or verbatim source lines.
Make the localization cues MORE SPECIFIC (e.g. enumerate distinct call sites
the verification suite tests separately). Make the verification method
actionable.

Output a JSON object inside one ```json fenced block with exactly:
- "root_cause_pattern": str
- "localization_cues": list of 2-5 strings (more specific than before)
- "verification_method": str
- "change_rationale": one sentence describing what changed and why

Hard rules: no diffs, no verbatim source lines, no test file paths.
```

**Opus call mechanics** (mirrors `memory/synthesize.py` exactly):

- `subprocess.run([CLAUDE_BIN, "-p", prompt, "--output-format", "json", "--no-session-persistence", "--model", model, "--disallowedTools", "WebSearch", "WebFetch", "Bash", "Read", "Edit", "Write"], cwd=empty_temp_dir, env=_synth_env(), timeout=timeout)`.
- `_extract_json` (shared with synthesize.py — import or move to `memory/_claude_io.py`).
- `_normalize` ensures missing fields default to empty.

**Write-back** (`write_revision(cache, iid, refined, *, source_tag, cache_path, lock)`):

Holds `lock` (single threading.Lock shared across workers, same pattern as `synthesize.py:work`).

```python
def write_revision(cache, iid, refined, *, source_tag, cache_path, lock,
                   failure_evidence_count, stuck_criterion, refined_from):
    with lock:
        entry = cache.setdefault(iid, {})
        revisions = entry.setdefault("revisions", [])
        if not revisions:
            # Lazy initialize revision 0 from current top-level fields
            revisions.append({
                "rev": 0,
                "parent_revision": None,
                "root_cause_pattern": entry.get("root_cause_pattern", ""),
                "localization_cues": entry.get("localization_cues", []),
                "verification_method": entry.get("verification_method", ""),
                "verifications": entry.get("verifications", []),
                "leak_lines_removed": entry.get("leak_lines_removed", 0),
                "source": entry.get("source", "synthesize.py"),
                "model": entry.get("model", "opus"),
                "created_at": None,
            })
        new_rev = {
            "rev": len(revisions),
            "parent_revision": len(revisions) - 1,
            "root_cause_pattern": refined["root_cause_pattern"],
            "localization_cues": refined["localization_cues"],
            "verification_method": refined["verification_method"],
            "leak_lines_removed": refined["leak_lines_removed"],
            "source": source_tag,
            "model": "opus",
            "created_at": _iso_now(),
            "failure_evidence_count": failure_evidence_count,
            "stuck_criterion": stuck_criterion,
            "refined_from": refined_from,
            "change_rationale": refined.get("change_rationale", ""),
        }
        revisions.append(new_rev)
        # Mirror to top-level aliases so extract_features and any other top-key reader sees latest.
        for f in ("root_cause_pattern", "localization_cues", "verification_method"):
            entry[f] = new_rev[f]
        entry["leak_lines_removed"] = new_rev["leak_lines_removed"]
        cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n")
```

Note: `verifications` is NOT regenerated by refinement (verifications are produced by `extract_verification.py`). If the operator wants refreshed verifications after refinement, they run `extract_verification.py --redo --only <iid>` as a separate step.

### `harness/prompts.py` — Lenient Edit Parser

**New regexes:**

```python
_INTENT_RE = re.compile(
    r"(?m)^\s*(?:<{3,}\s*SEARCH\b|={3,}\s*$|>{3,}\s*REPLACE\b|```edit\b)"
)
_EDIT_RE_LENIENT = re.compile(
    r"```(?:edit|edit:[A-Za-z0-9._/\-]+|patch|python|py|diff)?\s*\r?\n"
    r"(?P<body>.*?)"
    r"(?:\r?\n```|\Z)",
    re.DOTALL,
)
_SR_RE_LENIENT = re.compile(
    r"<{3,}\s*SEARCH\s*\r?\n(?P<search>.*?)\r?\n[ \t]*={3,}[ \t]*\r?\n"
    r"(?P<replace>.*?)\r?\n[ \t]*>{3,}\s*REPLACE\b",
    re.DOTALL,
)
```

**Extended `extract_edits`** (fast path unchanged):

```python
def extract_edits(text: str) -> list[tuple[str, str, str]]:
    text = text or ""
    # Fast path: well-formed fenced ```edit block + canonical SR markers.
    edits: list[tuple[str, str, str]] = []
    for block in _EDIT_RE.findall(text):
        path = _extract_path(block)
        if not path:
            continue
        for m in _SR_RE.finditer(block):
            edits.append((path, m.group("search"), m.group("replace")))
    if edits:
        return edits
    # Lenient fallback fires only on visible SR intent.
    if not _INTENT_RE.search(text):
        return []
    for fm in _EDIT_RE_LENIENT.finditer(text):
        block = fm.group("body")
        path = _extract_path(block)
        if not path:
            # Path may live on the line immediately before the opening fence.
            pre = text[: fm.start()].rstrip().splitlines()
            cand = pre[-1].strip().strip("`#* ").rstrip(":") if pre else ""
            if cand and "/" in cand and cand.endswith((".py", ".pyx", ".pyi")):
                path = cand
        if not path:
            continue
        for m in _SR_RE_LENIENT.finditer(block):
            edits.append((path, m.group("search"), m.group("replace")))
    # Last resort: bare SR markers with a path in the preceding 4 lines.
    if not edits:
        for m in _SR_RE_LENIENT.finditer(text):
            preceding = text[: m.start()].rstrip().splitlines()
            path = ""
            for ln in reversed(preceding[-4:]):
                s = ln.strip().strip("`#* ").rstrip(":")
                if s.endswith((".py", ".pyx", ".pyi")) and "/" in s:
                    path = s
                    break
            if path:
                edits.append((path, m.group("search"), m.group("replace")))
    return edits

def _extract_path(block: str) -> str:
    """First non-empty pre-SEARCH line, stripped of backticks/leading punct."""
    for ln in block.splitlines():
        if "<<<" in ln:
            return ""
        s = ln.strip()
        if not s:
            continue
        return s.strip("`").strip("`#* ").rstrip(":")
    return ""
```

**Diagnosis helpers:**

```python
def looks_like_edit_intent(text: str) -> bool:
    return bool(_INTENT_RE.search(text or ""))

def diagnose_edit_block(text: str) -> str:
    t = text or ""
    has_open_fence  = "```edit" in t or re.search(r"```(?:patch|python|py)\b", t)
    has_close_fence = bool(re.search(r"\n```\s*$|\n```\s*\n", t))
    has_search      = "<<<" in t and "SEARCH" in t
    has_equals      = re.search(r"\n={3,}\s*\n", t) is not None
    has_replace     = ">>>" in t and "REPLACE" in t
    if has_search and not has_replace:
        return "missing >>>>>>> REPLACE marker (block looks truncated)"
    if has_search and has_replace and not has_equals:
        return "missing ======= separator between SEARCH and REPLACE bodies"
    if has_open_fence and not has_close_fence:
        return "missing closing triple-backtick (reply was likely cut off)"
    if not has_open_fence and has_search:
        return "missing opening ```edit fence around the SEARCH/REPLACE block"
    return "malformed edit block (could not isolate SEARCH/REPLACE pair)"
```

### `harness/agent_loop.py` — Malformed-edit branch

Insert between the `extract_diff` branch (current ~line 175) and the `extract_command` fallthrough:

```python
# Edit-intent recovery: a SEARCH/REPLACE attempt that parsed to no edits.
# Tell the model the specific structural problem, not the generic "emit bash"
# hint. Without this branch, the model doom-loops the same truncated block
# (observed 4 identical turns in good_multi_loop__sympy-15976__gemma4_e4b__s0).
if looks_like_edit_intent(text):
    consecutive_parse_failures += 1
    diag = diagnose_edit_block(text)
    episode.notes.append(
        f"turn {turn} unparseable-edit ({diag}): {(text or '').strip()[:300]}"
    )
    messages.append({"role": "user", "content": _EDIT_MALFORMED_HINT.format(diag=diag)})
    if consecutive_parse_failures >= 6:
        episode.stop_reason = "parse_failures"
        episode.turns_used = turn
        break
    continue

# Existing extract_command branch follows unchanged.
```

`_EDIT_MALFORMED_HINT` is a template constant defined near the top of `agent_loop.py` (single-string, ~12 lines, see best-practices doc).

### `pipeline/router.py` — `select_arm_for_sample`

Shared helper:

```python
def _pick_unexplored(ranking: list[str], tried_arms_results: dict[str, list[bool]]) -> str:
    """Decision shared by RuleRouter and KNNRouter."""
    # 1. REPLAY_WIN: a prior sample for this task already passed -- replay.
    for arm, results in tried_arms_results.items():
        if any(results):
            return arm
    tried = set(tried_arms_results)
    # 2. FRESH_ARM: highest-ranked arm not yet tried.
    for arm in ranking:
        if arm not in tried:
            return arm
    # 3. EXHAUSTED_RANKING: ranking exhausted but RUNTIME_ARMS may still have unseen.
    for arm in RUNTIME_ARMS:
        if arm not in tried:
            return arm
    # 4. BURN_REPLAY: every runtime arm tried, all failed -- replay strongest.
    return ranking[0]
```

Per-router method:

```python
# RuleRouter
def select_arm_for_sample(self, features, model_slug, sample_idx, tried_arms_results):
    ranking = self.select(features, model_slug, k=len(RUNTIME_ARMS))
    return _pick_unexplored(ranking, tried_arms_results)

# KNNRouter
def select_arm_for_sample(self, features, model_slug, sample_idx, tried_arms_results,
                          *, outcomes=None, exclude_iid=None):
    ranking = self.select(features, model_slug, k=len(RUNTIME_ARMS),
                          outcomes=outcomes, exclude_iid=exclude_iid)
    return _pick_unexplored(ranking, tried_arms_results)
```

### `pipeline/arm_context.py` — `good_rotate` arm + `_synth_entry` revision-aware reader

**New branch** (peer to `good_router` at lines 211-226):

```python
if arm == "good_rotate":
    from pipeline.router import _ACTIVE_ROUTER, extract_features
    if not model_slug:
        return base, {"hint": "good_rotate", "missing_model": True}
    cache = json.loads(SYNTH_CACHE.read_text())
    if iid not in cache:
        return base, {"hint": "good_rotate", "no_features": True}
    features = extract_features(cache[iid])
    tried = _load_prior_sample_outcomes(iid, model_slug, sample_idx)
    sub_arm = _ACTIVE_ROUTER.select_arm_for_sample(features, model_slug, sample_idx, tried)
    prompt, meta = build_prompt(iid, sub_arm, client=client, model_slug=model_slug,
                                sample_idx=sample_idx)
    meta = dict(meta)
    meta["routed_from"] = "good_rotate"
    meta["routed_to"] = sub_arm
    meta["rotate_sample_idx"] = sample_idx
    meta["rotate_tried_history"] = tried
    meta["hint"] = "good_rotate"
    return prompt, meta
```

`_load_prior_sample_outcomes(iid, model_slug, sample_idx)` reads `runs_v2/<iid>__good_rotate__<model_slug>__s<j>/result.json` for `j < sample_idx`, extracts each cell's `arm_meta.routed_to` and `resolved`, returns `{routed_to: [resolved_bool, ...]}`.

**`_synth_entry` update** — return a merged view when `revisions` is present:

```python
def _synth_entry(iid: str) -> dict | None:
    global _synth_data
    if _synth_data is None:
        _synth_data = json.loads(SYNTH_CACHE.read_text()) if SYNTH_CACHE.exists() else {}
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

Backwards-compat: entries without `revisions` return unchanged. The aliased top-level fields are also correct after refinement (refinement script keeps them in sync), so this update is belt-and-suspenders for the `revisions` case.

### `pipeline/orchestrator.py` — Per-`(iid, model)` chain scheduling

```python
# In main(), after enumerate_cells produces `todo`:
rotate_cells = [c for c in todo if c.arm == "good_rotate"]
other_cells  = [c for c in todo if c.arm != "good_rotate"]
chains: dict[tuple[str, str], list[Cell]] = defaultdict(list)
for c in rotate_cells:
    chains[(c.iid, c.model)].append(c)
for chain in chains.values():
    chain.sort(key=lambda c: c.sample_idx)

def run_chain(chain):
    for c in chain:
        run_cell(c, llm, client, ...)  # serial: sample N writes result.json before N+1 reads

# Pool A (parallel) for other_cells, Pool B (parallel chains, serial within) for chains.values()
```

`_has_memory` gate gains a `good_rotate` case:
```python
if c.arm == "good_rotate":
    return c.iid in mem_ids and c.iid in synth_ids and c.iid in loop_ids
```

`run_cell` passes `cell.sample_idx` to `build_prompt`:
```python
user_prompt, arm_meta = build_prompt(
    cell.iid, cell.arm, client=client, model_slug=cell.model_slug, sample_idx=cell.sample_idx,
)
```

### `pipeline/router.py` — `evaluate_offline_rotate`

Parallels `evaluate_offline` but simulates per-sample arm rotation. Consumes the existing outcomes log under LOO (`exclude_iid=iid` for KNN). For each `(model, iid)`:

- maintain `tried: dict[str, list[bool]]`, `consume_idx: dict[str, int] = defaultdict(int)`.
- for s in range(k): pick arm via `router.select_arm_for_sample`; look up `outcomes[(model, iid, arm, consume_idx[arm])]` (fallback to sample 0 if no sample N record); record into `tried`, increment `consume_idx[arm]`; short-circuit when `True`.
- coverage = tasks with at least one True hit; reference points (best static arm, all-arms union) computed from arm-level pass@k as in current `evaluate_offline`.

CLI integration in `main()`: print a third row per router/k combination labeled `rotation=True`.

## Data flow

```
                  ┌─────────────────────────────┐
                  │   _oracle/outcomes_log.json │
                  │   (sample-level, 394 rows)  │
                  └──────────────┬──────────────┘
                                 │  select_stuck()
                                 v
                  ┌─────────────────────────────┐
                  │  stuck iids: e.g. 15976,    │
                  │  16766 for gemma4_e4b       │
                  └──────────────┬──────────────┘
                                 │  harvest_failing_transcripts()
                                 v
                  ┌─────────────────────────────┐
                  │  failure evidence (gold-    │
                  │  scrubbed, test-path-       │
                  │  filtered): stop_reason,    │
                  │  last-turn observations,    │
                  │  parse-failure notes        │
                  └──────────────┬──────────────┘
                                 │  build_refine_prompt()
                                 │  + current cue entry
                                 v
                  ┌─────────────────────────────┐
                  │   claude -p (Opus)          │
                  │   isolated temp cwd,        │
                  │   no Bash/Read/Edit tools   │
                  └──────────────┬──────────────┘
                                 │  refined JSON
                                 v
                  ┌─────────────────────────────┐
                  │  scrub_leak() defense in    │
                  │  depth against gold_added_  │
                  │  lines(iid)                 │
                  └──────────────┬──────────────┘
                                 │  write_revision()
                                 v
                  ┌─────────────────────────────┐
                  │   _oracle/synth_cache.json  │
                  │   revisions[].append(...)   │
                  │   top-level aliases ← new   │
                  └──────────────┬──────────────┘
                                 │  next eval run
                                 v
       arm_context._synth_entry() returns latest revision merged with metadata
       router.extract_features() reads top-level aliased localization_cues etc.
       good_rotate (independent track) reads runs_v2/ for prior sample outcomes
       and dispatches sample N+1 to a different sub-arm via select_arm_for_sample
```

## Operator workflow

```bash
# 1. Eval batch (writes runs_v2/)
uv run python -m pipeline.orchestrator --arms good good_synth good_loop good_multi_loop \
    -k 3 --workers 1

# 2. Refresh outcomes log
uv run python -m pipeline.router

# 3. Refine cues for stuck tasks (offline; no server needed)
uv run python -m memory.refine_from_outcomes --min-failure-count 3

# 4. (Optional) refresh verifications for refined tasks
uv run python -m memory.extract_verification --redo --only sympy__sympy-15976 sympy__sympy-16766

# 5. Archive pre-refinement runs and re-eval
mv runs_v2 runs_v2.cues_v1
uv run python -m pipeline.orchestrator --only sympy__sympy-15976 sympy__sympy-16766 \
    --arms good_synth good_loop good_multi_loop -k 3

# 6. Optionally add good_rotate to the next full run
uv run python -m pipeline.orchestrator --arms good_rotate -k 3
```

## Integration points

- **`memory/synthesize.py:_extract_json`**: refinement imports and reuses (or both move to `memory/_claude_io.py`).
- **`memory/to_memory_entry.py:gold_added_lines`, `scrub_leak`**: refinement imports and reuses for the defense-in-depth scrub.
- **`pipeline/router.py:_ACTIVE_ROUTER`**: `good_rotate` reads through the module-level global so swapping Rule→KNN by `set_router(KNNRouter())` is enough to flip rotation policy.
- **`harness/tests/test_search_replace.py`**: every existing test must pass unchanged (validated by `uv run python -m pytest harness/tests/ -q`).

## Edge cases (with handling)

1. **Opus returns malformed JSON.** `_extract_json` raises; per-task try/except in the worker logs the error and leaves the entry untouched. Sibling tasks unaffected.
2. **Refinement empties `root_cause_pattern`.** Rejected before write: `if not refined["root_cause_pattern"].strip(): raise ValueError(...)`. Logged with iid; no revision appended.
3. **Failing-transcript harvest finds < `min_failure_count` runs.** Task skipped; `--dry-run` shows skipped tasks with reason.
4. **Gold-scrub flags many leaks.** Refinement is still written; `leak_lines_removed` recorded on the revision. Operator inspects via `jq '.revisions[-1].leak_lines_removed' synth_cache.json`.
5. **`good_rotate` cell #s=2 starts before #s=1's `result.json` is written.** Impossible under the per-`(iid,model)` chain scheduler; documented invariant.
6. **Operator forgets to archive `runs_v2/` before re-eval.** `_has_memory` and `is_fresh` semantics mean re-evaluated cells overwrite; loss of pre-refinement data. Operational discipline; flagged in `_index.md` workflow.
7. **`_synth_data` cached in `arm_context` survives between refinement and next eval.** Refinement runs as a separate process; orchestrator starts a fresh process; cache reset naturally.

## Open questions (documented, not blocking)

1. Whether to add a `cues_rev` field to outcomes log rows. Cleaner attribution but schema churn.
2. Whether to extend stuck-task selection to "partially stuck" (e.g. < 20% win rate) tasks once the fully-stuck two are addressed.
3. Whether the parser's "raw markers without fence" recovery (last-resort) should also infer paths from `# path: foo.py`-style comments.
4. Whether `good_rotate` early-exits at the orchestrator level on the first within-task win.
