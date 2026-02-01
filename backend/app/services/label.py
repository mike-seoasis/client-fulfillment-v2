"""LabelService for generating 2-5 thematic labels per collection.

Provides intelligent label generation for collections of crawled pages
using a combination of:
1. Pattern-based labeling from page categories and content signals
2. LLM-based labeling via Claude for more nuanced thematic extraction

Labels help with:
- Navigation and filtering in the UI
- Content organization and grouping
- SEO and content strategy insights

Features:
- Parallel processing support with configurable concurrency (max 5 by default)
- Two-tier labeling: fast pattern-based with optional LLM fallback

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import asyncio
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient, get_claude

logger = get_logger(__name__)

# Threshold for logging slow operations (in milliseconds)
SLOW_OPERATION_THRESHOLD_MS = 1000

# Label constraints
MIN_LABELS = 2
MAX_LABELS = 5
MAX_LABEL_LENGTH = 50
MIN_LABEL_LENGTH = 2

# Parallel processing constraints
DEFAULT_MAX_CONCURRENT = 5
MAX_CONCURRENT_LIMIT = 10  # Absolute maximum to prevent resource exhaustion

# =============================================================================
# LLM PROMPT TEMPLATES FOR LABEL GENERATION
# =============================================================================
#
# These prompts are used when pattern-based labeling produces low-confidence
# results and LLM fallback is triggered. The prompts are designed to:
# 1. Generate 2-5 thematic, kebab-case labels
# 2. Provide confidence scores for quality assessment
# 3. Include reasoning for debugging and transparency
# 4. Handle diverse content types (e-commerce, blog, corporate, etc.)
#
# Usage:
#   system_prompt = LABEL_GENERATION_SYSTEM_PROMPT
#   user_prompt = LABEL_GENERATION_USER_PROMPT_TEMPLATE.format(
#       page_count=len(urls),
#       category_summary=category_summary,
#       sample_urls=formatted_urls,
#       sample_titles=formatted_titles,
#       sample_content=formatted_content,
#   )

LABEL_GENERATION_SYSTEM_PROMPT = """You are a content labeling expert specializing in web page analysis and content taxonomy. Your task is to generate 2-5 thematic labels for a collection of web pages that share common characteristics.

## Label Requirements

Labels should be:
1. **Descriptive**: Capture the thematic essence of the content (e.g., "e-commerce", "educational", "seasonal-promotions")
2. **Format**: Use kebab-case (lowercase with hyphens, e.g., "product-focused", "lead-generation")
3. **Length**: Between 2-50 characters each
4. **Unique**: No duplicate or redundant labels
5. **Relevant**: Directly applicable to the page collection

## Valid Label Categories

Consider labels from these dimensions:
- **Content Type**: e-commerce, blog-content, educational, informational, transactional
- **User Intent**: lead-generation, customer-support, brand-awareness, conversion-focused
- **Temporal**: seasonal, evergreen, trending, time-sensitive
- **Audience**: consumer, enterprise, developer, beginner-friendly
- **Industry**: retail, technology, healthcare, finance, travel
- **Page Function**: catalog, landing-page, support, checkout, account-management

## Response Format

Return ONLY a JSON object with this exact structure (no markdown, no explanation):
{
    "labels": ["label-1", "label-2", "label-3"],
    "confidence": 0.85,
    "reasoning": "Brief explanation of why these labels were chosen (1-2 sentences)"
}

## Guidelines

- Generate between 2-5 labels (minimum 2, maximum 5)
- Confidence score: 0.0 = uncertain, 1.0 = highly certain
- If pages are diverse with no clear theme, use broader labels with lower confidence
- Prioritize specificity over generality when content allows
- Avoid overly generic labels like "web" or "content" unless truly applicable"""

LABEL_GENERATION_USER_PROMPT_TEMPLATE = """Analyze this collection of {page_count} web pages and generate 2-5 thematic labels.

## Page Collection Summary

**Category Breakdown**: {category_summary}

**Sample URLs**:
{sample_urls}

**Sample Page Titles**:
{sample_titles}
{sample_content}
## Instructions

1. Identify common themes across the pages
2. Generate 2-5 descriptive labels in kebab-case format
3. Assign a confidence score based on how well the labels capture the collection's essence
4. Provide brief reasoning for your label choices

Respond with JSON only."""

# Default themes for pattern-based labeling
DEFAULT_THEMES = frozenset({
    "primary-nav",
    "secondary-nav",
    "footer",
    "high-traffic",
    "low-traffic",
    "needs-review",
    "optimized",
    "conversion-focused",
    "informational",
    "transactional",
    "educational",
    "promotional",
    "seasonal",
    "evergreen",
})


class LabelServiceError(Exception):
    """Base exception for LabelService errors."""

    pass


class LabelValidationError(LabelServiceError):
    """Raised when label validation fails."""

    def __init__(self, field: str, value: Any, message: str):
        self.field = field
        self.value = value
        self.message = message
        super().__init__(f"Validation failed for '{field}': {message}")


class LabelGenerationError(LabelServiceError):
    """Raised when label generation fails."""

    def __init__(self, message: str, project_id: str | None = None):
        self.project_id = project_id
        super().__init__(message)


@dataclass
class LabelRequest:
    """Request for label generation.

    Attributes:
        urls: List of URLs in the collection
        titles: List of page titles
        categories: List of page categories
        content_snippets: Optional list of content snippets (first 500 chars)
        project_id: Project ID for logging
    """

    urls: list[str]
    titles: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    content_snippets: list[str] = field(default_factory=list)
    project_id: str | None = None


@dataclass
class LabelResult:
    """Result of label generation.

    Attributes:
        success: Whether label generation succeeded
        labels: Generated labels (2-5 thematic labels)
        confidence: Confidence score (0.0 to 1.0)
        tier: Which tier was used ('pattern', 'llm', 'fallback')
        reasoning: LLM reasoning for label selection (if applicable)
        pattern_labels: Labels from pattern matching
        llm_labels: Labels from LLM (if used)
        error: Error message if failed
        duration_ms: Total time taken
        project_id: Project ID (for logging context)
    """

    success: bool
    labels: list[str] = field(default_factory=list)
    confidence: float = 0.0
    tier: str = "pattern"  # 'pattern', 'llm', 'fallback'
    reasoning: str | None = None
    pattern_labels: list[str] = field(default_factory=list)
    llm_labels: list[str] = field(default_factory=list)
    error: str | None = None
    duration_ms: float = 0.0
    project_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "success": self.success,
            "labels": self.labels,
            "confidence": self.confidence,
            "tier": self.tier,
            "reasoning": self.reasoning,
            "pattern_labels": self.pattern_labels,
            "llm_labels": self.llm_labels,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


@dataclass
class BatchLabelResult:
    """Result of batch label generation with parallel processing.

    Attributes:
        success: Whether all requests succeeded
        results: List of LabelResult for each request (same order as input)
        total_duration_ms: Total wall-clock time for the batch
        successful_count: Number of successful label generations
        failed_count: Number of failed label generations
        max_concurrent: Concurrency level used
    """

    success: bool
    results: list[LabelResult] = field(default_factory=list)
    total_duration_ms: float = 0.0
    successful_count: int = 0
    failed_count: int = 0
    max_concurrent: int = DEFAULT_MAX_CONCURRENT

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "success": self.success,
            "results": [r.to_dict() for r in self.results],
            "total_duration_ms": self.total_duration_ms,
            "successful_count": self.successful_count,
            "failed_count": self.failed_count,
            "max_concurrent": self.max_concurrent,
        }


class LabelService:
    """Service for generating thematic labels for page collections.

    Uses a two-tier approach:
    1. Pattern-based labeling from categories, URLs, and titles (fast, free)
    2. LLM-based labeling via Claude for nuanced thematic extraction (slower, costs tokens)

    The LLM is only used when pattern-based confidence is below threshold
    or when explicitly requested.

    Example usage:
        service = LabelService()

        # Generate labels for a collection of product pages
        result = await service.generate_labels(
            urls=["https://example.com/products/widget", ...],
            titles=["Widget Pro", "Widget Lite", ...],
            categories=["product", "product", ...],
            project_id="abc-123",
        )

        print(f"Labels: {result.labels}")  # ["e-commerce", "widgets", "electronics"]
        print(f"Confidence: {result.confidence}")  # 0.85
    """

    def __init__(
        self,
        claude_client: ClaudeClient | None = None,
        llm_fallback_threshold: float = 0.5,
        enable_llm_fallback: bool = True,
    ) -> None:
        """Initialize the label service.

        Args:
            claude_client: Claude client for LLM labeling (uses global if None)
            llm_fallback_threshold: Confidence threshold below which LLM is used
            enable_llm_fallback: Whether to enable LLM fallback at all
        """
        logger.debug(
            "LabelService.__init__ called",
            extra={
                "llm_fallback_threshold": llm_fallback_threshold,
                "enable_llm_fallback": enable_llm_fallback,
            },
        )

        self._claude_client = claude_client
        self._llm_fallback_threshold = llm_fallback_threshold
        self._enable_llm_fallback = enable_llm_fallback

        # Category to label mappings for pattern-based labeling
        self._category_labels: dict[str, list[str]] = {
            "homepage": ["main-landing", "brand-identity"],
            "product": ["e-commerce", "transactional", "product-focused"],
            "collection": ["catalog", "browse", "category-page"],
            "blog": ["content-marketing", "educational", "blog-content"],
            "policy": ["legal", "compliance", "informational"],
            "about": ["brand-story", "company-info", "about-us"],
            "contact": ["lead-generation", "customer-support", "contact-info"],
            "faq": ["support", "self-service", "faq-content"],
            "account": ["user-account", "authenticated", "member-area"],
            "cart": ["checkout", "conversion", "shopping-cart"],
            "search": ["site-search", "navigation", "discovery"],
        }

        # URL pattern to label mappings
        self._url_patterns: list[tuple[str, str]] = [
            (r"/sale|/clearance|/discount", "promotional"),
            (r"/new|/latest|/fresh", "new-arrivals"),
            (r"/best-seller|/popular|/top", "best-sellers"),
            (r"/seasonal|/holiday|/christmas|/summer", "seasonal"),
            (r"/guide|/how-to|/tutorial", "educational"),
            (r"/review|/testimonial", "social-proof"),
            (r"/pricing|/plans|/subscribe", "pricing"),
            (r"/demo|/trial|/free", "lead-generation"),
            (r"/partner|/affiliate", "partnership"),
            (r"/career|/jobs|/hiring", "careers"),
        ]

        logger.debug(
            "LabelService initialized",
            extra={
                "category_count": len(self._category_labels),
                "url_pattern_count": len(self._url_patterns),
                "llm_fallback_threshold": llm_fallback_threshold,
                "enable_llm_fallback": enable_llm_fallback,
            },
        )

    @property
    def llm_fallback_threshold(self) -> float:
        """Get the LLM fallback threshold."""
        return self._llm_fallback_threshold

    @property
    def valid_themes(self) -> frozenset[str]:
        """Get predefined valid theme names."""
        return DEFAULT_THEMES

    async def _get_claude_client(self) -> ClaudeClient | None:
        """Get Claude client for LLM fallback."""
        if self._claude_client is not None:
            return self._claude_client
        try:
            return await get_claude()
        except Exception as e:
            logger.warning(
                "Failed to get Claude client",
                extra={"error": str(e)},
            )
            return None

    def _validate_label(self, label: str) -> str:
        """Validate and normalize a single label.

        Args:
            label: Label to validate

        Returns:
            Normalized label (lowercase, trimmed)

        Raises:
            LabelValidationError: If label is invalid
        """
        if not label or not label.strip():
            logger.warning(
                "Validation failed: empty label",
                extra={"field": "label", "rejected_value": repr(label)},
            )
            raise LabelValidationError("label", label, "Label cannot be empty")

        normalized = label.strip().lower()

        if len(normalized) < MIN_LABEL_LENGTH:
            logger.warning(
                "Validation failed: label too short",
                extra={
                    "field": "label",
                    "rejected_value": normalized,
                    "min_length": MIN_LABEL_LENGTH,
                },
            )
            raise LabelValidationError(
                "label",
                normalized,
                f"Label must be at least {MIN_LABEL_LENGTH} characters",
            )

        if len(normalized) > MAX_LABEL_LENGTH:
            logger.warning(
                "Validation failed: label too long",
                extra={
                    "field": "label",
                    "rejected_value": normalized[:50] + "...",
                    "max_length": MAX_LABEL_LENGTH,
                },
            )
            raise LabelValidationError(
                "label",
                normalized,
                f"Label must be at most {MAX_LABEL_LENGTH} characters",
            )

        # Normalize: replace spaces/underscores with hyphens, remove special chars
        normalized = re.sub(r"[\s_]+", "-", normalized)
        normalized = re.sub(r"[^a-z0-9-]", "", normalized)
        normalized = re.sub(r"-+", "-", normalized)  # Collapse multiple hyphens
        normalized = normalized.strip("-")

        if not normalized:
            logger.warning(
                "Validation failed: label empty after normalization",
                extra={"field": "label", "rejected_value": label},
            )
            raise LabelValidationError(
                "label", label, "Label contains only invalid characters"
            )

        return normalized

    def _validate_labels(self, labels: list[str]) -> list[str]:
        """Validate and normalize a list of labels.

        Args:
            labels: Labels to validate

        Returns:
            List of normalized, unique labels (2-5 labels)
        """
        validated: list[str] = []
        seen: set[str] = set()

        for label in labels:
            try:
                normalized = self._validate_label(label)
                if normalized not in seen:
                    validated.append(normalized)
                    seen.add(normalized)
            except LabelValidationError:
                # Skip invalid labels, log already happened
                continue

        # Ensure we have 2-5 labels
        if len(validated) < MIN_LABELS:
            logger.debug(
                "Not enough valid labels",
                extra={
                    "valid_count": len(validated),
                    "min_required": MIN_LABELS,
                },
            )

        return validated[:MAX_LABELS]

    def _extract_pattern_labels(
        self,
        urls: list[str],
        titles: list[str],
        categories: list[str],
        project_id: str | None = None,
    ) -> tuple[list[str], float]:
        """Extract labels using pattern matching.

        Args:
            urls: List of URLs
            titles: List of page titles
            categories: List of page categories
            project_id: Project ID for logging

        Returns:
            Tuple of (labels, confidence)
        """
        start_time = time.monotonic()
        logger.debug(
            "_extract_pattern_labels() called",
            extra={
                "project_id": project_id,
                "url_count": len(urls),
                "title_count": len(titles),
                "category_count": len(categories),
            },
        )

        label_scores: Counter[str] = Counter()

        # 1. Extract labels from categories (highest weight)
        for category in categories:
            if category in self._category_labels:
                for label in self._category_labels[category]:
                    label_scores[label] += 3  # High weight for category match

        # 2. Extract labels from URL patterns
        for url in urls:
            url_lower = url.lower()
            for pattern, label in self._url_patterns:
                if re.search(pattern, url_lower):
                    label_scores[label] += 2  # Medium weight for URL pattern

        # 3. Extract labels from title keywords
        title_text = " ".join(titles).lower()
        keyword_patterns = [
            (r"\b(shop|buy|purchase|order)\b", "e-commerce"),
            (r"\b(learn|guide|how-to|tutorial)\b", "educational"),
            (r"\b(contact|reach|support|help)\b", "support"),
            (r"\b(sale|discount|offer|deal)\b", "promotional"),
            (r"\b(new|latest|just-in)\b", "new-arrivals"),
            (r"\b(blog|article|post|news)\b", "content"),
            (r"\b(service|solution|consulting)\b", "services"),
            (r"\b(pricing|plan|subscription)\b", "pricing"),
        ]
        for pattern, label in keyword_patterns:
            if re.search(pattern, title_text):
                label_scores[label] += 1  # Lower weight for title keywords

        # Get top labels
        if not label_scores:
            # Fallback labels based on dominant category
            category_counts = Counter(categories)
            if category_counts:
                dominant = category_counts.most_common(1)[0][0]
                fallback_labels = self._category_labels.get(
                    dominant, ["general-content"]
                )
                labels = fallback_labels[:MAX_LABELS]
                confidence = 0.3
            else:
                labels = ["general-content", "needs-review"]
                confidence = 0.2
        else:
            # Get top labels by score
            top_labels = label_scores.most_common(MAX_LABELS)
            labels = [label for label, _ in top_labels]

            # Calculate confidence based on score distribution
            total_score = sum(label_scores.values())
            top_score = sum(score for _, score in top_labels)
            confidence = min(0.8, 0.4 + (top_score / max(total_score, 1)) * 0.4)

        duration_ms = (time.monotonic() - start_time) * 1000
        logger.debug(
            "_extract_pattern_labels() completed",
            extra={
                "project_id": project_id,
                "labels": labels,
                "confidence": round(confidence, 3),
                "duration_ms": round(duration_ms, 2),
            },
        )

        if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
            logger.warning(
                "Slow pattern label extraction",
                extra={
                    "project_id": project_id,
                    "duration_ms": round(duration_ms, 2),
                },
            )

        return labels, confidence

    def _build_label_prompt(
        self,
        urls: list[str],
        titles: list[str],
        categories: list[str],
        content_snippets: list[str],
        project_id: str | None = None,
    ) -> tuple[str, str]:
        """Build the prompt for LLM label generation using templates.

        Args:
            urls: List of URLs
            titles: List of page titles
            categories: List of page categories
            content_snippets: List of content snippets
            project_id: Project ID for logging

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        logger.debug(
            "_build_label_prompt() called",
            extra={
                "project_id": project_id,
                "url_count": len(urls),
                "title_count": len(titles),
                "category_count": len(categories),
                "snippet_count": len(content_snippets),
            },
        )

        # Sample data for token efficiency
        sample_urls = urls[:10]
        sample_titles = [t for t in titles[:10] if t]  # Filter empty titles
        sample_content = [s for s in content_snippets[:5] if s]  # Filter empty snippets

        # Log validation if we had to truncate
        if len(urls) > 10:
            logger.debug(
                "Truncated URLs for prompt",
                extra={
                    "project_id": project_id,
                    "original_count": len(urls),
                    "sample_count": len(sample_urls),
                },
            )

        # Prepare category summary
        category_counts = Counter(categories)
        if category_counts:
            category_summary = ", ".join(
                f"{cat} ({count})" for cat, count in category_counts.most_common(5)
            )
        else:
            category_summary = "No categories available"
            logger.debug(
                "No categories provided for prompt",
                extra={"project_id": project_id},
            )

        # Format sample URLs
        formatted_urls = "\n".join(f"- {url}" for url in sample_urls)
        if not formatted_urls:
            formatted_urls = "- (no URLs provided)"
            logger.warning(
                "Validation failed: no URLs for label prompt",
                extra={
                    "project_id": project_id,
                    "field": "urls",
                    "rejected_value": "empty list",
                },
            )

        # Format sample titles
        formatted_titles = "\n".join(f"- {title}" for title in sample_titles)
        if not formatted_titles:
            formatted_titles = "- (no titles available)"

        # Format sample content (optional)
        if sample_content:
            truncated_snippets = [
                f"- {snippet[:200]}{'...' if len(snippet) > 200 else ''}"
                for snippet in sample_content
            ]
            formatted_content = (
                "\n**Sample Content Snippets**:\n" + "\n".join(truncated_snippets)
            )
        else:
            formatted_content = ""

        # Build user prompt from template
        user_prompt = LABEL_GENERATION_USER_PROMPT_TEMPLATE.format(
            page_count=len(urls),
            category_summary=category_summary,
            sample_urls=formatted_urls,
            sample_titles=formatted_titles,
            sample_content=formatted_content,
        )

        logger.debug(
            "_build_label_prompt() completed",
            extra={
                "project_id": project_id,
                "system_prompt_length": len(LABEL_GENERATION_SYSTEM_PROMPT),
                "user_prompt_length": len(user_prompt),
            },
        )

        return LABEL_GENERATION_SYSTEM_PROMPT, user_prompt

    async def _extract_llm_labels(
        self,
        urls: list[str],
        titles: list[str],
        categories: list[str],
        content_snippets: list[str],
        project_id: str | None = None,
    ) -> tuple[list[str], float, str | None]:
        """Extract labels using LLM (Claude).

        Uses the LABEL_GENERATION_SYSTEM_PROMPT and LABEL_GENERATION_USER_PROMPT_TEMPLATE
        constants to build prompts. Includes comprehensive error logging for:
        - Method entry/exit with parameters (sanitized)
        - All exceptions with full stack trace
        - Validation failures with field names and rejected values
        - State transitions at INFO level

        Args:
            urls: List of URLs
            titles: List of page titles
            categories: List of page categories
            content_snippets: List of content snippets
            project_id: Project ID for logging

        Returns:
            Tuple of (labels, confidence, reasoning)
        """
        start_time = time.monotonic()
        logger.debug(
            "_extract_llm_labels() called",
            extra={
                "project_id": project_id,
                "url_count": len(urls),
                "title_count": len(titles),
                "category_count": len(categories),
                "snippet_count": len(content_snippets),
            },
        )

        claude = await self._get_claude_client()
        if not claude or not claude.available:
            logger.warning(
                "Claude not available for LLM labeling",
                extra={
                    "project_id": project_id,
                    "reason": "client_unavailable",
                },
            )
            return [], 0.0, None

        # Build prompts using templates
        system_prompt, user_prompt = self._build_label_prompt(
            urls=urls,
            titles=titles,
            categories=categories,
            content_snippets=content_snippets,
            project_id=project_id,
        )

        logger.debug(
            "LLM prompt built from templates",
            extra={
                "project_id": project_id,
                "system_prompt_template": "LABEL_GENERATION_SYSTEM_PROMPT",
                "user_prompt_template": "LABEL_GENERATION_USER_PROMPT_TEMPLATE",
                "prompt_total_length": len(system_prompt) + len(user_prompt),
            },
        )

        try:
            result = await claude.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            if not result.success or not result.text:
                logger.warning(
                    "LLM label generation failed",
                    extra={
                        "project_id": project_id,
                        "error": result.error,
                        "status_code": result.status_code,
                        "request_id": result.request_id,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                return [], 0.0, None

            # Parse response
            import json

            response_text: str = result.text

            # Handle markdown code blocks (LLM may wrap JSON in code fences)
            original_response = response_text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
                logger.debug(
                    "Extracted JSON from markdown code block",
                    extra={"project_id": project_id, "fence_type": "json"},
                )
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
                logger.debug(
                    "Extracted JSON from generic code block",
                    extra={"project_id": project_id, "fence_type": "generic"},
                )

            response_text = response_text.strip()

            try:
                parsed = json.loads(response_text)

                # Validate required 'labels' field
                if "labels" not in parsed:
                    logger.warning(
                        "Validation failed: missing 'labels' field in LLM response",
                        extra={
                            "project_id": project_id,
                            "field": "labels",
                            "rejected_value": "field_missing",
                            "response_keys": list(parsed.keys()),
                        },
                    )
                    return [], 0.0, None

                raw_labels = parsed.get("labels", [])

                # Validate labels is a list
                if not isinstance(raw_labels, list):
                    logger.warning(
                        "Validation failed: 'labels' is not a list",
                        extra={
                            "project_id": project_id,
                            "field": "labels",
                            "rejected_value": type(raw_labels).__name__,
                            "expected_type": "list",
                        },
                    )
                    return [], 0.0, None

                # Validate confidence
                raw_confidence = parsed.get("confidence", 0.7)
                try:
                    confidence = float(raw_confidence)
                    if not 0.0 <= confidence <= 1.0:
                        logger.warning(
                            "Validation failed: confidence out of range",
                            extra={
                                "project_id": project_id,
                                "field": "confidence",
                                "rejected_value": confidence,
                                "valid_range": "0.0-1.0",
                            },
                        )
                        confidence = max(0.0, min(1.0, confidence))  # Clamp to valid range
                except (TypeError, ValueError) as e:
                    logger.warning(
                        "Validation failed: invalid confidence value",
                        extra={
                            "project_id": project_id,
                            "field": "confidence",
                            "rejected_value": str(raw_confidence),
                            "error": str(e),
                        },
                    )
                    confidence = 0.7  # Default confidence

                reasoning = parsed.get("reasoning")

                # Validate labels
                original_label_count = len(raw_labels)
                labels = self._validate_labels(raw_labels)

                if len(labels) < original_label_count:
                    logger.debug(
                        "Some labels filtered during validation",
                        extra={
                            "project_id": project_id,
                            "original_count": original_label_count,
                            "validated_count": len(labels),
                        },
                    )

                # Log state transition: LLM generation complete
                logger.info(
                    "LLM label generation complete",
                    extra={
                        "project_id": project_id,
                        "labels": labels,
                        "confidence": round(confidence, 3),
                        "reasoning_length": len(reasoning) if reasoning else 0,
                        "duration_ms": round(duration_ms, 2),
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                        "request_id": result.request_id,
                    },
                )

                if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                    logger.warning(
                        "Slow LLM label extraction",
                        extra={
                            "project_id": project_id,
                            "duration_ms": round(duration_ms, 2),
                            "input_tokens": result.input_tokens,
                            "output_tokens": result.output_tokens,
                        },
                    )

                return labels, confidence, reasoning

            except json.JSONDecodeError as e:
                logger.warning(
                    "Validation failed: LLM response is not valid JSON",
                    extra={
                        "project_id": project_id,
                        "field": "response",
                        "rejected_value": response_text[:200],
                        "error": str(e),
                        "error_position": e.pos if hasattr(e, "pos") else None,
                        "original_response_preview": original_response[:200],
                    },
                )
                return [], 0.0, None

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "LLM label generation exception",
                extra={
                    "project_id": project_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
                exc_info=True,
            )
            return [], 0.0, None

    async def generate_labels(
        self,
        urls: list[str],
        titles: list[str] | None = None,
        categories: list[str] | None = None,
        content_snippets: list[str] | None = None,
        project_id: str | None = None,
        force_llm: bool = False,
        skip_llm: bool = False,
    ) -> LabelResult:
        """Generate thematic labels for a collection of pages.

        Uses a two-tier approach:
        1. Pattern-based labeling from categories, URLs, and titles
        2. LLM fallback when confidence is below threshold

        Args:
            urls: List of page URLs in the collection
            titles: List of page titles (optional)
            categories: List of page categories (optional)
            content_snippets: List of content snippets for LLM (optional)
            project_id: Project ID for logging
            force_llm: Always use LLM regardless of pattern confidence
            skip_llm: Never use LLM even if confidence is low

        Returns:
            LabelResult with generated labels and metadata
        """
        start_time = time.monotonic()
        logger.debug(
            "generate_labels() called",
            extra={
                "project_id": project_id,
                "url_count": len(urls),
                "has_titles": titles is not None and len(titles) > 0,
                "has_categories": categories is not None and len(categories) > 0,
                "force_llm": force_llm,
                "skip_llm": skip_llm,
            },
        )

        # Validate inputs
        if not urls:
            logger.warning(
                "Validation failed: empty URL list",
                extra={"project_id": project_id, "field": "urls"},
            )
            return LabelResult(
                success=False,
                error="URL list cannot be empty",
                project_id=project_id,
            )

        titles = titles or []
        categories = categories or []
        content_snippets = content_snippets or []

        try:
            # --- TIER 1: Pattern-based labeling ---
            pattern_labels, pattern_confidence = self._extract_pattern_labels(
                urls=urls,
                titles=titles,
                categories=categories,
                project_id=project_id,
            )

            logger.debug(
                "Tier 1 (pattern) labeling complete",
                extra={
                    "project_id": project_id,
                    "pattern_labels": pattern_labels,
                    "pattern_confidence": round(pattern_confidence, 3),
                },
            )

            # Check if we should use LLM
            use_llm = False
            if force_llm:
                use_llm = True
                logger.debug(
                    "LLM forced by parameter",
                    extra={"project_id": project_id},
                )
            elif skip_llm:
                use_llm = False
            elif (
                self._enable_llm_fallback
                and pattern_confidence < self._llm_fallback_threshold
            ):
                use_llm = True
                logger.debug(
                    "LLM fallback triggered (low confidence)",
                    extra={
                        "project_id": project_id,
                        "pattern_confidence": pattern_confidence,
                        "threshold": self._llm_fallback_threshold,
                    },
                )

            # --- TIER 2: LLM fallback (if needed) ---
            llm_labels: list[str] = []
            llm_confidence = 0.0
            reasoning: str | None = None
            tier = "pattern"

            if use_llm:
                tier = "llm"
                llm_labels, llm_confidence, reasoning = await self._extract_llm_labels(
                    urls=urls,
                    titles=titles,
                    categories=categories,
                    content_snippets=content_snippets,
                    project_id=project_id,
                )

                if not llm_labels:
                    # LLM failed, fall back to pattern
                    tier = "fallback"
                    logger.info(
                        "LLM labeling failed, using pattern fallback",
                        extra={
                            "project_id": project_id,
                            "fallback_labels": pattern_labels,
                        },
                    )

            # Determine final labels
            if tier == "llm" and llm_labels:
                final_labels = llm_labels
                final_confidence = llm_confidence
            else:
                final_labels = pattern_labels
                final_confidence = pattern_confidence

            # Ensure we have at least MIN_LABELS
            if len(final_labels) < MIN_LABELS:
                # Add generic labels
                generic = ["general-content", "needs-review", "uncategorized"]
                for label in generic:
                    if label not in final_labels:
                        final_labels.append(label)
                    if len(final_labels) >= MIN_LABELS:
                        break
                final_confidence = min(final_confidence, 0.4)

            total_duration_ms = (time.monotonic() - start_time) * 1000

            logger.debug(
                "generate_labels() completed",
                extra={
                    "project_id": project_id,
                    "labels": final_labels,
                    "confidence": round(final_confidence, 3),
                    "tier": tier,
                    "duration_ms": round(total_duration_ms, 2),
                },
            )

            if total_duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow label generation",
                    extra={
                        "project_id": project_id,
                        "duration_ms": round(total_duration_ms, 2),
                        "tier": tier,
                    },
                )

            return LabelResult(
                success=True,
                labels=final_labels,
                confidence=final_confidence,
                tier=tier,
                reasoning=reasoning,
                pattern_labels=pattern_labels,
                llm_labels=llm_labels,
                duration_ms=round(total_duration_ms, 2),
                project_id=project_id,
            )

        except LabelServiceError:
            raise
        except Exception as e:
            total_duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Label generation failed with exception",
                extra={
                    "project_id": project_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            return LabelResult(
                success=False,
                error=str(e),
                duration_ms=round(total_duration_ms, 2),
                project_id=project_id,
            )

    async def generate_labels_for_request(
        self,
        request: LabelRequest,
        force_llm: bool = False,
        skip_llm: bool = False,
    ) -> LabelResult:
        """Generate labels using a LabelRequest object.

        Convenience method that unpacks a LabelRequest.

        Args:
            request: The label generation request
            force_llm: Always use LLM regardless of pattern confidence
            skip_llm: Never use LLM even if confidence is low

        Returns:
            LabelResult with generated labels and metadata
        """
        return await self.generate_labels(
            urls=request.urls,
            titles=request.titles,
            categories=request.categories,
            content_snippets=request.content_snippets,
            project_id=request.project_id,
            force_llm=force_llm,
            skip_llm=skip_llm,
        )

    async def generate_labels_batch(
        self,
        requests: list[LabelRequest],
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        force_llm: bool = False,
        skip_llm: bool = False,
    ) -> BatchLabelResult:
        """Generate labels for multiple collections in parallel.

        Processes multiple LabelRequest objects concurrently with a configurable
        concurrency limit. Results are returned in the same order as input requests.

        Uses asyncio.Semaphore to limit concurrent operations, preventing
        resource exhaustion when processing large batches.

        Args:
            requests: List of LabelRequest objects to process
            max_concurrent: Maximum concurrent operations (default 5, max 10)
            force_llm: Always use LLM regardless of pattern confidence
            skip_llm: Never use LLM even if confidence is low

        Returns:
            BatchLabelResult with results for each request (same order as input)

        Example:
            >>> requests = [
            ...     LabelRequest(urls=[...], titles=[...], project_id="proj-1"),
            ...     LabelRequest(urls=[...], titles=[...], project_id="proj-2"),
            ... ]
            >>> batch_result = await service.generate_labels_batch(requests, max_concurrent=5)
            >>> for result in batch_result.results:
            ...     print(f"{result.project_id}: {result.labels}")
        """
        start_time = time.monotonic()

        # Validate and clamp max_concurrent
        if max_concurrent < 1:
            logger.warning(
                "Validation failed: max_concurrent below minimum",
                extra={
                    "field": "max_concurrent",
                    "rejected_value": max_concurrent,
                    "clamped_to": 1,
                },
            )
            max_concurrent = 1
        elif max_concurrent > MAX_CONCURRENT_LIMIT:
            logger.warning(
                "Validation failed: max_concurrent above maximum",
                extra={
                    "field": "max_concurrent",
                    "rejected_value": max_concurrent,
                    "clamped_to": MAX_CONCURRENT_LIMIT,
                },
            )
            max_concurrent = MAX_CONCURRENT_LIMIT

        logger.debug(
            "generate_labels_batch() called",
            extra={
                "request_count": len(requests),
                "max_concurrent": max_concurrent,
                "force_llm": force_llm,
                "skip_llm": skip_llm,
            },
        )

        # Handle empty input
        if not requests:
            logger.debug("Empty request list, returning empty batch result")
            return BatchLabelResult(
                success=True,
                results=[],
                total_duration_ms=0.0,
                successful_count=0,
                failed_count=0,
                max_concurrent=max_concurrent,
            )

        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_with_semaphore(
            index: int, request: LabelRequest
        ) -> tuple[int, LabelResult]:
            """Process a single request with semaphore-controlled concurrency."""
            async with semaphore:
                logger.debug(
                    "Processing request in batch",
                    extra={
                        "index": index,
                        "project_id": request.project_id,
                        "url_count": len(request.urls),
                    },
                )
                try:
                    result = await self.generate_labels_for_request(
                        request=request,
                        force_llm=force_llm,
                        skip_llm=skip_llm,
                    )
                    return (index, result)
                except Exception as e:
                    # Catch-all for unexpected exceptions; create error result
                    logger.error(
                        "Unexpected error processing batch request",
                        extra={
                            "index": index,
                            "project_id": request.project_id,
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                        },
                        exc_info=True,
                    )
                    return (
                        index,
                        LabelResult(
                            success=False,
                            error=f"Unexpected error: {str(e)}",
                            project_id=request.project_id,
                        ),
                    )

        # Create tasks for all requests
        tasks = [
            process_with_semaphore(i, req)
            for i, req in enumerate(requests)
        ]

        # Execute all tasks concurrently (semaphore limits actual concurrency)
        indexed_results = await asyncio.gather(*tasks)

        # Sort results by original index to maintain order
        sorted_results = sorted(indexed_results, key=lambda x: x[0])
        results = [result for _, result in sorted_results]

        # Calculate statistics
        successful_count = sum(1 for r in results if r.success)
        failed_count = len(results) - successful_count
        total_duration_ms = (time.monotonic() - start_time) * 1000

        # Log state transition: batch complete
        logger.info(
            "Batch label generation complete",
            extra={
                "request_count": len(requests),
                "successful_count": successful_count,
                "failed_count": failed_count,
                "max_concurrent": max_concurrent,
                "total_duration_ms": round(total_duration_ms, 2),
            },
        )

        if total_duration_ms > SLOW_OPERATION_THRESHOLD_MS:
            logger.warning(
                "Slow batch label generation",
                extra={
                    "request_count": len(requests),
                    "total_duration_ms": round(total_duration_ms, 2),
                    "max_concurrent": max_concurrent,
                },
            )

        return BatchLabelResult(
            success=failed_count == 0,
            results=results,
            total_duration_ms=round(total_duration_ms, 2),
            successful_count=successful_count,
            failed_count=failed_count,
            max_concurrent=max_concurrent,
        )

    def generate_labels_sync(
        self,
        urls: list[str],
        titles: list[str] | None = None,
        categories: list[str] | None = None,
        project_id: str | None = None,
    ) -> tuple[list[str], float]:
        """Generate labels synchronously using patterns only (no LLM).

        For fast, pattern-only labeling when async is not available.

        Args:
            urls: List of page URLs
            titles: List of page titles
            categories: List of page categories
            project_id: Project ID for logging

        Returns:
            Tuple of (labels, confidence)
        """
        logger.debug(
            "generate_labels_sync() called",
            extra={
                "project_id": project_id,
                "url_count": len(urls),
            },
        )

        if not urls:
            return ["general-content", "needs-review"], 0.2

        titles = titles or []
        categories = categories or []

        return self._extract_pattern_labels(
            urls=urls,
            titles=titles,
            categories=categories,
            project_id=project_id,
        )


# Global LabelService instance
_label_service: LabelService | None = None


def get_label_service() -> LabelService:
    """Get the default LabelService instance (singleton).

    Returns:
        Default LabelService instance.
    """
    global _label_service
    if _label_service is None:
        _label_service = LabelService()
    return _label_service


async def generate_collection_labels(
    urls: list[str],
    titles: list[str] | None = None,
    categories: list[str] | None = None,
    project_id: str | None = None,
) -> LabelResult:
    """Convenience function to generate labels for a page collection.

    Uses the default LabelService singleton.

    Args:
        urls: List of page URLs
        titles: List of page titles
        categories: List of page categories
        project_id: Project ID for logging

    Returns:
        LabelResult with generated labels and metadata

    Example:
        >>> result = await generate_collection_labels(
        ...     urls=["https://example.com/products/widget", ...],
        ...     titles=["Widget Pro", ...],
        ...     categories=["product", ...],
        ... )
        >>> print(result.labels)
        ['e-commerce', 'product-focused', 'transactional']
    """
    service = get_label_service()
    return await service.generate_labels(
        urls=urls,
        titles=titles,
        categories=categories,
        project_id=project_id,
    )


async def generate_labels_batch(
    requests: list[LabelRequest],
    max_concurrent: int = DEFAULT_MAX_CONCURRENT,
    force_llm: bool = False,
    skip_llm: bool = False,
) -> BatchLabelResult:
    """Convenience function to generate labels for multiple collections in parallel.

    Uses the default LabelService singleton with configurable concurrency.

    Args:
        requests: List of LabelRequest objects to process
        max_concurrent: Maximum concurrent operations (default 5, max 10)
        force_llm: Always use LLM regardless of pattern confidence
        skip_llm: Never use LLM even if confidence is low

    Returns:
        BatchLabelResult with results for each request (same order as input)

    Example:
        >>> requests = [
        ...     LabelRequest(urls=["https://example.com/products/..."], project_id="p1"),
        ...     LabelRequest(urls=["https://example.com/blog/..."], project_id="p2"),
        ... ]
        >>> batch_result = await generate_labels_batch(requests, max_concurrent=5)
        >>> print(f"Success: {batch_result.successful_count}/{len(requests)}")
    """
    service = get_label_service()
    return await service.generate_labels_batch(
        requests=requests,
        max_concurrent=max_concurrent,
        force_llm=force_llm,
        skip_llm=skip_llm,
    )
