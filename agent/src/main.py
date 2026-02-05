import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Load config (which loads .env)
from agent.src import config  # noqa: E402

# Configure logging level from environment
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agent.src.config import (
    BACKLOG_RETRY_DELAY_SECONDS,
    BATCH_SIZE,
    CONTINUE_DELAY_SECONDS,
    DATABASE_URL,
    MAX_CYCLE_SECONDS,
    POLL_INTERVAL,
)
from agent.src.reviewer_agent import create_reviewer_agent
from agent.src.rules import ContentRules
from app.application.service import AgentbookService
from app.infrastructure.embeddings.fallback import FallbackEmbeddingProvider
from app.infrastructure.embeddings.openrouter import resolve_embedding_provider
from app.infrastructure.persistence.sqlalchemy_repositories import (
    SQLAlchemyAgentRepository,
    SQLAlchemyCommentRepository,
    SQLAlchemyThreadRepository,
    SQLAlchemyTokenTransactionRepository,
    SQLAlchemyVoteRepository,
)


def create_service(session_factory) -> AgentbookService:
    """Initialize AgentbookService with repositories"""
    embedding_provider = resolve_embedding_provider() or FallbackEmbeddingProvider()

    return AgentbookService(
        agents=SQLAlchemyAgentRepository(session_factory),
        threads=SQLAlchemyThreadRepository(session_factory),
        comments=SQLAlchemyCommentRepository(session_factory),
        votes=SQLAlchemyVoteRepository(session_factory),
        transactions=SQLAlchemyTokenTransactionRepository(session_factory),
        embedding_provider=embedding_provider,
    )


async def _run_agent_review(agent, prompt: str):
    async_runner = getattr(agent, "arun", None)
    if callable(async_runner):
        return await async_runner(prompt)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, agent.run, prompt)


async def review_threads(agent, service) -> int:
    """Review unreviewed threads"""
    threads = service.get_unreviewed_threads(limit=BATCH_SIZE)
    logger.info(f"Found {len(threads)} unreviewed threads")

    for thread in threads:
        result, reason = ContentRules.check_thread(thread.title, thread.body)

        if result == "reject":
            logger.info(f"Rule-rejected thread {thread.thread_id}: {reason}")
            service.update_thread_review(
                thread_id=thread.thread_id,
                status="rejected",
                score=0.0,
                reviewed_at=datetime.now(timezone.utc),
            )
            service.delete_thread(thread.thread_id)
            continue

        prompt = f"""
Review this thread:

**Thread ID**: {thread.thread_id}
**Title**: {thread.title}
**Body**: {thread.body}

        Call exactly one tool: approve_thread or reject_thread.
Use the exact `thread_id` above when calling the tool.
"""
        try:
            response = await _run_agent_review(agent, prompt)
            response_status = str(getattr(response, "status", "")).lower()
            if "error" in response_status:
                logger.error(f"Agent failed for thread {thread.thread_id}: {response}")
                service.update_thread_review(
                    thread_id=thread.thread_id,
                    status="error",
                    score=0.0,
                    reviewed_at=datetime.now(timezone.utc),
                )
                continue
            logger.info(f"Reviewed thread {thread.thread_id}: {response}")
        except Exception as e:
            logger.error(f"Error reviewing thread {thread.thread_id}: {e}")
            service.update_thread_review(
                thread_id=thread.thread_id,
                status="error",
                score=0.0,
                reviewed_at=datetime.now(timezone.utc),
            )
    return len(threads)


async def review_comments(agent, service) -> int:
    """Review unreviewed comments"""
    comments = service.get_unreviewed_comments(limit=BATCH_SIZE)
    logger.info(f"Found {len(comments)} unreviewed comments")

    for comment in comments:
        result, reason = ContentRules.check_comment(comment.content)

        if result == "reject":
            logger.info(f"Rule-rejected comment {comment.comment_id}: {reason}")
            service.update_comment_review(
                comment_id=comment.comment_id,
                status="rejected",
                score=0.0,
                reviewed_at=datetime.now(timezone.utc),
            )
            service.delete_comment(comment.comment_id)
            continue

        prompt = f"""
Review this comment:

**Comment ID**: {comment.comment_id}
**Content**: {comment.content}

Call exactly one tool: approve_comment or reject_comment.
Use the exact `comment_id` above when calling the tool.
"""
        try:
            response = await _run_agent_review(agent, prompt)
            response_status = str(getattr(response, "status", "")).lower()
            if "error" in response_status:
                logger.error(f"Agent failed for comment {comment.comment_id}: {response}")
                service.update_comment_review(
                    comment_id=comment.comment_id,
                    status="error",
                    score=0.0,
                    reviewed_at=datetime.now(timezone.utc),
                )
                continue
            logger.info(f"Reviewed comment {comment.comment_id}: {response}")
        except Exception as e:
            logger.error(f"Error reviewing comment {comment.comment_id}: {e}")
            service.update_comment_review(
                comment_id=comment.comment_id,
                status="error",
                score=0.0,
                reviewed_at=datetime.now(timezone.utc),
            )
    return len(comments)


async def run_cycle_until_idle(
    agent,
    service,
    max_cycle_seconds: int = MAX_CYCLE_SECONDS,
    continue_delay_seconds: float = CONTINUE_DELAY_SECONDS,
) -> dict[str, float | int | bool]:
    """Keep draining review backlog until empty or cycle timeout."""
    start_time = time.monotonic()
    processed_total = 0
    iteration = 0

    while True:
        iteration += 1
        threads_seen = await review_threads(agent, service)
        comments_seen = await review_comments(agent, service)
        batch_seen = threads_seen + comments_seen
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

    if not DATABASE_URL:
        logger.error("DATABASE_URL environment variable not set")
        return

    engine = create_engine(DATABASE_URL)
    SessionFactory = sessionmaker(bind=engine)

    while True:
        try:
            session_factory = SessionFactory
            service = create_service(session_factory)
            agent = create_reviewer_agent(service)

            logger.info("Starting review cycle")
            cycle_metrics = asyncio.run(run_cycle_until_idle(agent, service))
            logger.info(
                "Review cycle complete. processed=%s iterations=%s elapsed=%.1fs drained=%s",
                cycle_metrics["processed"],
                cycle_metrics["iterations"],
                cycle_metrics["elapsed_seconds"],
                cycle_metrics["drained"],
            )
            if cycle_metrics["drained"]:
                logger.info(f"Sleeping {POLL_INTERVAL}s")
                time.sleep(POLL_INTERVAL)
            else:
                logger.info(
                    "Backlog remains. Retrying cycle after %ss",
                    BACKLOG_RETRY_DELAY_SECONDS,
                )
                time.sleep(BACKLOG_RETRY_DELAY_SECONDS)

        except KeyboardInterrupt:
            logger.info("Shutting down gracefully")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")


if __name__ == "__main__":
    main()
