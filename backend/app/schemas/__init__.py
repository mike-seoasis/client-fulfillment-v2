"""Schemas layer - Pydantic models for API validation.

Schemas define the shape of data for API requests and responses.
They handle validation, serialization, and documentation.
"""

from app.schemas.categorize import (
    BatchPageRequest,
    CategorizeAllRequest,
    CategorizeAllResponse,
    CategorizeBatchRequest,
    CategorizedPageResponse,
    CategorizePageIdsRequest,
    CategorizePageIdsResponse,
    CategorizeRequest,
    CategorizeResponse,
    CategorizeStatsResponse,
    ContentAnalysisResponse,
    ContentSignalResponse,
    UpdateCategoryRequest,
    UpdateCategoryResponse,
)
from app.schemas.label import (
    BatchCollectionRequest,
    LabelAllRequest,
    LabelAllResponse,
    LabelBatchItemResponse,
    LabelBatchRequest,
    LabelBatchResponse,
    LabeledPageResponse,
    LabelGenerateRequest,
    LabelGenerateResponse,
    LabelPageIdsRequest,
    LabelPageIdsResponse,
    LabelStatsResponse,
)
from app.schemas.crawl import (
    VALID_CRAWL_STATUSES,
    VALID_TRIGGER_TYPES,
    CrawledPageListResponse,
    CrawledPageResponse,
    CrawlHistoryListResponse,
    CrawlHistoryResponse,
    CrawlProgressResponse,
    CrawlStartRequest,
    CrawlStopResponse,
)
from app.schemas.project import (
    VALID_PHASE_STATUSES,
    VALID_PHASES,
    VALID_PROJECT_STATUSES,
    PhaseStatusEntry,
    PhaseStatusUpdate,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)

__all__ = [
    # Project schemas
    "VALID_PROJECT_STATUSES",
    "VALID_PHASE_STATUSES",
    "VALID_PHASES",
    "PhaseStatusEntry",
    "ProjectCreate",
    "ProjectUpdate",
    "PhaseStatusUpdate",
    "ProjectResponse",
    "ProjectListResponse",
    # Crawl schemas
    "VALID_CRAWL_STATUSES",
    "VALID_TRIGGER_TYPES",
    "CrawlStartRequest",
    "CrawlHistoryResponse",
    "CrawlHistoryListResponse",
    "CrawledPageResponse",
    "CrawledPageListResponse",
    "CrawlProgressResponse",
    "CrawlStopResponse",
    # Categorize schemas
    "CategorizeRequest",
    "BatchPageRequest",
    "CategorizePageIdsRequest",
    "CategorizeAllRequest",
    "CategorizeBatchRequest",
    "ContentSignalResponse",
    "ContentAnalysisResponse",
    "CategorizeResponse",
    "CategorizedPageResponse",
    "CategorizePageIdsResponse",
    "CategorizeAllResponse",
    "CategorizeStatsResponse",
    "UpdateCategoryRequest",
    "UpdateCategoryResponse",
    # Label schemas
    "LabelGenerateRequest",
    "BatchCollectionRequest",
    "LabelBatchRequest",
    "LabelPageIdsRequest",
    "LabelAllRequest",
    "LabelGenerateResponse",
    "LabelBatchItemResponse",
    "LabelBatchResponse",
    "LabeledPageResponse",
    "LabelPageIdsResponse",
    "LabelAllResponse",
    "LabelStatsResponse",
]
