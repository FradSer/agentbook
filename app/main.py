from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.application.service import AgentbookService
from app.core.config import settings
from app.infrastructure.embeddings.fallback import FallbackEmbeddingProvider
from app.infrastructure.embeddings.openrouter import resolve_embedding_provider
from app.infrastructure.persistence.database import SessionLocal, init_schema
from app.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryCommentRepository,
    InMemoryThreadRepository,
    InMemoryTokenTransactionRepository,
    InMemoryVoteRepository,
)
from app.infrastructure.persistence.sqlalchemy_repositories import (
    SQLAlchemyAgentRepository,
    SQLAlchemyCommentRepository,
    SQLAlchemyThreadRepository,
    SQLAlchemyTokenTransactionRepository,
    SQLAlchemyVoteRepository,
)
from app.presentation.api.router import api_router


def _build_service() -> AgentbookService:
    embedding_provider = resolve_embedding_provider() or FallbackEmbeddingProvider()

    if settings.database_url:
        return AgentbookService(
            agents=SQLAlchemyAgentRepository(SessionLocal),
            threads=SQLAlchemyThreadRepository(SessionLocal),
            comments=SQLAlchemyCommentRepository(SessionLocal),
            votes=SQLAlchemyVoteRepository(SessionLocal),
            transactions=SQLAlchemyTokenTransactionRepository(SessionLocal),
            embedding_provider=embedding_provider,
        )

    return AgentbookService(
        agents=InMemoryAgentRepository(),
        threads=InMemoryThreadRepository(),
        comments=InMemoryCommentRepository(),
        votes=InMemoryVoteRepository(),
        transactions=InMemoryTokenTransactionRepository(),
        embedding_provider=embedding_provider,
    )


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.app_version, debug=settings.debug)
    origins = [item.strip() for item in settings.cors_allow_origins.split(",") if item.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.service = _build_service()

    if settings.auto_create_schema and settings.database_url:
        init_schema()

    app.include_router(api_router)
    return app


app = create_app()
