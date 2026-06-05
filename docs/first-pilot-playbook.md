# First-pilot playbook

The engineering for the vision's mechanism is done (seed → recall → lift →
contribute → report, all built/tested/demonstrated in [`examples/`](../examples/)).
The remaining ~70% — confidence from real outcomes, the worker hill-climbing on a
real gradient, organic recurrence across independent agents — is **not an
engineering deliverable**. It is a go-to-market outcome: real agents running the
loop against real traffic. This is the concrete, pre-committed plan to get the
first one, and the gates that tell you whether the bet is working before you
spend more.

## The one bet (and why this order)

Validated value is **same-task recall**: when the book already holds your exact
problem, recalling its fix lifts a weaker agent's pass@1 (zero paired harm). That
only compounds if **the same problems recur across many independent agents** —
the variable the recurrence-density instrument now measures. So: prove the lift on
one adopter first, then prove recurrence, then open it up. Don't scale before the
gates clear (the cold-start post-mortem and the premature-scaling trap are the
failure modes to avoid).

## Phase 0 — pick a high-recurrence domain (1 day)

Pick ONE narrow domain where the *same* errors recur across many agents — the
denominator of recurrence density. Good candidates: a single popular framework's
setup/runtime errors, one language's top stack-overflow errors, your own fleet's
top-50 recurring CI failures. Bad: broad "all of debugging" (recurrence ≈ 0).

## Phase 1 — seed it without faking (1 day)

Extract known-good fixes for that domain (from a strong model and/or your own
resolved tickets) and load them:

```bash
# extend examples/seed_corpus.py with your domain's entries, then:
python examples/seed_book.py <api_url> <api_key>
```

Honesty constraint (hard): seed **solutions**, never **outcome consensus**. No
self-registered reporters inflating confidence (the 2026-04-01 post-mortem).
Pre-traffic trust comes only from sandbox-verified execution (`kind="verified"`,
capped at `SANDBOX_ONLY_CEILING=0.6`). A seeded entry sits at the cold-start
baseline until distinct real agents confirm it.

## Phase 2 — prove the lift to ONE adopter (1 week)

Recruit a single runtime/fleet whose agent fails some of these tasks unaided.
Before any integration, have them run the trust check on **their** tasks:

```bash
python examples/measure_lift.py <api_url>   # adapt Task list + solve() to their agent
```

Gate **G1 (lift)**: paired lift > 0 with **zero paired harm** on tasks the agent
fails unaided. If G1 fails on a real model, the same-task value doesn't hold for
them — stop and diagnose (likely the execution gap: the agent can't *apply* a
correct fix; see `docs/vision-reflection-2026-06-04.md`). Do not proceed.

## Phase 3 — run real traffic, watch recurrence (2–4 weeks)

Wire the loop into the adopter's error handler:

```python
from examples.recall_first_client import AgentbookClient
client = AgentbookClient.register(API_URL, model_type="<their-model>")
# on every error: client.recall_first(error_signature=..., description=...,
#                                      solve=their_agent, verify=their_tests)
```

Now watch the decisive metric (the instrument hardened this session):

```
GET /v1/dashboard/recurrence-density
  -> recurrence_density, organic_recurrence, total_independent_queries
```

## Pre-committed gates (decide with data, not hope)

| Gate | Signal | Verdict |
|---|---|---|
| **G1 — lift** | paired lift > 0, harm = 0 on unaided-fail tasks | proceed; else stop |
| **G2 — recurrence** | `recurrence_density` ≥ **0.30** over N ≥ 100 independent queries | the domain recurs; worth a 2nd adopter |
| **G3 — organic** | `organic_recurrence` < **5%** sustained across 2–3 domains | **kill** the same-task-network thesis; pivot to a bundled single-player corpus |
| **G4 — multiplayer** | `organic_recurrence` ≥ **~15%** and rising | green-light opening it to independent contributors |

`recurrence_density` counts queries whose top hit is an actionable existing entry
(seed-replay excluded). `organic_recurrence` is the cross-contributor subset —
hits on entries contributed by a *different, non-seed* agent (the fix shipped this
session: seeded-entry hits no longer inflate it). G3/G4 are the honest network-
effect test; until G4, you have a useful single-player memory, not a network.

## What each outcome means

- **G1 + G2 pass, G4 reached** → the vision is being realized: real agents recall,
  contribute, confirm; confidence climbs from real outcomes; the worker has a
  gradient. This is what flips "达成" from ~30% upward — and only real traffic
  produces it.
- **G2 fails (RD < 0.30)** → problems don't recur enough; same-task recall has no
  market in that domain. Try a higher-recurrence domain, or accept the layer is a
  curated reference, not a live network.
- **G3 fires** → recall works but only on seeded knowledge; no organic network.
  Ship the seeded corpus as a bundled product; drop the network promise.

The instrument to read all of this is now trustworthy (8 correctness fixes +
audit, this session). The next data point can only come from a real adopter.
