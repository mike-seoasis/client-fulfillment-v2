"""API v1 router and endpoint organization."""

from fastapi import APIRouter

from app.api.v1.endpoints import categorize, crawl, label, projects, websocket

router = APIRouter(tags=["v1"])

# Include domain-specific routers
router.include_router(projects.router, prefix="/projects", tags=["Projects"])
router.include_router(
    crawl.router,
    prefix="/projects/{project_id}/phases/crawl",
    tags=["Crawl Phase"],
)
router.include_router(
    categorize.router,
    prefix="/projects/{project_id}/phases/categorize",
    tags=["Categorize Phase"],
)
router.include_router(
    label.router,
    prefix="/projects/{project_id}/phases/label",
    tags=["Label Phase"],
)
router.include_router(websocket.router, tags=["WebSocket"])
