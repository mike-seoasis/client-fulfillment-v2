"""Phase 5C: LLM QA fix service for minimal content corrections.

Uses Claude to fix AI trope patterns that regex-based detection might miss.
Makes minimal changes while preserving:
- Content structure (headings, paragraphs)
- Internal links (HTML anchors)
- Word count targets (300-450 words)
- Primary keyword usage

Features:
- JSON-structured LLM output for reliable parsing
- Detailed fix tracking (original vs fixed text)
- Batch processing with configurable concurrency
- Circuit breaker integration via Claude client

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

logger = get_logger(__name__)

# Constants
SLOW_OPERATION_THRESHOLD_MS = 1000
DEFAULT_MAX_CONCURRENT = 5  # Max concurrent LLM calls
LLM_TEMPERATURE = 0.3  # Slightly creative but controlled
LLM_MAX_TOKENS = 4096  # Enough for full content response


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

LLM_QA_FIX_SYSTEM_PROMPT = """You are a QA editor fixing e-commerce content for AI-generated writing patterns.

Your job is to make MINIMAL changes that fix specific issues while preserving:
1. Content structure (headings, paragraphs, HTML tags)
2. All internal links (preserve <a href="...">...</a> exactly)
3. Word count (keep within 300-450 words for bottom description)
4. Primary keyword usage and placement
5. The overall meaning and selling points

IMPORTANT RULES:
- Make the SMALLEST change that fixes the issue
- Never add new content, only modify problematic parts
- Preserve all HTML structure and links exactly
- Keep the same paragraph structure
- Maintain the same approximate word count
- Use conversational, human-sounding language

When fixing common AI patterns:
- Negation patterns ("aren't just X, they're Y") → Rewrite as direct benefit statement
- Banned words (delve, unlock, journey) → Use simpler, specific alternatives
- Em dashes (—) → Replace with periods or commas
- Triplet patterns (Fast. Simple. Powerful.) → Combine into a complete sentence
- Rhetorical questions at paragraph start → Convert to declarative statements

Respond ONLY with valid JSON in this exact format:
{
  "issues_found": ["description of issue 1", "description of issue 2"],
  "issues_fixed": ["what you changed for issue 1", "what you changed for issue 2"],
  "fixed_content": "the complete fixed HTML content here"
}

If no issues need fixing, return the content unchanged:
{
  "issues_found": [],
  "issues_fixed": [],
  "fixed_content": "original content unchanged"
}"""


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class IssueToFix:
    """Describes a specific issue that needs to be fixed."""

    issue_type: str
    matched_text: str
    position: int | None = None
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "issue_type": self.issue_type,
            "matched_text": self.matched_text,
            "position": self.position,
            "suggestion": self.suggestion,
        }


@dataclass
class FixApplied:
    """Describes a fix that was applied to the content."""

    issue_type: str
    original_text: str
    fixed_text: str
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "issue_type": self.issue_type,
            "original_text": self.original_text,
            "fixed_text": self.fixed_text,
            "explanation": self.explanation,
        }


@dataclass
class LLMQAFixInput:
    """Input data for LLM QA fix."""

    h1: str
    title_tag: str
    meta_description: str
    top_description: str
    bottom_description: str
    issues: list[IssueToFix]
    primary_keyword: str
    project_id: str | None = None
    page_id: str | None = None
    content_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging (sanitized)."""
        return {
            "h1_length": len(self.h1),
            "bottom_description_length": len(self.bottom_description),
            "issue_count": len(self.issues),
            "primary_keyword": self.primary_keyword[:50],  # Truncate
            "project_id": self.project_id,
            "page_id": self.page_id,
            "content_id": self.content_id,
        }


@dataclass
class LLMQAFixResult:
    """Result of Phase 5C LLM QA fix."""

    success: bool
    fixed_bottom_description: str | None = None
    issues_found: list[str] = field(default_factory=list)
    fixes_applied: list[FixApplied] = field(default_factory=list)
    fix_count: int = 0
    content_id: str | None = None
    page_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: str | None = None
    duration_ms: float = 0.0
    project_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "fixed_bottom_description_length": (
                len(self.fixed_bottom_description)
                if self.fixed_bottom_description
                else None
            ),
            "issues_found": self.issues_found,
            "fixes_applied": [f.to_dict() for f in self.fixes_applied],
            "fix_count": self.fix_count,
            "content_id": self.content_id,
            "page_id": self.page_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
            "project_id": self.project_id,
        }


# =============================================================================
# EXCEPTIONS
# =============================================================================


class LLMQAFixServiceError(Exception):
    """Base exception for LLM QA fix service errors."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.page_id = page_id


class LLMQAFixValidationError(LLMQAFixServiceError):
    """Raised when validation fails."""

    def __init__(
        self,
        field_name: str,
        value: Any,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(
            f"Validation error for {field_name}: {message}", project_id, page_id
        )
        self.field_name = field_name
        self.value = value


class LLMQAFixLLMError(LLMQAFixServiceError):
    """Raised when LLM call fails."""

    pass


# =============================================================================
# SERVICE
# =============================================================================


class LLMQAFixService:
    """Service for Phase 5C LLM-powered content fixes.

    Uses Claude to fix AI trope patterns with minimal changes:
    - Negation patterns ("aren't just X, they're Y")
    - Banned words (delve, unlock, journey)
    - Em dashes
    - Triplet patterns
    - Rhetorical question openers

    Usage:
        service = LLMQAFixService()
        result = await service.fix_content(
            input_data=LLMQAFixInput(
                h1="Premium Leather Wallets",
                title_tag="Premium Leather Wallets | Brand",
                meta_description="...",
                top_description="...",
                bottom_description="<h2>...</h2>...",
                issues=[IssueToFix(issue_type="negation_pattern", matched_text="...")],
                primary_keyword="leather wallets",
            ),
        )
    """

    def __init__(
        self,
        claude_client: ClaudeClient | None = None,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
    ) -> None:
        """Initialize LLM QA fix service.

        Args:
            claude_client: Optional Claude client (uses global if not provided)
            max_concurrent: Maximum concurrent LLM calls for batch processing
        """
        self._claude_client = claude_client
        self._max_concurrent = max_concurrent
        self._semaphore: asyncio.Semaphore | None = None

        logger.debug(
            "LLMQAFixService initialized",
            extra={"max_concurrent": max_concurrent},
        )

    async def _get_claude(self) -> ClaudeClient:
        """Get Claude client instance."""
        if self._claude_client is not None:
            return self._claude_client
        return await get_claude()

    def _get_semaphore(self) -> asyncio.Semaphore:
        """Get or create semaphore for concurrency control."""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrent)
        return self._semaphore

    def _build_user_prompt(
        self,
        input_data: LLMQAFixInput,
    ) -> str:
        """Build the user prompt for LLM QA fix.

        Args:
            input_data: Content and issues to fix

        Returns:
            Formatted prompt string
        """
        # Format issues list
        issues_text = "\n".join(
            f"- {issue.issue_type}: \"{issue.matched_text}\""
            + (f" (suggestion: {issue.suggestion})" if issue.suggestion else "")
            for issue in input_data.issues
        )

        return f"""Review and FIX this content for the keyword "{input_data.primary_keyword}":

---
{input_data.bottom_description}
---

Check for and FIX these SPECIFIC issues:

{issues_text}

IMPORTANT:
- Make MINIMAL changes. Only fix the specific issues listed above.
- Keep the same structure, length, and information.
- Preserve all links, formatting, and HTML exactly as-is.
- If no issues found, return the content unchanged.

Return a JSON object with issues_found, issues_fixed, and fixed_content."""

    def _parse_llm_response(
        self,
        response_text: str,
        project_id: str | None,
        page_id: str | None,
    ) -> dict[str, Any]:
        """Parse LLM JSON response.

        Args:
            response_text: Raw LLM response text
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            Parsed JSON dictionary

        Raises:
            LLMQAFixLLMError: If parsing fails
        """
        try:
            # Handle markdown code blocks
            json_text = response_text.strip()
            if json_text.startswith("```"):
                lines = json_text.split("\n")
                lines = lines[1:]  # Remove opening fence
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                json_text = "\n".join(lines)

            parsed: dict[str, Any] = json.loads(json_text)
            return parsed

        except json.JSONDecodeError as e:
            logger.warning(
                "LLM QA fix response parse error",
                extra={
                    "error": str(e),
                    "response_preview": response_text[:500],
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            raise LLMQAFixLLMError(
                f"Failed to parse LLM response: {e}",
                project_id=project_id,
                page_id=page_id,
            ) from e

    def _extract_fixes(
        self,
        parsed: dict[str, Any],
        _original_content: str,
        _fixed_content: str,
    ) -> list[FixApplied]:
        """Extract fix details from LLM response.

        Args:
            parsed: Parsed LLM response
            _original_content: Original content before fix (reserved for future diff analysis)
            _fixed_content: Content after fix (reserved for future diff analysis)

        Returns:
            List of FixApplied objects
        """
        fixes: list[FixApplied] = []
        issues_found = parsed.get("issues_found", [])
        issues_fixed = parsed.get("issues_fixed", [])

        # Pair up issues found with fixes applied
        for i, issue in enumerate(issues_found):
            fix_text = issues_fixed[i] if i < len(issues_fixed) else "Fixed"
            fixes.append(
                FixApplied(
                    issue_type=self._classify_issue(issue),
                    original_text=issue,
                    fixed_text=fix_text,
                    explanation=fix_text,
                )
            )

        return fixes

    def _classify_issue(self, issue_description: str) -> str:
        """Classify issue type from description.

        Args:
            issue_description: Issue description from LLM

        Returns:
            Issue type string
        """
        issue_lower = issue_description.lower()
        if "negation" in issue_lower or "aren't just" in issue_lower:
            return "negation_pattern"
        if "em dash" in issue_lower or "—" in issue_description:
            return "em_dash"
        if "triplet" in issue_lower or "pattern" in issue_lower:
            return "triplet_pattern"
        if "rhetorical" in issue_lower or "question" in issue_lower:
            return "rhetorical_question"
        if any(
            word in issue_lower
            for word in ["delve", "unlock", "journey", "crucial", "cutting-edge"]
        ):
            return "banned_word"
        return "other"

    async def fix_content(
        self,
        input_data: LLMQAFixInput,
    ) -> LLMQAFixResult:
        """Fix content issues using LLM.

        Phase 5C LLM QA fix:
        1. Build prompt with content and specific issues
        2. Call Claude to fix issues with minimal changes
        3. Parse structured JSON response
        4. Extract fix details
        5. Return fixed content

        Args:
            input_data: Content and issues to fix

        Returns:
            LLMQAFixResult with fixed content and details
        """
        start_time = time.monotonic()
        project_id = input_data.project_id
        page_id = input_data.page_id
        content_id = input_data.content_id

        logger.debug(
            "Phase 5C LLM QA fix starting",
            extra={
                "content_id": content_id,
                "issue_count": len(input_data.issues),
                "bottom_description_length": len(input_data.bottom_description),
                "primary_keyword": input_data.primary_keyword[:50],
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        # Validate inputs
        if not input_data.bottom_description or not input_data.bottom_description.strip():
            logger.warning(
                "LLM QA fix validation failed - empty bottom_description",
                extra={
                    "field": "bottom_description",
                    "value": "",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            raise LLMQAFixValidationError(
                "bottom_description",
                "",
                "Bottom description cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        if not input_data.issues:
            logger.warning(
                "LLM QA fix validation failed - no issues provided",
                extra={
                    "field": "issues",
                    "value": [],
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            raise LLMQAFixValidationError(
                "issues",
                [],
                "At least one issue must be provided",
                project_id=project_id,
                page_id=page_id,
            )

        try:
            # Log phase transition
            logger.info(
                "Phase 5C: LLM QA fix - in_progress",
                extra={
                    "content_id": content_id,
                    "issue_count": len(input_data.issues),
                    "phase": "5C",
                    "status": "in_progress",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            # Build prompt
            user_prompt = self._build_user_prompt(input_data)

            # Get Claude client and make request
            claude = await self._get_claude()

            if not claude.available:
                logger.warning(
                    "Claude not available for LLM QA fix",
                    extra={
                        "content_id": content_id,
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )
                return LLMQAFixResult(
                    success=False,
                    content_id=content_id,
                    page_id=page_id,
                    error="Claude LLM not configured",
                    duration_ms=(time.monotonic() - start_time) * 1000,
                    project_id=project_id,
                )

            result = await claude.complete(
                user_prompt=user_prompt,
                system_prompt=LLM_QA_FIX_SYSTEM_PROMPT,
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
            )

            if not result.success:
                logger.error(
                    "LLM QA fix Claude call failed",
                    extra={
                        "content_id": content_id,
                        "error": result.error,
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )
                return LLMQAFixResult(
                    success=False,
                    content_id=content_id,
                    page_id=page_id,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    error=f"LLM call failed: {result.error}",
                    duration_ms=(time.monotonic() - start_time) * 1000,
                    project_id=project_id,
                )

            # Parse response
            parsed = self._parse_llm_response(
                result.text or "",
                project_id,
                page_id,
            )

            # Extract results
            fixed_content = parsed.get("fixed_content", input_data.bottom_description)
            issues_found = parsed.get("issues_found", [])
            fixes_applied = self._extract_fixes(
                parsed,
                input_data.bottom_description,
                fixed_content,
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            # Log completion
            logger.info(
                "Phase 5C: LLM QA fix - completed",
                extra={
                    "content_id": content_id,
                    "fix_count": len(fixes_applied),
                    "issues_found": len(issues_found),
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "phase": "5C",
                    "status": "completed",
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow Phase 5C LLM QA fix operation",
                    extra={
                        "content_id": content_id,
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )

            return LLMQAFixResult(
                success=True,
                fixed_bottom_description=fixed_content,
                issues_found=issues_found,
                fixes_applied=fixes_applied,
                fix_count=len(fixes_applied),
                content_id=content_id,
                page_id=page_id,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                duration_ms=duration_ms,
                project_id=project_id,
            )

        except LLMQAFixValidationError:
            raise
        except LLMQAFixLLMError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Phase 5C LLM QA fix LLM error",
                extra={
                    "content_id": content_id,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            return LLMQAFixResult(
                success=False,
                content_id=content_id,
                page_id=page_id,
                error=str(e),
                duration_ms=duration_ms,
                project_id=project_id,
            )
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Phase 5C LLM QA fix unexpected error",
                extra={
                    "content_id": content_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "page_id": page_id,
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return LLMQAFixResult(
                success=False,
                content_id=content_id,
                page_id=page_id,
                error=f"Unexpected error: {e}",
                duration_ms=duration_ms,
                project_id=project_id,
            )

    async def fix_content_batch(
        self,
        inputs: list[LLMQAFixInput],
        project_id: str | None = None,
    ) -> list[LLMQAFixResult]:
        """Fix multiple content items with controlled concurrency.

        Args:
            inputs: List of content items to fix
            project_id: Project ID for logging

        Returns:
            List of LLMQAFixResult, one per input
        """
        start_time = time.monotonic()

        logger.info(
            "Batch LLM QA fix started",
            extra={
                "input_count": len(inputs),
                "max_concurrent": self._max_concurrent,
                "project_id": project_id,
            },
        )

        if not inputs:
            return []

        semaphore = self._get_semaphore()

        async def fix_with_semaphore(input_data: LLMQAFixInput) -> LLMQAFixResult:
            async with semaphore:
                return await self.fix_content(input_data)

        # Process concurrently with semaphore limiting
        results = await asyncio.gather(
            *[fix_with_semaphore(inp) for inp in inputs],
            return_exceptions=True,
        )

        # Convert exceptions to error results
        processed_results: list[LLMQAFixResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "Batch LLM QA fix item exception",
                    extra={
                        "item_index": i,
                        "content_id": inputs[i].content_id,
                        "error": str(result),
                        "error_type": type(result).__name__,
                        "project_id": project_id,
                    },
                )
                processed_results.append(
                    LLMQAFixResult(
                        success=False,
                        content_id=inputs[i].content_id,
                        page_id=inputs[i].page_id,
                        error=f"Exception: {result}",
                        duration_ms=0,
                        project_id=project_id,
                    )
                )
            elif isinstance(result, LLMQAFixResult):
                processed_results.append(result)

        duration_ms = (time.monotonic() - start_time) * 1000
        success_count = sum(1 for r in processed_results if r.success)
        total_fixes = sum(r.fix_count for r in processed_results)
        total_input_tokens = sum(r.input_tokens or 0 for r in processed_results)
        total_output_tokens = sum(r.output_tokens or 0 for r in processed_results)

        logger.info(
            "Batch LLM QA fix complete",
            extra={
                "input_count": len(inputs),
                "success_count": success_count,
                "failure_count": len(inputs) - success_count,
                "total_fixes": total_fixes,
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "duration_ms": round(duration_ms, 2),
                "project_id": project_id,
            },
        )

        if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
            logger.warning(
                "Slow batch LLM QA fix operation",
                extra={
                    "input_count": len(inputs),
                    "duration_ms": round(duration_ms, 2),
                    "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    "project_id": project_id,
                },
            )

        return processed_results


# =============================================================================
# SINGLETON
# =============================================================================


_llm_qa_fix_service: LLMQAFixService | None = None


def get_llm_qa_fix_service() -> LLMQAFixService:
    """Get the global LLM QA fix service instance.

    Usage:
        from app.services.llm_qa_fix import get_llm_qa_fix_service
        service = get_llm_qa_fix_service()
        result = await service.fix_content(input_data)
    """
    global _llm_qa_fix_service
    if _llm_qa_fix_service is None:
        _llm_qa_fix_service = LLMQAFixService()
        logger.info("LLMQAFixService singleton created")
    return _llm_qa_fix_service


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


async def fix_content(
    h1: str,
    title_tag: str,
    meta_description: str,
    top_description: str,
    bottom_description: str,
    issues: list[IssueToFix],
    primary_keyword: str,
    project_id: str | None = None,
    page_id: str | None = None,
    content_id: str | None = None,
) -> LLMQAFixResult:
    """Convenience function for Phase 5C LLM QA fix.

    Args:
        h1: Page H1 heading
        title_tag: Page title tag
        meta_description: Page meta description
        top_description: Above-the-fold description
        bottom_description: Full bottom description with issues
        issues: List of issues to fix
        primary_keyword: Primary keyword for the page
        project_id: Project ID for logging
        page_id: Page ID for logging
        content_id: Content ID for tracking

    Returns:
        LLMQAFixResult with fixed content
    """
    service = get_llm_qa_fix_service()
    input_data = LLMQAFixInput(
        h1=h1,
        title_tag=title_tag,
        meta_description=meta_description,
        top_description=top_description,
        bottom_description=bottom_description,
        issues=issues,
        primary_keyword=primary_keyword,
        project_id=project_id,
        page_id=page_id,
        content_id=content_id,
    )
    return await service.fix_content(input_data)
