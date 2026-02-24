"""Unit tests for ContentScoreService content quality analysis.

Tests cover:
- WordCountScore dataclass creation and serialization
- SemanticScore dataclass creation and serialization
- ReadabilityScore dataclass creation and serialization
- KeywordDensityScore dataclass creation and serialization
- EntityCoverageScore dataclass creation and serialization
- ContentScoreInput and ContentScoreResult dataclasses
- ContentScoreService initialization with custom weights
- Word count computation (_compute_word_count_score)
- Semantic analysis (_compute_semantic_score)
- Readability scoring (_compute_readability_score)
- Keyword density computation (_compute_keyword_density_score)
- Entity extraction (_compute_entity_coverage_score)
- score_content() main method
- score_content_batch() batch processing
- Singleton and convenience functions
- Validation and error handling
- Edge cases (empty content, unicode, etc.)

ERROR LOGGING REQUIREMENTS:
- Ensure test failures include full assertion context
- Log test setup/teardown at DEBUG level
- Capture and display logs from failed tests
- Include timing information in test reports
- Log mock/stub invocations for debugging

Target: 80% code coverage for ContentScoreService.
"""

import logging

import pytest

from app.services.content_score import (
    DEFAULT_SCORING_WEIGHTS,
    DEFAULT_TARGET_KEYWORD_DENSITY_MAX,
    DEFAULT_TARGET_KEYWORD_DENSITY_MIN,
    DEFAULT_TARGET_WORD_COUNT_MAX,
    DEFAULT_TARGET_WORD_COUNT_MIN,
    STOP_WORDS,
    ContentScoreInput,
    ContentScoreResult,
    ContentScoreService,
    ContentScoreServiceError,
    ContentScoreValidationError,
    EntityCoverageScore,
    KeywordDensityScore,
    ReadabilityScore,
    SemanticScore,
    WordCountScore,
    get_content_score_service,
    score_content,
)

# Enable debug logging for test visibility
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service() -> ContentScoreService:
    """Create a ContentScoreService instance."""
    logger.debug("Creating ContentScoreService")
    return ContentScoreService()


@pytest.fixture
def sample_content() -> str:
    """Sample content for scoring analysis."""
    logger.debug("Creating sample content fixture")
    return """
    Premium Leather Wallets for Men: The Ultimate Guide

    When shopping for a quality leather wallet, there are several factors to consider.
    Genuine leather wallets offer durability and style that synthetic materials cannot match.
    Our collection features bifold and trifold designs crafted from full-grain leather.

    The best wallets combine functionality with elegant design. Look for features like
    RFID blocking technology, multiple card slots, and a slim profile that fits
    comfortably in your pocket. Our wallets range from $49 to $199 depending on
    the leather quality and craftsmanship.

    Made in the USA, our wallets come with a lifetime warranty. Each wallet is
    hand-stitched by skilled artisans in our New York workshop. Whether you prefer
    classic brown or modern black, we have options for every style.

    Visit our store in Los Angeles or order online today. Free shipping on orders
    over $75. Contact us at support@example.com for custom orders.
    """


@pytest.fixture
def short_content() -> str:
    """Short content for edge case testing."""
    logger.debug("Creating short content fixture")
    return "This is a short piece of content for testing."


@pytest.fixture
def keyword_stuffed_content() -> str:
    """Content with keyword stuffing for density testing."""
    logger.debug("Creating keyword stuffed content fixture")
    return """
    Leather wallet leather wallet leather wallet. Buy leather wallet today.
    Leather wallet sale on leather wallet. Best leather wallet for leather wallet
    lovers. Leather wallet leather wallet leather wallet leather wallet.
    """


# ---------------------------------------------------------------------------
# Test: Data Classes
# ---------------------------------------------------------------------------


class TestWordCountScore:
    """Tests for WordCountScore dataclass."""

    def test_create_word_count_score(self) -> None:
        """Should create WordCountScore with all fields."""
        score = WordCountScore(
            word_count=500,
            sentence_count=25,
            paragraph_count=5,
            avg_words_per_sentence=20.0,
            score=0.85,
        )
        assert score.word_count == 500
        assert score.sentence_count == 25
        assert score.paragraph_count == 5
        assert score.avg_words_per_sentence == 20.0
        assert score.score == 0.85

    def test_word_count_score_to_dict(self) -> None:
        """Should convert to dictionary correctly."""
        score = WordCountScore(
            word_count=350,
            sentence_count=18,
            paragraph_count=3,
            avg_words_per_sentence=19.444,
            score=0.9234,
        )
        data = score.to_dict()

        assert data["word_count"] == 350
        assert data["sentence_count"] == 18
        assert data["paragraph_count"] == 3
        assert data["avg_words_per_sentence"] == 19.44  # Rounded to 2 decimals
        assert data["score"] == 0.9234  # Rounded to 4 decimals

    def test_word_count_score_defaults(self) -> None:
        """Should have correct default values."""
        score = WordCountScore()
        assert score.word_count == 0
        assert score.sentence_count == 0
        assert score.paragraph_count == 0
        assert score.avg_words_per_sentence == 0.0
        assert score.score == 0.0


class TestSemanticScore:
    """Tests for SemanticScore dataclass."""

    def test_create_semantic_score(self) -> None:
        """Should create SemanticScore with all fields."""
        score = SemanticScore(
            top_terms=[("leather", 0.15), ("wallet", 0.12), ("quality", 0.08)],
            term_diversity=0.65,
            content_depth=0.8,
            score=0.75,
        )
        assert len(score.top_terms) == 3
        assert score.term_diversity == 0.65
        assert score.content_depth == 0.8
        assert score.score == 0.75

    def test_semantic_score_to_dict(self) -> None:
        """Should convert to dictionary correctly."""
        score = SemanticScore(
            top_terms=[("leather", 0.15234), ("wallet", 0.12)],
            term_diversity=0.6543,
            content_depth=0.8,
            score=0.75,
        )
        data = score.to_dict()

        assert len(data["top_terms"]) == 2
        assert data["top_terms"][0]["term"] == "leather"
        assert data["top_terms"][0]["score"] == 0.1523  # Rounded
        assert data["term_diversity"] == 0.6543
        assert data["content_depth"] == 0.8

    def test_semantic_score_defaults(self) -> None:
        """Should have correct default values."""
        score = SemanticScore()
        assert score.top_terms == []
        assert score.term_diversity == 0.0
        assert score.content_depth == 0.0
        assert score.score == 0.0


class TestReadabilityScore:
    """Tests for ReadabilityScore dataclass."""

    def test_create_readability_score(self) -> None:
        """Should create ReadabilityScore with all fields."""
        score = ReadabilityScore(
            flesch_reading_ease=65.5,
            flesch_kincaid_grade=8.2,
            avg_syllables_per_word=1.45,
            score=0.9,
        )
        assert score.flesch_reading_ease == 65.5
        assert score.flesch_kincaid_grade == 8.2
        assert score.avg_syllables_per_word == 1.45
        assert score.score == 0.9

    def test_readability_score_to_dict(self) -> None:
        """Should convert to dictionary correctly."""
        score = ReadabilityScore(
            flesch_reading_ease=65.567,
            flesch_kincaid_grade=8.234,
            avg_syllables_per_word=1.456,
            score=0.9,
        )
        data = score.to_dict()

        assert data["flesch_reading_ease"] == 65.57  # Rounded to 2
        assert data["flesch_kincaid_grade"] == 8.23
        assert data["avg_syllables_per_word"] == 1.46
        assert data["score"] == 0.9


class TestKeywordDensityScore:
    """Tests for KeywordDensityScore dataclass."""

    def test_create_keyword_density_score(self) -> None:
        """Should create KeywordDensityScore with all fields."""
        score = KeywordDensityScore(
            primary_keyword="leather wallet",
            primary_density=1.5,
            secondary_keywords=[("genuine leather", 0.8), ("bifold", 0.3)],
            total_keyword_occurrences=15,
            score=0.85,
        )
        assert score.primary_keyword == "leather wallet"
        assert score.primary_density == 1.5
        assert len(score.secondary_keywords) == 2
        assert score.total_keyword_occurrences == 15
        assert score.score == 0.85

    def test_keyword_density_score_to_dict(self) -> None:
        """Should convert to dictionary correctly."""
        score = KeywordDensityScore(
            primary_keyword="leather",
            primary_density=1.5678,
            secondary_keywords=[("wallet", 0.8123)],
            total_keyword_occurrences=10,
            score=0.85,
        )
        data = score.to_dict()

        assert data["primary_keyword"] == "leather"
        assert data["primary_density"] == 1.5678  # Rounded to 4
        assert len(data["secondary_keywords"]) == 1
        assert data["secondary_keywords"][0]["keyword"] == "wallet"
        assert data["secondary_keywords"][0]["density"] == 0.8123


class TestEntityCoverageScore:
    """Tests for EntityCoverageScore dataclass."""

    def test_create_entity_coverage_score(self) -> None:
        """Should create EntityCoverageScore with all fields."""
        score = EntityCoverageScore(
            entities={"money": ["$49", "$199"], "location": ["USA", "New York"]},
            entity_count=4,
            entity_types_covered=2,
            coverage_ratio=0.33,
            score=0.7,
        )
        assert len(score.entities) == 2
        assert score.entity_count == 4
        assert score.entity_types_covered == 2
        assert score.coverage_ratio == 0.33
        assert score.score == 0.7

    def test_entity_coverage_score_to_dict(self) -> None:
        """Should convert and dedupe entities correctly."""
        score = EntityCoverageScore(
            entities={"money": ["$49", "$49", "$199"]},  # Duplicate
            entity_count=3,
            entity_types_covered=1,
            coverage_ratio=0.167,
            score=0.5,
        )
        data = score.to_dict()

        # Should dedupe
        assert len(data["entities"]["money"]) == 2  # $49 and $199


class TestContentScoreInput:
    """Tests for ContentScoreInput dataclass."""

    def test_create_minimal_input(self) -> None:
        """Should create input with minimal fields."""
        input_data = ContentScoreInput(content="Test content")
        assert input_data.content == "Test content"
        assert input_data.primary_keyword == ""
        assert input_data.secondary_keywords == []
        assert input_data.target_word_count_min == DEFAULT_TARGET_WORD_COUNT_MIN
        assert input_data.target_word_count_max == DEFAULT_TARGET_WORD_COUNT_MAX
        assert input_data.project_id is None
        assert input_data.page_id is None

    def test_create_full_input(self) -> None:
        """Should create input with all fields."""
        input_data = ContentScoreInput(
            content="Full test content",
            primary_keyword="test keyword",
            secondary_keywords=["related", "terms"],
            target_word_count_min=500,
            target_word_count_max=1500,
            project_id="proj-123",
            page_id="page-456",
        )
        assert input_data.content == "Full test content"
        assert input_data.primary_keyword == "test keyword"
        assert len(input_data.secondary_keywords) == 2
        assert input_data.target_word_count_min == 500
        assert input_data.target_word_count_max == 1500
        assert input_data.project_id == "proj-123"
        assert input_data.page_id == "page-456"

    def test_input_to_dict_sanitized(self) -> None:
        """Should sanitize content in to_dict()."""
        input_data = ContentScoreInput(
            content="Sensitive content that should not appear",
            primary_keyword="keyword",
            secondary_keywords=["a", "b", "c"],
            project_id="proj-123",
        )
        data = input_data.to_dict()

        # Content should be length only, not actual content
        assert "content_length" in data
        assert data["content_length"] == len(input_data.content)
        assert "Sensitive" not in str(data)


class TestContentScoreResult:
    """Tests for ContentScoreResult dataclass."""

    def test_create_success_result(self) -> None:
        """Should create a successful result."""
        result = ContentScoreResult(
            success=True,
            overall_score=0.85,
            word_count_score=WordCountScore(word_count=500, score=0.9),
            passed=True,
            duration_ms=15.5,
            project_id="proj-1",
        )
        assert result.success is True
        assert result.overall_score == 0.85
        assert result.passed is True
        assert result.error is None
        assert result.duration_ms == 15.5

    def test_create_failure_result(self) -> None:
        """Should create a failed result with error."""
        result = ContentScoreResult(
            success=False,
            error="Content cannot be empty",
            project_id="proj-1",
        )
        assert result.success is False
        assert result.error == "Content cannot be empty"
        assert result.passed is False

    def test_result_to_dict(self) -> None:
        """Should convert to dictionary correctly."""
        result = ContentScoreResult(
            success=True,
            overall_score=0.85678,
            word_count_score=WordCountScore(word_count=500, score=0.9),
            passed=True,
            duration_ms=15.567,
        )
        data = result.to_dict()

        assert data["success"] is True
        assert data["overall_score"] == 0.8568  # Rounded to 4
        assert data["word_count_score"]["word_count"] == 500
        assert data["duration_ms"] == 15.57  # Rounded to 2
        assert data["error"] is None


# ---------------------------------------------------------------------------
# Test: Exceptions
# ---------------------------------------------------------------------------


class TestExceptions:
    """Tests for exception classes."""

    def test_content_score_service_error(self) -> None:
        """Should create service error with context."""
        error = ContentScoreServiceError(
            message="Test error",
            project_id="proj-123",
            page_id="page-456",
        )
        assert str(error) == "Test error"
        assert error.project_id == "proj-123"
        assert error.page_id == "page-456"

    def test_content_score_validation_error(self) -> None:
        """Should create validation error with field info."""
        error = ContentScoreValidationError(
            field_name="content",
            value="",
            message="cannot be empty",
            project_id="proj-123",
        )
        assert "content" in str(error)
        assert "cannot be empty" in str(error)
        assert error.field_name == "content"
        assert error.value == ""


# ---------------------------------------------------------------------------
# Test: Service Initialization
# ---------------------------------------------------------------------------


class TestServiceInitialization:
    """Tests for ContentScoreService initialization."""

    def test_default_initialization(self) -> None:
        """Should initialize with default weights."""
        service = ContentScoreService()
        assert service.scoring_weights == DEFAULT_SCORING_WEIGHTS
        assert service.pass_threshold == 0.6

    def test_custom_weights(self) -> None:
        """Should accept custom weights."""
        custom_weights = {
            "word_count": 0.2,
            "semantic": 0.3,
            "readability": 0.2,
            "keyword_density": 0.2,
            "entity_coverage": 0.1,
        }
        service = ContentScoreService(scoring_weights=custom_weights)
        assert service.scoring_weights["word_count"] == 0.2
        assert service.scoring_weights["semantic"] == 0.3

    def test_weights_normalized(self) -> None:
        """Should normalize weights that don't sum to 1.0."""
        custom_weights = {
            "word_count": 0.1,
            "semantic": 0.1,
            "readability": 0.1,
            "keyword_density": 0.1,
            "entity_coverage": 0.1,
        }
        service = ContentScoreService(scoring_weights=custom_weights)
        # Sum should be normalized to 1.0
        weight_sum = sum(service.scoring_weights.values())
        assert 0.99 <= weight_sum <= 1.01

    def test_custom_pass_threshold(self) -> None:
        """Should accept custom pass threshold."""
        service = ContentScoreService(pass_threshold=0.8)
        assert service.pass_threshold == 0.8


# ---------------------------------------------------------------------------
# Test: Word Count Scoring
# ---------------------------------------------------------------------------


class TestWordCountScoring:
    """Tests for word count computation."""

    @pytest.mark.asyncio
    async def test_word_count_basic(self, service: ContentScoreService) -> None:
        """Should count words correctly."""
        content = "This is a test. It has ten words total here."
        input_data = ContentScoreInput(content=content)
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.word_count_score is not None
        # Count words (excluding very short ones)
        assert result.word_count_score.word_count > 0

    @pytest.mark.asyncio
    async def test_word_count_sentences(self, service: ContentScoreService) -> None:
        """Should count sentences correctly."""
        content = "First sentence. Second sentence! Third sentence?"
        input_data = ContentScoreInput(content=content)
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.word_count_score is not None
        assert result.word_count_score.sentence_count == 3

    @pytest.mark.asyncio
    async def test_word_count_paragraphs(self, service: ContentScoreService) -> None:
        """Should count paragraphs correctly."""
        content = "First paragraph here.\n\nSecond paragraph here.\n\nThird paragraph."
        input_data = ContentScoreInput(content=content)
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.word_count_score is not None
        assert result.word_count_score.paragraph_count == 3

    @pytest.mark.asyncio
    async def test_word_count_within_target(
        self, service: ContentScoreService, sample_content: str
    ) -> None:
        """Should score well for content within target range."""
        input_data = ContentScoreInput(
            content=sample_content,
            target_word_count_min=100,
            target_word_count_max=500,
        )
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.word_count_score is not None
        assert result.word_count_score.score >= 0.8

    @pytest.mark.asyncio
    async def test_word_count_below_target(
        self, service: ContentScoreService, short_content: str
    ) -> None:
        """Should penalize content below target."""
        input_data = ContentScoreInput(
            content=short_content,
            target_word_count_min=100,
            target_word_count_max=500,
        )
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.word_count_score is not None
        assert result.word_count_score.score < 0.5  # Penalized


# ---------------------------------------------------------------------------
# Test: Semantic Scoring
# ---------------------------------------------------------------------------


class TestSemanticScoring:
    """Tests for semantic analysis."""

    @pytest.mark.asyncio
    async def test_semantic_basic(
        self, service: ContentScoreService, sample_content: str
    ) -> None:
        """Should extract semantic features."""
        input_data = ContentScoreInput(content=sample_content)
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.semantic_score is not None
        assert len(result.semantic_score.top_terms) > 0
        assert result.semantic_score.term_diversity > 0

    @pytest.mark.asyncio
    async def test_semantic_filters_stop_words(
        self, service: ContentScoreService
    ) -> None:
        """Should filter out stop words."""
        content = "The the the and and and but but but."
        input_data = ContentScoreInput(content=content)
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.semantic_score is not None
        # All stop words = minimal score
        assert result.semantic_score.score <= 0.3

    @pytest.mark.asyncio
    async def test_semantic_term_diversity(
        self, service: ContentScoreService
    ) -> None:
        """Should measure term diversity."""
        diverse_content = """
        Leather wallets offer quality craftsmanship. Premium materials ensure
        durability. Stylish designs complement professional attire. Functional
        compartments organize cards efficiently.
        """
        repetitive_content = """
        Wallet wallet wallet wallet. Wallet wallet wallet wallet.
        Wallet wallet wallet wallet. Wallet wallet wallet.
        """

        diverse_result = await service.score_content(
            ContentScoreInput(content=diverse_content)
        )
        repetitive_result = await service.score_content(
            ContentScoreInput(content=repetitive_content)
        )

        assert diverse_result.success is True
        assert repetitive_result.success is True
        assert diverse_result.semantic_score is not None
        assert repetitive_result.semantic_score is not None
        # Diverse content should have higher diversity
        assert (
            diverse_result.semantic_score.term_diversity
            > repetitive_result.semantic_score.term_diversity
        )


# ---------------------------------------------------------------------------
# Test: Readability Scoring
# ---------------------------------------------------------------------------


class TestReadabilityScoring:
    """Tests for readability analysis."""

    @pytest.mark.asyncio
    async def test_readability_basic(
        self, service: ContentScoreService, sample_content: str
    ) -> None:
        """Should compute Flesch scores."""
        input_data = ContentScoreInput(content=sample_content)
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.readability_score is not None
        # Flesch reading ease should be in valid range
        assert 0 <= result.readability_score.flesch_reading_ease <= 100
        # Grade level should be positive
        assert result.readability_score.flesch_kincaid_grade >= 0

    @pytest.mark.asyncio
    async def test_readability_simple_text(
        self, service: ContentScoreService
    ) -> None:
        """Simple text should have high readability."""
        simple_content = "The cat sat on the mat. The dog ran in the park."
        input_data = ContentScoreInput(content=simple_content)
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.readability_score is not None
        # Simple text = high Flesch score
        assert result.readability_score.flesch_reading_ease > 60

    @pytest.mark.asyncio
    async def test_readability_complex_text(
        self, service: ContentScoreService
    ) -> None:
        """Complex text should have lower readability."""
        complex_content = """
        The juxtaposition of antithetical philosophical paradigms necessitates
        a comprehensive epistemological examination of the foundational
        presuppositions underlying contemporary ontological frameworks.
        """
        input_data = ContentScoreInput(content=complex_content)
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.readability_score is not None
        # Complex text = lower Flesch score
        assert result.readability_score.flesch_reading_ease < 50


# ---------------------------------------------------------------------------
# Test: Keyword Density Scoring
# ---------------------------------------------------------------------------


class TestKeywordDensityScoring:
    """Tests for keyword density analysis."""

    @pytest.mark.asyncio
    async def test_keyword_density_primary(
        self, service: ContentScoreService, sample_content: str
    ) -> None:
        """Should calculate primary keyword density."""
        input_data = ContentScoreInput(
            content=sample_content,
            primary_keyword="leather",
        )
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.keyword_density_score is not None
        assert result.keyword_density_score.primary_keyword == "leather"
        assert result.keyword_density_score.primary_density > 0

    @pytest.mark.asyncio
    async def test_keyword_density_secondary(
        self, service: ContentScoreService, sample_content: str
    ) -> None:
        """Should calculate secondary keyword densities."""
        input_data = ContentScoreInput(
            content=sample_content,
            primary_keyword="leather",
            secondary_keywords=["wallet", "quality"],
        )
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.keyword_density_score is not None
        assert len(result.keyword_density_score.secondary_keywords) == 2

    @pytest.mark.asyncio
    async def test_keyword_density_optimal(
        self, service: ContentScoreService
    ) -> None:
        """Should score well for optimal density."""
        # Content with ~1.5% keyword density
        words = ["leather"] * 3 + ["other", "words", "here"] * 67  # ~1.5%
        content = " ".join(words)
        input_data = ContentScoreInput(content=content, primary_keyword="leather")
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.keyword_density_score is not None
        density = result.keyword_density_score.primary_density
        # Should be in optimal range
        if DEFAULT_TARGET_KEYWORD_DENSITY_MIN <= density <= DEFAULT_TARGET_KEYWORD_DENSITY_MAX:
            assert result.keyword_density_score.score >= 0.9

    @pytest.mark.asyncio
    async def test_keyword_density_stuffing(
        self, service: ContentScoreService, keyword_stuffed_content: str
    ) -> None:
        """Should penalize keyword stuffing."""
        input_data = ContentScoreInput(
            content=keyword_stuffed_content,
            primary_keyword="leather wallet",
        )
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.keyword_density_score is not None
        # High density = penalized score
        assert result.keyword_density_score.score < 0.7

    @pytest.mark.asyncio
    async def test_keyword_density_no_keyword(
        self, service: ContentScoreService, sample_content: str
    ) -> None:
        """Should handle missing keyword gracefully."""
        input_data = ContentScoreInput(content=sample_content)
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.keyword_density_score is not None
        # No keyword = partial score
        assert result.keyword_density_score.score == 0.5


# ---------------------------------------------------------------------------
# Test: Entity Coverage Scoring
# ---------------------------------------------------------------------------


class TestEntityCoverageScoring:
    """Tests for entity extraction and coverage."""

    @pytest.mark.asyncio
    async def test_entity_extraction_money(
        self, service: ContentScoreService
    ) -> None:
        """Should extract money entities."""
        content = "Our products range from $49 to $199. Premium items cost $500."
        input_data = ContentScoreInput(content=content)
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.entity_coverage_score is not None
        assert "money" in result.entity_coverage_score.entities
        assert len(result.entity_coverage_score.entities["money"]) >= 2

    @pytest.mark.asyncio
    async def test_entity_extraction_location(
        self, service: ContentScoreService, sample_content: str
    ) -> None:
        """Should extract location entities."""
        input_data = ContentScoreInput(content=sample_content)
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.entity_coverage_score is not None
        assert "location" in result.entity_coverage_score.entities

    @pytest.mark.asyncio
    async def test_entity_extraction_numbers(
        self, service: ContentScoreService
    ) -> None:
        """Should extract numeric entities."""
        content = "Measures 5 inches wide. Weight is 2.5 lbs. Contains 12 slots."
        input_data = ContentScoreInput(content=content)
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.entity_coverage_score is not None
        assert "number" in result.entity_coverage_score.entities

    @pytest.mark.asyncio
    async def test_entity_coverage_diversity(
        self, service: ContentScoreService, sample_content: str
    ) -> None:
        """Should score well for diverse entities."""
        input_data = ContentScoreInput(content=sample_content)
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.entity_coverage_score is not None
        # Multiple entity types = better score
        assert result.entity_coverage_score.entity_types_covered >= 2
        assert result.entity_coverage_score.score >= 0.6


# ---------------------------------------------------------------------------
# Test: Main Scoring Method
# ---------------------------------------------------------------------------


class TestScoreContent:
    """Tests for the main score_content method."""

    @pytest.mark.asyncio
    async def test_score_content_success(
        self, service: ContentScoreService, sample_content: str
    ) -> None:
        """Should successfully score content."""
        input_data = ContentScoreInput(
            content=sample_content,
            primary_keyword="leather wallet",
            secondary_keywords=["quality", "genuine"],
            project_id="proj-123",
            page_id="page-456",
        )
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.overall_score > 0
        assert result.word_count_score is not None
        assert result.semantic_score is not None
        assert result.readability_score is not None
        assert result.keyword_density_score is not None
        assert result.entity_coverage_score is not None
        assert result.duration_ms > 0
        assert result.project_id == "proj-123"
        assert result.page_id == "page-456"

    @pytest.mark.asyncio
    async def test_score_content_empty_fails(
        self, service: ContentScoreService
    ) -> None:
        """Should fail for empty content."""
        input_data = ContentScoreInput(content="")
        result = await service.score_content(input_data)

        assert result.success is False
        assert result.error is not None
        assert "empty" in result.error.lower()

    @pytest.mark.asyncio
    async def test_score_content_whitespace_only_fails(
        self, service: ContentScoreService
    ) -> None:
        """Should fail for whitespace-only content."""
        input_data = ContentScoreInput(content="   \n\t  ")
        result = await service.score_content(input_data)

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_score_content_pass_threshold(
        self, service: ContentScoreService, sample_content: str
    ) -> None:
        """Should correctly determine pass/fail based on threshold."""
        input_data = ContentScoreInput(content=sample_content)
        result = await service.score_content(input_data)

        assert result.success is True
        # passed should reflect whether score meets threshold
        if result.overall_score >= service.pass_threshold:
            assert result.passed is True
        else:
            assert result.passed is False

    @pytest.mark.asyncio
    async def test_score_content_weighted_score(
        self, service: ContentScoreService, sample_content: str
    ) -> None:
        """Should calculate weighted overall score correctly."""
        input_data = ContentScoreInput(content=sample_content)
        result = await service.score_content(input_data)

        assert result.success is True
        # Overall score should be weighted sum of components
        expected = (
            (result.word_count_score.score * service.scoring_weights["word_count"])
            + (result.semantic_score.score * service.scoring_weights["semantic"])
            + (result.readability_score.score * service.scoring_weights["readability"])
            + (
                result.keyword_density_score.score
                * service.scoring_weights["keyword_density"]
            )
            + (
                result.entity_coverage_score.score
                * service.scoring_weights["entity_coverage"]
            )
        )
        assert abs(result.overall_score - expected) < 0.001


# ---------------------------------------------------------------------------
# Test: Batch Scoring
# ---------------------------------------------------------------------------


class TestScoreContentBatch:
    """Tests for batch content scoring."""

    @pytest.mark.asyncio
    async def test_batch_scoring_multiple(
        self, service: ContentScoreService, sample_content: str, short_content: str
    ) -> None:
        """Should score multiple content items."""
        inputs = [
            ContentScoreInput(content=sample_content),
            ContentScoreInput(content=short_content),
        ]
        results = await service.score_content_batch(inputs)

        assert len(results) == 2
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_batch_scoring_empty_list(
        self, service: ContentScoreService
    ) -> None:
        """Should handle empty input list."""
        results = await service.score_content_batch([])
        assert results == []

    @pytest.mark.asyncio
    async def test_batch_scoring_with_failures(
        self, service: ContentScoreService, sample_content: str
    ) -> None:
        """Should handle mixed success/failure in batch."""
        inputs = [
            ContentScoreInput(content=sample_content),
            ContentScoreInput(content=""),  # Will fail
            ContentScoreInput(content=sample_content),
        ]
        results = await service.score_content_batch(inputs)

        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert results[2].success is True


# ---------------------------------------------------------------------------
# Test: Singleton and Convenience Functions
# ---------------------------------------------------------------------------


class TestSingletonAndConvenience:
    """Tests for singleton and convenience functions."""

    def test_get_content_score_service_singleton(self) -> None:
        """Should return same instance."""
        service1 = get_content_score_service()
        service2 = get_content_score_service()
        assert service1 is service2

    @pytest.mark.asyncio
    async def test_score_content_convenience(
        self, sample_content: str
    ) -> None:
        """Should work as convenience function."""
        result = await score_content(
            content=sample_content,
            primary_keyword="leather",
            secondary_keywords=["wallet"],
            project_id="proj-test",
        )

        assert result.success is True
        assert result.overall_score > 0


# ---------------------------------------------------------------------------
# Test: Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and special inputs."""

    @pytest.mark.asyncio
    async def test_unicode_content(self, service: ContentScoreService) -> None:
        """Should handle unicode content."""
        content = "This product costs \u20ac50. Available in caf\u00e9 locations."
        input_data = ContentScoreInput(content=content)
        result = await service.score_content(input_data)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_html_content(self, service: ContentScoreService) -> None:
        """Should strip HTML tags."""
        content = "<p>This is <strong>bold</strong> text.</p><div>More content here.</div>"
        input_data = ContentScoreInput(content=content)
        result = await service.score_content(input_data)

        assert result.success is True
        # HTML should be stripped, words counted
        assert result.word_count_score is not None
        assert result.word_count_score.word_count > 0

    @pytest.mark.asyncio
    async def test_multi_word_keyword(
        self, service: ContentScoreService
    ) -> None:
        """Should handle multi-word keywords."""
        content = "Our leather wallet collection features premium leather wallet designs."
        input_data = ContentScoreInput(
            content=content,
            primary_keyword="leather wallet",
        )
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.keyword_density_score is not None
        assert result.keyword_density_score.total_keyword_occurrences >= 2

    @pytest.mark.asyncio
    async def test_very_long_content(self, service: ContentScoreService) -> None:
        """Should handle very long content."""
        content = "This is a test sentence. " * 1000
        input_data = ContentScoreInput(content=content)
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.word_count_score is not None
        assert result.word_count_score.word_count >= 3000

    @pytest.mark.asyncio
    async def test_single_word_content(
        self, service: ContentScoreService
    ) -> None:
        """Should handle single word content."""
        input_data = ContentScoreInput(content="test")
        result = await service.score_content(input_data)

        assert result.success is True
        assert result.overall_score > 0  # Should not crash

    @pytest.mark.asyncio
    async def test_numbers_only_content(
        self, service: ContentScoreService
    ) -> None:
        """Should handle numbers-only content."""
        content = "123 456 789 100 200 300"
        input_data = ContentScoreInput(content=content)
        result = await service.score_content(input_data)

        assert result.success is True


# ---------------------------------------------------------------------------
# Test: Stop Words
# ---------------------------------------------------------------------------


class TestStopWords:
    """Tests for stop word handling."""

    def test_stop_words_defined(self) -> None:
        """Should have comprehensive stop words list."""
        assert len(STOP_WORDS) > 100
        assert "the" in STOP_WORDS
        assert "and" in STOP_WORDS
        assert "is" in STOP_WORDS

    def test_stop_words_immutable(self) -> None:
        """Stop words should be a frozenset."""
        assert isinstance(STOP_WORDS, frozenset)
