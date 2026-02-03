"""API v1 router - REST endpoints for v2 rebuild."""

from fastapi import APIRouter

from app.api.v1.projects import router as projects_router

router = APIRouter(prefix="/api/v1")

# Include domain routers
router.include_router(projects_router)
