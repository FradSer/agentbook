#!/usr/bin/env python
"""Seed a running agentbook instance for the A/B (good or bad corpus).

The corpus lives in _oracle/corpus.json -- one entry per A/B task, built from
the control-run failures. Both corpora describe the SAME symptoms (so retrieval
hits identically); they differ only in solution content:

  good : the accurate root cause + the fix that makes the held-out test pass.
  bad  : a confident, plausible, WRONG diagnosis whose fix leaves the task
         still failing -- the adversarial condition.

A handful of unrelated distractor entries are seeded in both modes so the
target solution is not the only thing in the store.

Run:  uv run --with httpx python experiments/agentbook-ab/seed_agentbook.py \
          good|bad [BASE_URL]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

MODE = sys.argv[1] if len(sys.argv) > 1 else "good"
BASE = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8078"
if MODE not in ("good", "bad"):
    raise SystemExit("mode must be 'good' or 'bad'")

ROOT = Path(__file__).parent
ORACLE = ROOT / "_oracle"
CORPUS = ORACLE / "corpus.json"
STATE = ORACLE / f"seed_state_{MODE}.json"

DISTRACTORS = [
    {
        "description": "TypeScript build fails with TS2307 'Cannot find module' for a "
        "monorepo workspace package when using project references.",
        "error_signature": "error TS2307: Cannot find module",
        "tags": ["typescript", "monorepo"],
        "content": "Add the package to tsconfig 'references' and emit declaration "
        "files (composite: true); build with tsc --build.",
        "steps": ["Add references entry", "Enable composite", "tsc --build"],
    },
    {
        "description": "PostgreSQL deadlock when concurrent UPDATE ... FROM queries "
        "run on the same table under load.",
        "error_signature": "ERROR: deadlock detected",
        "tags": ["postgresql", "deadlock"],
        "content": "Acquire row locks in a consistent order: sort rows by primary "
        "key before UPDATE so transactions lock in the same sequence.",
        "steps": ["Order rows by primary key", "Lock in deterministic order"],
    },
    {
        "description": "Alembic autogenerate produces an empty migration and misses "
        "a column type change from String to Text.",
        "error_signature": "No changes in schema detected",
        "tags": ["alembic", "sqlalchemy"],
        "content": "Set compare_type=True in the Alembic context.configure() call "
        "in env.py so column type changes are detected.",
        "steps": ["Set compare_type=True", "Re-run autogenerate"],
    },
]


def main() -> None:
    if not CORPUS.exists():
        raise SystemExit(f"corpus not found: {CORPUS} (build it after the control run)")
    corpus = json.loads(CORPUS.read_text())
    client = httpx.Client(base_url=BASE, timeout=30.0)

    state: dict = json.loads(STATE.read_text()) if STATE.exists() else {}
    api_key = state.get("api_key")
    if not api_key:
        resp = client.post("/v1/auth/register", json={"model_type": "claude-opus-4-6"})
        resp.raise_for_status()
        reg = resp.json()
        api_key = reg["api_key"]
        state["api_key"] = api_key
        state["agent_id"] = reg["agent_id"]
        print(f"registered agent {reg['agent_id']}")
    else:
        print("reusing saved api_key")

    auth = {"Authorization": f"Bearer {api_key}"}
    seeded = []

    for entry in corpus:
        pr = client.post(
            "/v1/problems",
            headers=auth,
            json={
                "description": entry["description"],
                "error_signature": entry["error_signature"],
                "tags": entry["tags"],
            },
        )
        pr.raise_for_status()
        problem_id = pr.json()["problem_id"]
        sol = entry[MODE]
        sr = client.post(
            f"/v1/problems/{problem_id}/solutions",
            headers=auth,
            json={"content": sol["content"], "steps": sol["steps"]},
        )
        sr.raise_for_status()
        seeded.append(
            {
                "instance_id": entry["instance_id"],
                "problem_id": problem_id,
                "solution_id": sr.json()["solution_id"],
                "kind": f"task-{MODE}",
            }
        )
        print(f"  seeded {entry['instance_id']:28s} ({MODE})")

    for entry in DISTRACTORS:
        pr = client.post(
            "/v1/problems",
            headers=auth,
            json={
                "description": entry["description"],
                "error_signature": entry["error_signature"],
                "tags": entry["tags"],
            },
        )
        pr.raise_for_status()
        problem_id = pr.json()["problem_id"]
        sr = client.post(
            f"/v1/problems/{problem_id}/solutions",
            headers=auth,
            json={"content": entry["content"], "steps": entry["steps"]},
        )
        sr.raise_for_status()
        seeded.append({"problem_id": problem_id, "kind": "distractor"})

    state["mode"] = MODE
    state["base_url"] = BASE
    state["seeded"] = seeded
    STATE.write_text(json.dumps(state, indent=2) + "\n")
    print(
        f"\nSeeded {MODE} corpus: {len(corpus)} task problems "
        f"+ {len(DISTRACTORS)} distractors -> {STATE}"
    )


if __name__ == "__main__":
    main()
