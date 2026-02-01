"""API v1 router and endpoint organization."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    amazon_reviews,
    brand_config,
    categorize,
    content_plan,
    content_quality,
    content_word_count,
    content_writer,
    crawl,
    documents,
    keyword_research,
    label,
    link_validator,
    llm_qa_fix,
    notifications,
    paa_enrichment,
    projects,
    review_platforms,
    schedule,
    websocket,
)

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
router.include_router(
    keyword_research.router,
    prefix="/projects/{project_id}/phases/keyword_research",
    tags=["Keyword Research Phase"],
)
router.include_router(
    amazon_reviews.router,
    prefix="/projects/{project_id}/phases/amazon_reviews",
    tags=["Amazon Reviews Phase"],
)
router.include_router(
    paa_enrichment.router,
    prefix="/projects/{project_id}/phases/paa_enrichment",
    tags=["PAA Enrichment Phase"],
)
router.include_router(
    content_plan.router,
    prefix="/projects/{project_id}/phases/content_plan",
    tags=["Content Plan Phase"],
)
router.include_router(
    content_writer.router,
    prefix="/projects/{project_id}/phases/content_writer",
    tags=["Content Writer Phase"],
)
router.include_router(
    content_quality.router,
    prefix="/projects/{project_id}/phases/content_quality",
    tags=["Content Quality Phase"],
)
router.include_router(
    content_word_count.router,
    prefix="/projects/{project_id}/phases/word_count",
    tags=["Word Count Phase"],
)
router.include_router(
    link_validator.router,
    prefix="/projects/{project_id}/phases/link_validator",
    tags=["Link Validator Phase"],
)
router.include_router(
    llm_qa_fix.router,
    prefix="/projects/{project_id}/phases/llm_qa_fix",
    tags=["LLM QA Fix Phase"],
)
router.include_router(
    review_platforms.router,
    prefix="/projects/{project_id}/phases/review_platforms",
    tags=["Review Platforms Phase"],
)
router.include_router(
    schedule.router,
    prefix="/projects/{project_id}/phases/schedule",
    tags=["Schedule Configuration"],
)
router.include_router(websocket.router, tags=["WebSocket"])
router.include_router(
    brand_config.router,
    prefix="/projects/{project_id}/phases/brand_config",
    tags=["Brand Config Phase"],
)
router.include_router(
    notifications.router,
    prefix="/notifications",
    tags=["Notifications"],
)
router.include_router(
    documents.router,
    prefix="/projects/{project_id}/documents",
    tags=["Documents"],
)
