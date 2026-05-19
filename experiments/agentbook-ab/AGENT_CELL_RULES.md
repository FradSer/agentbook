# Agentbook A/B cell rules (two arms: control + good)

You are fixing **one** benchmark cell: `runs/<instance_id>__<arm>/`.

## Arms

| Arm | Agentbook |
|-----|-----------|
| **control** | No agentbook; fix from bug description only |
| **good** | Hint already fetched via `GET /v1/search` (RAG) and embedded in `prompt.md` from the live API |

There is **no bad arm** in this benchmark.

## Allowed reads

- `runs/<instance_id>__<arm>/prompt.md`
- Source under `runs/<instance_id>__<arm>/repo/`

## Forbidden

- `_oracle/` (gold.patch, test.patch, corpus files)
- `META.json`, `recalls/` (audit only; do not use gold paths from recall JSON)
- Other arms' `runs/<instance_id>__<other>/`
- Re-calling agentbook to fetch a different hint (use the recall in the prompt)

## Finish

```bash
cd runs/<instance_id>__<arm>/repo
git add -A
git commit -m "agent fix"
```

Do not run `score.py` or grading pytest.
