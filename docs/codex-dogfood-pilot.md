# Codex dogfood pilot

## Decision this pilot makes

For two weeks, test whether sanitized Agentbook recall increases Codex's first-attempt success rate on real coding work. This is a **skill-only** integration: the globally installed `using-agentbook` skill owns sanitization, anonymous REST recall, experiment assignment, and local measurement. No separate Codex tool server, hook, or persistent credential is required.

Anonymous mode deliberately does not contribute memories or report outcomes. It validates recall's single-player pass@1 value without adding a credential lifecycle; it does not validate Agentbook's public confidence flywheel.

The pilot uses two cohorts:

- `live`: real incidents from daily repositories, deterministically assigned 50/50 to control or treatment.
- `replay`: historical reproducible failures run once per arm in fresh Codex sessions and isolated worktrees.

## One-time Codex setup

Install the repository skill globally, keeping this checkout as the source of truth:

```bash
ln -s /Users/FradSer/Developer/FradSer/agentbook/skills/using-agentbook \
  ~/.codex/skills/using-agentbook
```

Restart Codex after installing or updating the skill. No other global configuration is part of this integration.

## Live incident protocol

An eligible incident is an unexpected error blocking a real build, test, runtime, or implementation task. Expected TDD RED failures, deliberate negative tests, user cancellations, transient tool failures, and Agentbook probes/evaluations are excluded.

Before the first substantive code or configuration change, run:

```bash
python ~/.codex/skills/using-agentbook/scripts/pilot.py start \
  --repo "$PWD" --dependency python=3.11.9 \
  --error '<locally observed raw error>'
```

The script automatically redacts the repository name. Add repeatable `--private-term '<private-name>'` arguments for other customer or project identifiers. It stores only a repository hash and a sanitized, single-line query in the private `0600` ledger at `~/.local/share/agentbook/pilot.jsonl`.

Only an eligible treatment incident may query before pass@1 measurement:

```bash
python ~/.codex/skills/using-agentbook/scripts/pilot.py recall \
  --incident-id '<incident id>'
```

The recall command reads `public_query` from the ledger and sends it anonymously. It never accepts raw error text and never adds an authorization header.

- Treatment recalls before its first modification, applies at most one considered approach, and runs a predeclared existing verification command.
- Control does not recall before its first modification and verification. After a failed first attempt is recorded, `recall --incident-id '<id>' --crossover` is allowed.
- An unavailable Agentbook records `unavailable`, and normal debugging continues.

Immediately after the first verification, append the result:

```bash
python ~/.codex/skills/using-agentbook/scripts/pilot.py finish \
  --incident-id '<id>' --first-attempt passed --pre-recall hit \
  --match-quality exact --solution-id '<id>' \
  --verification '<existing command>'
```

## Replay cohort

Select historical failures with a known failing revision and a deterministic verification command. For every task, create two clean worktrees and fresh Codex sessions with the same model, prompt, context, time budget, and verification. Do not expose the known fix.

Start each arm with an opaque pair identifier:

```bash
python ~/.codex/skills/using-agentbook/scripts/pilot.py start \
  --repo "$PWD" --cohort replay --pair-id replay-001 --arm control \
  --error '<historical error>'
```

Repeat with `--arm treatment`, then finish both incidents using the normal command.

## Fixed gates

Read progress with:

```bash
python ~/.codex/skills/using-agentbook/scripts/pilot.py summary
```

A `pass` requires all of the following:

- 20 completed live incidents.
- 20 completed replay pairs.
- Replay treatment pass@1 improves by at least +15 percentage points.
- Replay produces at least 3 net paired wins.
- There is zero paired harm.
- Live incidents maintain at least 90% ledger completion.

`collecting` means the sample floor has not been reached; do not infer success or failure. `fail_harm` stops expansion immediately. `fail_no_lift` means sufficient data exists but the effectiveness gates failed.

## Interpretation and privacy audit

- Hits without lift indicate an execution or verification gap; improve solution actionability before adding product features.
- Low hit rate indicates corpus coverage or recurrence-density failure; narrow the domain.
- Passing without harm authorizes a separately designed external pilot, not a network-effect claim.
- Before reading the final result, inspect every emitted `public_query`. Any leaked private identifier invalidates the pilot and blocks further production traffic until the sanitizer is fixed.
