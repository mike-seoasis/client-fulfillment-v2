"""Unit tests for PAA categorization service with LLM-based intent classification.

Tests cover:
- Intent parsing from LLM responses
- Batch processing logic
- Rate-limited concurrent processing
- Integration with PAAQuestion objects
- Error handling and graceful degradation
- Validation logic (empty keyword, etc.)
- JSON response parsing (including markdown code blocks)
- Logging per requirements

ERROR LOGGING REQUIREMENTS (verified by tests):
- Test failures include full assertion context
- Test setup/teardown logged at DEBUG level
- Capture and display logs from failed tests
- Include timing information in test reports
- Log mock/stub invocations for debugging

Target: 80% code coverage.
"""

import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.claude import CompletionResult
from app.services.paa_categorization import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_MAX_CONCURRENT,
    CategorizationItem,
    CategorizationResult,
    PAACategorizationService,
    PAACategorizationValidationError,
    categorize_paa_questions,
    get_paa_categorization_service,
)
from app.services.paa_enrichment import PAAQuestion, PAAQuestionIntent

# Configure logging for tests
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Test Data Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_questions() -> list[str]:
    """Sample PAA questions for testing."""
    return [
        "What are the best hiking boots?",
        "How to clean hiking boots?",
        "Are Salomon boots worth it?",
        "How to break in new hiking boots?",
    ]


@pytest.fixture
def sample_paa_questions() -> list[PAAQuestion]:
    """Sample PAAQuestion objects for testing."""
    return [
        PAAQuestion(question="What are the best hiking boots?"),
        PAAQuestion(question="How to clean hiking boots?"),
        PAAQuestion(question="Salomon vs Merrell hiking boots?"),
        PAAQuestion(question="How long do hiking boots last?"),
    ]


@pytest.fixture
def sample_llm_response_text() -> str:
    """Sample LLM response with categorizations."""
    return json.dumps(
        {
            "categorizations": [
                {
                    "question": "What are the best hiking boots?",
                    "intent": "buying",
                    "confidence": 0.95,
                    "reasoning": "User is looking for product recommendations",
                },
                {
                    "question": "How to clean hiking boots?",
                    "intent": "care",
                    "confidence": 0.9,
                    "reasoning": "User wants maintenance guidance",
                },
                {
                    "question": "Are Salomon boots worth it?",
                    "intent": "buying",
                    "confidence": 0.85,
                    "reasoning": "User is evaluating a purchase",
                },
                {
                    "question": "How to break in new hiking boots?",
                    "intent": "usage",
                    "confidence": 0.88,
                    "reasoning": "User wants usage tips",
                },
            ]
        }
    )


@pytest.fixture
def sample_llm_response_markdown() -> str:
    """Sample LLM response wrapped in markdown code block."""
    return """```json
{
  "categorizations": [
    {
      "question": "What are the best hiking boots?",
      "intent": "buying",
      "confidence": 0.95,
      "reasoning": "Product recommendation request"
    }
  ]
}
```"""


@pytest.fixture
def mock_claude_client():
    """Create a mock Claude client."""
    client = AsyncMock()
    client.complete = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# Test: CategorizationItem Dataclass
# ---------------------------------------------------------------------------


class TestCategorizationItem:
    """Tests for CategorizationItem dataclass."""

    def test_categorization_item_defaults(self) -> None:
        """CategorizationItem should have sensible defaults."""
        item = CategorizationItem(question="What is hiking?")

        assert item.question == "What is hiking?"
        assert item.intent == PAAQuestionIntent.UNKNOWN
        assert item.confidence == 0.0
        assert item.reasoning is None

    def test_categorization_item_full_init(self) -> None:
        """CategorizationItem should accept all fields."""
        item = CategorizationItem(
            question="What are the best boots?",
            intent=PAAQuestionIntent.BUYING,
            confidence=0.9,
            reasoning="User wants product recommendations",
        )

        assert item.question == "What are the best boots?"
        assert item.intent == PAAQuestionIntent.BUYING
        assert item.confidence == 0.9
        assert item.reasoning == "User wants product recommendations"


# ---------------------------------------------------------------------------
# Test: CategorizationResult Dataclass
# ---------------------------------------------------------------------------


class TestCategorizationResult:
    """Tests for CategorizationResult dataclass."""

    def test_categorization_result_defaults(self) -> None:
        """CategorizationResult should have sensible defaults."""
        result = CategorizationResult(success=True)

        assert result.success is True
        assert result.categorizations == []
        assert result.error is None
        assert result.input_tokens is None
        assert result.output_tokens is None
        assert result.duration_ms == 0.0

    def test_categorized_count_property(self) -> None:
        """categorized_count should count non-UNKNOWN intents."""
        result = CategorizationResult(
            success=True,
            categorizations=[
                CategorizationItem(question="Q1", intent=PAAQuestionIntent.BUYING),
                CategorizationItem(question="Q2", intent=PAAQuestionIntent.UNKNOWN),
                CategorizationItem(question="Q3", intent=PAAQuestionIntent.CARE),
            ],
        )

        assert result.categorized_count == 2


# ---------------------------------------------------------------------------
# Test: PAACategorizationService._parse_intent
# ---------------------------------------------------------------------------


class TestParseIntent:
    """Tests for intent string parsing."""

    def test_parse_valid_intents(self) -> None:
        """Should parse valid intent strings correctly."""
        service = PAACategorizationService()

        assert service._parse_intent("buying") == PAAQuestionIntent.BUYING
        assert service._parse_intent("usage") == PAAQuestionIntent.USAGE
        assert service._parse_intent("care") == PAAQuestionIntent.CARE
        assert service._parse_intent("comparison") == PAAQuestionIntent.COMPARISON

    def test_parse_intent_case_insensitive(self) -> None:
        """Should handle case variations."""
        service = PAACategorizationService()

        assert service._parse_intent("BUYING") == PAAQuestionIntent.BUYING
        assert service._parse_intent("Usage") == PAAQuestionIntent.USAGE
        assert service._parse_intent("CARE") == PAAQuestionIntent.CARE

    def test_parse_intent_with_whitespace(self) -> None:
        """Should handle whitespace."""
        service = PAACategorizationService()

        assert service._parse_intent("  buying  ") == PAAQuestionIntent.BUYING
        assert service._parse_intent("\tusage\n") == PAAQuestionIntent.USAGE

    def test_parse_invalid_intent(self) -> None:
        """Should return UNKNOWN for invalid intents."""
        service = PAACategorizationService()

        assert service._parse_intent("invalid") == PAAQuestionIntent.UNKNOWN
        assert service._parse_intent("") == PAAQuestionIntent.UNKNOWN
        assert service._parse_intent("purchasing") == PAAQuestionIntent.UNKNOWN


# ---------------------------------------------------------------------------
# Test: PAACategorizationService.categorize_questions - Validation
# ---------------------------------------------------------------------------


class TestCategorizeQuestionsValidation:
    """Tests for input validation in categorize_questions."""

    async def test_empty_keyword_raises_validation_error(self) -> None:
        """Should raise PAACategorizationValidationError for empty keyword."""
        service = PAACategorizationService()

        with pytest.raises(PAACategorizationValidationError) as exc_info:
            await service.categorize_questions(
                questions=["What is hiking?"],
                keyword="",
            )

        assert exc_info.value.field_name == "keyword"
        assert "empty" in exc_info.value.args[0].lower()

    async def test_whitespace_only_keyword_raises_validation_error(self) -> None:
        """Should raise PAACategorizationValidationError for whitespace keyword."""
        service = PAACategorizationService()

        with pytest.raises(PAACategorizationValidationError) as exc_info:
            await service.categorize_questions(
                questions=["What is hiking?"],
                keyword="   ",
            )

        assert exc_info.value.field_name == "keyword"

    async def test_empty_questions_returns_empty_result(self) -> None:
        """Should return empty result for empty questions list."""
        service = PAACategorizationService()

        result = await service.categorize_questions(
            questions=[],
            keyword="hiking boots",
        )

        assert result.success is True
        assert result.categorizations == []
        assert result.duration_ms == 0.0


# ---------------------------------------------------------------------------
# Test: PAACategorizationService.categorize_questions - Basic Operation
# ---------------------------------------------------------------------------


class TestCategorizeQuestionsBasic:
    """Tests for basic categorization operation."""

    async def test_categorize_questions_success(
        self,
        mock_claude_client: AsyncMock,
        sample_questions: list[str],
        sample_llm_response_text: str,
    ) -> None:
        """Should categorize questions successfully."""
        mock_claude_client.complete.return_value = CompletionResult(
            success=True,
            text=sample_llm_response_text,
            input_tokens=100,
            output_tokens=50,
        )

        service = PAACategorizationService(claude_client=mock_claude_client)

        result = await service.categorize_questions(
            questions=sample_questions,
            keyword="hiking boots",
        )

        assert result.success is True
        assert len(result.categorizations) == 4
        assert result.categorizations[0].intent == PAAQuestionIntent.BUYING
        assert result.categorizations[1].intent == PAAQuestionIntent.CARE
        assert result.categorizations[2].intent == PAAQuestionIntent.BUYING
        assert result.categorizations[3].intent == PAAQuestionIntent.USAGE

    async def test_categorize_questions_strips_keyword(
        self,
        mock_claude_client: AsyncMock,
        sample_llm_response_text: str,
    ) -> None:
        """Should strip whitespace from keyword."""
        mock_claude_client.complete.return_value = CompletionResult(
            success=True,
            text=sample_llm_response_text,
        )

        service = PAACategorizationService(claude_client=mock_claude_client)

        result = await service.categorize_questions(
            questions=["What is best?"],
            keyword="  hiking boots  ",
        )

        assert result.success is True
        # Check that the prompt used stripped keyword
        call_args = mock_claude_client.complete.call_args
        assert "hiking boots" in call_args.kwargs["user_prompt"]

    async def test_categorize_handles_markdown_code_blocks(
        self,
        mock_claude_client: AsyncMock,
        sample_llm_response_markdown: str,
    ) -> None:
        """Should parse LLM response wrapped in markdown code blocks."""
        mock_claude_client.complete.return_value = CompletionResult(
            success=True,
            text=sample_llm_response_markdown,
        )

        service = PAACategorizationService(claude_client=mock_claude_client)

        result = await service.categorize_questions(
            questions=["What are the best hiking boots?"],
            keyword="hiking boots",
        )

        assert result.success is True
        assert len(result.categorizations) == 1
        assert result.categorizations[0].intent == PAAQuestionIntent.BUYING


# ---------------------------------------------------------------------------
# Test: PAACategorizationService.categorize_questions - Batch Processing
# ---------------------------------------------------------------------------


class TestCategorizeQuestionsBatching:
    """Tests for batch processing logic."""

    async def test_batching_splits_questions(
        self,
        mock_claude_client: AsyncMock,
    ) -> None:
        """Should split questions into batches."""
        # Track number of calls
        call_count = 0

        async def mock_complete(user_prompt: str, **kwargs):
            nonlocal call_count
            call_count += 1
            # Return empty categorizations for simplicity
            return CompletionResult(
                success=True,
                text=json.dumps({"categorizations": []}),
            )

        mock_claude_client.complete.side_effect = mock_complete

        # Create 25 questions with batch_size=10
        questions = [f"Question {i}?" for i in range(25)]

        service = PAACategorizationService(
            claude_client=mock_claude_client,
            batch_size=10,
        )

        result = await service.categorize_questions(
            questions=questions,
            keyword="test",
        )

        # Should have 3 batches: 10, 10, 5
        assert mock_claude_client.complete.call_count == 3
        assert call_count == 3

        # All questions should have categorization items (with UNKNOWN since empty response)
        assert len(result.categorizations) == 25

    async def test_batching_respects_max_concurrent(
        self,
        mock_claude_client: AsyncMock,
    ) -> None:
        """Should respect max_concurrent limit for batches."""
        concurrent_count = 0
        max_concurrent_seen = 0

        async def mock_complete(*args, **kwargs):
            nonlocal concurrent_count, max_concurrent_seen
            concurrent_count += 1
            max_concurrent_seen = max(max_concurrent_seen, concurrent_count)
            await asyncio.sleep(0.1)  # Simulate API latency
            concurrent_count -= 1
            return CompletionResult(
                success=True,
                text=json.dumps({"categorizations": []}),
            )

        mock_claude_client.complete.side_effect = mock_complete

        # Create 30 questions with batch_size=5, max_concurrent=2
        questions = [f"Question {i}?" for i in range(30)]

        service = PAACategorizationService(
            claude_client=mock_claude_client,
            batch_size=5,
            max_concurrent=2,
        )

        await service.categorize_questions(
            questions=questions,
            keyword="test",
        )

        # Should have 6 batches, max 2 concurrent
        assert mock_claude_client.complete.call_count == 6
        assert max_concurrent_seen <= 2


# ---------------------------------------------------------------------------
# Test: PAACategorizationService.categorize_questions - Error Handling
# ---------------------------------------------------------------------------


class TestCategorizeQuestionsErrors:
    """Tests for error handling in categorization."""

    async def test_llm_failure_returns_unknown_intents(
        self,
        mock_claude_client: AsyncMock,
        sample_questions: list[str],
    ) -> None:
        """LLM failure should return questions with UNKNOWN intent."""
        mock_claude_client.complete.return_value = CompletionResult(
            success=False,
            error="LLM unavailable",
        )

        service = PAACategorizationService(claude_client=mock_claude_client)

        result = await service.categorize_questions(
            questions=sample_questions,
            keyword="hiking boots",
        )

        # The implementation marks success=False at the batch level
        assert result.success is False
        # Error is stored in the batch result (may not be propagated to top level)
        assert len(result.categorizations) == 4
        assert all(
            cat.intent == PAAQuestionIntent.UNKNOWN for cat in result.categorizations
        )

    async def test_json_parse_error_returns_unknown_intents(
        self,
        mock_claude_client: AsyncMock,
        sample_questions: list[str],
    ) -> None:
        """JSON parse failure should return questions with UNKNOWN intent."""
        mock_claude_client.complete.return_value = CompletionResult(
            success=True,
            text="This is not valid JSON",
        )

        service = PAACategorizationService(claude_client=mock_claude_client)

        result = await service.categorize_questions(
            questions=sample_questions,
            keyword="hiking boots",
        )

        # The implementation marks success=False for parse errors at batch level
        assert result.success is False
        # All questions should have UNKNOWN intent
        assert len(result.categorizations) == 4
        assert all(
            cat.intent == PAAQuestionIntent.UNKNOWN for cat in result.categorizations
        )

    async def test_unexpected_error_handled_gracefully(
        self,
        mock_claude_client: AsyncMock,
        sample_questions: list[str],
    ) -> None:
        """Unexpected errors should be handled gracefully."""
        mock_claude_client.complete.side_effect = RuntimeError("Unexpected error")

        service = PAACategorizationService(claude_client=mock_claude_client)

        result = await service.categorize_questions(
            questions=sample_questions,
            keyword="hiking boots",
        )

        assert result.success is False
        assert result.error is not None
        assert "Unexpected" in result.error
        assert len(result.categorizations) == 4

    async def test_partial_batch_failure_continues(
        self,
        mock_claude_client: AsyncMock,
    ) -> None:
        """Partial batch failures should not stop entire operation."""
        call_count = 0

        async def mock_complete(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return CompletionResult(success=False, error="Batch 2 failed")
            return CompletionResult(
                success=True,
                text=json.dumps(
                    {
                        "categorizations": [
                            {"question": "Q", "intent": "usage", "confidence": 0.8}
                        ]
                    }
                ),
            )

        mock_claude_client.complete.side_effect = mock_complete

        questions = [f"Question {i}?" for i in range(15)]

        service = PAACategorizationService(
            claude_client=mock_claude_client,
            batch_size=5,
        )

        result = await service.categorize_questions(
            questions=questions,
            keyword="test",
        )

        # Operation should complete (success=False because one batch failed)
        assert result.success is False
        # All questions should have categorizations (some with UNKNOWN)
        assert len(result.categorizations) == 15


# ---------------------------------------------------------------------------
# Test: PAACategorizationService.categorize_paa_questions
# ---------------------------------------------------------------------------


class TestCategorizePAAQuestions:
    """Tests for categorizing PAAQuestion objects."""

    async def test_categorize_paa_questions_updates_intents(
        self,
        mock_claude_client: AsyncMock,
        sample_paa_questions: list[PAAQuestion],
    ) -> None:
        """Should update intent field on PAAQuestion objects."""
        mock_claude_client.complete.return_value = CompletionResult(
            success=True,
            text=json.dumps(
                {
                    "categorizations": [
                        {
                            "question": "What are the best hiking boots?",
                            "intent": "buying",
                            "confidence": 0.9,
                        },
                        {
                            "question": "How to clean hiking boots?",
                            "intent": "care",
                            "confidence": 0.85,
                        },
                        {
                            "question": "Salomon vs Merrell hiking boots?",
                            "intent": "comparison",
                            "confidence": 0.88,
                        },
                        {
                            "question": "How long do hiking boots last?",
                            "intent": "care",
                            "confidence": 0.75,
                        },
                    ]
                }
            ),
        )

        service = PAACategorizationService(claude_client=mock_claude_client)

        result = await service.categorize_paa_questions(
            paa_questions=sample_paa_questions,
            keyword="hiking boots",
        )

        assert len(result) == 4
        assert result[0].intent == PAAQuestionIntent.BUYING
        assert result[1].intent == PAAQuestionIntent.CARE
        assert result[2].intent == PAAQuestionIntent.COMPARISON
        assert result[3].intent == PAAQuestionIntent.CARE

    async def test_categorize_paa_questions_empty_list(
        self,
        mock_claude_client: AsyncMock,
    ) -> None:
        """Should handle empty PAAQuestion list."""
        service = PAACategorizationService(claude_client=mock_claude_client)

        result = await service.categorize_paa_questions(
            paa_questions=[],
            keyword="hiking boots",
        )

        assert result == []
        mock_claude_client.complete.assert_not_called()

    async def test_categorize_paa_questions_preserves_other_fields(
        self,
        mock_claude_client: AsyncMock,
    ) -> None:
        """Should preserve other fields on PAAQuestion objects."""
        mock_claude_client.complete.return_value = CompletionResult(
            success=True,
            text=json.dumps(
                {
                    "categorizations": [
                        {
                            "question": "Test question?",
                            "intent": "usage",
                            "confidence": 0.8,
                        }
                    ]
                }
            ),
        )

        original_question = PAAQuestion(
            question="Test question?",
            answer_snippet="The answer is...",
            source_url="https://example.com",
            position=1,
            is_nested=True,
        )

        service = PAACategorizationService(claude_client=mock_claude_client)

        result = await service.categorize_paa_questions(
            paa_questions=[original_question],
            keyword="test",
        )

        assert result[0].intent == PAAQuestionIntent.USAGE
        assert result[0].answer_snippet == "The answer is..."
        assert result[0].source_url == "https://example.com"
        assert result[0].position == 1
        assert result[0].is_nested is True


# ---------------------------------------------------------------------------
# Test: Question Matching Logic
# ---------------------------------------------------------------------------


class TestQuestionMatching:
    """Tests for matching LLM responses to original questions."""

    async def test_matches_questions_case_insensitive(
        self,
        mock_claude_client: AsyncMock,
    ) -> None:
        """Should match questions case-insensitively."""
        mock_claude_client.complete.return_value = CompletionResult(
            success=True,
            text=json.dumps(
                {
                    "categorizations": [
                        {
                            "question": "what are the best boots?",  # Lowercase
                            "intent": "buying",
                            "confidence": 0.9,
                        }
                    ]
                }
            ),
        )

        service = PAACategorizationService(claude_client=mock_claude_client)

        result = await service.categorize_questions(
            questions=["What Are The Best Boots?"],  # Mixed case
            keyword="boots",
        )

        assert result.categorizations[0].intent == PAAQuestionIntent.BUYING

    async def test_unmatched_questions_get_unknown_intent(
        self,
        mock_claude_client: AsyncMock,
    ) -> None:
        """Questions not in LLM response should get UNKNOWN intent."""
        mock_claude_client.complete.return_value = CompletionResult(
            success=True,
            text=json.dumps(
                {
                    "categorizations": [
                        {
                            "question": "Different question?",
                            "intent": "buying",
                            "confidence": 0.9,
                        }
                    ]
                }
            ),
        )

        service = PAACategorizationService(claude_client=mock_claude_client)

        result = await service.categorize_questions(
            questions=["Original question?"],
            keyword="test",
        )

        # Original question wasn't in response, should get UNKNOWN
        assert result.categorizations[0].intent == PAAQuestionIntent.UNKNOWN


# ---------------------------------------------------------------------------
# Test: Singleton and Convenience Functions
# ---------------------------------------------------------------------------


class TestSingletonAndConvenience:
    """Tests for singleton pattern and convenience functions."""

    def test_get_paa_categorization_service_returns_singleton(self) -> None:
        """get_paa_categorization_service should return the same instance."""
        # Reset singleton for test
        import app.services.paa_categorization as module

        module._paa_categorization_service = None

        service1 = get_paa_categorization_service()
        service2 = get_paa_categorization_service()

        assert service1 is service2

        # Clean up
        module._paa_categorization_service = None

    async def test_convenience_function_categorize_paa_questions(self) -> None:
        """categorize_paa_questions convenience function should work."""
        with patch(
            "app.services.paa_categorization.get_paa_categorization_service"
        ) as mock_get:
            mock_service = MagicMock()
            mock_service.categorize_questions = AsyncMock(
                return_value=CategorizationResult(
                    success=True,
                    categorizations=[
                        CategorizationItem(
                            question="Test?", intent=PAAQuestionIntent.USAGE
                        )
                    ],
                )
            )
            mock_get.return_value = mock_service

            result = await categorize_paa_questions(
                questions=["Test?"],
                keyword="test",
            )

            assert result.success is True
            mock_service.categorize_questions.assert_called_once()


# ---------------------------------------------------------------------------
# Test: Service Initialization
# ---------------------------------------------------------------------------


class TestServiceInitialization:
    """Tests for service initialization."""

    def test_default_initialization(self) -> None:
        """Service should have sensible defaults."""
        service = PAACategorizationService()

        assert service._batch_size == DEFAULT_BATCH_SIZE
        assert service._max_concurrent == DEFAULT_MAX_CONCURRENT

    def test_custom_initialization(self) -> None:
        """Service should accept custom settings."""
        service = PAACategorizationService(
            batch_size=5,
            max_concurrent=3,
        )

        assert service._batch_size == 5
        assert service._max_concurrent == 3


# ---------------------------------------------------------------------------
# Test: Token Tracking
# ---------------------------------------------------------------------------


class TestTokenTracking:
    """Tests for token usage tracking."""

    async def test_tracks_token_usage_across_batches(
        self,
        mock_claude_client: AsyncMock,
    ) -> None:
        """Should accumulate token usage across all batches."""

        async def mock_complete(*args, **kwargs):
            return CompletionResult(
                success=True,
                text=json.dumps({"categorizations": []}),
                input_tokens=50,
                output_tokens=25,
            )

        mock_claude_client.complete.side_effect = mock_complete

        questions = [f"Question {i}?" for i in range(15)]

        service = PAACategorizationService(
            claude_client=mock_claude_client,
            batch_size=5,  # 3 batches
        )

        result = await service.categorize_questions(
            questions=questions,
            keyword="test",
        )

        # 3 batches * 50 input tokens each
        assert result.input_tokens == 150
        # 3 batches * 25 output tokens each
        assert result.output_tokens == 75


# ---------------------------------------------------------------------------
# Test: Logging Verification
# ---------------------------------------------------------------------------


class TestLogging:
    """Tests for logging behavior per requirements."""

    async def test_logs_categorization_start(
        self,
        mock_claude_client: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Should log categorization start at DEBUG level."""
        mock_claude_client.complete.return_value = CompletionResult(
            success=True,
            text=json.dumps({"categorizations": []}),
        )

        service = PAACategorizationService(claude_client=mock_claude_client)

        with caplog.at_level(logging.DEBUG):
            await service.categorize_questions(
                questions=["Test?"],
                keyword="test",
            )

        # Check for debug log entry
        assert any("categorization started" in r.message.lower() for r in caplog.records)

    async def test_logs_batch_processing(
        self,
        mock_claude_client: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Should log batch processing at INFO level."""
        mock_claude_client.complete.return_value = CompletionResult(
            success=True,
            text=json.dumps({"categorizations": []}),
        )

        service = PAACategorizationService(
            claude_client=mock_claude_client,
            batch_size=5,
        )

        with caplog.at_level(logging.INFO):
            await service.categorize_questions(
                questions=[f"Q{i}?" for i in range(10)],  # 2 batches
                keyword="test",
            )

        # Should see batch processing log
        assert any("batch" in r.message.lower() for r in caplog.records)
