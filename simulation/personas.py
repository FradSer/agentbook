"""Agent persona definitions for the simulation.

Five distinct persona types with different behavior patterns,
simulating realistic coding agent usage of AgentBook.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class AgentPersona:
    """Defines a simulated agent's behavior pattern."""

    name: str
    model_type: str
    # Behavior weights (0.0-1.0, used as probabilities)
    search_intensity: float  # How many searches to perform (scales 1-10)
    create_problem_prob: float  # Probability of creating problems
    create_solution_prob: float  # Probability of creating solutions
    report_outcome_prob: float  # Probability of reporting outcomes
    improve_prob: float  # Probability of improving solutions
    read_prob: float  # Probability of reading problem details
    lineage_prob: float  # Probability of checking lineage
    dashboard_prob: float  # Probability of reading dashboards
    # Timing
    min_jitter: float  # Minimum delay between ops (seconds)
    max_jitter: float  # Maximum delay between ops (seconds)
    # Problem domain preferences
    preferred_tags: list[str] = field(default_factory=list)
    num_problems_to_create: tuple[int, int] = (1, 3)
    num_solutions_per_problem: tuple[int, int] = (1, 2)


# ── Persona Definitions ──────────────────────────────────────────────

SEARCHER = AgentPersona(
    name="searcher",
    model_type="anthropic/claude-sonnet-4.6",
    search_intensity=0.9,
    create_problem_prob=0.1,
    create_solution_prob=0.1,
    report_outcome_prob=0.2,
    improve_prob=0.1,
    read_prob=0.8,
    lineage_prob=0.3,
    dashboard_prob=0.5,
    min_jitter=0.1,
    max_jitter=0.5,
    preferred_tags=["python", "docker", "typescript"],
    num_problems_to_create=(0, 1),
    num_solutions_per_problem=(0, 1),
)

CONTRIBUTOR = AgentPersona(
    name="contributor",
    model_type="openai/gpt-5.4",
    search_intensity=0.3,
    create_problem_prob=0.9,
    create_solution_prob=0.9,
    report_outcome_prob=0.4,
    improve_prob=0.5,
    read_prob=0.3,
    lineage_prob=0.2,
    dashboard_prob=0.2,
    min_jitter=0.2,
    max_jitter=0.8,
    preferred_tags=["react", "nextjs", "postgresql"],
    num_problems_to_create=(2, 4),
    num_solutions_per_problem=(1, 3),
)

REPORTER = AgentPersona(
    name="reporter",
    model_type="google/gemini-3-pro",
    search_intensity=0.4,
    create_problem_prob=0.1,
    create_solution_prob=0.1,
    report_outcome_prob=0.9,
    improve_prob=0.1,
    read_prob=0.6,
    lineage_prob=0.2,
    dashboard_prob=0.3,
    min_jitter=0.05,
    max_jitter=0.3,
    preferred_tags=["sqlalchemy", "fastapi", "redis"],
    num_problems_to_create=(0, 1),
    num_solutions_per_problem=(0, 1),
)

BALANCED = AgentPersona(
    name="balanced",
    model_type="anthropic/claude-opus-4.7",
    search_intensity=0.6,
    create_problem_prob=0.5,
    create_solution_prob=0.5,
    report_outcome_prob=0.5,
    improve_prob=0.3,
    read_prob=0.5,
    lineage_prob=0.4,
    dashboard_prob=0.3,
    min_jitter=0.1,
    max_jitter=0.6,
    preferred_tags=["docker", "react", "python"],
    num_problems_to_create=(1, 3),
    num_solutions_per_problem=(1, 2),
)

EXPLORER = AgentPersona(
    name="explorer",
    model_type="meta/llama-4-maverick",
    search_intensity=0.7,
    create_problem_prob=0.3,
    create_solution_prob=0.3,
    report_outcome_prob=0.3,
    improve_prob=0.2,
    read_prob=0.8,
    lineage_prob=0.7,
    dashboard_prob=0.6,
    min_jitter=0.15,
    max_jitter=0.7,
    preferred_tags=["vite", "tailwind", "pnpm"],
    num_problems_to_create=(1, 2),
    num_solutions_per_problem=(1, 2),
)

ALL_PERSONAS = [SEARCHER, CONTRIBUTOR, REPORTER, BALANCED, EXPLORER]


def assign_personas(num_agents: int) -> list[AgentPersona]:
    """Distribute personas across N agents.

    Ensures at least one of each type when num_agents >= 5.
    Remainder distributed round-robin.
    """
    if num_agents < len(ALL_PERSONAS):
        # Fewer agents than persona types: pick first N
        return [ALL_PERSONAS[i] for i in range(num_agents)]

    personas: list[AgentPersona] = []
    # First, assign one of each type
    for p in ALL_PERSONAS:
        personas.append(p)

    # Distribute remainder round-robin
    remaining = num_agents - len(ALL_PERSONAS)
    for i in range(remaining):
        personas.append(ALL_PERSONAS[i % len(ALL_PERSONAS)])

    # Shuffle to avoid ordering bias
    random.shuffle(personas)
    return personas
