"""Service layer for business logic."""

from app.services.brand_config import (
    BrandConfigService,
    GenerationStatus,
    ResearchContext,
)
from app.services.content_extraction import (
    ExtractedContent,
    extract_content_from_html,
    truncate_body_content,
)
from app.services.content_generation import (
    PipelinePageResult,
    PipelineResult,
    run_content_pipeline,
)
from app.services.content_quality import (
    QualityIssue,
    QualityResult,
    run_quality_checks,
)
from app.services.content_writing import (
    ContentWritingResult,
    PromptPair,
    build_content_prompt,
    generate_content,
)
from app.services.crawling import CrawlingService
from app.services.file import FileService
from app.services.label_taxonomy import (
    MAX_LABELS_PER_PAGE,
    MIN_LABELS_PER_PAGE,
    GeneratedTaxonomy,
    LabelAssignment,
    LabelTaxonomyService,
    LabelValidationError,
    LabelValidationResult,
    TaxonomyLabel,
    get_project_taxonomy_labels,
    validate_labels,
    validate_page_labels,
)
from app.services.link_injection import (
    BUDGET_MAX,
    BUDGET_MIN,
    LLM_FALLBACK_MODEL,
    MAX_ANCHOR_REUSE_VALIDATION,
    MAX_LINKS_PER_PARAGRAPH,
    MIN_WORDS_BETWEEN_LINKS,
    LinkInjector,
    LinkValidator,
    strip_internal_links,
)
from app.services.link_planning import (
    ANCHOR_LLM_MODEL,
    LABEL_OVERLAP_THRESHOLD,
    MAX_ANCHOR_REUSE,
    AnchorTextSelector,
    SiloLinkPlanner,
    calculate_budget,
    select_targets_cluster,
    select_targets_onboarding,
)
from app.services.pop_content_brief import (
    ContentBriefResult,
    fetch_content_brief,
)
from app.services.primary_keyword import (
    KeywordGenerationStats,
    PrimaryKeywordService,
)
from app.services.project import ProjectService

__all__ = [
    "ANCHOR_LLM_MODEL",
    "AnchorTextSelector",
    "BUDGET_MAX",
    "BUDGET_MIN",
    "BrandConfigService",
    "ContentBriefResult",
    "ContentWritingResult",
    "CrawlingService",
    "MAX_ANCHOR_REUSE",
    "MAX_ANCHOR_REUSE_VALIDATION",
    "MAX_LINKS_PER_PARAGRAPH",
    "MIN_WORDS_BETWEEN_LINKS",
    "QualityIssue",
    "QualityResult",
    "build_content_prompt",
    "ExtractedContent",
    "extract_content_from_html",
    "fetch_content_brief",
    "FileService",
    "generate_content",
    "GeneratedTaxonomy",
    "GenerationStatus",
    "get_project_taxonomy_labels",
    "KeywordGenerationStats",
    "LABEL_OVERLAP_THRESHOLD",
    "LLM_FALLBACK_MODEL",
    "LinkInjector",
    "LinkValidator",
    "LabelAssignment",
    "LabelTaxonomyService",
    "LabelValidationError",
    "LabelValidationResult",
    "MAX_LABELS_PER_PAGE",
    "MIN_LABELS_PER_PAGE",
    "PipelinePageResult",
    "PipelineResult",
    "PrimaryKeywordService",
    "ProjectService",
    "PromptPair",
    "ResearchContext",
    "run_content_pipeline",
    "run_quality_checks",
    "SiloLinkPlanner",
    "strip_internal_links",
    "calculate_budget",
    "select_targets_cluster",
    "select_targets_onboarding",
    "TaxonomyLabel",
    "truncate_body_content",
    "validate_labels",
    "validate_page_labels",
]
