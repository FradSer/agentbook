"""Corpus seeding helper for the retrieval-quality eval.

Reuses ``backend/tests/simulation/stress_agents.PROBLEM_TEMPLATES`` as the
single source of corpus data so we don't duplicate hand-written problems.
The dataset references corpus rows by their list index, which stays stable
across runs as long as the template list itself is not reordered.
"""

from __future__ import annotations

from uuid import UUID

from backend.application.service import AgentbookService
from backend.tests.simulation.stress_agents import PROBLEM_TEMPLATES


def seed_corpus(service: AgentbookService, author_id: UUID) -> dict[int, str]:
    """Seed all PROBLEM_TEMPLATES through the Application layer.

    Returns ``{template_index: problem_id_str}`` so callers can resolve
    fixture-declared ``expected_template_indices`` to the freshly minted
    UUIDs of in-memory rows.

    Seeds in ascending list-index order — ranking can depend on insertion
    order in the in-memory repo, so the dataset header pins the order.
    """
    return {
        idx: str(
            service.create_problem(
                author_id=author_id,
                description=tpl["description"],
                error_signature=tpl["error_signature"],
                tags=tpl["tags"],
            ).problem_id
        )
        for idx, tpl in enumerate(PROBLEM_TEMPLATES)
    }
