"""PAA question intent categorization service using LLM.

Categorizes PAA (People Also Ask) questions by user intent:
- buying: Questions about purchasing, pricing, recommendations
- usage: Questions about how to use, methods, processes
- care: Questions about maintenance, cleaning, longevity
- comparison: Questions comparing products, alternatives, vs

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import asyncio
import json
import time
import traceback
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient, get_claude
from app.services.paa_enrichment import PAAQuestion, PAAQuestionIntent

logger = get_logger(__name__)

# Constants
SLOW_OPERATION_THRESHOLD_MS = 1000
DEFAULT_MAX_CONCURRENT = 5
DEFAULT_BATCH_SIZE = 10  # Questions per LLM call


# System prompt for intent categorization
INTENT_CATEGORIZATION_SYSTEM_PROMPT = """You are an expert at analyzing user search intent. Your task is to categorize "People Also Ask" questions by the user's underlying intent.

Intent categories:
- buying: Questions about purchasing decisions, pricing, where to buy, best products, recommendations, value for money
- usage: Questions about how to use something, methods, processes, techniques, instructions, getting started
- care: Questions about maintenance, cleaning, storage, longevity, preservation, repairs, extending lifespan
- comparison: Questions comparing products, alternatives, differences, "vs" comparisons, choosing between options

Respond ONLY with valid JSON in this exact format:
{
  "categorizations": [
    {
      "question": "<original question text>",
      "intent": "<buying|usage|care|comparison>",
      "confidence": <0.0-1.0>,
      "reasoning": "<brief explanation>"
    }
  ]
}

Guidelines:
- Choose the single most appropriate intent category
- Score 0.8-1.0: Clear, unambiguous intent
- Score 0.6-0.8: Likely intent, some ambiguity
- Score 0.4-0.6: Unclear, could be multiple intents
- Keep reasoning brief (1 short sentence)
- Default to "usage" if the question is informational but unclear
- Questions about "best" or "top" products are typically "buying"
- Questions about "how to" clean/maintain are "care", not "usage"
- Questions with "vs" or "or" comparing options are "comparison"
"""


@dataclass
class CategorizationItem:
    """A single question with its categorization result."""

    question: str
    intent: PAAQuestionIntent = PAAQuestionIntent.UNKNOWN
    confidence: float = 0.0
    reasoning: str | None = None


@dataclass
class CategorizationResult:
    """Result of PAA question categorization operation."""

    success: bool
    categorizations: list[CategorizationItem] = field(default_factory=list)
    error: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    duration_ms: float = 0.0
    request_id: str | None = None

    @property
    def categorized_count(self) -> int:
        """Count of successfully categorized questions."""
        return len([c for c in self.categorizations if c.intent != PAAQuestionIntent.UNKNOWN])


class PAACategorizationServiceError(Exception):
    """Base exception for PAA categorization service errors."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.page_id = page_id


class PAACategorizationValidationError(PAACategorizationServiceError):
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


class PAACategorizationService:
    """Service for categorizing PAA questions by user intent.

    Uses Claude LLM to classify questions into intent categories:
    - buying: Purchase decisions, recommendations
    - usage: How to use, methods, processes
    - care: Maintenance, cleaning, longevity
    - comparison: Comparing options, alternatives

    Features:
    - Batch processing for efficient LLM usage
    - Configurable batch size and concurrency
    - Comprehensive logging per requirements

    Usage:
        service = PAACategorizationService()
        result = await service.categorize_questions(
            questions=["What is the best hiking boot?", "How to clean hiking boots?"],
            keyword="hiking boots",
        )
    """

    def __init__(
        self,
        claude_client: ClaudeClient | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
    ) -> None:
        """Initialize PAA categorization service.

        Args:
            claude_client: Claude client instance. If None, uses global.
            batch_size: Questions per LLM call (default 10).
            max_concurrent: Max concurrent LLM calls (default 5).
        """
        self._claude_client = claude_client
        self._batch_size = batch_size
        self._max_concurrent = max_concurrent

        logger.debug(
            "PAACategorizationService initialized",
            extra={
                "batch_size": self._batch_size,
                "max_concurrent": self._max_concurrent,
            },
        )

    async def _get_claude_client(self) -> ClaudeClient:
        """Get Claude client instance."""
        if self._claude_client is None:
            self._claude_client = await get_claude()
        return self._claude_client

    def _parse_intent(self, intent_str: str) -> PAAQuestionIntent:
        """Parse intent string to PAAQuestionIntent enum.

        Args:
            intent_str: Intent string from LLM response

        Returns:
            PAAQuestionIntent enum value
        """
        intent_lookup = {
            "buying": PAAQuestionIntent.BUYING,
            "usage": PAAQuestionIntent.USAGE,
            "care": PAAQuestionIntent.CARE,
            "comparison": PAAQuestionIntent.COMPARISON,
        }
        intent_lower = intent_str.lower().strip()
        return intent_lookup.get(intent_lower, PAAQuestionIntent.UNKNOWN)

    async def _categorize_batch(
        self,
        questions: list[str],
        keyword: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> CategorizationResult:
        """Categorize a batch of questions using Claude.

        Args:
            questions: List of question texts
            keyword: Original keyword context
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            CategorizationResult with categorized questions
        """
        start_time = time.monotonic()
        claude = await self._get_claude_client()

        logger.debug(
            "Categorizing batch of questions",
            extra={
                "question_count": len(questions),
                "keyword": keyword[:50],
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        if not questions:
            return CategorizationResult(
                success=True,
                categorizations=[],
                duration_ms=0.0,
            )

        # Build user prompt
        questions_list = "\n".join(f"- {q}" for q in questions)
        user_prompt = f"""Categorize these "People Also Ask" questions by user intent.

Context keyword: "{keyword}"

Questions:
{questions_list}

For each question, determine if the user intent is:
- buying (purchase decisions, recommendations, pricing)
- usage (how to use, methods, instructions)
- care (maintenance, cleaning, storage)
- comparison (comparing options, alternatives)

Respond with JSON only."""

        result = await claude.complete(
            user_prompt=user_prompt,
            system_prompt=INTENT_CATEGORIZATION_SYSTEM_PROMPT,
            temperature=0.0,  # Deterministic
            max_tokens=2048,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        if not result.success:
            logger.warning(
                "LLM categorization failed",
                extra={
                    "keyword": keyword[:50],
                    "question_count": len(questions),
                    "error": result.error,
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            # Return questions with UNKNOWN intent
            return CategorizationResult(
                success=False,
                categorizations=[
                    CategorizationItem(question=q, intent=PAAQuestionIntent.UNKNOWN)
                    for q in questions
                ],
                error=result.error,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                duration_ms=duration_ms,
                request_id=result.request_id,
            )

        # Parse LLM response
        try:
            response_text = result.text or ""
            json_text = response_text.strip()

            # Handle markdown code blocks
            if json_text.startswith("```"):
                lines = json_text.split("\n")
                lines = lines[1:]  # Remove first line
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                json_text = "\n".join(lines)

            parsed = json.loads(json_text)
            categorizations_data = parsed.get("categorizations", [])

            # Build lookup by normalized question
            cat_lookup: dict[str, dict[str, Any]] = {}
            for cat_data in categorizations_data:
                question = cat_data.get("question", "")
                cat_lookup[question.lower().strip()] = cat_data

            # Map results back to original questions
            categorizations: list[CategorizationItem] = []
            for question in questions:
                cat_data = cat_lookup.get(question.lower().strip(), {})

                intent_str = cat_data.get("intent", "unknown")
                intent = self._parse_intent(intent_str)
                confidence = float(cat_data.get("confidence", 0.0))
                reasoning = cat_data.get("reasoning")

                categorizations.append(
                    CategorizationItem(
                        question=question,
                        intent=intent,
                        confidence=confidence,
                        reasoning=reasoning,
                    )
                )

            logger.debug(
                "Batch categorization complete",
                extra={
                    "keyword": keyword[:50],
                    "question_count": len(questions),
                    "categorized_count": len([c for c in categorizations if c.intent != PAAQuestionIntent.UNKNOWN]),
                    "duration_ms": round(duration_ms, 2),
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow batch categorization operation",
                    extra={
                        "keyword": keyword[:50],
                        "question_count": len(questions),
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    },
                )

            return CategorizationResult(
                success=True,
                categorizations=categorizations,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                duration_ms=duration_ms,
                request_id=result.request_id,
            )

        except json.JSONDecodeError as e:
            logger.warning(
                "Failed to parse LLM categorization response",
                extra={
                    "keyword": keyword[:50],
                    "error": str(e),
                    "response": (result.text or "")[:500],
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            # Return questions with UNKNOWN intent
            return CategorizationResult(
                success=False,
                categorizations=[
                    CategorizationItem(question=q, intent=PAAQuestionIntent.UNKNOWN)
                    for q in questions
                ],
                error=f"Failed to parse response: {e}",
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                duration_ms=duration_ms,
                request_id=result.request_id,
            )

    async def categorize_questions(
        self,
        questions: list[str],
        keyword: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> CategorizationResult:
        """Categorize PAA questions by user intent.

        Processes questions in batches for efficient LLM usage.

        Args:
            questions: List of question texts to categorize
            keyword: Original keyword context (helps LLM understand domain)
            project_id: Project ID for logging context
            page_id: Page ID for logging context

        Returns:
            CategorizationResult with all categorized questions
        """
        start_time = time.monotonic()

        logger.debug(
            "PAA categorization started",
            extra={
                "question_count": len(questions),
                "keyword": keyword[:50],
                "batch_size": self._batch_size,
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        # Validate inputs
        if not keyword or not keyword.strip():
            logger.warning(
                "PAA categorization validation failed - empty keyword",
                extra={
                    "field": "keyword",
                    "value": "",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            raise PAACategorizationValidationError(
                "keyword",
                "",
                "Keyword cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        keyword = keyword.strip()

        if not questions:
            logger.debug(
                "No questions to categorize",
                extra={
                    "keyword": keyword[:50],
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            return CategorizationResult(
                success=True,
                categorizations=[],
                duration_ms=0.0,
            )

        try:
            # Split into batches
            batches: list[list[str]] = []
            for i in range(0, len(questions), self._batch_size):
                batches.append(questions[i:i + self._batch_size])

            logger.info(
                "Processing PAA categorization batches",
                extra={
                    "keyword": keyword[:50],
                    "question_count": len(questions),
                    "batch_count": len(batches),
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            # Process batches with rate limiting
            semaphore = asyncio.Semaphore(self._max_concurrent)

            async def process_batch(batch: list[str]) -> CategorizationResult:
                async with semaphore:
                    return await self._categorize_batch(
                        questions=batch,
                        keyword=keyword,
                        project_id=project_id,
                        page_id=page_id,
                    )

            batch_tasks = [process_batch(batch) for batch in batches]
            batch_results = await asyncio.gather(*batch_tasks)

            # Combine results
            all_categorizations: list[CategorizationItem] = []
            total_input_tokens = 0
            total_output_tokens = 0
            all_success = True

            for batch_result in batch_results:
                all_categorizations.extend(batch_result.categorizations)
                if batch_result.input_tokens:
                    total_input_tokens += batch_result.input_tokens
                if batch_result.output_tokens:
                    total_output_tokens += batch_result.output_tokens
                if not batch_result.success:
                    all_success = False

            duration_ms = (time.monotonic() - start_time) * 1000

            logger.info(
                "PAA categorization complete",
                extra={
                    "keyword": keyword[:50],
                    "question_count": len(questions),
                    "categorized_count": len([c for c in all_categorizations if c.intent != PAAQuestionIntent.UNKNOWN]),
                    "duration_ms": round(duration_ms, 2),
                    "total_input_tokens": total_input_tokens,
                    "total_output_tokens": total_output_tokens,
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow PAA categorization operation",
                    extra={
                        "keyword": keyword[:50],
                        "question_count": len(questions),
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    },
                )

            return CategorizationResult(
                success=all_success,
                categorizations=all_categorizations,
                input_tokens=total_input_tokens if total_input_tokens > 0 else None,
                output_tokens=total_output_tokens if total_output_tokens > 0 else None,
                duration_ms=duration_ms,
            )

        except PAACategorizationValidationError:
            raise
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "PAA categorization unexpected error",
                extra={
                    "keyword": keyword[:50],
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "page_id": page_id,
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return CategorizationResult(
                success=False,
                categorizations=[
                    CategorizationItem(question=q, intent=PAAQuestionIntent.UNKNOWN)
                    for q in questions
                ],
                error=f"Unexpected error: {e}",
                duration_ms=duration_ms,
            )

    async def categorize_paa_questions(
        self,
        paa_questions: list[PAAQuestion],
        keyword: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> list[PAAQuestion]:
        """Categorize PAA question objects and update their intent.

        Convenience method that takes PAAQuestion objects and returns
        them with updated intent fields.

        Args:
            paa_questions: List of PAAQuestion objects
            keyword: Original keyword context
            project_id: Project ID for logging context
            page_id: Page ID for logging context

        Returns:
            List of PAAQuestion objects with updated intent fields
        """
        if not paa_questions:
            return []

        # Extract question texts
        question_texts = [q.question for q in paa_questions]

        # Categorize
        result = await self.categorize_questions(
            questions=question_texts,
            keyword=keyword,
            project_id=project_id,
            page_id=page_id,
        )

        # Build lookup by normalized question text
        cat_lookup: dict[str, CategorizationItem] = {}
        for cat in result.categorizations:
            cat_lookup[cat.question.lower().strip()] = cat

        # Update PAA questions with intents
        updated_questions: list[PAAQuestion] = []
        for paa_q in paa_questions:
            cat_item = cat_lookup.get(paa_q.question.lower().strip())
            if cat_item is not None:
                paa_q.intent = cat_item.intent
            updated_questions.append(paa_q)

        logger.debug(
            "PAA questions categorized",
            extra={
                "keyword": keyword[:50],
                "total_count": len(paa_questions),
                "categorized_count": len([q for q in updated_questions if q.intent != PAAQuestionIntent.UNKNOWN]),
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        return updated_questions


# Global singleton instance
_paa_categorization_service: PAACategorizationService | None = None


def get_paa_categorization_service() -> PAACategorizationService:
    """Get the global PAA categorization service instance.

    Usage:
        from app.services.paa_categorization import get_paa_categorization_service
        service = get_paa_categorization_service()
        result = await service.categorize_questions(questions, keyword)
    """
    global _paa_categorization_service
    if _paa_categorization_service is None:
        _paa_categorization_service = PAACategorizationService()
        logger.info("PAACategorizationService singleton created")
    return _paa_categorization_service


async def categorize_paa_questions(
    questions: list[str],
    keyword: str,
    project_id: str | None = None,
    page_id: str | None = None,
) -> CategorizationResult:
    """Convenience function for PAA question categorization.

    Args:
        questions: List of question texts to categorize
        keyword: Original keyword context
        project_id: Project ID for logging
        page_id: Page ID for logging

    Returns:
        CategorizationResult with categorized questions
    """
    service = get_paa_categorization_service()
    return await service.categorize_questions(
        questions=questions,
        keyword=keyword,
        project_id=project_id,
        page_id=page_id,
    )
