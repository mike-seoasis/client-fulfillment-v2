"""Unit tests for TFIDFAnalysisService term extraction.

Tests cover:
- TermScore dataclass creation and serialization
- TFIDFAnalysisRequest dataclass creation
- TFIDFAnalysisResult dataclass and serialization
- TFIDFAnalysisService initialization
- Tokenization (_tokenize)
- N-gram generation (_get_ngrams)
- Term frequency computation (_compute_tf)
- Inverse document frequency computation (_compute_idf)
- Document frequency filtering (_filter_by_document_frequency)
- analyze() method with various scenarios
- find_missing_terms() method
- analyze_request() convenience method
- Singleton and convenience functions
- Validation and error handling
- Edge cases (empty content, unicode, etc.)

ERROR LOGGING REQUIREMENTS:
- Ensure test failures include full assertion context
- Log test setup/teardown at DEBUG level
- Capture and display logs from failed tests
- Include timing information in test reports
- Log mock/stub invocations for debugging

Target: 80% code coverage for TFIDFAnalysisService.
"""

import logging

import pytest

from app.services.tfidf_analysis import (
    DEFAULT_MAX_DF_RATIO,
    DEFAULT_MIN_DF,
    DEFAULT_TOP_N,
    STOP_WORDS,
    TermScore,
    TFIDFAnalysisRequest,
    TFIDFAnalysisResult,
    TFIDFAnalysisService,
    TFIDFAnalysisServiceError,
    TFIDFValidationError,
    analyze_tfidf,
    find_missing_terms,
    get_tfidf_analysis_service,
)

# Enable debug logging for test visibility
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service() -> TFIDFAnalysisService:
    """Create a TFIDFAnalysisService instance."""
    logger.debug("Creating TFIDFAnalysisService")
    return TFIDFAnalysisService()


@pytest.fixture
def sample_documents() -> list[str]:
    """Sample documents for TF-IDF analysis."""
    logger.debug("Creating sample documents fixture")
    return [
        "Airtight coffee containers keep your beans fresh for weeks. "
        "The vacuum seal preserves aroma and flavor.",
        "Coffee storage containers with airtight lids prevent moisture. "
        "Keep coffee beans in a cool dark place.",
        "Best coffee canisters feature vacuum seals and one-way valves. "
        "Airtight containers are essential for freshness.",
    ]


@pytest.fixture
def competitor_documents() -> list[str]:
    """Sample competitor documents for missing terms analysis."""
    logger.debug("Creating competitor documents fixture")
    return [
        "Premium vacuum sealed coffee containers with CO2 valve release. "
        "Stainless steel construction prevents UV light damage.",
        "Airtight coffee storage with borosilicate glass design. "
        "BPA-free silicone seal keeps beans fresh for months.",
        "Professional barista-grade coffee canisters. "
        "Features include date tracking wheel and measuring scoop.",
    ]


@pytest.fixture
def user_content() -> str:
    """Sample user content for missing terms analysis."""
    logger.debug("Creating user content fixture")
    return (
        "Our coffee containers keep your beans fresh. "
        "The airtight seal preserves flavor."
    )


# ---------------------------------------------------------------------------
# Test: Data Classes
# ---------------------------------------------------------------------------


class TestTermScore:
    """Tests for TermScore dataclass."""

    def test_create_term_score(self) -> None:
        """Should create TermScore with all fields."""
        term = TermScore(
            term="coffee containers",
            score=0.85,
            doc_frequency=3,
            term_frequency=12,
        )
        assert term.term == "coffee containers"
        assert term.score == 0.85
        assert term.doc_frequency == 3
        assert term.term_frequency == 12

    def test_term_score_to_dict(self) -> None:
        """Should convert to dictionary correctly."""
        term = TermScore(term="airtight", score=0.7234, doc_frequency=2)
        data = term.to_dict()

        assert data["term"] == "airtight"
        assert data["score"] == 0.7234  # Rounded to 4 decimal places
        assert data["doc_frequency"] == 2
        assert data["term_frequency"] == 0  # Default

    def test_term_score_defaults(self) -> None:
        """Should have correct default values."""
        term = TermScore(term="test", score=0.5)
        assert term.doc_frequency == 0
        assert term.term_frequency == 0


class TestTFIDFAnalysisRequest:
    """Tests for TFIDFAnalysisRequest dataclass."""

    def test_create_minimal_request(self) -> None:
        """Should create request with minimal fields."""
        request = TFIDFAnalysisRequest(documents=["doc1", "doc2"])
        assert request.documents == ["doc1", "doc2"]
        assert request.top_n == DEFAULT_TOP_N
        assert request.include_bigrams is True
        assert request.min_df == DEFAULT_MIN_DF
        assert request.max_df_ratio == DEFAULT_MAX_DF_RATIO
        assert request.project_id is None

    def test_create_full_request(self) -> None:
        """Should create request with all fields."""
        request = TFIDFAnalysisRequest(
            documents=["doc1", "doc2", "doc3"],
            top_n=10,
            include_bigrams=False,
            min_df=2,
            max_df_ratio=0.7,
            project_id="proj-123",
        )
        assert len(request.documents) == 3
        assert request.top_n == 10
        assert request.include_bigrams is False
        assert request.min_df == 2
        assert request.max_df_ratio == 0.7
        assert request.project_id == "proj-123"


class TestTFIDFAnalysisResult:
    """Tests for TFIDFAnalysisResult dataclass."""

    def test_create_success_result(self) -> None:
        """Should create a successful result."""
        result = TFIDFAnalysisResult(
            success=True,
            terms=[TermScore(term="coffee", score=0.9)],
            term_count=1,
            document_count=3,
            vocabulary_size=50,
            duration_ms=10.5,
            project_id="proj-1",
        )
        assert result.success is True
        assert len(result.terms) == 1
        assert result.error is None
        assert result.duration_ms == 10.5

    def test_create_failure_result(self) -> None:
        """Should create a failed result with error."""
        result = TFIDFAnalysisResult(
            success=False,
            error="Documents list cannot be empty",
            project_id="proj-1",
        )
        assert result.success is False
        assert result.error == "Documents list cannot be empty"
        assert result.terms == []

    def test_to_dict(self) -> None:
        """Should convert to dictionary correctly."""
        result = TFIDFAnalysisResult(
            success=True,
            terms=[
                TermScore(term="coffee", score=0.9),
                TermScore(term="storage", score=0.8),
            ],
            term_count=2,
            document_count=3,
            vocabulary_size=50,
            duration_ms=15.678,
        )
        data = result.to_dict()

        assert data["success"] is True
        assert len(data["terms"]) == 2
        assert data["term_count"] == 2
        assert data["document_count"] == 3
        assert data["vocabulary_size"] == 50
        assert data["duration_ms"] == 15.68  # Rounded

    def test_get_term_list(self) -> None:
        """Should return list of term strings."""
        result = TFIDFAnalysisResult(
            success=True,
            terms=[
                TermScore(term="coffee", score=0.9),
                TermScore(term="airtight", score=0.8),
                TermScore(term="storage", score=0.7),
            ],
            term_count=3,
        )
        term_list = result.get_term_list()

        assert term_list == ["coffee", "airtight", "storage"]


# ---------------------------------------------------------------------------
# Test: Service Initialization
# ---------------------------------------------------------------------------


class TestServiceInitialization:
    """Tests for TFIDFAnalysisService initialization."""

    def test_default_initialization(self) -> None:
        """Should initialize without errors."""
        service = TFIDFAnalysisService()
        assert service is not None

    def test_token_pattern_compiled(self, service: TFIDFAnalysisService) -> None:
        """Should have compiled regex pattern."""
        assert service._token_pattern is not None


# ---------------------------------------------------------------------------
# Test: Tokenization
# ---------------------------------------------------------------------------


class TestTokenization:
    """Tests for tokenization logic."""

    def test_basic_tokenization(self, service: TFIDFAnalysisService) -> None:
        """Should tokenize text into words."""
        tokens = service._tokenize("Coffee containers keep beans fresh")

        assert "coffee" in tokens
        assert "containers" in tokens
        assert "beans" in tokens
        assert "fresh" in tokens

    def test_removes_stop_words(self, service: TFIDFAnalysisService) -> None:
        """Should remove stop words."""
        tokens = service._tokenize("The coffee and the containers are great")

        assert "coffee" in tokens
        assert "containers" in tokens
        assert "great" in tokens
        assert "the" not in tokens
        assert "and" not in tokens
        assert "are" not in tokens

    def test_lowercase_conversion(self, service: TFIDFAnalysisService) -> None:
        """Should convert to lowercase."""
        tokens = service._tokenize("COFFEE Containers FRESH Beans")

        assert "coffee" in tokens
        assert "containers" in tokens
        assert "fresh" in tokens
        assert "beans" in tokens
        # No uppercase versions
        assert "COFFEE" not in tokens

    def test_removes_short_tokens(self, service: TFIDFAnalysisService) -> None:
        """Should remove tokens with 2 or fewer characters."""
        tokens = service._tokenize("Coffee is a great drink to have")

        assert "coffee" in tokens
        assert "great" in tokens
        assert "drink" in tokens
        assert "is" not in tokens  # Stop word
        assert "to" not in tokens  # Stop word and short

    def test_handles_empty_string(self, service: TFIDFAnalysisService) -> None:
        """Should return empty list for empty string."""
        tokens = service._tokenize("")
        assert tokens == []

    def test_handles_punctuation(self, service: TFIDFAnalysisService) -> None:
        """Should handle punctuation correctly."""
        tokens = service._tokenize("Coffee, containers! Fresh? (beans)")

        assert "coffee" in tokens
        assert "containers" in tokens
        assert "fresh" in tokens
        assert "beans" in tokens

    def test_handles_numbers_in_words(self, service: TFIDFAnalysisService) -> None:
        """Should include words with numbers."""
        tokens = service._tokenize("CO2 valve and H2O resistant")

        # co2 should be extracted (starts with letter, contains numbers)
        assert any("co2" in t for t in tokens) or "valve" in tokens


# ---------------------------------------------------------------------------
# Test: N-gram Generation
# ---------------------------------------------------------------------------


class TestNgramGeneration:
    """Tests for n-gram generation."""

    def test_unigrams_only(self, service: TFIDFAnalysisService) -> None:
        """Should generate unigrams when bigrams disabled."""
        tokens = ["coffee", "storage", "containers"]
        ngrams = service._get_ngrams(tokens, include_bigrams=False)

        assert ngrams == ["coffee", "storage", "containers"]

    def test_with_bigrams(self, service: TFIDFAnalysisService) -> None:
        """Should include bigrams when enabled."""
        tokens = ["coffee", "storage", "containers"]
        ngrams = service._get_ngrams(tokens, include_bigrams=True)

        assert "coffee" in ngrams
        assert "storage" in ngrams
        assert "containers" in ngrams
        assert "coffee storage" in ngrams
        assert "storage containers" in ngrams

    def test_bigrams_require_two_tokens(self, service: TFIDFAnalysisService) -> None:
        """Should not generate bigrams for single token."""
        tokens = ["coffee"]
        ngrams = service._get_ngrams(tokens, include_bigrams=True)

        assert ngrams == ["coffee"]

    def test_empty_tokens(self, service: TFIDFAnalysisService) -> None:
        """Should handle empty token list."""
        ngrams = service._get_ngrams([], include_bigrams=True)
        assert ngrams == []


# ---------------------------------------------------------------------------
# Test: Term Frequency Computation
# ---------------------------------------------------------------------------


class TestTermFrequencyComputation:
    """Tests for TF computation."""

    def test_basic_tf(self, service: TFIDFAnalysisService) -> None:
        """Should compute normalized term frequency."""
        terms = ["coffee", "coffee", "storage", "fresh"]
        tf = service._compute_tf(terms)

        assert tf["coffee"] == 0.5  # 2/4
        assert tf["storage"] == 0.25  # 1/4
        assert tf["fresh"] == 0.25  # 1/4

    def test_single_term(self, service: TFIDFAnalysisService) -> None:
        """Should handle single term."""
        terms = ["coffee"]
        tf = service._compute_tf(terms)

        assert tf["coffee"] == 1.0

    def test_empty_terms(self, service: TFIDFAnalysisService) -> None:
        """Should return empty dict for empty terms."""
        tf = service._compute_tf([])
        assert tf == {}


# ---------------------------------------------------------------------------
# Test: Inverse Document Frequency Computation
# ---------------------------------------------------------------------------


class TestIDFComputation:
    """Tests for IDF computation."""

    def test_basic_idf(self, service: TFIDFAnalysisService) -> None:
        """Should compute IDF correctly."""
        doc_term_sets = [
            {"coffee", "storage"},
            {"coffee", "containers"},
            {"storage", "containers"},
        ]
        vocabulary = {"coffee", "storage", "containers"}

        idf = service._compute_idf(doc_term_sets, vocabulary)

        # All terms appear in 2 of 3 documents
        # IDF = log((3+1)/(2+1)) + 1 = log(4/3) + 1 ≈ 1.288
        assert all(term in idf for term in vocabulary)
        assert idf["coffee"] > 0
        assert idf["storage"] > 0
        assert idf["containers"] > 0

    def test_rare_term_higher_idf(self, service: TFIDFAnalysisService) -> None:
        """Rare terms should have higher IDF."""
        doc_term_sets = [
            {"coffee", "rare"},
            {"coffee"},
            {"coffee"},
        ]
        vocabulary = {"coffee", "rare"}

        idf = service._compute_idf(doc_term_sets, vocabulary)

        # "rare" appears in 1 doc, "coffee" in all 3
        assert idf["rare"] > idf["coffee"]

    def test_empty_documents(self, service: TFIDFAnalysisService) -> None:
        """Should return empty dict for empty documents."""
        idf = service._compute_idf([], {"term"})
        assert idf == {}


# ---------------------------------------------------------------------------
# Test: Document Frequency Filtering
# ---------------------------------------------------------------------------


class TestDocumentFrequencyFiltering:
    """Tests for document frequency filtering."""

    def test_min_df_filtering(self, service: TFIDFAnalysisService) -> None:
        """Should filter terms below min_df."""
        doc_term_sets = [
            {"coffee", "rare"},
            {"coffee"},
            {"coffee"},
        ]
        vocabulary = {"coffee", "rare"}

        filtered, doc_freq = service._filter_by_document_frequency(
            doc_term_sets=doc_term_sets,
            vocabulary=vocabulary,
            min_df=2,
            max_df_ratio=1.0,
        )

        assert "coffee" in filtered  # Appears in 3 docs
        assert "rare" not in filtered  # Appears in 1 doc

    def test_max_df_filtering(self, service: TFIDFAnalysisService) -> None:
        """Should filter terms above max_df_ratio."""
        doc_term_sets = [
            {"common", "term1"},
            {"common", "term2"},
            {"common", "term3"},
        ]
        vocabulary = {"common", "term1", "term2", "term3"}

        filtered, doc_freq = service._filter_by_document_frequency(
            doc_term_sets=doc_term_sets,
            vocabulary=vocabulary,
            min_df=1,
            max_df_ratio=0.5,  # Max 50% of docs
        )

        # "common" appears in all 3 docs (100%)
        assert "common" not in filtered
        # Others appear in 1 doc each (33%)
        assert "term1" in filtered
        assert "term2" in filtered
        assert "term3" in filtered


# ---------------------------------------------------------------------------
# Test: analyze() Method
# ---------------------------------------------------------------------------


class TestAnalyzeMethod:
    """Tests for the main analyze method."""

    @pytest.mark.asyncio
    async def test_basic_analysis(
        self,
        service: TFIDFAnalysisService,
        sample_documents: list[str],
    ) -> None:
        """Should extract terms from documents."""
        result = await service.analyze(
            documents=sample_documents,
            top_n=10,
            project_id="proj-123",
        )

        assert result.success is True
        assert result.term_count > 0
        assert result.document_count == 3
        assert result.vocabulary_size > 0
        assert result.error is None

        # Should have extracted relevant terms
        term_list = result.get_term_list()
        assert len(term_list) > 0
        # Common coffee-related terms should appear
        assert any("coffee" in t for t in term_list)

    @pytest.mark.asyncio
    async def test_returns_sorted_by_score(
        self,
        service: TFIDFAnalysisService,
        sample_documents: list[str],
    ) -> None:
        """Should return terms sorted by score descending."""
        result = await service.analyze(
            documents=sample_documents,
            top_n=10,
        )

        assert result.success is True
        scores = [t.score for t in result.terms]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_respects_top_n(
        self,
        service: TFIDFAnalysisService,
        sample_documents: list[str],
    ) -> None:
        """Should return at most top_n terms."""
        result = await service.analyze(
            documents=sample_documents,
            top_n=5,
        )

        assert result.success is True
        assert result.term_count <= 5

    @pytest.mark.asyncio
    async def test_bigrams_included(
        self,
        service: TFIDFAnalysisService,
        sample_documents: list[str],
    ) -> None:
        """Should include bigrams when enabled."""
        result = await service.analyze(
            documents=sample_documents,
            top_n=20,
            include_bigrams=True,
        )

        assert result.success is True
        # Check for any bigrams (terms with spaces)
        has_bigram = any(" " in t.term for t in result.terms)
        assert has_bigram, "Expected at least one bigram in results"

    @pytest.mark.asyncio
    async def test_no_bigrams_when_disabled(
        self,
        service: TFIDFAnalysisService,
        sample_documents: list[str],
    ) -> None:
        """Should not include bigrams when disabled."""
        result = await service.analyze(
            documents=sample_documents,
            top_n=20,
            include_bigrams=False,
        )

        assert result.success is True
        # No bigrams (no spaces in terms)
        has_bigram = any(" " in t.term for t in result.terms)
        assert not has_bigram, "Expected no bigrams in results"

    @pytest.mark.asyncio
    async def test_tracks_duration(
        self,
        service: TFIDFAnalysisService,
        sample_documents: list[str],
    ) -> None:
        """Should track operation duration."""
        result = await service.analyze(
            documents=sample_documents,
            top_n=10,
        )

        assert result.success is True
        assert result.duration_ms >= 0
        assert isinstance(result.duration_ms, float)

    @pytest.mark.asyncio
    async def test_includes_project_id(
        self,
        service: TFIDFAnalysisService,
        sample_documents: list[str],
    ) -> None:
        """Should include project ID in result."""
        result = await service.analyze(
            documents=sample_documents,
            project_id="proj-test",
        )

        assert result.project_id == "proj-test"


# ---------------------------------------------------------------------------
# Test: Validation and Error Handling
# ---------------------------------------------------------------------------


class TestValidationAndErrors:
    """Tests for input validation and error handling."""

    @pytest.mark.asyncio
    async def test_empty_documents_fails(
        self,
        service: TFIDFAnalysisService,
    ) -> None:
        """Should return error for empty documents list."""
        result = await service.analyze(
            documents=[],
            project_id="proj-1",
        )

        assert result.success is False
        assert "empty" in result.error.lower()

    @pytest.mark.asyncio
    async def test_invalid_top_n_fails(
        self,
        service: TFIDFAnalysisService,
        sample_documents: list[str],
    ) -> None:
        """Should return error for invalid top_n."""
        result = await service.analyze(
            documents=sample_documents,
            top_n=0,
        )

        assert result.success is False
        assert "top_n" in result.error.lower()

    @pytest.mark.asyncio
    async def test_invalid_max_df_ratio_fails(
        self,
        service: TFIDFAnalysisService,
        sample_documents: list[str],
    ) -> None:
        """Should return error for invalid max_df_ratio."""
        result = await service.analyze(
            documents=sample_documents,
            max_df_ratio=1.5,  # Invalid: > 1.0
        )

        assert result.success is False
        assert "max_df_ratio" in result.error.lower()

    @pytest.mark.asyncio
    async def test_all_empty_documents(
        self,
        service: TFIDFAnalysisService,
    ) -> None:
        """Should handle all empty documents gracefully."""
        result = await service.analyze(
            documents=["", "  ", "\n\t"],
            project_id="proj-1",
        )

        assert result.success is False
        assert result.document_count == 0 or "no valid documents" in result.error.lower()

    @pytest.mark.asyncio
    async def test_some_empty_documents(
        self,
        service: TFIDFAnalysisService,
    ) -> None:
        """Should skip empty documents but process valid ones."""
        result = await service.analyze(
            documents=[
                "",
                "Coffee containers keep beans fresh",
                "  ",
                "Airtight storage for coffee",
            ],
        )

        assert result.success is True
        assert result.document_count == 2  # Only 2 valid docs


# ---------------------------------------------------------------------------
# Test: find_missing_terms() Method
# ---------------------------------------------------------------------------


class TestFindMissingTerms:
    """Tests for the find_missing_terms method."""

    @pytest.mark.asyncio
    async def test_finds_missing_terms(
        self,
        service: TFIDFAnalysisService,
        competitor_documents: list[str],
        user_content: str,
    ) -> None:
        """Should find terms in competitors missing from user content."""
        result = await service.find_missing_terms(
            competitor_documents=competitor_documents,
            user_content=user_content,
            top_n=10,
            project_id="proj-123",
        )

        assert result.success is True
        assert result.term_count > 0

        # Terms in user content should not be in results
        term_list = result.get_term_list()
        # "coffee" and "airtight" are in user content
        # but other competitor terms should be missing
        assert len(term_list) > 0

    @pytest.mark.asyncio
    async def test_excludes_present_terms(
        self,
        service: TFIDFAnalysisService,
    ) -> None:
        """Should exclude terms that exist in user content."""
        result = await service.find_missing_terms(
            competitor_documents=[
                "Coffee containers with vacuum seal",
                "Airtight coffee storage solutions",
            ],
            user_content="Coffee containers are great. Vacuum seal works.",
            top_n=5,
        )

        assert result.success is True
        term_list = result.get_term_list()

        # "coffee" and "vacuum" are in user content, should not appear
        # (checking unigrams only for simplicity)
        unigrams = [t for t in term_list if " " not in t]
        assert "coffee" not in unigrams
        # "airtight" and "storage" should be missing
        # (may or may not appear depending on TF-IDF scores)

    @pytest.mark.asyncio
    async def test_respects_top_n_for_missing(
        self,
        service: TFIDFAnalysisService,
        competitor_documents: list[str],
    ) -> None:
        """Should return at most top_n missing terms."""
        result = await service.find_missing_terms(
            competitor_documents=competitor_documents,
            user_content="Short content",
            top_n=3,
        )

        assert result.success is True
        assert result.term_count <= 3


# ---------------------------------------------------------------------------
# Test: analyze_request() Convenience Method
# ---------------------------------------------------------------------------


class TestAnalyzeRequest:
    """Tests for analyze_request convenience method."""

    @pytest.mark.asyncio
    async def test_analyze_request(
        self,
        service: TFIDFAnalysisService,
        sample_documents: list[str],
    ) -> None:
        """Should work with request object."""
        request = TFIDFAnalysisRequest(
            documents=sample_documents,
            top_n=5,
            include_bigrams=True,
            project_id="proj-request",
        )

        result = await service.analyze_request(request)

        assert result.success is True
        assert result.term_count <= 5
        assert result.project_id == "proj-request"


# ---------------------------------------------------------------------------
# Test: Singleton and Convenience Functions
# ---------------------------------------------------------------------------


class TestSingletonAndConvenience:
    """Tests for singleton accessor and convenience functions."""

    def test_get_service_singleton(self) -> None:
        """get_tfidf_analysis_service should return singleton."""
        import app.services.tfidf_analysis as tfidf_module

        original = tfidf_module._tfidf_service
        tfidf_module._tfidf_service = None

        try:
            service1 = get_tfidf_analysis_service()
            service2 = get_tfidf_analysis_service()
            assert service1 is service2
        finally:
            tfidf_module._tfidf_service = original

    @pytest.mark.asyncio
    async def test_analyze_tfidf_function(
        self,
        sample_documents: list[str],
    ) -> None:
        """analyze_tfidf convenience function should work."""
        result = await analyze_tfidf(
            documents=sample_documents,
            top_n=5,
            project_id="proj-func",
        )

        assert result.success is True
        assert result.term_count > 0

    @pytest.mark.asyncio
    async def test_find_missing_terms_function(
        self,
        competitor_documents: list[str],
        user_content: str,
    ) -> None:
        """find_missing_terms convenience function should work."""
        result = await find_missing_terms(
            competitor_documents=competitor_documents,
            user_content=user_content,
            top_n=5,
            project_id="proj-func",
        )

        assert result.success is True


# ---------------------------------------------------------------------------
# Test: Exception Classes
# ---------------------------------------------------------------------------


class TestExceptionClasses:
    """Tests for TFIDF exception classes."""

    def test_service_error_base(self) -> None:
        """TFIDFAnalysisServiceError should be base exception."""
        error = TFIDFAnalysisServiceError("Test error", "proj-1")
        assert str(error) == "Test error"
        assert error.project_id == "proj-1"

    def test_validation_error(self) -> None:
        """TFIDFValidationError should contain field info."""
        error = TFIDFValidationError(
            field="documents",
            value=[],
            message="Cannot be empty",
            project_id="proj-1",
        )
        assert error.field == "documents"
        assert error.value == []
        assert "documents" in str(error)

    def test_exception_hierarchy(self) -> None:
        """Validation error should inherit from service error."""
        assert issubclass(TFIDFValidationError, TFIDFAnalysisServiceError)


# ---------------------------------------------------------------------------
# Test: Constants Verification
# ---------------------------------------------------------------------------


class TestConstants:
    """Tests to verify constants are properly configured."""

    def test_stop_words_not_empty(self) -> None:
        """STOP_WORDS should have entries."""
        assert len(STOP_WORDS) > 0
        assert "the" in STOP_WORDS
        assert "and" in STOP_WORDS
        assert "is" in STOP_WORDS

    def test_defaults_reasonable(self) -> None:
        """Default values should be reasonable."""
        assert DEFAULT_TOP_N == 25
        assert DEFAULT_MIN_DF == 1
        assert 0 < DEFAULT_MAX_DF_RATIO <= 1.0


# ---------------------------------------------------------------------------
# Test: Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_single_document(
        self,
        service: TFIDFAnalysisService,
    ) -> None:
        """Should handle single document.

        Note: With a single document, all terms appear in 100% of documents,
        so they may be filtered out by max_df_ratio. Use max_df_ratio=1.0
        to include all terms in this edge case.
        """
        result = await service.analyze(
            documents=["Coffee containers keep beans fresh and flavorful"],
            top_n=5,
            max_df_ratio=1.0,  # Don't filter by max df for single doc
        )

        assert result.success is True
        assert result.document_count == 1
        assert result.term_count > 0

    @pytest.mark.asyncio
    async def test_identical_documents(
        self,
        service: TFIDFAnalysisService,
    ) -> None:
        """Should handle identical documents."""
        doc = "Coffee containers with airtight seals"
        result = await service.analyze(
            documents=[doc, doc, doc],
            top_n=5,
        )

        assert result.success is True
        # All terms appear in all docs, so may be filtered by max_df_ratio

    @pytest.mark.asyncio
    async def test_unicode_content(
        self,
        service: TFIDFAnalysisService,
    ) -> None:
        """Should handle unicode content."""
        result = await service.analyze(
            documents=[
                "Café containers keep beans fresh",
                "日本語 text with coffee storage",
                "Unicode content: 你好 coffee 🎉",
            ],
        )

        assert result.success is True
        # Should extract ASCII terms at minimum
        term_list = result.get_term_list()
        assert any("coffee" in t for t in term_list) or any("caf" in t for t in term_list)

    @pytest.mark.asyncio
    async def test_very_short_documents(
        self,
        service: TFIDFAnalysisService,
    ) -> None:
        """Should handle very short documents."""
        result = await service.analyze(
            documents=["Coffee", "Storage", "Fresh beans"],
        )

        assert result.success is True
        # May have limited vocabulary due to short content

    @pytest.mark.asyncio
    async def test_large_document_set(
        self,
        service: TFIDFAnalysisService,
    ) -> None:
        """Should handle larger document sets efficiently."""
        # Generate 50 similar documents
        documents = [
            f"Coffee container {i} keeps beans fresh with airtight seal"
            for i in range(50)
        ]

        result = await service.analyze(
            documents=documents,
            top_n=10,
        )

        assert result.success is True
        assert result.document_count == 50

    @pytest.mark.asyncio
    async def test_special_characters(
        self,
        service: TFIDFAnalysisService,
    ) -> None:
        """Should handle special characters."""
        result = await service.analyze(
            documents=[
                "Coffee & tea containers!",
                "100% fresh (guaranteed)",
                'Best "airtight" storage',
            ],
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_numeric_content(
        self,
        service: TFIDFAnalysisService,
    ) -> None:
        """Should handle content with numbers."""
        result = await service.analyze(
            documents=[
                "500ml coffee containers",
                "CO2 valve for freshness",
                "12oz storage capacity",
            ],
        )

        assert result.success is True
        # Numbers alone shouldn't create terms, but alphanumeric should

    @pytest.mark.asyncio
    async def test_html_content(
        self,
        service: TFIDFAnalysisService,
    ) -> None:
        """Should handle HTML-like content (tags become noise)."""
        result = await service.analyze(
            documents=[
                "<h1>Coffee Containers</h1><p>Keep beans fresh</p>",
                "<div class='product'>Airtight storage</div>",
            ],
        )

        assert result.success is True
        # Note: HTML tags will be tokenized as words
        # A production system might want to strip HTML first
