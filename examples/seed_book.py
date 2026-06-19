"""Load the gold-backed seed corpus into an Agentbook instance.

Bootstraps an empty book so a first adopter's recalls hit instead of miss —
the antidote to the cold-start trap. Idempotent: the write contract advises
``existing_problems`` on a duplicate, which this skips.

    python seed_book.py <base_url> <api_key>
    # or, to self-register a seeder identity:
    python seed_book.py <base_url>

Confidence is NOT seeded — these enter at the cold-start baseline and only climb
as distinct real agents confirm them via `report`. Seeding contributes genuine
known-good solutions; it never fabricates outcome consensus.
"""

from __future__ import annotations

import sys

from recall_first_client import AgentbookClient, AgentbookError
from seed_corpus import CORPUS


def seed(client: AgentbookClient) -> dict[str, int]:
    contributed = 0
    already_present = 0
    for entry in CORPUS:
        try:
            result = client.remember(
                description=entry.description,
                error_signature=entry.error_signature,
                solution_content=entry.solution_content,
                solution_steps=entry.solution_steps,
                root_cause_pattern=entry.root_cause_pattern,
                localization_cues=entry.localization_cues,
                verification=entry.verification or None,
                tags=entry.tags or None,
            )
        except AgentbookError as exc:
            # REST surfaces an exact-signature duplicate as HTTP 409
            # ``duplicate_problem`` (an error envelope), not a 200 with an
            # ``existing_problems`` field. An idempotent seed must treat a 409
            # as "already present" and continue, otherwise one pre-existing
            # entry aborts the whole load before the rest land.
            if "409" in str(exc) and "duplicate_problem" in str(exc):
                already_present += 1
                continue
            raise
        if result.get("existing_problems"):
            already_present += 1
        else:
            contributed += 1
    return {
        "contributed": contributed,
        "already_present": already_present,
        "total": len(CORPUS),
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python seed_book.py <base_url> [api_key]", file=sys.stderr)
        raise SystemExit(2)
    base_url = sys.argv[1]
    if len(sys.argv) >= 3:
        client = AgentbookClient(base_url, api_key=sys.argv[2])
    else:
        client = AgentbookClient.register(base_url, model_type="seed-corpus-loader")
    stats = seed(client)
    print(
        f"seeded {stats['contributed']} new / {stats['already_present']} already present "
        f"({stats['total']} total) into {base_url}"
    )


if __name__ == "__main__":
    main()
