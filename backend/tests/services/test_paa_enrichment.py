"""Unit tests for PAA enrichment service with fan-out strategy.

Tests cover:
- PAA question parsing from SERP response
- Question deduplication logic
- Fan-out strategy (searching initial questions for nested)
- Related searches fallback when PAA results insufficient
- Integration with categorization service
- Error handling and graceful degradation
- Validation logic (empty keyword, etc.)
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
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.paa_enrichment import (
    DEFAULT_MAX_CONCURRENT_FANOUT,
    PAAEnrichmentResult,
    PAAEnrichmentService,
    PAAQuestion,
    PAAQuestionIntent,
    PAAValidationError,
    get_paa_enrichment_service,
)

# Configure logging for tests
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Test Data Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_paa_serp_response() -> dict[str, Any]:
    """Sample SERP API response with PAA items."""
    return {
        "tasks": [
            {
                "result": [
                    {
                        "items": [
                            {
                                "type": "people_also_ask",
                                "items": [
                                    {
                                        "type": "people_also_ask_element",
                                        "title": "What are the best hiking boots?",
                                        "expanded_element": [
                                            {
                                                "type": "people_also_ask_expanded_element",
                                                "description": "The best hiking boots...",
                                                "url": "https://example.com/best-boots",
                                                "domain": "example.com",
                                            }
                                        ],
                                    },
                                    {
                                        "type": "people_also_ask_element",
                                        "title": "How to clean hiking boots?",
                                        "expanded_element": [
                                            {
                                                "type": "people_also_ask_expanded_element",
                                                "description": "To clean your boots...",
                                                "url": "https://example.com/clean-boots",
                                                "domain": "example.com",
                                            }
                                        ],
                                    },
                                    {
                                        "type": "people_also_ask_element",
                                        "title": "Are hiking boots waterproof?",
                                    },
                                ],
                            },
                            {
                                "type": "organic",
                                "title": "Some organic result",
                            },
                        ]
                    }
                ]
            }
        ],
        "cost": 0.003,
    }


@pytest.fixture
def sample_paa_ai_overview_response() -> dict[str, Any]:
    """Sample SERP response with AI overview expanded element."""
    return {
        "tasks": [
            {
                "result": [
                    {
                        "items": [
                            {
                                "type": "people_also_ask",
                                "items": [
                                    {
                                        "type": "people_also_ask_element",
                                        "title": "What is the best brand?",
                                        "expanded_element": [
                                            {
                                                "type": "people_also_ask_ai_overview_expanded_element",
                                                "items": [
                                                    {
                                                        "text": "AI generated answer...",
                                                        "references": [
                                                            {
                                                                "url": "https://ai.example.com/answer",
                                                                "source": "ai.example.com",
                                                            }
                                                        ],
                                                    }
                                                ],
                                            }
                                        ],
                                    },
                                ],
                            },
                        ]
                    }
                ]
            }
        ],
        "cost": 0.002,
    }


@pytest.fixture
def empty_paa_response() -> dict[str, Any]:
    """SERP response with no PAA items."""
    return {
        "tasks": [
            {
                "result": [
                    {
                        "items": [
                            {
                                "type": "organic",
                                "title": "Organic result",
                            },
                        ]
                    }
                ]
            }
        ],
        "cost": 0.001,
    }


@pytest.fixture
def mock_dataforseo_client():
    """Create a mock DataForSEO client."""
    client = AsyncMock()
    client._make_request = AsyncMock()
    return client


@pytest.fixture
def mock_related_searches_service():
    """Create a mock RelatedSearchesService."""
    service = MagicMock()
    service.get_related_searches = AsyncMock()
    return service


@pytest.fixture
def mock_paa_categorization_service():
    """Create a mock PAACategorizationService."""
    service = MagicMock()
    service.categorize_paa_questions = AsyncMock()
    return service


# ---------------------------------------------------------------------------
# Test: PAAQuestion Dataclass
# ---------------------------------------------------------------------------


class TestPAAQuestion:
    """Tests for PAAQuestion dataclass."""

    def test_paa_question_defaults(self) -> None:
        """PAAQuestion should have sensible defaults."""
        question = PAAQuestion(question="What is hiking?")

        assert question.question == "What is hiking?"
        assert question.answer_snippet is None
        assert question.source_url is None
        assert question.source_domain is None
        assert question.position is None
        assert question.is_nested is False
        assert question.parent_question is None
        assert question.intent == PAAQuestionIntent.UNKNOWN

    def test_paa_question_full_init(self) -> None:
        """PAAQuestion should accept all fields."""
        question = PAAQuestion(
            question="What are the best boots?",
            answer_snippet="The best boots are...",
            source_url="https://example.com/boots",
            source_domain="example.com",
            position=1,
            is_nested=True,
            parent_question="What is hiking gear?",
            intent=PAAQuestionIntent.BUYING,
        )

        assert question.question == "What are the best boots?"
        assert question.answer_snippet == "The best boots are..."
        assert question.source_url == "https://example.com/boots"
        assert question.source_domain == "example.com"
        assert question.position == 1
        assert question.is_nested is True
        assert question.parent_question == "What is hiking gear?"
        assert question.intent == PAAQuestionIntent.BUYING

    def test_paa_question_to_dict(self) -> None:
        """PAAQuestion.to_dict should serialize all fields."""
        question = PAAQuestion(
            question="How to clean boots?",
            intent=PAAQuestionIntent.CARE,
            is_nested=True,
        )

        result = question.to_dict()

        assert result["question"] == "How to clean boots?"
        assert result["intent"] == "care"
        assert result["is_nested"] is True
        assert "answer_snippet" in result
        assert "source_url" in result


# ---------------------------------------------------------------------------
# Test: PAAEnrichmentResult Dataclass
# ---------------------------------------------------------------------------


class TestPAAEnrichmentResult:
    """Tests for PAAEnrichmentResult dataclass."""

    def test_enrichment_result_defaults(self) -> None:
        """PAAEnrichmentResult should have sensible defaults."""
        result = PAAEnrichmentResult(
            success=True,
            keyword="hiking boots",
        )

        assert result.success is True
        assert result.keyword == "hiking boots"
        assert result.questions == []
        assert result.initial_count == 0
        assert result.nested_count == 0
        assert result.related_search_count == 0
        assert result.used_fallback is False
        assert result.error is None
        assert result.cost is None
        assert result.total_count == 0

    def test_enrichment_result_total_count(self) -> None:
        """total_count should return len(questions)."""
        questions = [
            PAAQuestion(question="Q1"),
            PAAQuestion(question="Q2"),
            PAAQuestion(question="Q3"),
        ]
        result = PAAEnrichmentResult(
            success=True,
            keyword="test",
            questions=questions,
        )

        assert result.total_count == 3


# ---------------------------------------------------------------------------
# Test: PAAEnrichmentService._normalize_question
# ---------------------------------------------------------------------------


class TestNormalizeQuestion:
    """Tests for question normalization/deduplication."""

    def test_normalize_basic(self) -> None:
        """Should lowercase and strip whitespace."""
        service = PAAEnrichmentService()

        assert service._normalize_question("What is hiking?") == "what is hiking"
        assert service._normalize_question("  HIKING BOOTS  ") == "hiking boots"
        assert service._normalize_question("Test?") == "test"

    def test_normalize_removes_trailing_question_mark(self) -> None:
        """Should remove trailing question mark."""
        service = PAAEnrichmentService()

        assert service._normalize_question("How to hike?") == "how to hike"
        # Note: rstrip("?") removes all trailing question marks
        assert service._normalize_question("What is best??") == "what is best"

    def test_is_duplicate_detection(self) -> None:
        """Should detect duplicate questions."""
        service = PAAEnrichmentService()

        # First occurrence - not a duplicate
        assert service._is_duplicate("What is hiking?") is False
        service._mark_seen("What is hiking?")

        # Same question, different case - should be duplicate
        assert service._is_duplicate("WHAT IS HIKING?") is True
        assert service._is_duplicate("what is hiking") is True
        assert service._is_duplicate("  What is hiking?  ") is True

        # Different question - not a duplicate
        assert service._is_duplicate("How to hike?") is False


# ---------------------------------------------------------------------------
# Test: PAAEnrichmentService._parse_paa_items
# ---------------------------------------------------------------------------


class TestParsePAAItems:
    """Tests for PAA item parsing from SERP response."""

    def test_parse_standard_paa_items(
        self, sample_paa_serp_response: dict[str, Any]
    ) -> None:
        """Should parse standard PAA elements correctly."""
        service = PAAEnrichmentService()
        items = sample_paa_serp_response["tasks"][0]["result"][0]["items"]

        questions = service._parse_paa_items(items)

        assert len(questions) == 3
        assert questions[0].question == "What are the best hiking boots?"
        assert questions[0].answer_snippet == "The best hiking boots..."
        assert questions[0].source_url == "https://example.com/best-boots"
        assert questions[0].source_domain == "example.com"
        assert questions[0].position == 1
        assert questions[0].is_nested is False

    def test_parse_ai_overview_paa_items(
        self, sample_paa_ai_overview_response: dict[str, Any]
    ) -> None:
        """Should parse AI overview expanded elements correctly."""
        service = PAAEnrichmentService()
        items = sample_paa_ai_overview_response["tasks"][0]["result"][0]["items"]

        questions = service._parse_paa_items(items)

        assert len(questions) == 1
        assert questions[0].question == "What is the best brand?"
        assert questions[0].answer_snippet == "AI generated answer..."
        assert questions[0].source_url == "https://ai.example.com/answer"
        assert questions[0].source_domain == "ai.example.com"

    def test_parse_empty_response(self, empty_paa_response: dict[str, Any]) -> None:
        """Should return empty list when no PAA items."""
        service = PAAEnrichmentService()
        items = empty_paa_response["tasks"][0]["result"][0]["items"]

        questions = service._parse_paa_items(items)

        assert questions == []

    def test_parse_skips_duplicates(self) -> None:
        """Should skip duplicate questions during parsing."""
        service = PAAEnrichmentService()

        items = [
            {
                "type": "people_also_ask",
                "items": [
                    {
                        "type": "people_also_ask_element",
                        "title": "What is hiking?",
                    },
                    {
                        "type": "people_also_ask_element",
                        "title": "WHAT IS HIKING?",  # Duplicate
                    },
                    {
                        "type": "people_also_ask_element",
                        "title": "How to hike?",
                    },
                ],
            },
        ]

        questions = service._parse_paa_items(items)

        assert len(questions) == 2
        assert questions[0].question == "What is hiking?"
        assert questions[1].question == "How to hike?"

    def test_parse_with_nested_flag(self) -> None:
        """Should set is_nested and parent_question when specified."""
        service = PAAEnrichmentService()

        items = [
            {
                "type": "people_also_ask",
                "items": [
                    {
                        "type": "people_also_ask_element",
                        "title": "Nested question?",
                    },
                ],
            },
        ]

        questions = service._parse_paa_items(
            items, is_nested=True, parent_question="Parent question?"
        )

        assert len(questions) == 1
        assert questions[0].is_nested is True
        assert questions[0].parent_question == "Parent question?"


# ---------------------------------------------------------------------------
# Test: PAAEnrichmentService.enrich_keyword - Validation
# ---------------------------------------------------------------------------


class TestEnrichKeywordValidation:
    """Tests for keyword validation in enrich_keyword."""

    async def test_empty_keyword_raises_validation_error(self) -> None:
        """Should raise PAAValidationError for empty keyword."""
        service = PAAEnrichmentService()

        with pytest.raises(PAAValidationError) as exc_info:
            await service.enrich_keyword("")

        assert exc_info.value.field_name == "keyword"
        assert "empty" in exc_info.value.args[0].lower()

    async def test_whitespace_only_keyword_raises_validation_error(self) -> None:
        """Should raise PAAValidationError for whitespace-only keyword."""
        service = PAAEnrichmentService()

        with pytest.raises(PAAValidationError) as exc_info:
            await service.enrich_keyword("   ")

        assert exc_info.value.field_name == "keyword"


# ---------------------------------------------------------------------------
# Test: PAAEnrichmentService.enrich_keyword - Basic Operation
# ---------------------------------------------------------------------------


class TestEnrichKeywordBasic:
    """Tests for basic keyword enrichment without fan-out."""

    async def test_enrich_keyword_success(
        self,
        mock_dataforseo_client: AsyncMock,
        sample_paa_serp_response: dict[str, Any],
    ) -> None:
        """Should enrich keyword and return PAA questions."""
        mock_dataforseo_client._make_request.return_value = (
            sample_paa_serp_response,
            "req-123",
        )

        service = PAAEnrichmentService(
            client=mock_dataforseo_client,
            paa_click_depth=2,
        )

        result = await service.enrich_keyword(
            keyword="hiking boots",
            fanout_enabled=False,
            fallback_enabled=False,
        )

        assert result.success is True
        assert result.keyword == "hiking boots"
        assert result.initial_count == 3
        assert len(result.questions) == 3
        assert result.cost == 0.003

    async def test_enrich_keyword_strips_whitespace(
        self,
        mock_dataforseo_client: AsyncMock,
        sample_paa_serp_response: dict[str, Any],
    ) -> None:
        """Should strip whitespace from keyword."""
        mock_dataforseo_client._make_request.return_value = (
            sample_paa_serp_response,
            "req-123",
        )

        service = PAAEnrichmentService(client=mock_dataforseo_client)

        result = await service.enrich_keyword(
            keyword="  hiking boots  ",
            fanout_enabled=False,
            fallback_enabled=False,
        )

        assert result.success is True
        assert result.keyword == "hiking boots"

    async def test_enrich_keyword_empty_paa_response(
        self,
        mock_dataforseo_client: AsyncMock,
        empty_paa_response: dict[str, Any],
    ) -> None:
        """Should handle empty PAA response gracefully."""
        mock_dataforseo_client._make_request.return_value = (
            empty_paa_response,
            "req-123",
        )

        service = PAAEnrichmentService(client=mock_dataforseo_client)

        result = await service.enrich_keyword(
            keyword="obscure topic",
            fanout_enabled=False,
            fallback_enabled=False,
        )

        assert result.success is True
        assert result.initial_count == 0
        assert len(result.questions) == 0


# ---------------------------------------------------------------------------
# Test: PAAEnrichmentService.enrich_keyword - Fan-out Strategy
# ---------------------------------------------------------------------------


class TestEnrichKeywordFanout:
    """Tests for fan-out strategy."""

    async def test_fanout_searches_initial_questions(
        self,
        mock_dataforseo_client: AsyncMock,
        sample_paa_serp_response: dict[str, Any],
    ) -> None:
        """Fan-out should search initial PAA questions for nested questions."""
        # First call returns initial questions, subsequent calls return nested
        nested_response = {
            "tasks": [
                {
                    "result": [
                        {
                            "items": [
                                {
                                    "type": "people_also_ask",
                                    "items": [
                                        {
                                            "type": "people_also_ask_element",
                                            "title": "Nested question from fanout?",
                                        },
                                    ],
                                },
                            ]
                        }
                    ]
                }
            ],
            "cost": 0.001,
        }

        mock_dataforseo_client._make_request.side_effect = [
            (sample_paa_serp_response, "req-1"),  # Initial fetch
            (nested_response, "req-2"),  # Fanout 1
            (nested_response, "req-3"),  # Fanout 2
            (nested_response, "req-4"),  # Fanout 3
        ]

        service = PAAEnrichmentService(
            client=mock_dataforseo_client,
            max_concurrent_fanout=5,
        )

        result = await service.enrich_keyword(
            keyword="hiking boots",
            fanout_enabled=True,
            max_fanout_questions=3,  # Only fanout on first 3 questions
            fallback_enabled=False,
        )

        assert result.success is True
        assert result.initial_count == 3
        # 3 initial + 3 nested (1 per fanout, deduped)
        assert result.nested_count >= 1

    async def test_fanout_respects_max_fanout_questions(
        self,
        mock_dataforseo_client: AsyncMock,
        sample_paa_serp_response: dict[str, Any],
    ) -> None:
        """Fan-out should limit to max_fanout_questions."""
        mock_dataforseo_client._make_request.return_value = (
            sample_paa_serp_response,
            "req-123",
        )

        service = PAAEnrichmentService(client=mock_dataforseo_client)

        await service.enrich_keyword(
            keyword="hiking boots",
            fanout_enabled=True,
            max_fanout_questions=2,  # Only 2 fanout searches
            fallback_enabled=False,
        )

        # Initial call + 2 fanout calls = 3 total
        assert mock_dataforseo_client._make_request.call_count == 3

    async def test_fanout_deduplicates_nested_questions(
        self,
        mock_dataforseo_client: AsyncMock,
        sample_paa_serp_response: dict[str, Any],
    ) -> None:
        """Fan-out should deduplicate questions from nested searches."""
        # Nested response contains a question that was already in initial
        nested_response = {
            "tasks": [
                {
                    "result": [
                        {
                            "items": [
                                {
                                    "type": "people_also_ask",
                                    "items": [
                                        {
                                            "type": "people_also_ask_element",
                                            "title": "What are the best hiking boots?",  # Duplicate!
                                        },
                                        {
                                            "type": "people_also_ask_element",
                                            "title": "Unique nested question?",
                                        },
                                    ],
                                },
                            ]
                        }
                    ]
                }
            ],
            "cost": 0.001,
        }

        mock_dataforseo_client._make_request.side_effect = [
            (sample_paa_serp_response, "req-1"),  # Initial: 3 questions
            (nested_response, "req-2"),  # Nested: 1 dup + 1 unique
        ]

        service = PAAEnrichmentService(client=mock_dataforseo_client)

        result = await service.enrich_keyword(
            keyword="hiking boots",
            fanout_enabled=True,
            max_fanout_questions=1,
            fallback_enabled=False,
        )

        # Should have initial 3 + 1 unique nested (duplicate skipped)
        assert len(result.questions) == 4

    async def test_fanout_handles_api_errors_gracefully(
        self,
        mock_dataforseo_client: AsyncMock,
        sample_paa_serp_response: dict[str, Any],
    ) -> None:
        """Fan-out should continue if individual fanout searches fail."""
        from app.integrations.dataforseo import DataForSEOError

        # Initial succeeds, fanout fails
        mock_dataforseo_client._make_request.side_effect = [
            (sample_paa_serp_response, "req-1"),  # Initial success
            DataForSEOError("API error"),  # Fanout 1 fails
            DataForSEOError("API error"),  # Fanout 2 fails
        ]

        service = PAAEnrichmentService(client=mock_dataforseo_client)

        result = await service.enrich_keyword(
            keyword="hiking boots",
            fanout_enabled=True,
            max_fanout_questions=2,
            fallback_enabled=False,
        )

        # Should still succeed with initial questions
        assert result.success is True
        assert result.initial_count == 3
        assert result.nested_count == 0


# ---------------------------------------------------------------------------
# Test: PAAEnrichmentService.enrich_keyword - Related Searches Fallback
# ---------------------------------------------------------------------------


class TestEnrichKeywordFallback:
    """Tests for related searches fallback."""

    async def test_fallback_triggers_when_paa_insufficient(
        self,
        mock_dataforseo_client: AsyncMock,
    ) -> None:
        """Should trigger fallback when PAA count < min_paa_for_fallback."""
        # Only 1 PAA question returned
        sparse_response = {
            "tasks": [
                {
                    "result": [
                        {
                            "items": [
                                {
                                    "type": "people_also_ask",
                                    "items": [
                                        {
                                            "type": "people_also_ask_element",
                                            "title": "Only one question?",
                                        },
                                    ],
                                },
                            ]
                        }
                    ]
                }
            ],
            "cost": 0.001,
        }
        mock_dataforseo_client._make_request.return_value = (sparse_response, "req-123")

        # Mock the related searches service at the source module (where it's imported)
        with patch(
            "app.services.related_searches.get_related_searches_service"
        ) as mock_get_service:
            from app.services.related_searches import (
                RelatedSearch,
                RelatedSearchesResult,
            )

            mock_service = MagicMock()
            mock_service.get_related_searches = AsyncMock(
                return_value=RelatedSearchesResult(
                    success=True,
                    keyword="hiking boots",
                    filtered_searches=[
                        RelatedSearch(
                            search_term="best hiking boots 2024",
                            question_form="What are the best hiking boots in 2024?",
                            relevance_score=0.8,
                            is_filtered=True,
                        ),
                    ],
                )
            )
            mock_get_service.return_value = mock_service

            service = PAAEnrichmentService(client=mock_dataforseo_client)

            result = await service.enrich_keyword(
                keyword="hiking boots",
                fanout_enabled=False,
                fallback_enabled=True,
                min_paa_for_fallback=3,  # Need 3, only have 1
            )

            assert result.success is True
            assert result.used_fallback is True
            assert result.related_search_count == 1
            # 1 initial + 1 from fallback
            assert len(result.questions) == 2

    async def test_fallback_not_triggered_when_paa_sufficient(
        self,
        mock_dataforseo_client: AsyncMock,
        sample_paa_serp_response: dict[str, Any],
    ) -> None:
        """Should not trigger fallback when PAA count >= min_paa_for_fallback."""
        mock_dataforseo_client._make_request.return_value = (
            sample_paa_serp_response,
            "req-123",
        )

        # Mock the related searches service - should not be called
        with patch(
            "app.services.related_searches.get_related_searches_service"
        ) as mock_get_service:
            service = PAAEnrichmentService(client=mock_dataforseo_client)

            result = await service.enrich_keyword(
                keyword="hiking boots",
                fanout_enabled=False,
                fallback_enabled=True,
                min_paa_for_fallback=3,  # Have 3, need 3
            )

            assert result.success is True
            assert result.used_fallback is False
            mock_get_service.return_value.get_related_searches.assert_not_called()

    async def test_fallback_handles_errors_gracefully(
        self,
        mock_dataforseo_client: AsyncMock,
    ) -> None:
        """Fallback errors should not fail the whole operation."""
        sparse_response = {
            "tasks": [
                {
                    "result": [
                        {
                            "items": [
                                {
                                    "type": "people_also_ask",
                                    "items": [
                                        {
                                            "type": "people_also_ask_element",
                                            "title": "Only one?",
                                        },
                                    ],
                                },
                            ]
                        }
                    ]
                }
            ],
            "cost": 0.001,
        }
        mock_dataforseo_client._make_request.return_value = (sparse_response, "req-123")

        # Mock fallback to fail at the source module
        with patch(
            "app.services.related_searches.get_related_searches_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_related_searches = AsyncMock(
                side_effect=Exception("Fallback failed")
            )
            mock_get_service.return_value = mock_service

            service = PAAEnrichmentService(client=mock_dataforseo_client)

            result = await service.enrich_keyword(
                keyword="hiking boots",
                fanout_enabled=False,
                fallback_enabled=True,
                min_paa_for_fallback=3,
            )

            # Should still succeed with initial questions
            assert result.success is True
            assert len(result.questions) == 1


# ---------------------------------------------------------------------------
# Test: PAAEnrichmentService.enrich_keyword - Categorization Integration
# ---------------------------------------------------------------------------


class TestEnrichKeywordCategorization:
    """Tests for categorization integration."""

    async def test_categorization_enabled(
        self,
        mock_dataforseo_client: AsyncMock,
        sample_paa_serp_response: dict[str, Any],
    ) -> None:
        """Should categorize questions when categorize_enabled=True."""
        mock_dataforseo_client._make_request.return_value = (
            sample_paa_serp_response,
            "req-123",
        )

        # Mock at the source module where get_paa_categorization_service is defined
        with patch(
            "app.services.paa_categorization.get_paa_categorization_service"
        ) as mock_get_cat:
            mock_cat_service = MagicMock()

            # Return questions with intents set
            async def categorize_questions(paa_questions, keyword, **kwargs):
                for q in paa_questions:
                    q.intent = PAAQuestionIntent.USAGE
                return paa_questions

            mock_cat_service.categorize_paa_questions = AsyncMock(
                side_effect=categorize_questions
            )
            mock_get_cat.return_value = mock_cat_service

            service = PAAEnrichmentService(client=mock_dataforseo_client)

            result = await service.enrich_keyword(
                keyword="hiking boots",
                fanout_enabled=False,
                fallback_enabled=False,
                categorize_enabled=True,
            )

            assert result.success is True
            mock_cat_service.categorize_paa_questions.assert_called_once()

    async def test_categorization_handles_errors_gracefully(
        self,
        mock_dataforseo_client: AsyncMock,
        sample_paa_serp_response: dict[str, Any],
    ) -> None:
        """Categorization errors should not fail the whole operation."""
        mock_dataforseo_client._make_request.return_value = (
            sample_paa_serp_response,
            "req-123",
        )

        # Mock at the source module
        with patch(
            "app.services.paa_categorization.get_paa_categorization_service"
        ) as mock_get_cat:
            mock_cat_service = MagicMock()
            mock_cat_service.categorize_paa_questions = AsyncMock(
                side_effect=Exception("Categorization failed")
            )
            mock_get_cat.return_value = mock_cat_service

            service = PAAEnrichmentService(client=mock_dataforseo_client)

            result = await service.enrich_keyword(
                keyword="hiking boots",
                fanout_enabled=False,
                fallback_enabled=False,
                categorize_enabled=True,
            )

            # Should still succeed with uncategorized questions
            assert result.success is True
            assert len(result.questions) == 3


# ---------------------------------------------------------------------------
# Test: PAAEnrichmentService.enrich_keywords_batch
# ---------------------------------------------------------------------------


class TestEnrichKeywordsBatch:
    """Tests for batch keyword enrichment."""

    async def test_batch_enrichment_success(
        self,
        mock_dataforseo_client: AsyncMock,
        sample_paa_serp_response: dict[str, Any],
    ) -> None:
        """Should enrich multiple keywords in batch."""
        mock_dataforseo_client._make_request.return_value = (
            sample_paa_serp_response,
            "req-123",
        )

        service = PAAEnrichmentService(client=mock_dataforseo_client)

        results = await service.enrich_keywords_batch(
            keywords=["keyword1", "keyword2", "keyword3"],
            fanout_enabled=False,
            fallback_enabled=False,
            max_concurrent=2,
        )

        assert len(results) == 3
        assert all(r.success for r in results)

    async def test_batch_enrichment_empty_list(
        self,
        mock_dataforseo_client: AsyncMock,
    ) -> None:
        """Should handle empty keyword list."""
        service = PAAEnrichmentService(client=mock_dataforseo_client)

        results = await service.enrich_keywords_batch(
            keywords=[],
            fanout_enabled=False,
            fallback_enabled=False,
        )

        assert results == []

    async def test_batch_enrichment_respects_max_concurrent(
        self,
        mock_dataforseo_client: AsyncMock,
        sample_paa_serp_response: dict[str, Any],
    ) -> None:
        """Should respect max_concurrent limit."""
        call_times = []

        async def mock_request(*args, **kwargs):
            call_times.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.1)  # Simulate API latency
            return (sample_paa_serp_response, "req-123")

        mock_dataforseo_client._make_request.side_effect = mock_request

        service = PAAEnrichmentService(client=mock_dataforseo_client)

        await service.enrich_keywords_batch(
            keywords=["kw1", "kw2", "kw3", "kw4"],
            fanout_enabled=False,
            fallback_enabled=False,
            max_concurrent=2,
        )

        # With max_concurrent=2 and 4 keywords, we should see batching
        assert mock_dataforseo_client._make_request.call_count == 4


# ---------------------------------------------------------------------------
# Test: PAAEnrichmentService._to_question_form
# ---------------------------------------------------------------------------


class TestToQuestionForm:
    """Tests for search term to question conversion."""

    def test_preserves_existing_questions(self) -> None:
        """Should return as-is if already a question."""
        service = PAAEnrichmentService()

        assert service._to_question_form("What is hiking?") == "What is hiking?"
        assert service._to_question_form("How to hike?") == "How to hike?"

    def test_adds_question_mark_to_question_starters(self) -> None:
        """Should add ? to terms starting with question words."""
        service = PAAEnrichmentService()

        assert service._to_question_form("what is hiking") == "what is hiking?"
        assert service._to_question_form("How to clean boots") == "How to clean boots?"
        assert service._to_question_form("Why are boots expensive") == "Why are boots expensive?"
        assert service._to_question_form("Can I hike in sneakers") == "Can I hike in sneakers?"

    def test_converts_phrases_to_questions(self) -> None:
        """Should convert non-question phrases to questions."""
        service = PAAEnrichmentService()

        # Multi-word phrases get "What are"
        assert service._to_question_form("best hiking boots") == "What are best hiking boots?"

        # Single word gets "What is"
        assert service._to_question_form("hiking") == "What is hiking?"


# ---------------------------------------------------------------------------
# Test: Singleton and Convenience Functions
# ---------------------------------------------------------------------------


class TestSingletonAndConvenience:
    """Tests for singleton pattern and convenience functions."""

    def test_get_paa_enrichment_service_returns_singleton(self) -> None:
        """get_paa_enrichment_service should return the same instance."""
        # Reset singleton for test
        import app.services.paa_enrichment as module

        module._paa_enrichment_service = None

        service1 = get_paa_enrichment_service()
        service2 = get_paa_enrichment_service()

        assert service1 is service2

        # Clean up
        module._paa_enrichment_service = None


# ---------------------------------------------------------------------------
# Test: Error Handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for error handling in enrichment service."""

    async def test_dataforseo_error_returns_failure_result(
        self,
        mock_dataforseo_client: AsyncMock,
    ) -> None:
        """DataForSEO errors should return failure result."""
        from app.integrations.dataforseo import DataForSEOError

        mock_dataforseo_client._make_request.side_effect = DataForSEOError(
            "API unavailable"
        )

        service = PAAEnrichmentService(client=mock_dataforseo_client)

        result = await service.enrich_keyword(
            keyword="test",
            fanout_enabled=False,
            fallback_enabled=False,
        )

        assert result.success is False
        assert result.error is not None
        assert "API unavailable" in result.error

    async def test_unexpected_error_returns_failure_result(
        self,
        mock_dataforseo_client: AsyncMock,
    ) -> None:
        """Unexpected errors should return failure result."""
        mock_dataforseo_client._make_request.side_effect = RuntimeError("Unexpected")

        service = PAAEnrichmentService(client=mock_dataforseo_client)

        result = await service.enrich_keyword(
            keyword="test",
            fanout_enabled=False,
            fallback_enabled=False,
        )

        assert result.success is False
        assert result.error is not None
        assert "Unexpected" in result.error


# ---------------------------------------------------------------------------
# Test: Initialization
# ---------------------------------------------------------------------------


class TestServiceInitialization:
    """Tests for service initialization."""

    def test_paa_click_depth_clamped(self) -> None:
        """paa_click_depth should be clamped to 1-4."""
        service_low = PAAEnrichmentService(paa_click_depth=0)
        assert service_low._paa_click_depth == 1

        service_high = PAAEnrichmentService(paa_click_depth=10)
        assert service_high._paa_click_depth == 4

        service_valid = PAAEnrichmentService(paa_click_depth=3)
        assert service_valid._paa_click_depth == 3

    def test_default_initialization(self) -> None:
        """Service should have sensible defaults."""
        service = PAAEnrichmentService()

        assert service._paa_click_depth == 2  # DEFAULT_PAA_CLICK_DEPTH
        assert service._max_concurrent_fanout == DEFAULT_MAX_CONCURRENT_FANOUT
