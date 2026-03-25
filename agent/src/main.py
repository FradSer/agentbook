import asyncio
import logging
import time
from datetime import UTC, datetime

# Load config (which loads .env)
from agent.src.config import settings  # noqa: E402

# Configure logging level from environment
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from agent.src.backoff import BackoffState
from agent.src.research_loop import run_research_cycle
from agent.src.researcher_agent import create_researcher_agent
from agent.src.reviewer_agent import create_reviewer_agent
from agent.src.synthesis import SYSTEM_AGENT_ID
from agent.src.tools import get_researcher_tools
from backend.application.gate import check_spam
from backend.application.service import AgentbookService
from backend.domain.models import Agent as AgentModel
from backend.infrastructure.embeddings.fallback import FallbackEmbeddingProvider
from backend.infrastructure.embeddings.openrouter import resolve_embedding_provider
from backend.infrastructure.persistence.sqlalchemy_repositories import (
    SQLAlchemyAgentRepository,
    SQLAlchemyOutcomeRepository,
    SQLAlchemyProblemRepository,
    SQLAlchemyResearchCycleRepository,
    SQLAlchemySolutionRepository,
    SQLAlchemyTokenTransactionRepository,
)


def create_service(session: Session) -> AgentbookService:
    """Initialize AgentbookService with repositories using a session"""
    embedding_provider = resolve_embedding_provider() or FallbackEmbeddingProvider()

    def session_factory():
        return session

    return AgentbookService(
        agents=SQLAlchemyAgentRepository(session_factory),
        transactions=SQLAlchemyTokenTransactionRepository(session_factory),
        embedding_provider=embedding_provider,
        problems=SQLAlchemyProblemRepository(session_factory),
        solutions=SQLAlchemySolutionRepository(session_factory),
        outcomes=SQLAlchemyOutcomeRepository(session_factory),
        research_cycles=SQLAlchemyResearchCycleRepository(session_factory),
    )


async def _run_agent_review(agent, prompt: str):
    async_runner = getattr(agent, "arun", None)
    if callable(async_runner):
        return await async_runner(prompt)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, agent.run, prompt)


def review_content(agent, service) -> int:
    """Review unreviewed problems and solutions using Stage 1 gate + AI."""
    count = 0

    problems = service.get_unreviewed_problems(limit=100)
    for p in problems:
        result = check_spam(p.description, "problem")
        if not result.passed:
            service.update_review(
                content_id=p.problem_id,
                status="rejected",
                score=0.0,
                reviewed_at=datetime.now(UTC),
            )
        else:
            agent.run(f"Review this problem (ID: {p.problem_id}): {p.description}")
        count += 1

    solutions = service.get_unreviewed_solutions(limit=100)
    for s in solutions:
        content = s.content if hasattr(s, "content") else ""
        result = check_spam(content, "solution")
        if not result.passed:
            service.update_review(
                content_id=s.solution_id,
                status="rejected",
                score=0.0,
                reviewed_at=datetime.now(UTC),
            )
        else:
            agent.run(f"Review this solution (ID: {s.solution_id}): {content}")
        count += 1

    return count


async def run_cycle_until_idle(
    agent,
    service,
    max_cycle_seconds: int | None = None,
    continue_delay_seconds: float | None = None,
) -> dict[str, float | int | bool]:
    """Keep draining review backlog until empty or cycle timeout."""
    if max_cycle_seconds is None:
        max_cycle_seconds = settings.agent_max_cycle_seconds
    if continue_delay_seconds is None:
        continue_delay_seconds = settings.agent_continue_delay_seconds

    start_time = time.monotonic()
    processed_total = 0
    iteration = 0

    while True:
        iteration += 1
        batch_seen = review_content(agent, service)
        processed_total += batch_seen

        if batch_seen == 0:
            elapsed = time.monotonic() - start_time
            return {
                "processed": processed_total,
                "iterations": iteration,
                "elapsed_seconds": elapsed,
                "drained": True,
            }

        elapsed = time.monotonic() - start_time
        if elapsed >= max_cycle_seconds:
            logger.warning(
                "Cycle timeout reached after %.1fs with backlog still incoming; continuing next cycle",
                elapsed,
            )
            return {
                "processed": processed_total,
                "iterations": iteration,
                "elapsed_seconds": elapsed,
                "drained": False,
            }

        if continue_delay_seconds > 0:
            await asyncio.sleep(continue_delay_seconds)


def main():
    """Main polling loop"""
    logger.info("Starting Agentbook ReviewerAgent")
    researcher_model = settings.agent_researcher_model_name or settings.agent_model_name
    logger.info("Reviewer LLM: %s", settings.agent_model_name)
    logger.info("Researcher LLM: %s", researcher_model)

    if not settings.database_url:
        logger.error("DATABASE_URL environment variable not set")
        return
    if not settings.openrouter_api_key:
        logger.error("OPENROUTER_API_KEY environment variable not set")
        return

    engine = create_engine(settings.database_url)
    SessionFactory = sessionmaker(bind=engine)

    # Ensure system agent exists in DB (required for research_cycles FK)
    with SessionFactory() as session:
        _service = create_service(session)
        existing = _service._agents.get(SYSTEM_AGENT_ID)
        if existing is None:
            _service._agents.add(
                AgentModel(
                    agent_id=SYSTEM_AGENT_ID,
                    api_key_hash="system",
                    model_type=settings.agent_model_name,
                    token_balance=0,
                )
            )
            session.commit()
            logger.info("Registered system agent in database")
        else:
            existing.model_type = settings.agent_model_name
            _service._agents.add(existing)
            session.commit()

    backoff = BackoffState(base_delay=settings.agent_poll_interval)

    while True:
        try:
            with SessionFactory() as session:
                service = create_service(session)
                agent = create_reviewer_agent(service)
                researcher = create_researcher_agent(tools=get_researcher_tools(service))

                logger.info("Starting review cycle")
                cycle_metrics = asyncio.run(run_cycle_until_idle(agent, service))
                logger.info(
                    "Review cycle complete. processed=%s iterations=%s elapsed=%.1fs drained=%s",
                    cycle_metrics["processed"],
                    cycle_metrics["iterations"],
                    cycle_metrics["elapsed_seconds"],
                    cycle_metrics["drained"],
                )

                research_metrics = asyncio.run(run_research_cycle(researcher, service))
                logger.info(
                    "Research cycle complete. candidates=%s improved=%s no_improvement=%s researcher_model=%s",
                    research_metrics.get("candidates", 0),
                    research_metrics.get("improved", 0),
                    research_metrics.get("no_improvement", 0),
                    researcher_model,
                )

                session.commit()

            backoff.reset()

            if cycle_metrics["drained"]:
                logger.info(f"Sleeping {settings.agent_poll_interval}s")
                time.sleep(settings.agent_poll_interval)
            else:
                logger.info(
                    "Backlog remains. Retrying cycle after %ss",
                    settings.agent_backlog_retry_delay_seconds,
                )
                time.sleep(settings.agent_backlog_retry_delay_seconds)

        except KeyboardInterrupt:
            logger.info("Shutting down gracefully")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            backoff.increment()
            delay = backoff.get_delay()
            logger.info(f"Sleeping {delay}s before retry (backoff)")
            time.sleep(delay)


if __name__ == "__main__":
    main()
