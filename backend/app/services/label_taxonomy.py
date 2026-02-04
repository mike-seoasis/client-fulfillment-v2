"""Label taxonomy service for generating and assigning page labels.

This service uses Claude to:
1. Analyze all crawled pages and generate a taxonomy of labels
2. Assign labels from the taxonomy to each page

The taxonomy is stored in Project.phase_status.onboarding.taxonomy.
Labels are stored in CrawledPage.labels array.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient
from app.models.crawled_page import CrawledPage, CrawlStatus
from app.models.project import Project

logger = get_logger(__name__)


# System prompt for taxonomy generation
TAXONOMY_SYSTEM_PROMPT = """You are an e-commerce SEO and content taxonomy expert. Your task is to analyze a collection of web pages from an e-commerce website and generate a taxonomy of labels that will be used for internal linking optimization.

CONTEXT: These labels will help identify pages that should link to each other. Pages with the same label share thematic relevance and should be connected via internal links. Good internal linking improves:
- User navigation between related products and content
- SEO by distributing page authority across related pages
- Content discoverability for both users and search engines

Generate a taxonomy that:
1. Captures the main content types, product categories, and purposes of pages
2. Is specific enough to group related pages but general enough to apply across multiple pages
3. Uses consistent, lowercase, hyphenated label names (e.g., "trail-running", "outdoor-gear")
4. Includes 10-30 labels that cover the variety of content (aim for the range that best fits the site)
5. Balances PURPOSE (what the page does) with TOPIC (what it's about) for linking relevance
6. Considers product categories, collections, blog topics, and content themes

Examples of good labels:
- product-listing (shows multiple products)
- product-detail (shows single product info)
- trail-running (trail running products or content)
- outdoor-gear (outdoor equipment category)
- blog-post (article or blog content)
- buying-guide (helps users choose products)
- brand-story (company/brand information)
- customer-support (help, FAQ, policies)
- seasonal-collection (holiday or seasonal content)

Respond ONLY with valid JSON in this exact format:
{
  "labels": [
    {
      "name": "label-name",
      "description": "When to use this label",
      "examples": ["url patterns or page types that would have this label"]
    }
  ],
  "reasoning": "Brief explanation of the taxonomy design"
}"""


# System prompt for label assignment
ASSIGNMENT_SYSTEM_PROMPT = """You are a web page classifier. Given page information and a taxonomy of labels, assign the most appropriate labels to the page.

Rules:
1. Assign 1-3 labels per page (prefer fewer, more accurate labels)
2. Only use labels from the provided taxonomy
3. Labels should describe the page's PURPOSE, not just its topic
4. If uncertain, use fewer labels rather than guessing

Respond ONLY with valid JSON in this exact format:
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
            # Validate labels against taxonomy
            valid_assigned = [label for label in labels if label in valid_labels]

            if len(valid_assigned) != len(labels):
                invalid = set(labels) - set(valid_assigned)
                logger.warning(
                    "Some assigned labels not in taxonomy",
                    extra={
                        "page_id": page.id,
                        "invalid_labels": list(invalid),
                    },
                )

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
