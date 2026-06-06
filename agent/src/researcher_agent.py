from __future__ import annotations

from pathlib import Path

from agno.agent import Agent

from agent.src.config import settings
from agent.src.llm import build_agent_model

# Fallback constant used when program.md is missing
_RESEARCHER_INSTRUCTIONS_FALLBACK = """
You are the ResearcherAgent for Agentbook — an autonomous hill-climbing loop that improves solutions.

## Loop semantics (karpathy/autoresearch pattern)
Each call is one iteration: read context → propose modification → measure → keep or discard.
The metric is `confidence` (outcome-driven Bayesian score, 0.0–1.0).
You ONLY keep a proposal when it strictly increases confidence.

## Your two tools

1. `propose_improvement(solution_id, improved_content, reasoning, steps)` — submit a candidate.
   The system will run hill-climbing: accepted only if confidence strictly improves.

2. `skip_improvement(problem_id, reason)` — declare no improvement possible for this cycle.

Always call exactly ONE of these two tools. Never respond with plain text only.

## Simplicity criterion (Karpathy rule)
Reject proposals that are MORE THAN 2x the length of the current solution unless you have strong
evidence (from the outcome data below) that the extra complexity is necessary.
Tiny improvement + ugly complexity = skip.

## Decision process
1. Read the outcome data (success/failure counts, failure notes, environments).
2. Identify the most impactful weakness in the current best solution.
3. Propose the MINIMAL change that addresses that weakness.
4. If no weakness is identifiable or no improvement is possible, call skip_improvement.

## Quality rules
- Prefer concrete, actionable steps over vague descriptions.
- Simpler solutions beat complex ones when confidence is equal.
- A solution that works in more environments is better.
"""


def _load_instructions() -> str:
    """Load researcher instructions from program.md (autoresearch pattern), with fallback."""
    custom_path = settings.agent_researcher_instructions_path
    path = Path(custom_path) if custom_path else Path(__file__).parent / "program.md"
    if path.exists():
        return path.read_text()
    return _RESEARCHER_INSTRUCTIONS_FALLBACK


def create_researcher_agent(tools: list) -> Agent:
    return Agent(
        model=build_agent_model(researcher=True),
        instructions=_load_instructions(),
        tools=tools,
    )


def build_synthesis_llm_fn():
    """A tools-less text->text callable on the researcher model.

    Used by the synthesis pass to distil active solutions into canonical content
    plus transferable structured knowledge. Kept separate from the research agent
    so synthesis is not biased by the hill-climbing instructions or tools.
    """
    agent = Agent(
        model=build_agent_model(researcher=True),
        instructions=(
            "You are a precise knowledge-synthesis agent. Follow the requested "
            "output format exactly and output nothing else."
        ),
    )

    def _call(prompt: str) -> str:
        response = agent.run(prompt)
        return str(getattr(response, "content", response))

    return _call
