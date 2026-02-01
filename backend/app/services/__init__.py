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
from app.services.keyword_cache import (
    CachedKeywordData,
    CacheStats,
    KeywordCacheResult,
    KeywordCacheService,
    KeywordCacheServiceError,
    KeywordCacheValidationError,
    cache_keyword_data,
    get_cached_keyword,
    get_keyword_cache_service,
)
from app.services.keyword_ideas import (
    KeywordIdeaGenerationError,
    KeywordIdeaRequest,
    KeywordIdeaResult,
    KeywordIdeaService,
    KeywordIdeaServiceError,
    KeywordIdeaValidationError,
    generate_keyword_ideas,
    get_keyword_idea_service,
)
from app.services.keyword_specificity import (
    KeywordSpecificityFilterError,
    KeywordSpecificityService,
    KeywordSpecificityServiceError,
    KeywordSpecificityValidationError,
    SpecificityFilterRequest,
    SpecificityFilterResult,
    filter_keywords_by_specificity,
    get_keyword_specificity_service,
)
from app.services.keyword_volume import (
    KeywordVolumeData,
    KeywordVolumeLookupError,
    KeywordVolumeResult,
    KeywordVolumeService,
    KeywordVolumeServiceError,
    KeywordVolumeValidationError,
    VolumeStats,
    get_keyword_volume_service,
    lookup_keyword_volumes,
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
    # Keyword cache service
    "KeywordCacheService",
    "KeywordCacheServiceError",
    "KeywordCacheValidationError",
    "KeywordCacheResult",
    "CachedKeywordData",
    "CacheStats",
    "cache_keyword_data",
    "get_cached_keyword",
    "get_keyword_cache_service",
    # Keyword idea service
    "KeywordIdeaService",
    "KeywordIdeaServiceError",
    "KeywordIdeaGenerationError",
    "KeywordIdeaValidationError",
    "KeywordIdeaRequest",
    "KeywordIdeaResult",
    "generate_keyword_ideas",
    "get_keyword_idea_service",
    # Keyword volume service
    "KeywordVolumeService",
    "KeywordVolumeServiceError",
    "KeywordVolumeLookupError",
    "KeywordVolumeValidationError",
    "KeywordVolumeData",
    "KeywordVolumeResult",
    "VolumeStats",
    "lookup_keyword_volumes",
    "get_keyword_volume_service",
    # Keyword specificity service
    "KeywordSpecificityService",
    "KeywordSpecificityServiceError",
    "KeywordSpecificityFilterError",
    "KeywordSpecificityValidationError",
    "SpecificityFilterRequest",
    "SpecificityFilterResult",
    "filter_keywords_by_specificity",
    "get_keyword_specificity_service",
]
