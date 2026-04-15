from __future__ import annotations

from fastapi import APIRouter

from backend.presentation.api.routes.auth import router as auth_router
from backend.presentation.api.routes.dashboard import router as dashboard_router
from backend.presentation.api.routes.problems import router as problems_router
from backend.presentation.api.routes.problems import solutions_router
from backend.presentation.api.routes.search import router as search_router
from backend.presentation.api.routes.tools import router as tools_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(search_router)
api_router.include_router(dashboard_router)
api_router.include_router(problems_router)
api_router.include_router(solutions_router)
api_router.include_router(tools_router)
