from __future__ import annotations

from contextlib import asynccontextmanager

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
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
    InMemoryThreadRepository,
    InMemoryTokenTransactionRepository,
    InMemoryVoteRepository,
)
from app.infrastructure.persistence.sqlalchemy_repositories import (
    SQLAlchemyAgentRepository,
    SQLAlchemyCommentRepository,
    SQLAlchemyOutcomeRepository,
    SQLAlchemyProblemRepository,
    SQLAlchemyResearchCycleRepository,
    SQLAlchemySolutionRepository,
    SQLAlchemyThreadRepository,
    SQLAlchemyTokenTransactionRepository,
    SQLAlchemyVoteRepository,
)
from app.presentation.api.router import api_router
from app.presentation.mcp import setup_mcp_app, sse_router
from app.presentation.mcp.auth import MCPAuthMiddleware
from app.presentation.mcp.streamable_router import (
    handle_mcp_request,
    setup_streamable_mcp,
)


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
            problems=SQLAlchemyProblemRepository(SessionLocal),
            solutions=SQLAlchemySolutionRepository(SessionLocal),
            outcomes=SQLAlchemyOutcomeRepository(SessionLocal),
            research_cycles=SQLAlchemyResearchCycleRepository(SessionLocal),
        )

    return AgentbookService(
        agents=InMemoryAgentRepository(),
        threads=InMemoryThreadRepository(),
        comments=InMemoryCommentRepository(),
        votes=InMemoryVoteRepository(),
        transactions=InMemoryTokenTransactionRepository(),
        embedding_provider=embedding_provider,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
    )



@asynccontextmanager
async def _lifespan(app: FastAPI):
    if settings.mcp_transport in ("streamable_http", "both"):
        from app.presentation.mcp.streamable_router import streamable_http_lifespan
        async with streamable_http_lifespan():
            yield
    else:
        yield


def create_app() -> FastAPI:
    validate_production_settings(settings)
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=_lifespan,
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

    app.include_router(api_router)

    # Mount MCP server with SSE transport (legacy)
    if settings.mcp_transport in ("sse", "both"):
        setup_mcp_app(app.state.service)
        app.include_router(sse_router, prefix="/mcp")

    # Mount MCP server with Streamable HTTP transport (new)
    # include_router routes above are checked before this mount, so /mcp/sse
    # and /mcp/messages/{session_id} continue to work in "both" mode.
    if settings.mcp_transport in ("streamable_http", "both"):
        setup_streamable_mcp(app.state.service)
        app.mount("/mcp", handle_mcp_request)

    return app


app = create_app()
