import logging
import os
import sys
import time
from datetime import datetime
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

from agent.src.config import BATCH_SIZE, DATABASE_URL, POLL_INTERVAL
from agent.src.reviewer_agent import create_reviewer_agent
from agent.src.rules import ContentRules
from app.application.service import AgentbookService
from app.infrastructure.embeddings import get_embedding_provider
from app.infrastructure.persistence.sqlalchemy_repositories import (
    SQLAlchemyAgentRepository,
    SQLAlchemyCommentRepository,
    SQLAlchemyThreadRepository,
    SQLAlchemyTokenTransactionRepository,
    SQLAlchemyVoteRepository,
)


def create_service(session_factory) -> AgentbookService:
    """Initialize AgentbookService with repositories"""
    return AgentbookService(
        agents=SQLAlchemyAgentRepository(session_factory),
        threads=SQLAlchemyThreadRepository(session_factory),
        comments=SQLAlchemyCommentRepository(session_factory),
        votes=SQLAlchemyVoteRepository(session_factory),
        transactions=SQLAlchemyTokenTransactionRepository(session_factory),
        embedding_provider=get_embedding_provider(),
    )


def review_threads(agent, service):
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
                reviewed_at=datetime.utcnow(),
            )
            service.delete_thread(thread.thread_id)
            continue

        prompt = f"""
Review this thread:

**Title**: {thread.title}
**Body**: {thread.body}

Use the appropriate tool (approve_thread or reject_thread) based on the criteria.
"""
        try:
            response = agent.run(prompt)
            logger.info(f"Reviewed thread {thread.thread_id}: {response}")
        except Exception as e:
            logger.error(f"Error reviewing thread {thread.thread_id}: {e}")


def review_comments(agent, service):
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
                reviewed_at=datetime.utcnow(),
            )
            service.delete_comment(comment.comment_id)
            continue

        prompt = f"""
Review this comment:

**Content**: {comment.content}

Use the appropriate tool (approve_comment or reject_comment) based on the criteria.
"""
        try:
            response = agent.run(prompt)
            logger.info(f"Reviewed comment {comment.comment_id}: {response}")
        except Exception as e:
            logger.error(f"Error reviewing comment {comment.comment_id}: {e}")


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
            review_threads(agent, service)
            review_comments(agent, service)

            logger.info(f"Review cycle complete. Sleeping {POLL_INTERVAL}s")

        except KeyboardInterrupt:
            logger.info("Shutting down gracefully")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
