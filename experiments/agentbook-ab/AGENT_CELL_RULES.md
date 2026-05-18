# Agentbook A/B cell rules (mandatory)

You are fixing **one** benchmark cell: `runs/<instance_id>__<arm>/`.

## Allowed reads

- `runs/<instance_id>__<arm>/prompt.md`
- Source under `runs/<instance_id>__<arm>/repo/`
- `tasks/<instance_id>/BUG.md` only if the prompt references it (optional)

## Forbidden (instant disqualification)

- Any path under `_oracle/` (`gold.patch`, `test.patch`, `corpus.json`, `corpus.simulated.json`, etc.)
- Reading `META.json` for gold file hints
- `tasks/<instance_id>/repo/` (pristine base; do not copy fixes from there)
- Other arms' `runs/<instance_id>__<other>/` directories
- Applying or reading unified diffs from prior experiment logs

## Edits

- **Source files only** — never edit test files listed in META or under `*test*`.
- Minimal fix for the bug described in the prompt.
- For **bad** arm: follow the Agentbook Hint even if suspicious; do not substitute the gold fix.
- For **good** arm: verify the hint against code before applying.
- For **control** arm: no agentbook hint; explore and fix from the bug description only.

## Finish

```bash
cd runs/<instance_id>__<arm>/repo
git add -A
git commit -m "agent fix"   # skip if no source changes
```

Do **not** run `score.py`, `pytest` on FAIL_TO_PASS grading nodes, or read test patches.
