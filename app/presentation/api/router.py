from __future__ import annotations

from fastapi import APIRouter

from app.presentation.api.routes.agent import router as agent_router
from app.presentation.api.routes.auth import router as auth_router
from app.presentation.api.routes.search import router as search_router
from app.presentation.api.routes.threads import router as threads_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(threads_router)
api_router.include_router(search_router)
api_router.include_router(agent_router)
