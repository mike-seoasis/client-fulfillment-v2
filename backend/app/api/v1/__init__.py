"""API v1 router - REST endpoints for v2 rebuild."""

from fastapi import APIRouter

from app.api.v1.brand_config import router as brand_config_router
from app.api.v1.clusters import router as clusters_router
from app.api.v1.content_generation import router as content_generation_router
from app.api.v1.files import router as files_router
from app.api.v1.links import router as links_router
from app.api.v1.projects import router as projects_router
from app.api.v1.wordpress import router as wordpress_router

router = APIRouter(prefix="/api/v1")

# Include domain routers
router.include_router(projects_router)
router.include_router(files_router)
router.include_router(brand_config_router)
router.include_router(content_generation_router)
router.include_router(clusters_router)
router.include_router(links_router)
router.include_router(wordpress_router)
