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

# retrieval_quality_dataset.json references indices 0..14 explicitly. Any
# reorder, insert, or delete in PROBLEM_TEMPLATES silently shifts ground
# truth, so we hard-fail at seed time instead of producing meaningless
# recall numbers.
_EXPECTED_TEMPLATE_COUNT = 15


def seed_corpus(service: AgentbookService, author_id: UUID) -> dict[int, str]:
    """Seed all PROBLEM_TEMPLATES through the Application layer.

    Returns ``{template_index: problem_id_str}`` so callers can resolve
    fixture-declared ``expected_template_indices`` to the freshly minted
    UUIDs of in-memory rows.

    Seeds in ascending list-index order — ranking can depend on insertion
    order in the in-memory repo, so the dataset header pins the order.

    Hard-fails when ``PROBLEM_TEMPLATES`` no longer has exactly
    ``_EXPECTED_TEMPLATE_COUNT`` entries to surface fixture drift loudly
    instead of producing silently-wrong metrics.
    """
    if len(PROBLEM_TEMPLATES) != _EXPECTED_TEMPLATE_COUNT:
        raise AssertionError(
            f"PROBLEM_TEMPLATES list shape changed: expected "
            f"{_EXPECTED_TEMPLATE_COUNT} entries, got {len(PROBLEM_TEMPLATES)}. "
            f"retrieval_quality_dataset.json references indices 0..{_EXPECTED_TEMPLATE_COUNT - 1}; "
            f"reordering, inserting, or deleting templates is a fixture-breaking "
            f"change and requires re-collecting the baseline."
        )
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
