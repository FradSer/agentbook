from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.application.errors import (
    AgentToolError,
    ErrorType,
    NotFoundError,
    RateLimitError,
    UnauthorizedError,
)
from backend.application.service import AgentbookService
from backend.core.config import settings, validate_production_settings
from backend.core.rate_limit import limiter
from backend.infrastructure.embeddings.fallback import FallbackEmbeddingProvider
from backend.infrastructure.embeddings.openrouter import resolve_embedding_provider
from backend.infrastructure.persistence.database import SessionLocal
from backend.infrastructure.persistence.in_memory import (
    InMemoryAgentRepository,
    InMemoryOutcomeRepository,
    InMemoryProblemRepository,
    InMemoryResearchCycleRepository,
    InMemorySolutionRepository,
)
from backend.infrastructure.persistence.sqlalchemy_repositories import (
    SQLAlchemyAgentRepository,
    SQLAlchemyOutcomeRepository,
    SQLAlchemyProblemRepository,
    SQLAlchemyResearchCycleRepository,
    SQLAlchemySolutionRepository,
)
from backend.presentation.api.router import api_router
from backend.presentation.mcp import setup_mcp_app, sse_router
from backend.presentation.mcp.auth import MCPAuthMiddleware
from backend.presentation.mcp.streamable_router import (
    handle_mcp_request,
    setup_streamable_mcp,
)

logger = logging.getLogger(__name__)


_AGENT_TOOL_ERROR_STATUS = {
    ErrorType.NOT_FOUND: 404,
    ErrorType.UNAUTHORIZED: 401,
    ErrorType.RATE_LIMITED: 429,
    ErrorType.SCHEMA_MISMATCH: 422,
    ErrorType.UPSTREAM_TIMEOUT: 504,
    ErrorType.INTERNAL: 500,
}


def _install_agent_tool_error_handler(app: FastAPI) -> None:
    @app.exception_handler(AgentToolError)
    async def _handler(request: Request, exc: AgentToolError) -> JSONResponse:
        return JSONResponse(
            status_code=_AGENT_TOOL_ERROR_STATUS[exc.error_type],
            content={
                "error": {
                    "type": exc.error_type.value,
                    "is_retryable": exc.is_retryable,
                    "message": exc.message,
                }
            },
        )


def _install_domain_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def _not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(RateLimitError)
    async def _rate_limited(request: Request, exc: RateLimitError) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": str(exc)})

    @app.exception_handler(UnauthorizedError)
    async def _unauthorized(request: Request, exc: UnauthorizedError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(exc)})


def _build_service() -> AgentbookService:
    import os

    if os.getenv("DEMO_MODE") == "1":
        from backend.demo import build_demo_repos

        agents, problems, solutions, outcomes, cycles = build_demo_repos()
        return AgentbookService(
            agents=agents,
            embedding_provider=FallbackEmbeddingProvider(),
            problems=problems,
            solutions=solutions,
            outcomes=outcomes,
            research_cycles=cycles,
        )

    embedding_provider = resolve_embedding_provider() or FallbackEmbeddingProvider()

    from backend.infrastructure.evaluation.llm_evaluator import (
        resolve_evaluator_provider,
    )

    evaluator = resolve_evaluator_provider() if settings.evaluator_enabled else None

    sandbox = None
    if settings.sandbox_enabled:
        from backend.infrastructure.sandbox import resolve_sandbox_provider

        sandbox = resolve_sandbox_provider()

    from backend.infrastructure.persistence.in_memory import (
        InMemoryProblemRelationshipRepository,
    )

    relationships = (
        InMemoryProblemRelationshipRepository()
        if settings.knowledge_graph_enabled
        else None
    )

    if settings.database_url:
        return AgentbookService(
            agents=SQLAlchemyAgentRepository(SessionLocal),
            embedding_provider=embedding_provider,
            evaluator=evaluator,
            sandbox=sandbox,
            problems=SQLAlchemyProblemRepository(SessionLocal),
            solutions=SQLAlchemySolutionRepository(SessionLocal),
            outcomes=SQLAlchemyOutcomeRepository(SessionLocal),
            research_cycles=SQLAlchemyResearchCycleRepository(SessionLocal),
            problem_relationships=relationships,
        )

    return AgentbookService(
        agents=InMemoryAgentRepository(),
        embedding_provider=embedding_provider,
        evaluator=evaluator,
        sandbox=sandbox,
        problems=InMemoryProblemRepository(),
        solutions=InMemorySolutionRepository(),
        outcomes=InMemoryOutcomeRepository(),
        research_cycles=InMemoryResearchCycleRepository(),
        problem_relationships=relationships,
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
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
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
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(MCPAuthMiddleware)
    app.state.service = _build_service()
    _install_agent_tool_error_handler(app)
    _install_domain_error_handlers(app)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(
            "Unhandled exception on %s %s", request.method, request.url.path
        )
        origin = request.headers.get("origin")
        headers = {}
        if origin:
            headers["access-control-allow-origin"] = origin
            headers["access-control-allow-credentials"] = "true"
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
            headers=headers,
        )

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
