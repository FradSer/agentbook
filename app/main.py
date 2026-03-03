from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.application.service import AgentbookService
from app.core.config import settings, validate_production_settings
from app.infrastructure.embeddings.fallback import FallbackEmbeddingProvider
from app.infrastructure.embeddings.openrouter import resolve_embedding_provider
from app.infrastructure.persistence.database import SessionLocal
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
from app.presentation.mcp import setup_mcp_app, sse_router
from app.presentation.mcp.auth import MCPAuthMiddleware


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


def _build_service_v2():
    from app.application.service_v2 import AgentbookServiceV2

    embed = resolve_embedding_provider() or FallbackEmbeddingProvider()
    embed_fn = embed.embed if hasattr(embed, "embed") else None

    if settings.database_url:
        from app.infrastructure.persistence.sqlalchemy_repositories_v2 import (
            SQLAlchemyOutcomeRepository,
            SQLAlchemyProblemRepository,
            SQLAlchemySolutionRepository,
        )
        return AgentbookServiceV2(
            problems=SQLAlchemyProblemRepository(SessionLocal),
            solutions=SQLAlchemySolutionRepository(SessionLocal),
            outcomes=SQLAlchemyOutcomeRepository(SessionLocal),
            embed=embed_fn,
        )

    from app.infrastructure.persistence.in_memory_v2 import (
        InMemoryOutcomeRepository,
        InMemoryProblemRepository,
        InMemorySolutionRepository,
    )
    return AgentbookServiceV2(
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        embed=embed_fn,
    )


def create_app() -> FastAPI:
    validate_production_settings(settings)
    app = FastAPI(
        title=settings.app_name, version=settings.app_version, debug=settings.debug
    )
    origins = [
        item.strip() for item in settings.cors_allow_origins.split(",") if item.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(MCPAuthMiddleware)
    app.state.service = _build_service()
    app.state.service_v2 = _build_service_v2()

    app.include_router(api_router)
    # Mount MCP server with SSE transport
    setup_mcp_app(app.state.service, app.state.service_v2)
    app.include_router(sse_router, prefix="/mcp")
    return app


app = create_app()
