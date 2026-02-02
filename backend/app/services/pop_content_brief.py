"""POP Content Brief service for fetching and storing content briefs.

Fetches content brief data from PageOptimizer Pro API and manages storage.
Content briefs provide keyword targets, LSI terms, competitor data, and
optimization recommendations for content creation.

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import time
import traceback
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.pop import (
    POPClient,
    POPError,
    POPTaskStatus,
    get_pop_client,
)
from app.models.content_brief import ContentBrief

logger = get_logger(__name__)

# Constants
SLOW_OPERATION_THRESHOLD_MS = 1000


@dataclass
class POPContentBriefResult:
    """Result of a POP content brief fetch operation."""

    success: bool
    keyword: str
    target_url: str
    task_id: str | None = None
    brief_id: str | None = None  # Database record ID after persistence
    word_count_target: int | None = None
    word_count_min: int | None = None
    word_count_max: int | None = None
    heading_targets: list[dict[str, Any]] = field(default_factory=list)
    keyword_targets: list[dict[str, Any]] = field(default_factory=list)
    lsi_terms: list[dict[str, Any]] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)
    related_questions: list[dict[str, Any]] = field(default_factory=list)
    related_searches: list[dict[str, Any]] = field(default_factory=list)
    competitors: list[dict[str, Any]] = field(default_factory=list)
    page_score_target: float | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0
    request_id: str | None = None


class POPContentBriefServiceError(Exception):
    """Base exception for POP content brief service errors."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.page_id = page_id


class POPContentBriefValidationError(POPContentBriefServiceError):
    """Raised when validation fails."""

    def __init__(
        self,
        field_name: str,
        value: str,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(
            f"Validation error for {field_name}: {message}", project_id, page_id
        )
        self.field_name = field_name
        self.value = value


class POPContentBriefService:
    """Service for fetching and storing POP content briefs.

    Features:
    - Fetches content briefs from PageOptimizer Pro API
    - Creates POP tasks and polls for results
    - Parses and normalizes brief data
    - Comprehensive logging per requirements

    Usage:
        service = POPContentBriefService()
        result = await service.fetch_brief(
            project_id="uuid",
            page_id="uuid",
            keyword="best hiking boots",
            target_url="https://example.com/hiking-boots",
        )
    """

    def __init__(
        self,
        session: AsyncSession | None = None,
        client: POPClient | None = None,
    ) -> None:
        """Initialize POP content brief service.

        Args:
            session: Optional async SQLAlchemy session for persistence.
                     If None, persistence operations will not be available.
            client: POP client instance. If None, uses global instance.
        """
        self._session = session
        self._client = client

        logger.debug(
            "POPContentBriefService initialized",
            extra={
                "client_provided": client is not None,
                "session_provided": session is not None,
            },
        )

    async def _get_client(self) -> POPClient:
        """Get POP client instance."""
        if self._client is None:
            self._client = await get_pop_client()
        return self._client

    async def save_brief(
        self,
        page_id: str,
        keyword: str,
        result: POPContentBriefResult,
        project_id: str | None = None,
    ) -> ContentBrief:
        """Save a content brief to the database.

        Creates or updates a content brief for the given page. If a brief already
        exists for the same page, it will be replaced (upsert behavior).

        Args:
            page_id: UUID of the crawled page this brief is for
            keyword: Target keyword for content optimization
            result: POPContentBriefResult from fetch_brief()
            project_id: Optional project ID for logging context

        Returns:
            The created or updated ContentBrief model instance

        Raises:
            POPContentBriefServiceError: If session is not available or save fails
        """
        start_time = time.monotonic()

        # Method entry log with sanitized parameters
        logger.debug(
            "save_brief method entry",
            extra={
                "page_id": page_id,
                "project_id": project_id,
                "keyword": keyword[:50] if keyword else "",
                "task_id": result.task_id,
            },
        )

        if self._session is None:
            raise POPContentBriefServiceError(
                "Database session not available - cannot save brief",
                project_id=project_id,
                page_id=page_id,
            )

        try:
            # Check if a brief already exists for this page
            stmt = select(ContentBrief).where(ContentBrief.page_id == page_id)
            db_result = await self._session.execute(stmt)
            existing = db_result.scalar_one_or_none()

            if existing:
                # Update existing brief (replace)
                existing.keyword = keyword
                existing.pop_task_id = result.task_id
                existing.word_count_target = result.word_count_target
                existing.word_count_min = result.word_count_min
                existing.word_count_max = result.word_count_max
                existing.heading_targets = result.heading_targets
                existing.keyword_targets = result.keyword_targets
                existing.lsi_terms = result.lsi_terms
                existing.entities = result.entities
                existing.related_questions = result.related_questions
                existing.related_searches = result.related_searches
                existing.competitors = result.competitors
                existing.page_score_target = result.page_score_target
                existing.raw_response = result.raw_response
                existing.updated_at = datetime.now(UTC)

                brief = existing

                logger.info(
                    "Updated existing content brief",
                    extra={
                        "brief_id": brief.id,
                        "page_id": page_id,
                        "project_id": project_id,
                        "keyword": keyword[:50],
                        "pop_task_id": result.task_id,
                    },
                )
            else:
                # Create new brief
                brief = ContentBrief(
                    page_id=page_id,
                    keyword=keyword,
                    pop_task_id=result.task_id,
                    word_count_target=result.word_count_target,
                    word_count_min=result.word_count_min,
                    word_count_max=result.word_count_max,
                    heading_targets=result.heading_targets,
                    keyword_targets=result.keyword_targets,
                    lsi_terms=result.lsi_terms,
                    entities=result.entities,
                    related_questions=result.related_questions,
                    related_searches=result.related_searches,
                    competitors=result.competitors,
                    page_score_target=result.page_score_target,
                    raw_response=result.raw_response,
                )
                self._session.add(brief)

                logger.info(
                    "Created new content brief",
                    extra={
                        "page_id": page_id,
                        "project_id": project_id,
                        "keyword": keyword[:50],
                        "pop_task_id": result.task_id,
                    },
                )

            await self._session.flush()
            await self._session.refresh(brief)

            duration_ms = (time.monotonic() - start_time) * 1000

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow content brief save operation",
                    extra={
                        "brief_id": brief.id,
                        "page_id": page_id,
                        "project_id": project_id,
                        "task_id": result.task_id,
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    },
                )

            # Method exit log with result summary
            logger.debug(
                "save_brief method exit",
                extra={
                    "brief_id": brief.id,
                    "page_id": page_id,
                    "project_id": project_id,
                    "task_id": result.task_id,
                    "success": True,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return brief

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Failed to save content brief",
                extra={
                    "page_id": page_id,
                    "project_id": project_id,
                    "task_id": result.task_id,
                    "keyword": keyword[:50] if keyword else "",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            # Method exit log on error
            logger.debug(
                "save_brief method exit",
                extra={
                    "brief_id": None,
                    "page_id": page_id,
                    "project_id": project_id,
                    "task_id": result.task_id,
                    "success": False,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
            )
            raise POPContentBriefServiceError(
                f"Failed to save content brief: {e}",
                project_id=project_id,
                page_id=page_id,
            ) from e

    def _parse_brief_data(
        self,
        raw_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Parse raw POP API response into structured brief data.

        Extracts structured data from POP API responses following their schema:
        - wordCount: {current, target} - word count targets
        - tagCounts: [{tagLabel, min, max, mean, signalCnt}] - heading structure
        - cleanedContentBrief: {title, pageTitle, subHeadings, p} - keyword targets by section
        - lsaPhrases: [{phrase, weight, averageCount, targetCount}] - LSI terms
        - relatedQuestions: [{question, link, snippet, title}] - PAA data
        - competitors: [{url, title, pageScore}] - competitor data

        Args:
            raw_data: Raw API response data

        Returns:
            Dictionary with parsed brief fields
        """
        return {
            "word_count_target": self._extract_word_count_target(raw_data),
            "word_count_min": self._extract_word_count_min(raw_data),
            "word_count_max": self._extract_word_count_max(raw_data),
            "heading_targets": self._extract_heading_targets(raw_data),
            "keyword_targets": self._extract_keyword_targets(raw_data),
            "lsi_terms": self._extract_lsi_terms(raw_data),
            "entities": self._extract_entities(raw_data),
            "related_questions": self._extract_related_questions(raw_data),
            "related_searches": self._extract_related_searches(raw_data),
            "competitors": self._extract_competitors(raw_data),
            "page_score_target": self._extract_page_score_target(raw_data),
        }

    def _extract_word_count_target(self, raw_data: dict[str, Any]) -> int | None:
        """Extract word count target from POP response.

        POP API provides wordCount.target for target word count.
        Falls back to averaging competitors if not present.
        """
        word_count = raw_data.get("wordCount")
        if isinstance(word_count, dict):
            target = word_count.get("target")
            if target is not None:
                return int(target) if isinstance(target, (int, float)) else None
        return None

    def _extract_word_count_min(self, raw_data: dict[str, Any]) -> int | None:
        """Extract minimum word count from POP response.

        POP API does not provide explicit min, so we derive from tagCounts
        or use 80% of target as a reasonable minimum.
        """
        # Check tagCounts for word count entry
        tag_counts = raw_data.get("tagCounts", [])
        if isinstance(tag_counts, list):
            for tag in tag_counts:
                if isinstance(tag, dict):
                    label = tag.get("tagLabel", "").lower()
                    if "word" in label and "count" in label:
                        min_val = tag.get("min")
                        if min_val is not None:
                            return (
                                int(min_val)
                                if isinstance(min_val, (int, float))
                                else None
                            )

        # Fall back to 80% of target
        target = self._extract_word_count_target(raw_data)
        if target is not None:
            return int(target * 0.8)
        return None

    def _extract_word_count_max(self, raw_data: dict[str, Any]) -> int | None:
        """Extract maximum word count from POP response.

        POP API does not provide explicit max, so we derive from tagCounts
        or use 120% of target as a reasonable maximum.
        """
        # Check tagCounts for word count entry
        tag_counts = raw_data.get("tagCounts", [])
        if isinstance(tag_counts, list):
            for tag in tag_counts:
                if isinstance(tag, dict):
                    label = tag.get("tagLabel", "").lower()
                    if "word" in label and "count" in label:
                        max_val = tag.get("max")
                        if max_val is not None:
                            return (
                                int(max_val)
                                if isinstance(max_val, (int, float))
                                else None
                            )

        # Fall back to 120% of target
        target = self._extract_word_count_target(raw_data)
        if target is not None:
            return int(target * 1.2)
        return None

    def _extract_heading_targets(
        self, raw_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract heading structure targets from tagCounts.

        POP API provides tagCounts array with entries like:
        - tagLabel: 'H1 tag total', 'H2 tag total', 'H3 tag total', 'H4 tag total'
        - min: minimum count required
        - max: maximum count required
        - mean: average count across competitors
        - signalCnt: current count on target page
        """
        heading_targets: list[dict[str, Any]] = []
        tag_counts = raw_data.get("tagCounts", [])

        if not isinstance(tag_counts, list):
            return heading_targets

        # Map tag labels to heading levels
        heading_labels = {
            "h1": ["h1 tag", "h1 total", "h1 tag total"],
            "h2": ["h2 tag", "h2 total", "h2 tag total"],
            "h3": ["h3 tag", "h3 total", "h3 tag total"],
            "h4": ["h4 tag", "h4 total", "h4 tag total"],
        }

        for tag in tag_counts:
            if not isinstance(tag, dict):
                continue

            tag_label = str(tag.get("tagLabel", "")).lower()

            for level, patterns in heading_labels.items():
                if any(pattern in tag_label for pattern in patterns):
                    min_count = tag.get("min")
                    max_count = tag.get("max")

                    heading_targets.append(
                        {
                            "level": level,
                            "text": None,  # POP doesn't provide suggested text in tagCounts
                            "min_count": int(min_count)
                            if isinstance(min_count, (int, float))
                            else None,
                            "max_count": int(max_count)
                            if isinstance(max_count, (int, float))
                            else None,
                            "priority": None,
                        }
                    )
                    break  # Found the level, move to next tag

        return heading_targets

    def _extract_keyword_targets(
        self, raw_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract keyword density targets by section from cleanedContentBrief.

        POP API provides cleanedContentBrief with sections:
        - title: keyword targets for meta title
        - pageTitle: keyword targets for page title (H1)
        - subHeadings: keyword targets for H2/H3
        - p: keyword targets for paragraph content

        Each section has arrays with:
        - term: {phrase, type, weight}
        - contentBrief: {current, target}
        """
        keyword_targets: list[dict[str, Any]] = []
        content_brief = raw_data.get("cleanedContentBrief", {})

        if not isinstance(content_brief, dict):
            return keyword_targets

        # Map section names to our normalized section names
        section_mapping = {
            "title": "title",
            "pageTitle": "h1",
            "subHeadings": "h2",  # POP treats subHeadings as H2+H3
            "p": "paragraph",
        }

        for pop_section, our_section in section_mapping.items():
            section_data = content_brief.get(pop_section, [])
            if not isinstance(section_data, list):
                continue

            for item in section_data:
                if not isinstance(item, dict):
                    continue

                term = item.get("term", {})
                if not isinstance(term, dict):
                    continue

                phrase = term.get("phrase")
                if not phrase:
                    continue

                brief = item.get("contentBrief", {})
                target_count = brief.get("target") if isinstance(brief, dict) else None

                keyword_targets.append(
                    {
                        "keyword": str(phrase),
                        "section": our_section,
                        "count_min": None,  # POP doesn't provide explicit min per keyword
                        "count_max": None,  # POP doesn't provide explicit max per keyword
                        "density_target": float(target_count)
                        if isinstance(target_count, (int, float))
                        else None,
                    }
                )

        # Also extract from section totals (titleTotal, pageTitleTotal, subHeadingsTotal, pTotal)
        total_sections = {
            "titleTotal": "title",
            "pageTitleTotal": "h1",
            "subHeadingsTotal": "h2",
            "pTotal": "paragraph",
        }

        for pop_total, our_section in total_sections.items():
            total_data = content_brief.get(pop_total, {})
            if not isinstance(total_data, dict):
                continue

            min_val = total_data.get("min")
            max_val = total_data.get("max")

            # Only add if we have min/max data and haven't already captured this section
            if min_val is not None or max_val is not None:
                keyword_targets.append(
                    {
                        "keyword": f"_total_{our_section}",  # Special marker for section totals
                        "section": our_section,
                        "count_min": int(min_val)
                        if isinstance(min_val, (int, float))
                        else None,
                        "count_max": int(max_val)
                        if isinstance(max_val, (int, float))
                        else None,
                        "density_target": None,
                    }
                )

        return keyword_targets

    def _extract_lsi_terms(self, raw_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract LSI terms from lsaPhrases array.

        POP API provides lsaPhrases with:
        - phrase: the LSI term
        - weight: importance weight
        - averageCount: average count in competitors
        - targetCount: recommended target count
        """
        lsi_terms: list[dict[str, Any]] = []
        lsa_phrases = raw_data.get("lsaPhrases", [])

        if not isinstance(lsa_phrases, list):
            return lsi_terms

        for item in lsa_phrases:
            if not isinstance(item, dict):
                continue

            phrase = item.get("phrase")
            if not phrase:
                continue

            weight = item.get("weight")
            avg_count = item.get("averageCount")
            target_count = item.get("targetCount")

            lsi_terms.append(
                {
                    "phrase": str(phrase),
                    "weight": float(weight)
                    if isinstance(weight, (int, float))
                    else None,
                    "average_count": float(avg_count)
                    if isinstance(avg_count, (int, float))
                    else None,
                    "target_count": int(target_count)
                    if isinstance(target_count, (int, float))
                    else None,
                }
            )

        return lsi_terms

    def _extract_entities(self, raw_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract entities from POP response.

        POP API may provide entities in various forms. Handles gracefully
        if not present.
        """
        entities: list[dict[str, Any]] = []
        entities_data = raw_data.get("entities", [])

        if not isinstance(entities_data, list):
            return entities

        for item in entities_data:
            if not isinstance(item, dict):
                continue

            name = item.get("name") or item.get("entity")
            if not name:
                continue

            salience = item.get("salience")
            entities.append(
                {
                    "name": str(name),
                    "type": str(item.get("type", "")) if item.get("type") else None,
                    "salience": float(salience)
                    if isinstance(salience, (int, float))
                    else None,
                }
            )

        return entities

    def _extract_related_questions(
        self, raw_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract related questions (PAA) from relatedQuestions array.

        POP API provides relatedQuestions with:
        - question: the question text
        - link: source URL
        - snippet: answer snippet
        - title: title of the source
        - displayed_link: formatted display link
        """
        related_questions: list[dict[str, Any]] = []
        questions_data = raw_data.get("relatedQuestions", [])

        if not isinstance(questions_data, list):
            return related_questions

        for item in questions_data:
            if not isinstance(item, dict):
                continue

            question = item.get("question")
            if not question:
                continue

            related_questions.append(
                {
                    "question": str(question),
                    "answer_snippet": str(item.get("snippet", ""))
                    if item.get("snippet")
                    else None,
                    "source_url": str(item.get("link", ""))
                    if item.get("link")
                    else None,
                }
            )

        return related_questions

    def _extract_related_searches(
        self, raw_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract related searches from relatedSearches array.

        POP API provides relatedSearches with:
        - query: the search query
        - link: URL
        - items: array of related items
        """
        related_searches: list[dict[str, Any]] = []
        searches_data = raw_data.get("relatedSearches", [])

        if not isinstance(searches_data, list):
            return related_searches

        for item in searches_data:
            if not isinstance(item, dict):
                continue

            query = item.get("query")
            if not query:
                continue

            related_searches.append(
                {
                    "query": str(query),
                    "relevance": None,  # POP doesn't provide relevance score
                }
            )

        return related_searches

    def _extract_competitors(self, raw_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract competitor data from competitors array.

        POP API provides competitors with:
        - url: competitor page URL
        - title: page title
        - pageScore: optimization score
        - plus additional data like h2Texts, h3Texts, schemaTypes, etc.
        """
        competitors: list[dict[str, Any]] = []
        competitors_data = raw_data.get("competitors", [])

        if not isinstance(competitors_data, list):
            return competitors

        for idx, item in enumerate(competitors_data):
            if not isinstance(item, dict):
                continue

            url = item.get("url")
            if not url:
                continue

            page_score = item.get("pageScore")

            competitors.append(
                {
                    "url": str(url),
                    "title": str(item.get("title", "")) if item.get("title") else None,
                    "page_score": float(page_score)
                    if isinstance(page_score, (int, float))
                    else None,
                    "word_count": None,  # POP doesn't provide word count directly per competitor
                    "position": idx + 1,  # Infer position from array order
                }
            )

        return competitors

    def _extract_page_score_target(self, raw_data: dict[str, Any]) -> float | None:
        """Extract page score target from POP response.

        POP API provides pageScore or pageScoreValue at top level
        of cleanedContentBrief.
        """
        # Try cleanedContentBrief first
        content_brief = raw_data.get("cleanedContentBrief", {})
        if isinstance(content_brief, dict):
            page_score = content_brief.get("pageScore")
            if isinstance(page_score, (int, float)):
                return float(page_score)

            page_score_value = content_brief.get("pageScoreValue")
            if page_score_value is not None:
                try:
                    return float(page_score_value)
                except (ValueError, TypeError):
                    pass

        # Try top-level
        page_score = raw_data.get("pageScore")
        if isinstance(page_score, (int, float)):
            return float(page_score)

        return None

    async def fetch_brief(
        self,
        project_id: str,
        page_id: str,
        keyword: str,
        target_url: str,
    ) -> POPContentBriefResult:
        """Fetch a content brief from POP API for a keyword/URL.

        Creates a POP report task, polls for completion, and parses
        the results into a structured content brief.

        Args:
            project_id: Project ID for logging context
            page_id: Page ID for logging context
            keyword: Target keyword for content optimization
            target_url: URL of the page to optimize

        Returns:
            POPContentBriefResult with brief data or error
        """
        start_time = time.monotonic()

        # Method entry log with sanitized parameters
        logger.debug(
            "fetch_brief method entry",
            extra={
                "project_id": project_id,
                "page_id": page_id,
                "keyword": keyword[:50] if keyword else "",
                "target_url": target_url[:100] if target_url else "",
            },
        )

        # Validate inputs
        if not keyword or not keyword.strip():
            logger.warning(
                "Content brief validation failed - empty keyword",
                extra={
                    "field": "keyword",
                    "value": "",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            raise POPContentBriefValidationError(
                "keyword",
                "",
                "Keyword cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        if not target_url or not target_url.strip():
            logger.warning(
                "Content brief validation failed - empty target_url",
                extra={
                    "field": "target_url",
                    "value": "",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            raise POPContentBriefValidationError(
                "target_url",
                "",
                "Target URL cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        keyword = keyword.strip()
        target_url = target_url.strip()

        try:
            client = await self._get_client()

            # Phase transition: brief_fetch_started
            logger.info(
                "brief_fetch_started",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": keyword[:50],
                    "target_url": target_url[:100],
                },
            )

            # Step 1: Create report task
            logger.info(
                "Creating POP report task for content brief",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": keyword[:50],
                },
            )

            task_result = await client.create_report_task(
                keyword=keyword,
                url=target_url,
            )

            if not task_result.success or not task_result.task_id:
                duration_ms = (time.monotonic() - start_time) * 1000
                logger.error(
                    "Failed to create POP report task",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "keyword": keyword[:50],
                        "error": task_result.error,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                # Method exit log on task creation failure
                logger.debug(
                    "fetch_brief method exit",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "success": False,
                        "brief_id": None,
                        "error": task_result.error,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                return POPContentBriefResult(
                    success=False,
                    keyword=keyword,
                    target_url=target_url,
                    error=task_result.error or "Failed to create report task",
                    duration_ms=duration_ms,
                    request_id=task_result.request_id,
                )

            task_id = task_result.task_id

            logger.info(
                "POP report task created, polling for results",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": keyword[:50],
                    "task_id": task_id,
                },
            )

            # Step 2: Poll for task completion
            poll_result = await client.poll_for_result(task_id)

            if not poll_result.success:
                duration_ms = (time.monotonic() - start_time) * 1000
                logger.error(
                    "POP task polling failed",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "keyword": keyword[:50],
                        "task_id": task_id,
                        "error": poll_result.error,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                # Method exit log on polling failure
                logger.debug(
                    "fetch_brief method exit",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "task_id": task_id,
                        "success": False,
                        "brief_id": None,
                        "error": poll_result.error,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                return POPContentBriefResult(
                    success=False,
                    keyword=keyword,
                    target_url=target_url,
                    task_id=task_id,
                    error=poll_result.error or "Task polling failed",
                    duration_ms=duration_ms,
                    request_id=poll_result.request_id,
                )

            if poll_result.status == POPTaskStatus.FAILURE:
                duration_ms = (time.monotonic() - start_time) * 1000
                error_msg = poll_result.data.get("error") if poll_result.data else None
                logger.error(
                    "POP task failed",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "keyword": keyword[:50],
                        "task_id": task_id,
                        "error": error_msg,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                # Method exit log on task failure
                logger.debug(
                    "fetch_brief method exit",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "task_id": task_id,
                        "success": False,
                        "brief_id": None,
                        "error": error_msg,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                return POPContentBriefResult(
                    success=False,
                    keyword=keyword,
                    target_url=target_url,
                    task_id=task_id,
                    error=error_msg or "Task failed",
                    raw_response=poll_result.data,
                    duration_ms=duration_ms,
                    request_id=poll_result.request_id,
                )

            # Step 3: Parse the response data
            raw_data = poll_result.data
            parsed = self._parse_brief_data(raw_data)

            duration_ms = (time.monotonic() - start_time) * 1000

            # Brief extraction stats at INFO level
            logger.info(
                "brief_extraction_stats",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "task_id": task_id,
                    "word_count_target": parsed.get("word_count_target"),
                    "word_count_min": parsed.get("word_count_min"),
                    "word_count_max": parsed.get("word_count_max"),
                    "lsi_term_count": len(parsed.get("lsi_terms", [])),
                    "competitor_count": len(parsed.get("competitors", [])),
                    "heading_target_count": len(parsed.get("heading_targets", [])),
                    "keyword_target_count": len(parsed.get("keyword_targets", [])),
                    "related_question_count": len(parsed.get("related_questions", [])),
                    "page_score_target": parsed.get("page_score_target"),
                },
            )

            # Phase transition: brief_fetch_completed
            logger.info(
                "brief_fetch_completed",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": keyword[:50],
                    "task_id": task_id,
                    "success": True,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow content brief fetch operation",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "task_id": task_id,
                        "keyword": keyword[:50],
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    },
                )

            result = POPContentBriefResult(
                success=True,
                keyword=keyword,
                target_url=target_url,
                task_id=task_id,
                word_count_target=parsed.get("word_count_target"),
                word_count_min=parsed.get("word_count_min"),
                word_count_max=parsed.get("word_count_max"),
                heading_targets=parsed.get("heading_targets", []),
                keyword_targets=parsed.get("keyword_targets", []),
                lsi_terms=parsed.get("lsi_terms", []),
                entities=parsed.get("entities", []),
                related_questions=parsed.get("related_questions", []),
                related_searches=parsed.get("related_searches", []),
                competitors=parsed.get("competitors", []),
                page_score_target=parsed.get("page_score_target"),
                raw_response=raw_data,
                duration_ms=duration_ms,
                request_id=poll_result.request_id,
            )

            # Method exit log with result summary
            logger.debug(
                "fetch_brief method exit",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "task_id": task_id,
                    "success": True,
                    "brief_id": None,  # Not saved yet at this point
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return result

        except POPContentBriefValidationError:
            raise
        except POPError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "POP API error during content brief fetch",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": keyword[:50],
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            # Method exit log on error
            logger.debug(
                "fetch_brief method exit",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "success": False,
                    "brief_id": None,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
            )
            return POPContentBriefResult(
                success=False,
                keyword=keyword,
                target_url=target_url,
                error=str(e),
                duration_ms=duration_ms,
                request_id=getattr(e, "request_id", None),
            )
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Unexpected error during content brief fetch",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": keyword[:50],
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            # Method exit log on unexpected error
            logger.debug(
                "fetch_brief method exit",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "success": False,
                    "brief_id": None,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
            )
            return POPContentBriefResult(
                success=False,
                keyword=keyword,
                target_url=target_url,
                error=f"Unexpected error: {e}",
                duration_ms=duration_ms,
            )

    async def fetch_and_save_brief(
        self,
        project_id: str,
        page_id: str,
        keyword: str,
        target_url: str,
    ) -> POPContentBriefResult:
        """Fetch a content brief from POP API and save it to the database.

        This is a convenience method that combines fetch_brief() and save_brief()
        into a single operation. After successful fetch, the brief is automatically
        persisted to the database. If a brief already exists for the same page,
        it will be replaced.

        Args:
            project_id: Project ID for logging context
            page_id: Page ID (FK to crawled_pages) - required for persistence
            keyword: Target keyword for content optimization
            target_url: URL of the page to optimize

        Returns:
            POPContentBriefResult with brief data and brief_id (if saved) or error

        Raises:
            POPContentBriefValidationError: If validation fails
            POPContentBriefServiceError: If persistence fails (session not available)
        """
        # Method entry log with sanitized parameters
        logger.debug(
            "fetch_and_save_brief method entry",
            extra={
                "project_id": project_id,
                "page_id": page_id,
                "keyword": keyword[:50] if keyword else "",
                "target_url": target_url[:100] if target_url else "",
            },
        )

        # Step 1: Fetch the brief from POP API
        result = await self.fetch_brief(
            project_id=project_id,
            page_id=page_id,
            keyword=keyword,
            target_url=target_url,
        )

        # Step 2: If fetch was successful and we have a session, save to database
        if result.success and self._session is not None:
            try:
                brief = await self.save_brief(
                    page_id=page_id,
                    keyword=keyword,
                    result=result,
                    project_id=project_id,
                )

                # Update result with the database record ID
                result.brief_id = brief.id

                logger.info(
                    "Content brief fetched and saved successfully",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "brief_id": brief.id,
                        "keyword": keyword[:50],
                        "task_id": result.task_id,
                    },
                )

                # Method exit log with result summary (success with save)
                logger.debug(
                    "fetch_and_save_brief method exit",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "brief_id": brief.id,
                        "task_id": result.task_id,
                        "success": True,
                        "saved": True,
                    },
                )

            except POPContentBriefServiceError:
                # Re-raise persistence errors
                raise
            except Exception as e:
                logger.error(
                    "Failed to save content brief after successful fetch",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "task_id": result.task_id,
                        "keyword": keyword[:50],
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "stack_trace": traceback.format_exc(),
                    },
                    exc_info=True,
                )
                raise POPContentBriefServiceError(
                    f"Failed to save content brief: {e}",
                    project_id=project_id,
                    page_id=page_id,
                ) from e

        elif result.success and self._session is None:
            logger.warning(
                "Content brief fetched but not saved - no database session",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "task_id": result.task_id,
                    "keyword": keyword[:50],
                },
            )

            # Method exit log with result summary (success without save)
            logger.debug(
                "fetch_and_save_brief method exit",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "brief_id": None,
                    "task_id": result.task_id,
                    "success": True,
                    "saved": False,
                },
            )

        else:
            # Fetch failed
            logger.debug(
                "fetch_and_save_brief method exit",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "brief_id": None,
                    "success": False,
                    "saved": False,
                    "error": result.error,
                },
            )

        return result


# Global singleton instance
_pop_content_brief_service: POPContentBriefService | None = None


def get_pop_content_brief_service() -> POPContentBriefService:
    """Get the global POP content brief service instance.

    Usage:
        from app.services.pop_content_brief import get_pop_content_brief_service
        service = get_pop_content_brief_service()
        result = await service.fetch_brief(
            project_id="uuid",
            page_id="uuid",
            keyword="hiking boots",
            target_url="https://example.com/hiking-boots",
        )
    """
    global _pop_content_brief_service
    if _pop_content_brief_service is None:
        _pop_content_brief_service = POPContentBriefService()
        logger.info("POPContentBriefService singleton created")
    return _pop_content_brief_service


async def fetch_content_brief(
    project_id: str,
    page_id: str,
    keyword: str,
    target_url: str,
) -> POPContentBriefResult:
    """Convenience function for fetching a content brief.

    Args:
        project_id: Project ID for logging context
        page_id: Page ID for logging context
        keyword: Target keyword for content optimization
        target_url: URL of the page to optimize

    Returns:
        POPContentBriefResult with brief data or error
    """
    service = get_pop_content_brief_service()
    return await service.fetch_brief(
        project_id=project_id,
        page_id=page_id,
        keyword=keyword,
        target_url=target_url,
    )


async def fetch_and_save_content_brief(
    session: AsyncSession,
    project_id: str,
    page_id: str,
    keyword: str,
    target_url: str,
) -> POPContentBriefResult:
    """Convenience function for fetching and saving a content brief.

    This function creates a new service instance with the provided session,
    fetches the content brief from POP API, and saves it to the database.
    If a brief already exists for the same page, it will be replaced.

    Args:
        session: Async SQLAlchemy session for database operations
        project_id: Project ID for logging context
        page_id: Page ID (FK to crawled_pages) - required for persistence
        keyword: Target keyword for content optimization
        target_url: URL of the page to optimize

    Returns:
        POPContentBriefResult with brief data and brief_id (if saved) or error

    Example:
        async with get_session() as session:
            result = await fetch_and_save_content_brief(
                session=session,
                project_id="uuid",
                page_id="uuid",
                keyword="hiking boots",
                target_url="https://example.com/hiking-boots",
            )
            if result.success:
                print(f"Brief saved with ID: {result.brief_id}")
    """
    service = POPContentBriefService(session=session)
    return await service.fetch_and_save_brief(
        project_id=project_id,
        page_id=page_id,
        keyword=keyword,
        target_url=target_url,
    )
