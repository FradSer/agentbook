from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

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


def _api_error(
    *,
    code: str,
    message: str,
    retryable: bool,
    action: str,
    details: object | None = None,
) -> dict:
    payload = {
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
            "action": action,
        }
    }
    if details is not None:
        payload["error"]["details"] = details
    return payload


# Default retry window when the throttler can't supply a precise hint.
# 60s mirrors the smallest configured window (per-minute search).
_DEFAULT_RETRY_AFTER_SECONDS = 60


def _retry_after_from_slowapi(exc: RateLimitExceeded) -> int:
    """Read the bucket reset window straight off the slowapi exception.

    ``exc.limit`` is the slowapi ``LimitWrapper``; its ``.limit`` is the
    underlying ``limits.RateLimitItem``, whose ``get_expiry()`` is the
    canonical seconds-per-window. Falls back to the default when an
    exotic slowapi internal layout removes that path.
    """
    try:
        return max(1, int(exc.limit.limit.get_expiry()))
    except (AttributeError, TypeError, ValueError):
        return _DEFAULT_RETRY_AFTER_SECONDS


def _rate_limited_response(*, message: str, retry_after: int) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content=_api_error(
            code="rate_limited",
            message=message,
            retryable=True,
            action="retry_after_delay",
            details={"retry_after_seconds": retry_after},
        ),
        headers={"Retry-After": str(retry_after)},
    )


def _http_error_code(status_code: int) -> tuple[str, bool, str]:
    if status_code == 401:
        return "unauthorized", False, "provide_valid_api_key"
    if status_code == 404:
        return "not_found", False, "check_resource_id"
    if status_code == 429:
        return "rate_limited", True, "retry_after_delay"
    if status_code == 422:
        return "invalid_input", False, "fix_request"
    if 400 <= status_code < 500:
        return "invalid_request", False, "fix_request"
    return "internal_error", True, "retry_or_contact_operator"


def _install_domain_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def _not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=_api_error(
                code="not_found",
                message=str(exc),
                retryable=False,
                action="check_resource_id",
            ),
        )

    @app.exception_handler(RateLimitError)
    async def _rate_limited(request: Request, exc: RateLimitError) -> JSONResponse:
        return _rate_limited_response(
            message=str(exc),
            retry_after=exc.retry_after_seconds or _DEFAULT_RETRY_AFTER_SECONDS,
        )

    @app.exception_handler(UnauthorizedError)
    async def _unauthorized(request: Request, exc: UnauthorizedError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content=_api_error(
                code="unauthorized",
                message=str(exc),
                retryable=False,
                action="provide_valid_api_key",
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        # Registered against the Starlette base class, not fastapi.HTTPException:
        # routing-layer errors (405 Method Not Allowed, unmatched-route 404) are
        # raised as the base type, so a handler bound to the FastAPI subclass
        # misses them and they leak the raw {"detail": ...} shape.
        code, retryable, action = _http_error_code(exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content=_api_error(
                code=code,
                message=str(exc.detail),
                retryable=retryable,
                action=action,
            ),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_api_error(
                code="invalid_input",
                message="Request validation failed",
                retryable=False,
                action="fix_request",
                # jsonable_encoder decodes the raw request body (bytes) that
                # Pydantic embeds in errors() — a plain json.dumps would crash
                # the handler itself, surfacing a bare 500 to the caller.
                details=jsonable_encoder(exc.errors()),
            ),
        )

    @app.exception_handler(RateLimitExceeded)
    async def _slowapi_rate_limited(
        request: Request, exc: RateLimitExceeded
    ) -> JSONResponse:
        return _rate_limited_response(
            message=str(exc.detail),
            retry_after=_retry_after_from_slowapi(exc),
        )


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

    # Resolver chain (highest precedence first):
    #   Voyage v3-large (asymmetric, code-tuned) -> OpenRouter
    #   text-embedding-3-small (legacy) -> deterministic Fallback (CI/local).
    # Local imports keep these out of the module top-level so ruff's
    # unused-import sweep doesn't strip them between edits.
    from backend.infrastructure.embeddings.openrouter import (
        resolve_embedding_provider as resolve_openrouter_embedding,
    )
    from backend.infrastructure.embeddings.voyage import (
        resolve_embedding_provider as resolve_voyage_embedding,
    )
    from backend.infrastructure.reranking import resolve_rerank_fn

    embedding_provider = (
        resolve_voyage_embedding()
        or resolve_openrouter_embedding()
        or FallbackEmbeddingProvider()
    )
    rerank_fn = resolve_rerank_fn()
    if not settings.voyage_api_key and settings.database_url:
        # Loud signal in production-shaped env: operator probably forgot to
        # set the key. Don't error — local dev / CI still need to work.
        logger.warning(
            "VOYAGE_API_KEY unset in production-shaped env; reranker is NoOp."
        )

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
            rerank_fn=rerank_fn,
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
        rerank_fn=rerank_fn,
    )


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from backend.presentation.mcp.streamable_router import streamable_http_lifespan

    # Pre-warm the embedding provider so the first real request doesn't pay
    # the ~500ms TLS handshake / credential cache populate cost. Failures
    # are logged but never block startup — the search path falls back to
    # the keyword retriever when embeddings are unavailable.
    service = getattr(app.state, "service", None)
    if service is not None and service._embedding_provider is not None:
        try:
            service._embedding_provider.embed("warmup", input_type="document")
        except Exception as e:  # noqa: BLE001
            logger.warning("embedding-prewarm-failed error=%s", e)

    async with streamable_http_lifespan():
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

    @app.middleware("http")
    async def normalize_mcp_mount_path(request: Request, call_next):
        if request.scope.get("path") == "/mcp":
            request.scope["path"] = "/mcp/"
        return await call_next(request)

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
        # Echo Origin only when it's already on the allowlist — otherwise
        # an attacker page reads 500 bodies cross-origin via this handler
        # bypassing the CORSMiddleware allowlist entirely. The body is
        # bounded ("Internal server error") but the policy escape is real.
        origin = request.headers.get("origin")
        headers = {}
        if origin and (origin in origins or "*" in origins):
            headers["access-control-allow-origin"] = origin
            headers["access-control-allow-credentials"] = "true"
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
            headers=headers,
        )

    app.include_router(api_router)

    setup_streamable_mcp(app.state.service)
    app.mount("/mcp", handle_mcp_request)

    return app


app = create_app()
