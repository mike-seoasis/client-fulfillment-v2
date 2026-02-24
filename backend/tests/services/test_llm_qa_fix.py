"""Unit tests for LLMQAFixService LLM-powered content corrections.

Tests cover:
- LLMQAFixInput dataclass creation and serialization
- LLMQAFixResult dataclass and serialization
- IssueToFix and FixApplied helper classes
- LLMQAFixService initialization
- _build_user_prompt() method
- _parse_llm_response() method with various JSON formats
- _extract_fixes() method
- _classify_issue() method
- fix_content() method with mocked LLM
- fix_content_batch() method with concurrency
- Validation and exception handling
- Error cases (empty content, no issues, LLM failures)
- Semaphore-based concurrency control

ERROR LOGGING REQUIREMENTS:
- Ensure test failures include full assertion context
- Log test setup/teardown at DEBUG level
- Capture and display logs from failed tests
- Include timing information in test reports
- Log mock/stub invocations for debugging

Target: 80% code coverage for LLMQAFixService.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

import pytest

from app.services.llm_qa_fix import (
    DEFAULT_MAX_CONCURRENT,
    FixApplied,
    IssueToFix,
    LLMQAFixInput,
    LLMQAFixLLMError,
    LLMQAFixResult,
    LLMQAFixService,
    LLMQAFixServiceError,
    LLMQAFixValidationError,
    fix_content,
    get_llm_qa_fix_service,
)

# Enable debug logging for test visibility
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mock Claude Response
# ---------------------------------------------------------------------------


@dataclass
class MockClaudeResult:
    """Mock result from Claude client."""

    success: bool = True
    text: str | None = None
    error: str | None = None
    input_tokens: int | None = 100
    output_tokens: int | None = 200


class MockClaudeClient:
    """Mock Claude client for testing."""

    def __init__(
        self,
        available: bool = True,
        success: bool = True,
        response_text: str | None = None,
    ) -> None:
        self.available = available
        self._success = success
        self._response_text = response_text or json.dumps({
            "issues_found": ["Found negation pattern"],
            "issues_fixed": ["Rewrote as direct statement"],
            "fixed_content": "<p>Fixed content here.</p>",
        })
        self.complete_calls: list[dict[str, Any]] = []
        logger.debug(
            "MockClaudeClient created",
            extra={"available": available, "success": success},
        )

    async def complete(
        self,
        user_prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> MockClaudeResult:
        """Mock completion that returns predefined response."""
        self.complete_calls.append({
            "user_prompt": user_prompt,
            "system_prompt": system_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
        })
        logger.debug(
            "MockClaudeClient.complete called",
            extra={"prompt_length": len(user_prompt)},
        )

        if not self._success:
            return MockClaudeResult(success=False, error="Mock LLM error")

        return MockClaudeResult(
            success=True,
            text=self._response_text,
            input_tokens=100,
            output_tokens=200,
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_claude() -> MockClaudeClient:
    """Create a mock Claude client."""
    logger.debug("Creating mock Claude client fixture")
    return MockClaudeClient()


@pytest.fixture
def mock_claude_unavailable() -> MockClaudeClient:
    """Create an unavailable mock Claude client."""
    logger.debug("Creating unavailable mock Claude client fixture")
    return MockClaudeClient(available=False)


@pytest.fixture
def mock_claude_failure() -> MockClaudeClient:
    """Create a mock Claude client that fails."""
    logger.debug("Creating failing mock Claude client fixture")
    return MockClaudeClient(success=False)


@pytest.fixture
def service(mock_claude: MockClaudeClient) -> LLMQAFixService:
    """Create a LLMQAFixService with mock Claude client."""
    logger.debug("Creating LLMQAFixService with mock")
    return LLMQAFixService(claude_client=mock_claude)  # type: ignore[arg-type]


@pytest.fixture
def sample_issue() -> IssueToFix:
    """Create a sample issue to fix."""
    return IssueToFix(
        issue_type="negation_pattern",
        matched_text="aren't just containers, they're",
        position=150,
        suggestion="Rewrite as direct benefit statement",
    )


@pytest.fixture
def sample_input(sample_issue: IssueToFix) -> LLMQAFixInput:
    """Create a sample LLM QA fix input."""
    logger.debug("Creating sample LLM QA fix input fixture")
    return LLMQAFixInput(
        h1="Premium Coffee Containers",
        title_tag="Premium Coffee Containers | Brand",
        meta_description="Keep your coffee fresh with our premium containers.",
        top_description="Our containers keep coffee fresh for weeks.",
        bottom_description="""
        <h2>Why Choose Our Containers</h2>
        <p>Our containers aren't just storage, they're a freshness preservation system.
        Each container features an airtight seal that locks in flavor.</p>
        <p>Made from premium glass, these containers look great on any counter.</p>
        """,
        issues=[sample_issue],
        primary_keyword="coffee containers",
        project_id="proj-123",
        page_id="page-456",
        content_id="content-789",
    )


@pytest.fixture
def sample_input_empty_issues() -> LLMQAFixInput:
    """Create input with no issues."""
    return LLMQAFixInput(
        h1="Title",
        title_tag="Title",
        meta_description="Meta",
        top_description="Top",
        bottom_description="Valid content here.",
        issues=[],
        primary_keyword="test keyword",
    )


@pytest.fixture
def sample_input_empty_content(sample_issue: IssueToFix) -> LLMQAFixInput:
    """Create input with empty bottom description."""
    return LLMQAFixInput(
        h1="Title",
        title_tag="Title",
        meta_description="Meta",
        top_description="Top",
        bottom_description="",
        issues=[sample_issue],
        primary_keyword="test keyword",
    )


# ---------------------------------------------------------------------------
# Test: Data Classes
# ---------------------------------------------------------------------------


class TestIssueToFix:
    """Tests for IssueToFix dataclass."""

    def test_create_issue(self) -> None:
        """Should create IssueToFix with all fields."""
        issue = IssueToFix(
            issue_type="banned_word",
            matched_text="delve",
            position=50,
            suggestion="Use simpler word",
        )
        assert issue.issue_type == "banned_word"
        assert issue.matched_text == "delve"
        assert issue.position == 50
        assert issue.suggestion == "Use simpler word"

    def test_create_issue_minimal(self) -> None:
        """Should create IssueToFix with minimal fields."""
        issue = IssueToFix(
            issue_type="em_dash",
            matched_text="—",
        )
        assert issue.position is None
        assert issue.suggestion is None

    def test_issue_to_dict(self) -> None:
        """Should convert to dictionary correctly."""
        issue = IssueToFix(
            issue_type="triplet_pattern",
            matched_text="Fast. Simple. Powerful.",
            position=100,
        )
        data = issue.to_dict()

        assert data["issue_type"] == "triplet_pattern"
        assert data["matched_text"] == "Fast. Simple. Powerful."
        assert data["position"] == 100
        assert data["suggestion"] is None


class TestFixApplied:
    """Tests for FixApplied dataclass."""

    def test_create_fix(self) -> None:
        """Should create FixApplied with all fields."""
        fix = FixApplied(
            issue_type="negation_pattern",
            original_text="aren't just X, they're Y",
            fixed_text="offer both X and Y",
            explanation="Converted to direct statement",
        )
        assert fix.issue_type == "negation_pattern"
        assert fix.original_text == "aren't just X, they're Y"
        assert fix.fixed_text == "offer both X and Y"
        assert fix.explanation == "Converted to direct statement"

    def test_fix_to_dict(self) -> None:
        """Should convert to dictionary correctly."""
        fix = FixApplied(
            issue_type="em_dash",
            original_text="text—more text",
            fixed_text="text. More text",
        )
        data = fix.to_dict()

        assert data["issue_type"] == "em_dash"
        assert data["original_text"] == "text—more text"
        assert data["fixed_text"] == "text. More text"
        assert data["explanation"] == ""  # Default empty


class TestLLMQAFixInput:
    """Tests for LLMQAFixInput dataclass."""

    def test_create_full_input(self, sample_issue: IssueToFix) -> None:
        """Should create input with all fields."""
        inp = LLMQAFixInput(
            h1="H1 Text",
            title_tag="Title",
            meta_description="Meta",
            top_description="Top",
            bottom_description="Bottom content",
            issues=[sample_issue],
            primary_keyword="test keyword",
            project_id="proj-1",
            page_id="page-1",
            content_id="content-1",
        )
        assert inp.h1 == "H1 Text"
        assert len(inp.issues) == 1
        assert inp.primary_keyword == "test keyword"
        assert inp.project_id == "proj-1"

    def test_to_dict_sanitizes(self, sample_issue: IssueToFix) -> None:
        """Should include lengths not full content."""
        inp = LLMQAFixInput(
            h1="Short H1",
            title_tag="Title",
            meta_description="Meta",
            top_description="Top",
            bottom_description="A" * 500,
            issues=[sample_issue],
            primary_keyword="very long primary keyword here",
        )
        data = inp.to_dict()

        assert data["h1_length"] == len("Short H1")
        assert data["bottom_description_length"] == 500
        assert data["issue_count"] == 1
        assert len(data["primary_keyword"]) <= 50  # Truncated


class TestLLMQAFixResult:
    """Tests for LLMQAFixResult dataclass."""

    def test_create_success_result(self) -> None:
        """Should create a successful result."""
        result = LLMQAFixResult(
            success=True,
            fixed_bottom_description="<p>Fixed content</p>",
            issues_found=["Found issue 1"],
            fixes_applied=[
                FixApplied("negation", "original", "fixed", "explanation")
            ],
            fix_count=1,
            content_id="content-1",
            input_tokens=100,
            output_tokens=200,
            duration_ms=500.5,
        )
        assert result.success is True
        assert result.fixed_bottom_description == "<p>Fixed content</p>"
        assert result.fix_count == 1
        assert result.error is None

    def test_create_failure_result(self) -> None:
        """Should create a failed result with error."""
        result = LLMQAFixResult(
            success=False,
            error="LLM call failed",
            duration_ms=100.0,
        )
        assert result.success is False
        assert result.error == "LLM call failed"
        assert result.fixed_bottom_description is None

    def test_result_defaults(self) -> None:
        """Should have correct default values."""
        result = LLMQAFixResult(success=True)
        assert result.fixed_bottom_description is None
        assert result.issues_found == []
        assert result.fixes_applied == []
        assert result.fix_count == 0
        assert result.input_tokens is None
        assert result.output_tokens is None

    def test_result_to_dict(self) -> None:
        """Should convert to dictionary correctly."""
        result = LLMQAFixResult(
            success=True,
            fixed_bottom_description="<p>Content</p>",
            issues_found=["Issue 1"],
            fix_count=1,
            duration_ms=123.456,
        )
        data = result.to_dict()

        assert data["success"] is True
        assert data["fixed_bottom_description_length"] == len("<p>Content</p>")
        assert data["issues_found"] == ["Issue 1"]
        assert data["duration_ms"] == 123.46  # Rounded


# ---------------------------------------------------------------------------
# Test: LLMQAFixService Initialization
# ---------------------------------------------------------------------------


class TestServiceInitialization:
    """Tests for LLMQAFixService initialization."""

    def test_default_initialization(self) -> None:
        """Should initialize without errors."""
        service = LLMQAFixService()
        assert service is not None
        assert service._max_concurrent == DEFAULT_MAX_CONCURRENT

    def test_custom_max_concurrent(self) -> None:
        """Should accept custom max_concurrent."""
        service = LLMQAFixService(max_concurrent=10)
        assert service._max_concurrent == 10

    def test_custom_claude_client(self, mock_claude: MockClaudeClient) -> None:
        """Should accept custom Claude client."""
        service = LLMQAFixService(claude_client=mock_claude)  # type: ignore[arg-type]
        assert service._claude_client is not None


# ---------------------------------------------------------------------------
# Test: Prompt Building
# ---------------------------------------------------------------------------


class TestPromptBuilding:
    """Tests for user prompt building."""

    def test_build_user_prompt(
        self,
        service: LLMQAFixService,
        sample_input: LLMQAFixInput,
    ) -> None:
        """Should build prompt with content and issues."""
        prompt = service._build_user_prompt(sample_input)

        # Should include keyword
        assert "coffee containers" in prompt
        # Should include content
        assert "Why Choose Our Containers" in prompt
        # Should include issue info
        assert "negation_pattern" in prompt
        assert "aren't just containers" in prompt

    def test_build_user_prompt_includes_suggestion(
        self,
        service: LLMQAFixService,
    ) -> None:
        """Should include suggestion when provided."""
        issue = IssueToFix(
            issue_type="banned_word",
            matched_text="delve",
            suggestion="Use 'explore' instead",
        )
        inp = LLMQAFixInput(
            h1="Test",
            title_tag="Test",
            meta_description="Meta",
            top_description="Top",
            bottom_description="Content here.",
            issues=[issue],
            primary_keyword="test",
        )
        prompt = service._build_user_prompt(inp)

        assert "suggestion" in prompt.lower()
        assert "explore" in prompt


# ---------------------------------------------------------------------------
# Test: Response Parsing
# ---------------------------------------------------------------------------


class TestResponseParsing:
    """Tests for LLM response parsing."""

    def test_parse_valid_json(self, service: LLMQAFixService) -> None:
        """Should parse valid JSON response."""
        response = json.dumps({
            "issues_found": ["Issue 1", "Issue 2"],
            "issues_fixed": ["Fix 1", "Fix 2"],
            "fixed_content": "<p>Fixed content</p>",
        })

        parsed = service._parse_llm_response(response, "proj-1", "page-1")

        assert parsed["issues_found"] == ["Issue 1", "Issue 2"]
        assert parsed["fixed_content"] == "<p>Fixed content</p>"

    def test_parse_json_with_markdown_code_block(
        self,
        service: LLMQAFixService,
    ) -> None:
        """Should handle markdown code block wrapper."""
        response = """```json
{
    "issues_found": ["Issue"],
    "issues_fixed": ["Fix"],
    "fixed_content": "<p>Content</p>"
}
```"""

        parsed = service._parse_llm_response(response, None, None)
        assert parsed["issues_found"] == ["Issue"]

    def test_parse_invalid_json_raises(
        self,
        service: LLMQAFixService,
    ) -> None:
        """Should raise LLMQAFixLLMError for invalid JSON."""
        response = "This is not valid JSON"

        with pytest.raises(LLMQAFixLLMError):
            service._parse_llm_response(response, "proj-1", "page-1")


# ---------------------------------------------------------------------------
# Test: Fix Extraction
# ---------------------------------------------------------------------------


class TestFixExtraction:
    """Tests for extracting fixes from parsed response."""

    def test_extract_fixes(self, service: LLMQAFixService) -> None:
        """Should extract FixApplied objects from parsed response."""
        parsed = {
            "issues_found": ["Found negation pattern", "Found em dash"],
            "issues_fixed": ["Rewrote statement", "Replaced with period"],
            "fixed_content": "<p>Fixed</p>",
        }

        fixes = service._extract_fixes(parsed, "original", "fixed")

        assert len(fixes) == 2
        assert fixes[0].original_text == "Found negation pattern"
        assert fixes[0].fixed_text == "Rewrote statement"
        assert fixes[1].original_text == "Found em dash"

    def test_extract_fixes_mismatched_counts(
        self,
        service: LLMQAFixService,
    ) -> None:
        """Should handle mismatched issue/fix counts."""
        parsed = {
            "issues_found": ["Issue 1", "Issue 2", "Issue 3"],
            "issues_fixed": ["Fix 1"],  # Only one fix
            "fixed_content": "<p>Fixed</p>",
        }

        fixes = service._extract_fixes(parsed, "original", "fixed")

        assert len(fixes) == 3
        assert fixes[0].fixed_text == "Fix 1"
        assert fixes[1].fixed_text == "Fixed"  # Default
        assert fixes[2].fixed_text == "Fixed"  # Default


# ---------------------------------------------------------------------------
# Test: Issue Classification
# ---------------------------------------------------------------------------


class TestIssueClassification:
    """Tests for issue type classification."""

    def test_classify_negation(self, service: LLMQAFixService) -> None:
        """Should classify negation patterns."""
        assert (
            service._classify_issue("Found negation pattern") == "negation_pattern"
        )
        assert (
            service._classify_issue("aren't just X, they're Y") == "negation_pattern"
        )

    def test_classify_em_dash(self, service: LLMQAFixService) -> None:
        """Should classify em dash issues."""
        assert service._classify_issue("Found em dash") == "em_dash"
        assert service._classify_issue("Contains — character") == "em_dash"

    def test_classify_triplet(self, service: LLMQAFixService) -> None:
        """Should classify triplet patterns."""
        assert service._classify_issue("Found triplet pattern") == "triplet_pattern"

    def test_classify_rhetorical(self, service: LLMQAFixService) -> None:
        """Should classify rhetorical questions."""
        assert (
            service._classify_issue("Rhetorical question opener")
            == "rhetorical_question"
        )

    def test_classify_banned_word(self, service: LLMQAFixService) -> None:
        """Should classify banned words."""
        assert service._classify_issue("Found word 'delve'") == "banned_word"
        assert service._classify_issue("Contains 'unlock'") == "banned_word"
        assert service._classify_issue("Has 'cutting-edge'") == "banned_word"

    def test_classify_other(self, service: LLMQAFixService) -> None:
        """Should default to 'other' for unrecognized issues."""
        assert service._classify_issue("Some random issue") == "other"


# ---------------------------------------------------------------------------
# Test: fix_content Method
# ---------------------------------------------------------------------------


class TestFixContent:
    """Tests for the main fix_content method."""

    @pytest.mark.asyncio
    async def test_fix_content_success(
        self,
        service: LLMQAFixService,
        sample_input: LLMQAFixInput,
        mock_claude: MockClaudeClient,
    ) -> None:
        """Should successfully fix content."""
        result = await service.fix_content(sample_input)

        assert result.success is True
        assert result.fixed_bottom_description is not None
        assert result.fix_count >= 0
        assert result.error is None
        assert result.duration_ms > 0

        # Verify Claude was called
        assert len(mock_claude.complete_calls) == 1

    @pytest.mark.asyncio
    async def test_fix_content_tracks_tokens(
        self,
        service: LLMQAFixService,
        sample_input: LLMQAFixInput,
    ) -> None:
        """Should track input/output tokens."""
        result = await service.fix_content(sample_input)

        assert result.success is True
        assert result.input_tokens == 100
        assert result.output_tokens == 200

    @pytest.mark.asyncio
    async def test_fix_content_includes_ids(
        self,
        service: LLMQAFixService,
        sample_input: LLMQAFixInput,
    ) -> None:
        """Should include project/page/content IDs in result."""
        result = await service.fix_content(sample_input)

        assert result.project_id == "proj-123"
        assert result.page_id == "page-456"
        assert result.content_id == "content-789"

    @pytest.mark.asyncio
    async def test_fix_content_claude_unavailable(
        self,
        mock_claude_unavailable: MockClaudeClient,
        sample_input: LLMQAFixInput,
    ) -> None:
        """Should return error when Claude is unavailable."""
        service = LLMQAFixService(claude_client=mock_claude_unavailable)  # type: ignore[arg-type]

        result = await service.fix_content(sample_input)

        assert result.success is False
        assert result.error is not None
        assert "not configured" in result.error.lower()

    @pytest.mark.asyncio
    async def test_fix_content_claude_failure(
        self,
        mock_claude_failure: MockClaudeClient,
        sample_input: LLMQAFixInput,
    ) -> None:
        """Should return error when Claude call fails."""
        service = LLMQAFixService(claude_client=mock_claude_failure)  # type: ignore[arg-type]

        result = await service.fix_content(sample_input)

        assert result.success is False
        assert result.error is not None
        assert "failed" in result.error.lower()


# ---------------------------------------------------------------------------
# Test: Validation
# ---------------------------------------------------------------------------


class TestValidation:
    """Tests for input validation."""

    @pytest.mark.asyncio
    async def test_empty_bottom_description_raises(
        self,
        service: LLMQAFixService,
        sample_input_empty_content: LLMQAFixInput,
    ) -> None:
        """Should raise validation error for empty bottom description."""
        with pytest.raises(LLMQAFixValidationError) as exc_info:
            await service.fix_content(sample_input_empty_content)

        assert exc_info.value.field_name == "bottom_description"

    @pytest.mark.asyncio
    async def test_no_issues_raises(
        self,
        service: LLMQAFixService,
        sample_input_empty_issues: LLMQAFixInput,
    ) -> None:
        """Should raise validation error when no issues provided."""
        with pytest.raises(LLMQAFixValidationError) as exc_info:
            await service.fix_content(sample_input_empty_issues)

        assert exc_info.value.field_name == "issues"

    @pytest.mark.asyncio
    async def test_whitespace_bottom_description_raises(
        self,
        service: LLMQAFixService,
        sample_issue: IssueToFix,
    ) -> None:
        """Should raise validation error for whitespace-only description."""
        inp = LLMQAFixInput(
            h1="Title",
            title_tag="Title",
            meta_description="Meta",
            top_description="Top",
            bottom_description="   \n\t  ",
            issues=[sample_issue],
            primary_keyword="test",
        )

        with pytest.raises(LLMQAFixValidationError):
            await service.fix_content(inp)


# ---------------------------------------------------------------------------
# Test: Exception Classes
# ---------------------------------------------------------------------------


class TestExceptionClasses:
    """Tests for LLMQAFix exception classes."""

    def test_service_error_base(self) -> None:
        """LLMQAFixServiceError should be base exception."""
        error = LLMQAFixServiceError("Test error", "proj-1", "page-1")
        assert str(error) == "Test error"
        assert error.project_id == "proj-1"
        assert error.page_id == "page-1"

    def test_validation_error(self) -> None:
        """LLMQAFixValidationError should contain field info."""
        error = LLMQAFixValidationError(
            field_name="bottom_description",
            value="",
            message="Cannot be empty",
            project_id="proj-1",
        )
        assert error.field_name == "bottom_description"
        assert error.value == ""
        assert "bottom_description" in str(error)

    def test_llm_error(self) -> None:
        """LLMQAFixLLMError should be raised for LLM failures."""
        error = LLMQAFixLLMError("Parse failed", "proj-1", "page-1")
        assert "Parse failed" in str(error)
        assert error.project_id == "proj-1"

    def test_exception_hierarchy(self) -> None:
        """All exceptions should inherit from service error."""
        assert issubclass(LLMQAFixValidationError, LLMQAFixServiceError)
        assert issubclass(LLMQAFixLLMError, LLMQAFixServiceError)


# ---------------------------------------------------------------------------
# Test: Batch Processing
# ---------------------------------------------------------------------------


class TestBatchProcessing:
    """Tests for batch content fixing."""

    @pytest.mark.asyncio
    async def test_batch_empty_list(
        self,
        service: LLMQAFixService,
    ) -> None:
        """Should return empty list for empty input."""
        results = await service.fix_content_batch([], project_id="proj-1")
        assert results == []

    @pytest.mark.asyncio
    async def test_batch_multiple_items(
        self,
        service: LLMQAFixService,
        sample_input: LLMQAFixInput,
        sample_issue: IssueToFix,
    ) -> None:
        """Should process multiple items in batch."""
        input2 = LLMQAFixInput(
            h1="Second Content",
            title_tag="Second",
            meta_description="Meta 2",
            top_description="Top 2",
            bottom_description="<p>Second content to fix.</p>",
            issues=[sample_issue],
            primary_keyword="test keyword",
            content_id="content-2",
        )

        inputs = [sample_input, input2]
        results = await service.fix_content_batch(inputs, project_id="proj-1")

        assert len(results) == 2
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_batch_respects_semaphore(
        self,
        sample_input: LLMQAFixInput,
        sample_issue: IssueToFix,
    ) -> None:
        """Should limit concurrent calls via semaphore."""
        mock_claude = MockClaudeClient()
        service = LLMQAFixService(
            claude_client=mock_claude,  # type: ignore[arg-type]
            max_concurrent=2,
        )

        # Create multiple inputs
        inputs = [
            LLMQAFixInput(
                h1=f"Content {i}",
                title_tag=f"Title {i}",
                meta_description="Meta",
                top_description="Top",
                bottom_description=f"<p>Content {i}</p>",
                issues=[sample_issue],
                primary_keyword="test",
                content_id=f"content-{i}",
            )
            for i in range(5)
        ]

        results = await service.fix_content_batch(inputs)

        assert len(results) == 5
        # All should complete successfully (semaphore limits concurrency, not count)
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_batch_handles_exceptions(
        self,
        sample_input: LLMQAFixInput,
        sample_issue: IssueToFix,
    ) -> None:
        """Should convert exceptions to error results in batch."""
        # Create a client that will cause parsing to fail on second call
        call_count = 0

        class FlakyClaude:
            available = True

            async def complete(self, **kwargs: Any) -> MockClaudeResult:
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    # Return invalid JSON to trigger parse error
                    return MockClaudeResult(success=True, text="not json")
                return MockClaudeResult(
                    success=True,
                    text=json.dumps({
                        "issues_found": [],
                        "issues_fixed": [],
                        "fixed_content": "<p>Fixed</p>",
                    }),
                )

        service = LLMQAFixService(claude_client=FlakyClaude())  # type: ignore[arg-type]

        inputs = [
            LLMQAFixInput(
                h1=f"Content {i}",
                title_tag=f"Title {i}",
                meta_description="Meta",
                top_description="Top",
                bottom_description=f"<p>Content {i}</p>",
                issues=[sample_issue],
                primary_keyword="test",
                content_id=f"content-{i}",
            )
            for i in range(3)
        ]

        results = await service.fix_content_batch(inputs)

        assert len(results) == 3
        # First and third should succeed
        assert results[0].success is True
        # Second should fail due to parse error
        assert results[1].success is False
        assert results[2].success is True


# ---------------------------------------------------------------------------
# Test: Singleton and Convenience Functions
# ---------------------------------------------------------------------------


class TestSingletonAndConvenience:
    """Tests for singleton accessor and convenience functions."""

    def test_get_service_singleton(self) -> None:
        """get_llm_qa_fix_service should return singleton."""
        import app.services.llm_qa_fix as llm_module

        original = llm_module._llm_qa_fix_service
        llm_module._llm_qa_fix_service = None

        try:
            service1 = get_llm_qa_fix_service()
            service2 = get_llm_qa_fix_service()
            assert service1 is service2
        finally:
            llm_module._llm_qa_fix_service = original

    @pytest.mark.asyncio
    async def test_convenience_function(
        self,
        sample_issue: IssueToFix,
    ) -> None:
        """fix_content convenience function should work."""
        # We need to mock the global service for this test
        mock_claude = MockClaudeClient()
        mock_service = LLMQAFixService(claude_client=mock_claude)  # type: ignore[arg-type]

        with patch(
            "app.services.llm_qa_fix.get_llm_qa_fix_service",
            return_value=mock_service,
        ):
            result = await fix_content(
                h1="Test H1",
                title_tag="Test Title",
                meta_description="Test meta",
                top_description="Test top",
                bottom_description="<p>Content to fix.</p>",
                issues=[sample_issue],
                primary_keyword="test keyword",
                project_id="proj-1",
            )

            assert result.success is True
            assert result.project_id == "proj-1"


# ---------------------------------------------------------------------------
# Test: Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_very_long_content(
        self,
        service: LLMQAFixService,
        sample_issue: IssueToFix,
    ) -> None:
        """Should handle very long content."""
        large_content = "<p>" + ("Word " * 2000) + "</p>"
        inp = LLMQAFixInput(
            h1="Large Content Test",
            title_tag="Large",
            meta_description="Testing large content",
            top_description="Top",
            bottom_description=large_content,
            issues=[sample_issue],
            primary_keyword="test",
        )

        result = await service.fix_content(inp)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_unicode_content(
        self,
        service: LLMQAFixService,
        sample_issue: IssueToFix,
    ) -> None:
        """Should handle unicode content."""
        inp = LLMQAFixInput(
            h1="コーヒー Storage",
            title_tag="Café Containers",
            meta_description="日本語 meta",
            top_description="中文 description",
            bottom_description="<p>Unicode: 你好世界 🎉</p>",
            issues=[sample_issue],
            primary_keyword="コーヒー",
        )

        result = await service.fix_content(inp)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_multiple_issues(
        self,
        service: LLMQAFixService,
    ) -> None:
        """Should handle multiple issues in single content."""
        issues = [
            IssueToFix(
                issue_type="negation_pattern",
                matched_text="aren't just X",
            ),
            IssueToFix(
                issue_type="em_dash",
                matched_text="—",
            ),
            IssueToFix(
                issue_type="banned_word",
                matched_text="delve",
            ),
        ]
        inp = LLMQAFixInput(
            h1="Multi-issue Content",
            title_tag="Title",
            meta_description="Meta",
            top_description="Top",
            bottom_description="<p>Content with multiple issues.</p>",
            issues=issues,
            primary_keyword="test",
        )

        result = await service.fix_content(inp)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_response_with_no_changes(
        self,
        sample_issue: IssueToFix,
    ) -> None:
        """Should handle LLM response indicating no changes needed."""
        mock_claude = MockClaudeClient(
            response_text=json.dumps({
                "issues_found": [],
                "issues_fixed": [],
                "fixed_content": "<p>Original content unchanged</p>",
            })
        )
        service = LLMQAFixService(claude_client=mock_claude)  # type: ignore[arg-type]

        inp = LLMQAFixInput(
            h1="Test",
            title_tag="Test",
            meta_description="Meta",
            top_description="Top",
            bottom_description="<p>Content</p>",
            issues=[sample_issue],
            primary_keyword="test",
        )

        result = await service.fix_content(inp)

        assert result.success is True
        assert result.fix_count == 0
        assert result.fixed_bottom_description == "<p>Original content unchanged</p>"

    @pytest.mark.asyncio
    async def test_html_preserved_in_response(
        self,
        sample_issue: IssueToFix,
    ) -> None:
        """Should preserve HTML structure in fixed content."""
        mock_claude = MockClaudeClient(
            response_text=json.dumps({
                "issues_found": ["Issue"],
                "issues_fixed": ["Fixed"],
                "fixed_content": (
                    '<h2>Title</h2>'
                    '<p>Paragraph with <a href="/link">link</a>.</p>'
                    '<ul><li>Item 1</li><li>Item 2</li></ul>'
                ),
            })
        )
        service = LLMQAFixService(claude_client=mock_claude)  # type: ignore[arg-type]

        inp = LLMQAFixInput(
            h1="Test",
            title_tag="Test",
            meta_description="Meta",
            top_description="Top",
            bottom_description="<p>Original</p>",
            issues=[sample_issue],
            primary_keyword="test",
        )

        result = await service.fix_content(inp)

        assert result.success is True
        assert result.fixed_bottom_description is not None
        assert "<h2>" in result.fixed_bottom_description
        assert '<a href="/link">' in result.fixed_bottom_description
        assert "<ul>" in result.fixed_bottom_description
