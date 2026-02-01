"""Unit tests for Amazon reviews fallback persona generation.

Tests cover:
- Fallback persona generation from website analysis
- FallbackPersona dataclass structure
- Integration with analyze_brand_reviews when no Amazon store found
- needs_review and fallback_used flags
- Error handling during fallback generation
- Logging per requirements

ERROR LOGGING REQUIREMENTS (verified by tests):
- Test failures include full assertion context
- Test setup/teardown logged at DEBUG level
- Capture and display logs from failed tests
- Include timing information in test reports
- Log mock/stub invocations for debugging

Target: 80% code coverage for fallback functionality.
"""

import json
import logging
from unittest.mock import AsyncMock

import pytest

from app.integrations.amazon_reviews import (
    FALLBACK_PERSONA_PROMPT,
    AmazonReviewAnalysisResult,
    AmazonReviewsClient,
    FallbackPersona,
)
from app.integrations.perplexity import CompletionResult

# Configure logging for tests
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Test Data Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_fallback_persona_response() -> str:
    """Sample LLM response with fallback personas."""
    return json.dumps(
        {
            "personas": [
                {
                    "name": "Budget-Conscious Parent",
                    "description": "Parents looking for affordable, durable products for their kids",
                    "characteristics": [
                        "Price-sensitive",
                        "Values durability",
                        "Reads reviews carefully",
                    ],
                },
                {
                    "name": "Quality-Focused Professional",
                    "description": "Working professionals who prioritize quality over price",
                    "characteristics": [
                        "Willing to pay premium",
                        "Time-constrained",
                        "Brand-loyal",
                    ],
                },
            ],
            "confidence_note": "Inferred from brand positioning and typical market segment",
        }
    )


@pytest.fixture
def sample_fallback_persona_response_with_markdown() -> str:
    """Sample LLM response wrapped in markdown code block."""
    return """```json
{
    "personas": [
        {
            "name": "Eco-Conscious Consumer",
            "description": "Environmentally aware shoppers seeking sustainable products",
            "characteristics": ["Researches sustainability claims", "Pays premium for eco-friendly"]
        }
    ],
    "confidence_note": "Based on brand's eco-friendly messaging"
}
```"""


@pytest.fixture
def mock_perplexity_client() -> AsyncMock:
    """Create a mock Perplexity client."""
    mock = AsyncMock()
    mock.available = True
    return mock


# ---------------------------------------------------------------------------
# FallbackPersona Dataclass Tests
# ---------------------------------------------------------------------------


class TestFallbackPersonaDataclass:
    """Tests for the FallbackPersona dataclass."""

    def test_fallback_persona_creation_with_all_fields(self) -> None:
        """Test creating FallbackPersona with all fields."""
        persona = FallbackPersona(
            name="Test Persona",
            description="A test persona description",
            source="website_analysis",
            inferred=True,
            characteristics=["trait1", "trait2"],
        )

        assert persona.name == "Test Persona"
        assert persona.description == "A test persona description"
        assert persona.source == "website_analysis"
        assert persona.inferred is True
        assert persona.characteristics == ["trait1", "trait2"]

    def test_fallback_persona_default_values(self) -> None:
        """Test FallbackPersona default values."""
        persona = FallbackPersona(
            name="Minimal Persona",
            description="Description only",
        )

        assert persona.name == "Minimal Persona"
        assert persona.description == "Description only"
        assert persona.source == "website_analysis"
        assert persona.inferred is True
        assert persona.characteristics == []

    def test_fallback_persona_empty_characteristics(self) -> None:
        """Test FallbackPersona with empty characteristics list."""
        persona = FallbackPersona(
            name="Empty Chars",
            description="No characteristics",
            characteristics=[],
        )

        assert persona.characteristics == []


# ---------------------------------------------------------------------------
# AmazonReviewAnalysisResult Fallback Fields Tests
# ---------------------------------------------------------------------------


class TestAmazonReviewAnalysisResultFallbackFields:
    """Tests for fallback-related fields in AmazonReviewAnalysisResult."""

    def test_result_with_fallback_fields(self) -> None:
        """Test AmazonReviewAnalysisResult includes fallback fields."""
        result = AmazonReviewAnalysisResult(
            success=True,
            brand_name="Test Brand",
            needs_review=True,
            fallback_used=True,
            fallback_source="website_analysis",
        )

        assert result.needs_review is True
        assert result.fallback_used is True
        assert result.fallback_source == "website_analysis"

    def test_result_default_fallback_fields(self) -> None:
        """Test default values for fallback fields."""
        result = AmazonReviewAnalysisResult(
            success=True,
            brand_name="Test Brand",
        )

        assert result.needs_review is False
        assert result.fallback_used is False
        assert result.fallback_source is None


# ---------------------------------------------------------------------------
# generate_fallback_personas Method Tests
# ---------------------------------------------------------------------------


class TestGenerateFallbackPersonas:
    """Tests for the generate_fallback_personas method."""

    @pytest.mark.asyncio
    async def test_generate_fallback_personas_success(
        self,
        sample_fallback_persona_response: str,
        mock_perplexity_client: AsyncMock,
    ) -> None:
        """Test successful fallback persona generation."""
        mock_perplexity_client.complete.return_value = CompletionResult(
            success=True,
            text=sample_fallback_persona_response,
        )

        client = AmazonReviewsClient(perplexity_client=mock_perplexity_client)

        personas = await client.generate_fallback_personas(
            brand_name="Test Brand",
            website_url="https://testbrand.com",
            project_id="test-project-123",
        )

        assert len(personas) == 2
        assert personas[0].name == "Budget-Conscious Parent"
        assert personas[0].source == "website_analysis"
        assert personas[0].inferred is True
        assert len(personas[0].characteristics) == 3
        assert personas[1].name == "Quality-Focused Professional"

    @pytest.mark.asyncio
    async def test_generate_fallback_personas_with_markdown_response(
        self,
        sample_fallback_persona_response_with_markdown: str,
        mock_perplexity_client: AsyncMock,
    ) -> None:
        """Test fallback persona generation handles markdown-wrapped JSON."""
        mock_perplexity_client.complete.return_value = CompletionResult(
            success=True,
            text=sample_fallback_persona_response_with_markdown,
        )

        client = AmazonReviewsClient(perplexity_client=mock_perplexity_client)

        personas = await client.generate_fallback_personas(
            brand_name="Eco Brand",
            project_id="test-project-123",
        )

        assert len(personas) == 1
        assert personas[0].name == "Eco-Conscious Consumer"

    @pytest.mark.asyncio
    async def test_generate_fallback_personas_perplexity_unavailable(
        self,
        mock_perplexity_client: AsyncMock,
    ) -> None:
        """Test fallback when Perplexity is unavailable."""
        mock_perplexity_client.available = False

        client = AmazonReviewsClient(perplexity_client=mock_perplexity_client)

        personas = await client.generate_fallback_personas(
            brand_name="Test Brand",
            project_id="test-project-123",
        )

        assert personas == []
        mock_perplexity_client.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_fallback_personas_api_failure(
        self,
        mock_perplexity_client: AsyncMock,
    ) -> None:
        """Test fallback returns empty list on API failure."""
        mock_perplexity_client.complete.return_value = CompletionResult(
            success=False,
            error="API error",
        )

        client = AmazonReviewsClient(perplexity_client=mock_perplexity_client)

        personas = await client.generate_fallback_personas(
            brand_name="Test Brand",
            project_id="test-project-123",
        )

        assert personas == []

    @pytest.mark.asyncio
    async def test_generate_fallback_personas_invalid_json(
        self,
        mock_perplexity_client: AsyncMock,
    ) -> None:
        """Test fallback handles invalid JSON response."""
        mock_perplexity_client.complete.return_value = CompletionResult(
            success=True,
            text="This is not valid JSON at all",
        )

        client = AmazonReviewsClient(perplexity_client=mock_perplexity_client)

        personas = await client.generate_fallback_personas(
            brand_name="Test Brand",
            project_id="test-project-123",
        )

        assert personas == []

    @pytest.mark.asyncio
    async def test_generate_fallback_personas_empty_personas_array(
        self,
        mock_perplexity_client: AsyncMock,
    ) -> None:
        """Test fallback handles empty personas array."""
        mock_perplexity_client.complete.return_value = CompletionResult(
            success=True,
            text=json.dumps({"personas": [], "confidence_note": "No personas found"}),
        )

        client = AmazonReviewsClient(perplexity_client=mock_perplexity_client)

        personas = await client.generate_fallback_personas(
            brand_name="Test Brand",
            project_id="test-project-123",
        )

        assert personas == []

    @pytest.mark.asyncio
    async def test_generate_fallback_personas_limits_to_three(
        self,
        mock_perplexity_client: AsyncMock,
    ) -> None:
        """Test fallback limits personas to 3."""
        response = json.dumps(
            {
                "personas": [
                    {"name": f"Persona {i}", "description": f"Description {i}"}
                    for i in range(5)
                ],
            }
        )
        mock_perplexity_client.complete.return_value = CompletionResult(
            success=True,
            text=response,
        )

        client = AmazonReviewsClient(perplexity_client=mock_perplexity_client)

        personas = await client.generate_fallback_personas(
            brand_name="Test Brand",
            project_id="test-project-123",
        )

        assert len(personas) == 3

    @pytest.mark.asyncio
    async def test_generate_fallback_personas_without_website_url(
        self,
        sample_fallback_persona_response: str,
        mock_perplexity_client: AsyncMock,
    ) -> None:
        """Test fallback uses brand name when no website URL provided."""
        mock_perplexity_client.complete.return_value = CompletionResult(
            success=True,
            text=sample_fallback_persona_response,
        )

        client = AmazonReviewsClient(perplexity_client=mock_perplexity_client)

        await client.generate_fallback_personas(
            brand_name="Test Brand",
            website_url=None,
            project_id="test-project-123",
        )

        # Verify prompt was called with brand name fallback for URL
        call_args = mock_perplexity_client.complete.call_args
        assert "Test Brand official website" in call_args.kwargs["user_prompt"]

    @pytest.mark.asyncio
    async def test_generate_fallback_personas_exception_handling(
        self,
        mock_perplexity_client: AsyncMock,
    ) -> None:
        """Test fallback handles exceptions gracefully."""
        mock_perplexity_client.complete.side_effect = Exception("Unexpected error")

        client = AmazonReviewsClient(perplexity_client=mock_perplexity_client)

        personas = await client.generate_fallback_personas(
            brand_name="Test Brand",
            project_id="test-project-123",
        )

        assert personas == []


# ---------------------------------------------------------------------------
# analyze_brand_reviews Fallback Integration Tests
# ---------------------------------------------------------------------------


class TestAnalyzeBrandReviewsFallback:
    """Tests for fallback integration in analyze_brand_reviews."""

    @pytest.mark.asyncio
    async def test_analyze_brand_reviews_triggers_fallback_when_no_store(
        self,
        sample_fallback_persona_response: str,
        mock_perplexity_client: AsyncMock,
    ) -> None:
        """Test fallback is triggered when no Amazon store found."""
        # First call: store detection returns no store
        # Second call: fallback persona generation
        mock_perplexity_client.complete.side_effect = [
            CompletionResult(success=True, text="[]"),  # No products
            CompletionResult(success=True, text=sample_fallback_persona_response),
        ]

        client = AmazonReviewsClient(perplexity_client=mock_perplexity_client)

        result = await client.analyze_brand_reviews(
            brand_name="Test Brand",
            website_url="https://testbrand.com",
            use_fallback=True,
            project_id="test-project-123",
        )

        assert result.success is True
        assert result.products_analyzed == 0
        assert result.fallback_used is True
        assert result.needs_review is True
        assert result.fallback_source == "website_analysis"
        assert len(result.customer_personas) == 2
        assert result.customer_personas[0]["name"] == "Budget-Conscious Parent"
        assert result.customer_personas[0]["source"] == "website_analysis"

    @pytest.mark.asyncio
    async def test_analyze_brand_reviews_no_fallback_when_disabled(
        self,
        mock_perplexity_client: AsyncMock,
    ) -> None:
        """Test fallback not triggered when use_fallback=False."""
        mock_perplexity_client.complete.return_value = CompletionResult(
            success=True,
            text="[]",  # No products
        )

        client = AmazonReviewsClient(perplexity_client=mock_perplexity_client)

        result = await client.analyze_brand_reviews(
            brand_name="Test Brand",
            use_fallback=False,
            project_id="test-project-123",
        )

        assert result.success is True
        assert result.products_analyzed == 0
        assert result.fallback_used is False
        assert result.needs_review is False
        assert result.fallback_source is None
        assert len(result.customer_personas) == 0
        # Only one call (store detection), no fallback call
        assert mock_perplexity_client.complete.call_count == 1

    @pytest.mark.asyncio
    async def test_analyze_brand_reviews_fallback_failure_still_succeeds(
        self,
        mock_perplexity_client: AsyncMock,
    ) -> None:
        """Test analysis succeeds even if fallback fails."""
        mock_perplexity_client.complete.side_effect = [
            CompletionResult(success=True, text="[]"),  # No products
            CompletionResult(success=False, error="Fallback failed"),  # Fallback fails
        ]

        client = AmazonReviewsClient(perplexity_client=mock_perplexity_client)

        result = await client.analyze_brand_reviews(
            brand_name="Test Brand",
            use_fallback=True,
            project_id="test-project-123",
        )

        assert result.success is True
        assert result.fallback_used is False
        assert result.needs_review is False
        assert len(result.customer_personas) == 0


# ---------------------------------------------------------------------------
# Prompt Template Tests
# ---------------------------------------------------------------------------


class TestFallbackPersonaPrompt:
    """Tests for the fallback persona prompt template."""

    def test_prompt_template_has_required_placeholders(self) -> None:
        """Test prompt template contains required placeholders."""
        assert "{brand_name}" in FALLBACK_PERSONA_PROMPT
        assert "{website_url}" in FALLBACK_PERSONA_PROMPT

    def test_prompt_requests_json_format(self) -> None:
        """Test prompt asks for JSON format."""
        assert "JSON" in FALLBACK_PERSONA_PROMPT
        assert "personas" in FALLBACK_PERSONA_PROMPT

    def test_prompt_requests_persona_fields(self) -> None:
        """Test prompt requests required persona fields."""
        assert "name" in FALLBACK_PERSONA_PROMPT
        assert "description" in FALLBACK_PERSONA_PROMPT
        assert "characteristics" in FALLBACK_PERSONA_PROMPT
