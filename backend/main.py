from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

from backend.application.service import AgentbookService
from backend.core.config import settings, validate_production_settings
from backend.infrastructure.embeddings.fallback import FallbackEmbeddingProvider
from backend.infrastructure.embeddings.openrouter import resolve_embedding_provider
from backend.infrastructure.persistence.database import SessionLocal
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
    InMemoryTokenTransactionRepository,
)
from backend.infrastructure.persistence.sqlalchemy_repositories import (
    SQLAlchemyAgentRepository,
    SQLAlchemyOutcomeRepository,
    SQLAlchemyProblemRepository,
    SQLAlchemyResearchCycleRepository,
    SQLAlchemySolutionRepository,
    SQLAlchemyTokenTransactionRepository,
)
from backend.presentation.api.router import api_router
from backend.presentation.mcp import setup_mcp_app, sse_router
from backend.presentation.mcp.auth import MCPAuthMiddleware
from backend.presentation.mcp.streamable_router import (
    handle_mcp_request,
    setup_streamable_mcp,
)


def _build_service() -> AgentbookService:
    import os

    if os.getenv("DEMO_MODE") == "1":
        from backend.demo import build_demo_repos
        agents, transactions, problems, solutions, outcomes, cycles = build_demo_repos()
        return AgentbookService(
            agents=agents,
            transactions=transactions,
            embedding_provider=FallbackEmbeddingProvider(),
            problems=problems,
            solutions=solutions,
            outcomes=outcomes,
            research_cycles=cycles,
        )

    embedding_provider = resolve_embedding_provider() or FallbackEmbeddingProvider()

    if settings.database_url:
        return AgentbookService(
            agents=SQLAlchemyAgentRepository(SessionLocal),
            transactions=SQLAlchemyTokenTransactionRepository(SessionLocal),
            embedding_provider=embedding_provider,
            problems=SQLAlchemyProblemRepository(SessionLocal),
            solutions=SQLAlchemySolutionRepository(SessionLocal),
            outcomes=SQLAlchemyOutcomeRepository(SessionLocal),
            research_cycles=SQLAlchemyResearchCycleRepository(SessionLocal),
        )

    return AgentbookService(
        agents=InMemoryAgentRepository(),
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
        from backend.presentation.mcp.streamable_router import streamable_http_lifespan
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

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        origin = request.headers.get("origin")
        headers = {}
        if origin:
            headers["access-control-allow-origin"] = origin
            headers["access-control-allow-credentials"] = "true"
        return JSONResponse(status_code=500, content={"detail": "Internal server error"}, headers=headers)

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
