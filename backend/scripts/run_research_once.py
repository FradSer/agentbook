"""Run a single Auto Research (hill-climbing) cycle against the live database.

Usage::

    uv run python -m backend.scripts.run_research_once --batch 10 --cooldown-hours 0
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from agent.src.config import settings as agent_settings
from agent.src.llm import active_llm_provider, llm_api_key_configured, resolve_model_id
from agent.src.main import create_service
from agent.src.research_loop import run_research_cycle
from agent.src.researcher_agent import create_researcher_agent
from agent.src.tools import get_researcher_tools
from backend.core.config import settings

logger = logging.getLogger("agentbook.run_research_once")


async def _run(batch: int, cooldown_hours: int | None) -> dict:
    from backend.infrastructure.persistence.database import SessionLocal

    if not agent_settings.agent_research_enabled:
        logger.warning("AGENT_RESEARCH_ENABLED is false; enabling for this run")
        agent_settings.agent_research_enabled = True

    prev_batch = agent_settings.agent_research_batch_size
    agent_settings.agent_research_batch_size = batch
    try:
        with SessionLocal() as session:
            service = create_service(session)
            researcher = create_researcher_agent(tools=get_researcher_tools(service))
            metrics = await run_research_cycle(
                researcher, service, cooldown_hours=cooldown_hours
            )
            session.commit()
            return metrics
    finally:
        agent_settings.agent_research_batch_size = prev_batch


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    parser = argparse.ArgumentParser(description="Run one Agentbook research cycle")
    parser.add_argument("--batch", type=int, default=5, help="Max candidates per cycle")
    parser.add_argument(
        "--cooldown-hours",
        type=int,
        default=0,
        help="Override research cooldown (0 = no cooldown for imports)",
    )
    args = parser.parse_args(argv)

    if not settings.database_url:
        print("error: DATABASE_URL must be set", file=sys.stderr)
        return 2
    if not llm_api_key_configured():
        print(
            f"error: LLM credentials missing for provider={active_llm_provider()} "
            "(set NVIDIA_API_KEY, CF_AIG_*, or OPENROUTER_API_KEY)",
            file=sys.stderr,
        )
        return 2

    logger.info(
        "research-once provider=%s model=%s batch=%d cooldown_hours=%s",
        active_llm_provider(),
        resolve_model_id(researcher=True),
        args.batch,
        args.cooldown_hours,
    )
    metrics = asyncio.run(_run(args.batch, args.cooldown_hours))
    print("Research cycle:", metrics)
    if metrics.get("skipped"):
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
