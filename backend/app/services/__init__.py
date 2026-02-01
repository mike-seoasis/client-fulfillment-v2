"""Services layer - Business logic and orchestration.

Services coordinate between repositories, integrations, and other services
to implement business use cases. They contain no direct database or
external API access - that's delegated to repositories and integrations.
"""

from app.services.category import (
    CategorizationRequest,
    CategorizationResult,
    CategoryNotFoundError,
    CategoryService,
    CategoryServiceError,
    CategoryValidationError,
    categorize_page,
    get_category_service,
)
from app.services.crawl import (
    CrawlConfig,
    CrawlNotFoundError,
    CrawlPatternError,
    CrawlProgress,
    CrawlService,
    CrawlServiceError,
    CrawlValidationError,
    PatternMatcher,
)
from app.services.label import (
    BatchLabelResult,
    LabelGenerationError,
    LabelRequest,
    LabelResult,
    LabelService,
    LabelServiceError,
    LabelValidationError,
    generate_collection_labels,
    generate_labels_batch,
    get_label_service,
)
from app.services.project import (
    InvalidPhaseTransitionError,
    ProjectNotFoundError,
    ProjectService,
    ProjectServiceError,
    ProjectValidationError,
)
from app.services.related_collections import (
    Collection,
    CollectionNotFoundError,
    CollectionValidationError,
    RelatedCollectionMatch,
    RelatedCollectionsError,
    RelatedCollectionsResult,
    RelatedCollectionsService,
    find_related_collections,
    get_related_collections_service,
)

__all__ = [
    # Project service
    "ProjectService",
    "ProjectServiceError",
    "ProjectNotFoundError",
    "ProjectValidationError",
    "InvalidPhaseTransitionError",
    # Crawl service
    "CrawlService",
    "CrawlServiceError",
    "CrawlNotFoundError",
    "CrawlValidationError",
    "CrawlPatternError",
    "CrawlConfig",
    "CrawlProgress",
    "PatternMatcher",
    # Category service
    "CategoryService",
    "CategoryServiceError",
    "CategoryNotFoundError",
    "CategoryValidationError",
    "CategorizationRequest",
    "CategorizationResult",
    "categorize_page",
    "get_category_service",
    # Label service
    "LabelService",
    "LabelServiceError",
    "LabelGenerationError",
    "LabelValidationError",
    "LabelRequest",
    "LabelResult",
    "BatchLabelResult",
    "generate_collection_labels",
    "generate_labels_batch",
    "get_label_service",
    # Related collections service
    "RelatedCollectionsService",
    "RelatedCollectionsError",
    "CollectionNotFoundError",
    "CollectionValidationError",
    "Collection",
    "RelatedCollectionMatch",
    "RelatedCollectionsResult",
    "find_related_collections",
    "get_related_collections_service",
]
