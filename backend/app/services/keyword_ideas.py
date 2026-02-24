"""KeywordIdeaService for generating 20-30 keyword ideas per collection.

Implements Step 1 of the keyword research workflow: LLM-based keyword idea
generation for collection pages.

Features:
- LLM-based keyword generation via Claude
- Generates 20-30 keyword variations per collection
- Includes long-tail variations (3-5 words)
- Includes question-based keywords
- Includes comparison keywords
- Avoids brand names unless instructed
- Comprehensive error logging per requirements

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient, get_claude

logger = get_logger(__name__)

# Threshold for logging slow operations (in milliseconds)
SLOW_OPERATION_THRESHOLD_MS = 1000

# Keyword idea constraints
MIN_IDEAS = 20
MAX_IDEAS = 30
MAX_KEYWORD_LENGTH = 100


# =============================================================================
# LLM PROMPT TEMPLATES FOR KEYWORD IDEA GENERATION
# =============================================================================
#
# These prompts are used to generate 20-30 keyword ideas for a collection page.
# The prompts are designed to:
# 1. Generate diverse keyword variations
# 2. Include long-tail variations (3-5 words)
# 3. Include question-based keywords
# 4. Include comparison keywords
# 5. Avoid brand names unless instructed
#
# Usage:
#   system_prompt = KEYWORD_IDEA_SYSTEM_PROMPT
#   user_prompt = KEYWORD_IDEA_USER_PROMPT_TEMPLATE.format(
#       collection_title=...,
#       url=...,
#       content_excerpt=...,
#   )

KEYWORD_IDEA_SYSTEM_PROMPT = """You are a keyword research expert specializing in e-commerce SEO. Your task is to generate keyword ideas for collection pages that will help them rank in search engines.

## Keyword Requirements

Generate exactly 20-30 keyword ideas that:
1. **Relevance**: Directly relate to the products in the collection
2. **Diversity**: Include a mix of keyword types:
   - Primary search terms (what people search to find these products)
   - Long-tail variations (3-5 words, more specific)
   - Question keywords ("best X for Y", "how to choose X", "what is the best X")
   - Comparison keywords ("X vs Y", "X or Y")
3. **Searchability**: Terms people actually search for, not marketing jargon
4. **No brand names**: Avoid specific brand names unless the page is about a brand

## Response Format

Return ONLY a JSON array of keywords (no markdown, no explanation):
["keyword 1", "keyword 2", "keyword 3", ...]

## Guidelines

- Return between 20-30 keywords (aim for 25)
- Each keyword should be 1-6 words
- Use lowercase unless proper nouns
- Include singular and plural variations where appropriate
- Focus on commercial and informational intent keywords
- Include both head terms and long-tail variations"""

KEYWORD_IDEA_USER_PROMPT_TEMPLATE = """Generate 20-30 keyword ideas for this collection page.

Collection: {collection_title}
URL: {url}
Products include: {content_excerpt}

Include:
- Primary search terms (what people search to find these products)
- Long-tail variations (3-5 words)
- Question keywords ("best X for Y", "how to choose X")
- Comparison keywords ("X vs Y")

Return JSON array of keywords only:
["keyword 1", "keyword 2", ...]"""


class KeywordIdeaServiceError(Exception):
    """Base exception for KeywordIdeaService errors."""

    pass


class KeywordIdeaValidationError(KeywordIdeaServiceError):
    """Raised when input validation fails."""

    def __init__(self, field: str, value: Any, message: str):
        self.field = field
        self.value = value
        self.message = message
        super().__init__(f"Validation failed for '{field}': {message}")


class KeywordIdeaGenerationError(KeywordIdeaServiceError):
    """Raised when keyword idea generation fails."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ):
        self.project_id = project_id
        self.page_id = page_id
        super().__init__(message)


@dataclass
class KeywordIdeaRequest:
    """Request for keyword idea generation.

    Attributes:
        collection_title: Title of the collection (e.g., "Coffee Containers")
        url: URL of the collection page
        content_excerpt: First 500-1000 chars of page content (products, descriptions)
        project_id: Project ID for logging
        page_id: Page ID for logging
    """

    collection_title: str
    url: str
    content_excerpt: str = ""
    project_id: str | None = None
    page_id: str | None = None


@dataclass
class KeywordIdeaResult:
    """Result of keyword idea generation.

    Attributes:
        success: Whether generation succeeded
        keywords: Generated keyword ideas (20-30 keywords)
        keyword_count: Number of keywords generated
        error: Error message if failed
        duration_ms: Total time taken
        input_tokens: Claude input tokens used
        output_tokens: Claude output tokens used
        request_id: Claude request ID for debugging
        project_id: Project ID (for logging context)
        page_id: Page ID (for logging context)
    """

    success: bool
    keywords: list[str] = field(default_factory=list)
    keyword_count: int = 0
    error: str | None = None
    duration_ms: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    request_id: str | None = None
    project_id: str | None = None
    page_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "success": self.success,
            "keywords": self.keywords,
            "keyword_count": self.keyword_count,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "request_id": self.request_id,
        }


class KeywordIdeaService:
    """Service for generating keyword ideas for collection pages.

    Uses Claude LLM to generate 20-30 keyword ideas per collection,
    including long-tail variations, question keywords, and comparison keywords.

    Example usage:
        service = KeywordIdeaService()

        result = await service.generate_ideas(
            collection_title="Coffee Containers",
            url="https://example.com/collections/coffee-containers",
            content_excerpt="Airtight coffee canisters, vacuum coffee storage...",
            project_id="abc-123",
            page_id="page-456",
        )

        print(f"Keywords: {result.keywords}")
        # ["airtight coffee containers", "coffee storage containers", ...]
    """

    def __init__(
        self,
        claude_client: ClaudeClient | None = None,
    ) -> None:
        """Initialize the keyword idea service.

        Args:
            claude_client: Claude client for LLM generation (uses global if None)
        """
        logger.debug(
            "KeywordIdeaService.__init__ called",
            extra={
                "has_custom_client": claude_client is not None,
            },
        )

        self._claude_client = claude_client

        logger.debug("KeywordIdeaService initialized")

    async def _get_claude_client(self) -> ClaudeClient | None:
        """Get Claude client for LLM generation."""
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

    def _validate_keyword(self, keyword: str) -> str | None:
        """Validate and normalize a single keyword.

        Args:
            keyword: Keyword to validate

        Returns:
            Normalized keyword or None if invalid
        """
        if not keyword or not isinstance(keyword, str):
            return None

        normalized = keyword.strip()

        if not normalized:
            return None

        if len(normalized) > MAX_KEYWORD_LENGTH:
            logger.debug(
                "Keyword too long, truncating",
                extra={
                    "keyword_preview": normalized[:50],
                    "original_length": len(normalized),
                    "max_length": MAX_KEYWORD_LENGTH,
                },
            )
            normalized = normalized[:MAX_KEYWORD_LENGTH]

        # Normalize: lowercase, remove extra whitespace
        normalized = " ".join(normalized.lower().split())

        return normalized if normalized else None

    def _validate_keywords(self, keywords: list[Any]) -> list[str]:
        """Validate and normalize a list of keywords.

        Args:
            keywords: Keywords to validate

        Returns:
            List of normalized, unique keywords
        """
        validated: list[str] = []
        seen: set[str] = set()

        for keyword in keywords:
            normalized = self._validate_keyword(str(keyword) if keyword else "")
            if normalized and normalized not in seen:
                validated.append(normalized)
                seen.add(normalized)

        return validated

    def _build_prompt(
        self,
        collection_title: str,
        url: str,
        content_excerpt: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> tuple[str, str]:
        """Build the prompt for LLM keyword idea generation.

        Args:
            collection_title: Title of the collection
            url: URL of the collection page
            content_excerpt: Content excerpt from the page
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        logger.debug(
            "_build_prompt() called",
            extra={
                "project_id": project_id,
                "page_id": page_id,
                "collection_title_length": len(collection_title),
                "url_length": len(url),
                "content_excerpt_length": len(content_excerpt),
            },
        )

        # Truncate content excerpt if too long (for token efficiency)
        max_excerpt_length = 1500
        if len(content_excerpt) > max_excerpt_length:
            content_excerpt = content_excerpt[:max_excerpt_length] + "..."
            logger.debug(
                "Truncated content excerpt for prompt",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "truncated_to": max_excerpt_length,
                },
            )

        # Build user prompt from template
        user_prompt = KEYWORD_IDEA_USER_PROMPT_TEMPLATE.format(
            collection_title=collection_title,
            url=url,
            content_excerpt=content_excerpt or "(no content available)",
        )

        logger.debug(
            "_build_prompt() completed",
            extra={
                "project_id": project_id,
                "page_id": page_id,
                "system_prompt_length": len(KEYWORD_IDEA_SYSTEM_PROMPT),
                "user_prompt_length": len(user_prompt),
            },
        )

        return KEYWORD_IDEA_SYSTEM_PROMPT, user_prompt

    async def generate_ideas(
        self,
        collection_title: str,
        url: str,
        content_excerpt: str = "",
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> KeywordIdeaResult:
        """Generate keyword ideas for a collection page.

        Uses Claude LLM to generate 20-30 keyword ideas including
        long-tail variations, question keywords, and comparison keywords.

        Args:
            collection_title: Title of the collection (e.g., "Coffee Containers")
            url: URL of the collection page
            content_excerpt: First 500-1000 chars of page content
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            KeywordIdeaResult with generated keywords and metadata
        """
        start_time = time.monotonic()
        logger.debug(
            "generate_ideas() called",
            extra={
                "project_id": project_id,
                "page_id": page_id,
                "collection_title": collection_title[:100] if collection_title else "",
                "url": url[:200] if url else "",
                "content_excerpt_length": len(content_excerpt) if content_excerpt else 0,
            },
        )

        # Validate inputs
        if not collection_title or not collection_title.strip():
            logger.warning(
                "Validation failed: empty collection_title",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "field": "collection_title",
                    "rejected_value": repr(collection_title),
                },
            )
            return KeywordIdeaResult(
                success=False,
                error="Collection title cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        if not url or not url.strip():
            logger.warning(
                "Validation failed: empty url",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "field": "url",
                    "rejected_value": repr(url),
                },
            )
            return KeywordIdeaResult(
                success=False,
                error="URL cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        # Get Claude client
        claude = await self._get_claude_client()
        if not claude or not claude.available:
            logger.warning(
                "Claude not available for keyword idea generation",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "reason": "client_unavailable",
                },
            )
            return KeywordIdeaResult(
                success=False,
                error="Claude LLM not available (missing API key or service unavailable)",
                project_id=project_id,
                page_id=page_id,
            )

        # Build prompts
        system_prompt, user_prompt = self._build_prompt(
            collection_title=collection_title.strip(),
            url=url.strip(),
            content_excerpt=content_excerpt,
            project_id=project_id,
            page_id=page_id,
        )

        try:
            # Call Claude
            result = await claude.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.7,  # Slightly higher for creative diversity
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            if not result.success or not result.text:
                logger.warning(
                    "LLM keyword idea generation failed",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "error": result.error,
                        "status_code": result.status_code,
                        "request_id": result.request_id,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                return KeywordIdeaResult(
                    success=False,
                    error=result.error or "LLM request failed",
                    duration_ms=round(duration_ms, 2),
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    request_id=result.request_id,
                    project_id=project_id,
                    page_id=page_id,
                )

            # Parse response
            response_text: str = result.text

            # Handle markdown code blocks (LLM may wrap JSON in code fences)
            original_response = response_text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
                logger.debug(
                    "Extracted JSON from markdown code block",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "fence_type": "json",
                    },
                )
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
                logger.debug(
                    "Extracted JSON from generic code block",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "fence_type": "generic",
                    },
                )

            response_text = response_text.strip()

            try:
                parsed = json.loads(response_text)

                # Validate response is a list
                if not isinstance(parsed, list):
                    logger.warning(
                        "Validation failed: LLM response is not a list",
                        extra={
                            "project_id": project_id,
                            "page_id": page_id,
                            "field": "response",
                            "rejected_value": type(parsed).__name__,
                            "expected_type": "list",
                        },
                    )
                    return KeywordIdeaResult(
                        success=False,
                        error="LLM response is not a list of keywords",
                        duration_ms=round(duration_ms, 2),
                        input_tokens=result.input_tokens,
                        output_tokens=result.output_tokens,
                        request_id=result.request_id,
                        project_id=project_id,
                        page_id=page_id,
                    )

                # Validate and normalize keywords
                original_count = len(parsed)
                keywords = self._validate_keywords(parsed)

                if len(keywords) < original_count:
                    logger.debug(
                        "Some keywords filtered during validation",
                        extra={
                            "project_id": project_id,
                            "page_id": page_id,
                            "original_count": original_count,
                            "validated_count": len(keywords),
                        },
                    )

                # Log if keyword count is outside expected range
                if len(keywords) < MIN_IDEAS:
                    logger.warning(
                        "Fewer keywords than expected",
                        extra={
                            "project_id": project_id,
                            "page_id": page_id,
                            "keyword_count": len(keywords),
                            "min_expected": MIN_IDEAS,
                        },
                    )
                elif len(keywords) > MAX_IDEAS:
                    logger.debug(
                        "More keywords than expected, keeping all",
                        extra={
                            "project_id": project_id,
                            "page_id": page_id,
                            "keyword_count": len(keywords),
                            "max_expected": MAX_IDEAS,
                        },
                    )

                # Log state transition: generation complete
                logger.info(
                    "Keyword idea generation complete",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "keyword_count": len(keywords),
                        "duration_ms": round(duration_ms, 2),
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                        "request_id": result.request_id,
                    },
                )

                if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                    logger.warning(
                        "Slow keyword idea generation",
                        extra={
                            "project_id": project_id,
                            "page_id": page_id,
                            "duration_ms": round(duration_ms, 2),
                            "input_tokens": result.input_tokens,
                            "output_tokens": result.output_tokens,
                        },
                    )

                return KeywordIdeaResult(
                    success=True,
                    keywords=keywords,
                    keyword_count=len(keywords),
                    duration_ms=round(duration_ms, 2),
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    request_id=result.request_id,
                    project_id=project_id,
                    page_id=page_id,
                )

            except json.JSONDecodeError as e:
                logger.warning(
                    "Validation failed: LLM response is not valid JSON",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "field": "response",
                        "rejected_value": response_text[:200],
                        "error": str(e),
                        "error_position": e.pos if hasattr(e, "pos") else None,
                        "original_response_preview": original_response[:200],
                    },
                )
                return KeywordIdeaResult(
                    success=False,
                    error=f"Failed to parse LLM response as JSON: {e}",
                    duration_ms=round(duration_ms, 2),
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    request_id=result.request_id,
                    project_id=project_id,
                    page_id=page_id,
                )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Keyword idea generation exception",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
                exc_info=True,
            )
            return KeywordIdeaResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
                duration_ms=round(duration_ms, 2),
                project_id=project_id,
                page_id=page_id,
            )

    async def generate_ideas_for_request(
        self,
        request: KeywordIdeaRequest,
    ) -> KeywordIdeaResult:
        """Generate keyword ideas using a KeywordIdeaRequest object.

        Convenience method that unpacks a KeywordIdeaRequest.

        Args:
            request: The keyword idea generation request

        Returns:
            KeywordIdeaResult with generated keywords and metadata
        """
        return await self.generate_ideas(
            collection_title=request.collection_title,
            url=request.url,
            content_excerpt=request.content_excerpt,
            project_id=request.project_id,
            page_id=request.page_id,
        )


# Global KeywordIdeaService instance
_keyword_idea_service: KeywordIdeaService | None = None


def get_keyword_idea_service() -> KeywordIdeaService:
    """Get the default KeywordIdeaService instance (singleton).

    Returns:
        Default KeywordIdeaService instance.
    """
    global _keyword_idea_service
    if _keyword_idea_service is None:
        _keyword_idea_service = KeywordIdeaService()
    return _keyword_idea_service


async def generate_keyword_ideas(
    collection_title: str,
    url: str,
    content_excerpt: str = "",
    project_id: str | None = None,
    page_id: str | None = None,
) -> KeywordIdeaResult:
    """Convenience function to generate keyword ideas for a collection.

    Uses the default KeywordIdeaService singleton.

    Args:
        collection_title: Title of the collection
        url: URL of the collection page
        content_excerpt: Content excerpt from the page
        project_id: Project ID for logging
        page_id: Page ID for logging

    Returns:
        KeywordIdeaResult with generated keywords and metadata

    Example:
        >>> result = await generate_keyword_ideas(
        ...     collection_title="Coffee Containers",
        ...     url="https://example.com/collections/coffee-containers",
        ...     content_excerpt="Airtight coffee canisters, vacuum coffee storage...",
        ...     project_id="abc-123",
        ...     page_id="page-456",
        ... )
        >>> print(result.keywords)
        ['airtight coffee containers', 'coffee storage containers', ...]
    """
    service = get_keyword_idea_service()
    return await service.generate_ideas(
        collection_title=collection_title,
        url=url,
        content_excerpt=content_excerpt,
        project_id=project_id,
        page_id=page_id,
    )
