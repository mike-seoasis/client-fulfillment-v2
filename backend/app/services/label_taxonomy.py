"""Label taxonomy service for generating and assigning page labels.

This service uses Claude to:
1. Analyze all crawled pages and generate a taxonomy of labels
2. Assign labels from the taxonomy to each page
3. Validate labels for both AI assignment and user edits

The taxonomy is stored in Project.phase_status.onboarding.taxonomy.
Labels are stored in CrawledPage.labels array.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient
from app.models.crawled_page import CrawledPage, CrawlStatus
from app.models.project import Project

logger = get_logger(__name__)


# Constants for label validation
MIN_LABELS_PER_PAGE = 2
MAX_LABELS_PER_PAGE = 5


@dataclass
class LabelValidationError:
    """Represents a single validation error."""

    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class LabelValidationResult:
    """Result of label validation."""

    valid: bool
    labels: list[str]
    errors: list[LabelValidationError] = field(default_factory=list)

    @property
    def error_messages(self) -> list[str]:
        """Return list of error messages for simple display."""
        return [e.message for e in self.errors]


def validate_labels(
    labels: list[str],
    taxonomy_labels: set[str] | list[str],
    *,
    min_labels: int = MIN_LABELS_PER_PAGE,
    max_labels: int = MAX_LABELS_PER_PAGE,
) -> LabelValidationResult:
    """Validate labels against a taxonomy and count constraints.

    This function validates:
    1. All labels exist in the provided taxonomy
    2. The label count is within the allowed range (default 2-5)
    3. Labels are normalized (lowercase, stripped)

    Use this for both AI label assignment validation and user edit validation.

    Args:
        labels: List of labels to validate.
        taxonomy_labels: Set or list of valid label names from taxonomy.
        min_labels: Minimum number of labels required (default 2).
        max_labels: Maximum number of labels allowed (default 5).

    Returns:
        LabelValidationResult with valid flag, normalized labels, and any errors.

    Examples:
        >>> taxonomy = {"product-detail", "outdoor-gear", "trail-running"}
        >>> result = validate_labels(["product-detail", "outdoor-gear"], taxonomy)
        >>> result.valid
        True

        >>> result = validate_labels(["product-detail", "invalid-label"], taxonomy)
        >>> result.valid
        False
        >>> result.error_messages
        ["Invalid labels: 'invalid-label'. Must be from project taxonomy."]
    """
    errors: list[LabelValidationError] = []

    # Convert taxonomy to set for O(1) lookup
    valid_taxonomy = set(taxonomy_labels) if isinstance(taxonomy_labels, list) else taxonomy_labels

    # Normalize labels (lowercase, strip whitespace)
    normalized_labels = [label.strip().lower() for label in labels if label.strip()]

    # Remove duplicates while preserving order
    seen: set[str] = set()
    unique_labels: list[str] = []
    for label in normalized_labels:
        if label not in seen:
            seen.add(label)
            unique_labels.append(label)
    normalized_labels = unique_labels

    # Validate label count
    if len(normalized_labels) < min_labels:
        errors.append(
            LabelValidationError(
                code="too_few_labels",
                message=f"At least {min_labels} labels are required. Got {len(normalized_labels)}.",
                details={
                    "min_required": min_labels,
                    "actual_count": len(normalized_labels),
                },
            )
        )

    if len(normalized_labels) > max_labels:
        errors.append(
            LabelValidationError(
                code="too_many_labels",
                message=f"Maximum {max_labels} labels allowed. Got {len(normalized_labels)}.",
                details={
                    "max_allowed": max_labels,
                    "actual_count": len(normalized_labels),
                },
            )
        )

    # Validate all labels are in taxonomy
    invalid_labels = [label for label in normalized_labels if label not in valid_taxonomy]
    if invalid_labels:
        # Format list nicely for error message
        if len(invalid_labels) == 1:
            invalid_str = f"'{invalid_labels[0]}'"
        else:
            invalid_str = ", ".join(f"'{label}'" for label in invalid_labels)

        errors.append(
            LabelValidationError(
                code="invalid_labels",
                message=f"Invalid labels: {invalid_str}. Must be from project taxonomy.",
                details={
                    "invalid_labels": invalid_labels,
                    "valid_labels": sorted(valid_taxonomy),
                },
            )
        )

    return LabelValidationResult(
        valid=len(errors) == 0,
        labels=normalized_labels,
        errors=errors,
    )


async def get_project_taxonomy_labels(
    db: AsyncSession,
    project_id: str,
) -> set[str] | None:
    """Get the set of valid taxonomy label names for a project.

    Args:
        db: AsyncSession for database operations.
        project_id: Project ID to get taxonomy for.

    Returns:
        Set of valid label names, or None if no taxonomy exists.
    """
    project = await db.get(Project, project_id)
    if not project:
        return None

    stored_taxonomy = project.phase_status.get("onboarding", {}).get("taxonomy")
    if not stored_taxonomy:
        return None

    labels = stored_taxonomy.get("labels", [])
    return {label.get("name", "") for label in labels if label.get("name")}


async def validate_page_labels(
    db: AsyncSession,
    project_id: str,
    labels: list[str],
) -> LabelValidationResult:
    """Validate labels for a page against the project's taxonomy.

    Convenience function that loads the taxonomy and validates labels in one call.
    Use this in API endpoints for user label edits.

    Args:
        db: AsyncSession for database operations.
        project_id: Project ID to validate against.
        labels: List of labels to validate.

    Returns:
        LabelValidationResult with valid flag, normalized labels, and any errors.
    """
    taxonomy_labels = await get_project_taxonomy_labels(db, project_id)

    if taxonomy_labels is None:
        return LabelValidationResult(
            valid=False,
            labels=[],
            errors=[
                LabelValidationError(
                    code="no_taxonomy",
                    message="No taxonomy exists for this project. Generate taxonomy first.",
                    details={"project_id": project_id},
                )
            ],
        )

    return validate_labels(labels, taxonomy_labels)


# System prompt for taxonomy generation
TAXONOMY_SYSTEM_PROMPT = """You are an e-commerce product categorization expert. Your task is to analyze collection pages from an e-commerce website and generate a taxonomy of PRODUCT CATEGORY labels.

CRITICAL: Every page MUST have at least one accurate label. If a page sells a unique product category that no other page has, CREATE A LABEL FOR IT. It is BETTER to have a unique label than to mislabel or use generic fallbacks.

IMPORTANT: Focus on WHAT PRODUCTS are sold, not page structure. Labels like "product-listing" or "collection-page" are USELESS because they apply to every page.

GOOD labels describe product categories:
- "travel-mugs" - travel coffee mugs and tumblers
- "french-presses" - french press coffee makers
- "coffee-storage" - airtight coffee containers
- "cannabis-storage" - cannabis/herb storage containers (even if only one page sells these!)
- "pour-over" - pour-over coffee equipment
- "cold-brew" - cold brew coffee makers
- "gift-sets" - bundled gift products

BANNED labels (NEVER generate these - they are too generic):
- "product-listing" - applies to all collection pages
- "accessories" - BANNED, too vague. Instead use specific types like "coffee-accessories", "camping-accessories"
- "shop" - meaningless
- "collection" - applies to everything
- "all-products" - meaningless, use specific product categories instead
- "products" - meaningless
- "gear" - too vague, be specific about what type of gear

Generate a taxonomy that:
1. Describes SPECIFIC product categories based on the products sold
2. Uses the URL path and title to infer product types (e.g., "/collections/bru-trek" with title "BruTrek® Coffee Gear" → "travel-coffee-gear")
3. INCLUDES labels for unique product categories even if only one page uses them (e.g., cannabis storage)
4. Uses lowercase, hyphenated names
5. Creates as many labels as needed to accurately describe ALL pages (typically 5-20)

Respond ONLY with valid JSON:
{
  "labels": [
    {
      "name": "label-name",
      "description": "What products this covers",
      "examples": ["example products or collections"]
    }
  ],
  "reasoning": "Brief explanation"
}"""


# System prompt for label assignment
ASSIGNMENT_SYSTEM_PROMPT = """You are a product categorization expert. Given a collection page and a taxonomy of product category labels, assign the labels that describe WHAT PRODUCTS are on this page.

CRITICAL: Look at the URL path and page title to identify what product categories are sold. Examples:
- URL contains "cannascape" or title mentions "Weed Storage" → MUST use cannabis-related label
- URL contains "bru-trek" or title mentions "Travel Presses" → use travel coffee gear labels
- URL contains "airscape" or title mentions "Coffee Canister" → use storage labels

IMPORTANT: Only assign labels that describe the actual product categories. Look at:
- The URL path (e.g., "/collections/cannascape" = cannabis storage products)
- The page title (e.g., "Cannascape® Weed Storage" = cannabis storage)
- The H1/H2 headings for product category hints

Rules:
1. Assign 2-4 labels that describe the product categories on the page
2. ONLY use labels from the provided taxonomy
3. Be SPECIFIC - match labels to what's actually sold on the page
4. If a page sells cannabis/weed products, you MUST use a cannabis-related label
5. NEVER use generic fallbacks if a specific label exists in the taxonomy

Respond ONLY with valid JSON:
{
  "labels": ["label-1", "label-2"],
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation"
}"""


@dataclass
class TaxonomyLabel:
    """A label in the taxonomy with its definition."""

    name: str
    description: str
    examples: list[str]


@dataclass
class GeneratedTaxonomy:
    """Result of taxonomy generation."""

    labels: list[TaxonomyLabel]
    reasoning: str


@dataclass
class LabelAssignment:
    """Result of label assignment for a single page."""

    page_id: str
    labels: list[str]
    confidence: float
    reasoning: str | None
    success: bool
    error: str | None = None


class LabelTaxonomyService:
    """Service for generating label taxonomies and assigning labels to pages."""

    def __init__(self, claude_client: ClaudeClient) -> None:
        """Initialize the label taxonomy service.

        Args:
            claude_client: ClaudeClient for LLM operations.
        """
        self._claude = claude_client

    async def generate_taxonomy(
        self,
        db: AsyncSession,
        project_id: str,
    ) -> GeneratedTaxonomy | None:
        """Generate a label taxonomy by analyzing all crawled pages for a project.

        Analyzes page titles, URLs, and content summaries to create a taxonomy
        of labels that can be used to categorize the pages.

        Args:
            db: AsyncSession for database operations.
            project_id: Project ID to generate taxonomy for.

        Returns:
            GeneratedTaxonomy with labels and reasoning, or None if generation failed.
        """
        # Fetch completed pages for the project
        stmt = (
            select(CrawledPage)
            .where(CrawledPage.project_id == project_id)
            .where(CrawledPage.status == CrawlStatus.COMPLETED.value)
        )
        result = await db.execute(stmt)
        pages = list(result.scalars().all())

        if not pages:
            logger.warning(
                "No completed pages found for taxonomy generation",
                extra={"project_id": project_id},
            )
            return None

        logger.info(
            "Generating taxonomy for project",
            extra={"project_id": project_id, "page_count": len(pages)},
        )

        # Build page summaries for Claude
        page_summaries = []
        for page in pages:
            summary = f"- URL: {page.normalized_url}"
            if page.title:
                summary += f"\n  Title: {page.title}"
            if page.meta_description:
                summary += f"\n  Description: {page.meta_description[:200]}"
            if page.headings:
                h1s = page.headings.get("h1", [])
                if h1s:
                    summary += f"\n  H1: {h1s[0] if h1s else 'None'}"
            if page.product_count:
                summary += f"\n  Products: {page.product_count}"
            if page.word_count:
                summary += f"\n  Word count: {page.word_count}"
            page_summaries.append(summary)

        # Build user prompt
        user_prompt = f"""Analyze these {len(pages)} pages from a website and generate a taxonomy of labels:

{chr(10).join(page_summaries)}

Generate a taxonomy that captures the main content types and purposes of these pages."""

        # Call Claude
        completion = await self._claude.complete(
            user_prompt=user_prompt,
            system_prompt=TAXONOMY_SYSTEM_PROMPT,
            temperature=0.1,  # Low temp for consistency
            max_tokens=2000,
        )

        if not completion.success:
            logger.error(
                "Failed to generate taxonomy",
                extra={
                    "project_id": project_id,
                    "error": completion.error,
                },
            )
            return None

        # Parse response
        try:
            response_text = completion.text or ""
            json_text = self._extract_json(response_text)
            parsed = json.loads(json_text)

            labels = [
                TaxonomyLabel(
                    name=label.get("name", ""),
                    description=label.get("description", ""),
                    examples=label.get("examples", []),
                )
                for label in parsed.get("labels", [])
            ]

            taxonomy = GeneratedTaxonomy(
                labels=labels,
                reasoning=parsed.get("reasoning", ""),
            )

            # Store taxonomy in project phase_status
            project = await db.get(Project, project_id)
            if project:
                # Initialize onboarding section if needed
                if "onboarding" not in project.phase_status:
                    project.phase_status["onboarding"] = {}

                # Store taxonomy as serializable dict with timestamp
                project.phase_status["onboarding"]["taxonomy"] = {
                    "labels": [
                        {
                            "name": label.name,
                            "description": label.description,
                            "examples": label.examples,
                        }
                        for label in taxonomy.labels
                    ],
                    "reasoning": taxonomy.reasoning,
                    "generated_at": datetime.now(UTC).isoformat(),
                }

                # Mark phase_status as modified for SQLAlchemy
                from sqlalchemy.orm.attributes import flag_modified

                flag_modified(project, "phase_status")
                await db.flush()

                logger.info(
                    "Taxonomy generated and stored",
                    extra={
                        "project_id": project_id,
                        "label_count": len(taxonomy.labels),
                        "labels": [label.name for label in taxonomy.labels],
                    },
                )

            return taxonomy

        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse taxonomy response",
                extra={
                    "project_id": project_id,
                    "error": str(e),
                    "response": (completion.text or "")[:500],
                },
            )
            return None

    async def assign_labels(
        self,
        db: AsyncSession,
        project_id: str,
        taxonomy: GeneratedTaxonomy | None = None,
    ) -> list[LabelAssignment]:
        """Assign labels from the taxonomy to each crawled page.

        If no taxonomy is provided, attempts to load it from the project's
        phase_status.onboarding.taxonomy field.

        Args:
            db: AsyncSession for database operations.
            project_id: Project ID to assign labels for.
            taxonomy: Optional taxonomy to use (loads from project if not provided).

        Returns:
            List of LabelAssignment results for each page.
        """
        # Load taxonomy from project if not provided
        if taxonomy is None:
            project = await db.get(Project, project_id)
            if not project:
                logger.error(
                    "Project not found",
                    extra={"project_id": project_id},
                )
                return []

            stored_taxonomy = (
                project.phase_status.get("onboarding", {}).get("taxonomy")
            )
            if not stored_taxonomy:
                logger.error(
                    "No taxonomy found for project",
                    extra={"project_id": project_id},
                )
                return []

            # Reconstruct taxonomy from stored data
            taxonomy = GeneratedTaxonomy(
                labels=[
                    TaxonomyLabel(
                        name=label.get("name", ""),
                        description=label.get("description", ""),
                        examples=label.get("examples", []),
                    )
                    for label in stored_taxonomy.get("labels", [])
                ],
                reasoning=stored_taxonomy.get("reasoning", ""),
            )

        # Fetch completed pages
        stmt = (
            select(CrawledPage)
            .where(CrawledPage.project_id == project_id)
            .where(CrawledPage.status == CrawlStatus.COMPLETED.value)
        )
        result = await db.execute(stmt)
        pages = list(result.scalars().all())

        if not pages:
            logger.warning(
                "No completed pages found for label assignment",
                extra={"project_id": project_id},
            )
            return []

        logger.info(
            "Assigning labels to pages",
            extra={
                "project_id": project_id,
                "page_count": len(pages),
                "taxonomy_labels": [label.name for label in taxonomy.labels],
            },
        )

        # Build taxonomy description for prompt
        taxonomy_desc = "\n".join(
            f"- {label.name}: {label.description}"
            for label in taxonomy.labels
        )

        assignments: list[LabelAssignment] = []

        # Process each page
        for page in pages:
            assignment = await self._assign_labels_to_page(
                page=page,
                taxonomy_desc=taxonomy_desc,
                valid_labels={label.name for label in taxonomy.labels},
            )
            assignments.append(assignment)

            # Update page labels in database
            if assignment.success:
                page.labels = assignment.labels
                await db.flush()

        # Log summary
        successful = sum(1 for a in assignments if a.success)
        logger.info(
            "Label assignment completed",
            extra={
                "project_id": project_id,
                "total_pages": len(pages),
                "successful": successful,
                "failed": len(pages) - successful,
            },
        )

        return assignments

    async def _assign_labels_to_page(
        self,
        page: CrawledPage,
        taxonomy_desc: str,
        valid_labels: set[str],
    ) -> LabelAssignment:
        """Assign labels to a single page.

        Args:
            page: CrawledPage to assign labels to.
            taxonomy_desc: Formatted taxonomy description for the prompt.
            valid_labels: Set of valid label names from taxonomy.

        Returns:
            LabelAssignment result.
        """
        # Build page info for prompt
        page_info = f"URL: {page.normalized_url}"
        if page.title:
            page_info += f"\nTitle: {page.title}"
        if page.meta_description:
            page_info += f"\nDescription: {page.meta_description[:300]}"
        if page.headings:
            h1s = page.headings.get("h1", [])
            h2s = page.headings.get("h2", [])
            if h1s:
                page_info += f"\nH1: {', '.join(h1s[:3])}"
            if h2s:
                page_info += f"\nH2: {', '.join(h2s[:5])}"
        if page.product_count:
            page_info += f"\nProducts on page: {page.product_count}"
        if page.word_count:
            page_info += f"\nWord count: {page.word_count}"

        user_prompt = f"""Assign labels to this page using the taxonomy below.

TAXONOMY:
{taxonomy_desc}

PAGE:
{page_info}

Respond with JSON only."""

        # Call Claude
        completion = await self._claude.complete(
            user_prompt=user_prompt,
            system_prompt=ASSIGNMENT_SYSTEM_PROMPT,
            temperature=0.0,  # Deterministic
            max_tokens=500,
        )

        if not completion.success:
            return LabelAssignment(
                page_id=page.id,
                labels=[],
                confidence=0.0,
                reasoning=None,
                success=False,
                error=completion.error,
            )

        # Parse response
        try:
            response_text = completion.text or ""
            json_text = self._extract_json(response_text)
            parsed = json.loads(json_text)

            labels = parsed.get("labels", [])

            # Validate labels using the validation function
            validation_result = validate_labels(labels, valid_labels)

            if not validation_result.valid:
                # Log validation issues but still use the valid labels we got
                for error in validation_result.errors:
                    if error.code == "invalid_labels":
                        logger.warning(
                            "AI assigned labels not in taxonomy",
                            extra={
                                "page_id": page.id,
                                "invalid_labels": error.details.get("invalid_labels", []),
                            },
                        )
                    elif error.code in ("too_few_labels", "too_many_labels"):
                        logger.warning(
                            f"AI label count validation: {error.message}",
                            extra={"page_id": page.id},
                        )

            # Filter to only valid labels from taxonomy
            valid_assigned = [
                label for label in validation_result.labels
                if label in valid_labels
            ]

            return LabelAssignment(
                page_id=page.id,
                labels=valid_assigned,
                confidence=float(parsed.get("confidence", 0.5)),
                reasoning=parsed.get("reasoning"),
                success=True,
            )

        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse label assignment response",
                extra={
                    "page_id": page.id,
                    "error": str(e),
                    "response": (completion.text or "")[:300],
                },
            )
            return LabelAssignment(
                page_id=page.id,
                labels=[],
                confidence=0.0,
                reasoning=None,
                success=False,
                error=f"JSON parse error: {e}",
            )

    def _extract_json(self, text: str) -> str:
        """Extract JSON from a response that may contain markdown code blocks.

        Args:
            text: Response text that may contain JSON.

        Returns:
            Extracted JSON string.
        """
        json_text = text.strip()

        # Handle markdown code blocks
        if json_text.startswith("```"):
            lines = json_text.split("\n")
            lines = lines[1:]  # Remove opening fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]  # Remove closing fence
            json_text = "\n".join(lines)

        return json_text
