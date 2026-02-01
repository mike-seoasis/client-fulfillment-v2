"""Unit tests for RelatedCollectionsService label overlap scoring algorithm.

Tests cover:
- Jaccard similarity coefficient calculation
- Collection dataclass creation and validation
- RelatedCollectionMatch dataclass and serialization
- RelatedCollectionsResult dataclass and serialization
- find_related() method with various scenarios
- find_related_by_collection() convenience method
- rank_by_similarity() method
- find_clusters() clustering algorithm
- Singleton pattern and convenience functions
- Validation and exception handling
- Edge cases (empty sets, identical sets, no overlap)

ERROR LOGGING REQUIREMENTS:
- Ensure test failures include full assertion context
- Log test setup/teardown at DEBUG level
- Capture and display logs from failed tests
- Include timing information in test reports
- Log mock/stub invocations for debugging

Target: 80% code coverage for RelatedCollectionsService.
"""

import logging

import pytest

from app.services.related_collections import (
    DEFAULT_MAX_RESULTS,
    DEFAULT_SIMILARITY_THRESHOLD,
    Collection,
    CollectionNotFoundError,
    CollectionValidationError,
    RelatedCollectionMatch,
    RelatedCollectionsError,
    RelatedCollectionsResult,
    RelatedCollectionsService,
    find_related_collections,
    get_related_collections_service,
)

# Enable debug logging for test visibility
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service() -> RelatedCollectionsService:
    """Create a RelatedCollectionsService instance with default settings."""
    logger.debug("Creating RelatedCollectionsService with defaults")
    return RelatedCollectionsService()


@pytest.fixture
def service_strict() -> RelatedCollectionsService:
    """Create a RelatedCollectionsService with strict threshold (0.5)."""
    logger.debug("Creating RelatedCollectionsService with strict threshold 0.5")
    return RelatedCollectionsService(
        similarity_threshold=0.5,
        max_results=5,
    )


@pytest.fixture
def sample_collections() -> list[Collection]:
    """Create a set of sample collections for testing."""
    logger.debug("Creating sample collections fixture")
    return [
        Collection(
            id="c1",
            name="Electronics Products",
            labels={"electronics", "gadgets", "tech", "products"},
            page_count=50,
            category="product",
            project_id="proj-1",
        ),
        Collection(
            id="c2",
            name="Tech Blog",
            labels={"tech", "blog", "tutorials", "reviews"},
            page_count=30,
            category="blog",
            project_id="proj-1",
        ),
        Collection(
            id="c3",
            name="Home Appliances",
            labels={"electronics", "appliances", "home", "products"},
            page_count=40,
            category="product",
            project_id="proj-1",
        ),
        Collection(
            id="c4",
            name="Fashion Items",
            labels={"fashion", "clothing", "accessories", "products"},
            page_count=60,
            category="product",
            project_id="proj-1",
        ),
        Collection(
            id="c5",
            name="Cooking Blog",
            labels={"cooking", "recipes", "blog", "food"},
            page_count=25,
            category="blog",
            project_id="proj-1",
        ),
        Collection(
            id="c6",
            name="Empty Collection",
            labels=set(),
            page_count=0,
            project_id="proj-1",
        ),
    ]


@pytest.fixture
def electronics_labels() -> set[str]:
    """Source labels for electronics-focused search."""
    return {"electronics", "gadgets", "tech", "devices"}


# ---------------------------------------------------------------------------
# Test: Collection Dataclass
# ---------------------------------------------------------------------------


class TestCollectionDataclass:
    """Tests for the Collection dataclass."""

    def test_create_minimal_collection(self) -> None:
        """Should create collection with minimal required fields."""
        collection = Collection(
            id="c1",
            name="Test Collection",
            labels={"label1", "label2"},
        )
        assert collection.id == "c1"
        assert collection.name == "Test Collection"
        assert collection.labels == {"label1", "label2"}
        assert collection.page_count == 0  # Default
        assert collection.category is None  # Default
        assert collection.project_id is None  # Default
        assert collection.metadata == {}  # Default

    def test_create_full_collection(self) -> None:
        """Should create collection with all fields."""
        metadata = {"source": "crawl", "last_updated": "2024-01-15"}
        collection = Collection(
            id="c1",
            name="Full Collection",
            labels={"tag1", "tag2", "tag3"},
            page_count=100,
            category="product",
            project_id="proj-123",
            metadata=metadata,
        )
        assert collection.id == "c1"
        assert collection.name == "Full Collection"
        assert len(collection.labels) == 3
        assert collection.page_count == 100
        assert collection.category == "product"
        assert collection.project_id == "proj-123"
        assert collection.metadata["source"] == "crawl"

    def test_collection_with_empty_labels(self) -> None:
        """Should allow collection with empty label set."""
        collection = Collection(
            id="c1",
            name="Empty Labels",
            labels=set(),
        )
        assert collection.labels == set()
        assert len(collection.labels) == 0


# ---------------------------------------------------------------------------
# Test: RelatedCollectionMatch Dataclass
# ---------------------------------------------------------------------------


class TestRelatedCollectionMatchDataclass:
    """Tests for the RelatedCollectionMatch dataclass."""

    def test_create_match(self) -> None:
        """Should create a match with all fields."""
        collection = Collection(
            id="c1",
            name="Match",
            labels={"a", "b", "c"},
            page_count=10,
            category="blog",
        )
        match = RelatedCollectionMatch(
            collection=collection,
            similarity_score=0.75,
            overlapping_labels={"a", "b"},
            unique_to_source={"x"},
            unique_to_match={"c"},
        )
        assert match.collection.id == "c1"
        assert match.similarity_score == 0.75
        assert match.overlapping_labels == {"a", "b"}
        assert match.unique_to_source == {"x"}
        assert match.unique_to_match == {"c"}

    def test_match_to_dict(self) -> None:
        """Should convert match to dictionary correctly."""
        collection = Collection(
            id="c1",
            name="Test Match",
            labels={"label1", "label2"},
            page_count=25,
            category="product",
        )
        match = RelatedCollectionMatch(
            collection=collection,
            similarity_score=0.6667,
            overlapping_labels={"label1", "label2"},
            unique_to_source={"source_only"},
            unique_to_match=set(),
        )
        data = match.to_dict()

        assert data["collection_id"] == "c1"
        assert data["collection_name"] == "Test Match"
        assert data["similarity_score"] == 0.6667  # Rounded to 4 decimals
        assert data["overlapping_labels"] == ["label1", "label2"]  # Sorted
        assert data["unique_to_source"] == ["source_only"]
        assert data["unique_to_match"] == []
        assert data["overlap_count"] == 2
        assert data["category"] == "product"
        assert data["page_count"] == 25

    def test_match_to_dict_sorting(self) -> None:
        """Should sort label sets alphabetically in dict output."""
        collection = Collection(id="c1", name="Test", labels=set())
        match = RelatedCollectionMatch(
            collection=collection,
            similarity_score=0.5,
            overlapping_labels={"zebra", "apple", "mango"},
            unique_to_source={"dog", "cat"},
            unique_to_match={"zulu", "alpha"},
        )
        data = match.to_dict()

        assert data["overlapping_labels"] == ["apple", "mango", "zebra"]
        assert data["unique_to_source"] == ["cat", "dog"]
        assert data["unique_to_match"] == ["alpha", "zulu"]


# ---------------------------------------------------------------------------
# Test: RelatedCollectionsResult Dataclass
# ---------------------------------------------------------------------------


class TestRelatedCollectionsResultDataclass:
    """Tests for the RelatedCollectionsResult dataclass."""

    def test_create_success_result(self) -> None:
        """Should create a successful result."""
        result = RelatedCollectionsResult(
            success=True,
            source_collection_id="source-1",
            source_labels={"a", "b", "c"},
            total_candidates=10,
            filtered_count=7,
            duration_ms=15.5,
            project_id="proj-1",
        )
        assert result.success is True
        assert result.source_collection_id == "source-1"
        assert result.source_labels == {"a", "b", "c"}
        assert result.matches == []  # Default
        assert result.total_candidates == 10
        assert result.filtered_count == 7
        assert result.error is None  # Default
        assert result.duration_ms == 15.5
        assert result.project_id == "proj-1"

    def test_create_failure_result(self) -> None:
        """Should create a failed result with error."""
        result = RelatedCollectionsResult(
            success=False,
            source_collection_id="source-1",
            error="Source labels cannot be empty",
        )
        assert result.success is False
        assert result.error == "Source labels cannot be empty"
        assert result.matches == []
        assert result.total_candidates == 0

    def test_result_defaults(self) -> None:
        """Should have correct default values."""
        result = RelatedCollectionsResult(
            success=True,
            source_collection_id="test",
        )
        assert result.source_labels == set()
        assert result.matches == []
        assert result.total_candidates == 0
        assert result.filtered_count == 0
        assert result.error is None
        assert result.duration_ms == 0.0
        assert result.project_id is None

    def test_result_to_dict(self) -> None:
        """Should convert result to dictionary correctly."""
        collection = Collection(id="c1", name="Match", labels={"x"})
        match = RelatedCollectionMatch(
            collection=collection,
            similarity_score=0.8,
            overlapping_labels={"x"},
            unique_to_source={"a"},
            unique_to_match=set(),
        )
        result = RelatedCollectionsResult(
            success=True,
            source_collection_id="source-1",
            source_labels={"a", "x"},
            matches=[match],
            total_candidates=5,
            filtered_count=4,
            duration_ms=12.34,
        )
        data = result.to_dict()

        assert data["success"] is True
        assert data["source_collection_id"] == "source-1"
        assert data["source_labels"] == ["a", "x"]  # Sorted
        assert data["match_count"] == 1
        assert len(data["matches"]) == 1
        assert data["total_candidates"] == 5
        assert data["filtered_count"] == 4
        assert data["duration_ms"] == 12.34
        assert data["error"] is None


# ---------------------------------------------------------------------------
# Test: RelatedCollectionsService Initialization
# ---------------------------------------------------------------------------


class TestServiceInitialization:
    """Tests for RelatedCollectionsService initialization."""

    def test_default_initialization(self) -> None:
        """Should initialize with default values."""
        service = RelatedCollectionsService()
        assert service.similarity_threshold == DEFAULT_SIMILARITY_THRESHOLD
        assert service.max_results == DEFAULT_MAX_RESULTS

    def test_custom_threshold(self) -> None:
        """Should accept custom similarity threshold."""
        service = RelatedCollectionsService(similarity_threshold=0.3)
        assert service.similarity_threshold == 0.3

    def test_custom_max_results(self) -> None:
        """Should accept custom max results."""
        service = RelatedCollectionsService(max_results=20)
        assert service.max_results == 20

    def test_threshold_boundary_zero(self) -> None:
        """Should accept threshold of 0.0."""
        service = RelatedCollectionsService(similarity_threshold=0.0)
        assert service.similarity_threshold == 0.0

    def test_threshold_boundary_one(self) -> None:
        """Should accept threshold of 1.0."""
        service = RelatedCollectionsService(similarity_threshold=1.0)
        assert service.similarity_threshold == 1.0

    def test_invalid_threshold_below_zero(self) -> None:
        """Should reject threshold below 0.0."""
        with pytest.raises(CollectionValidationError) as exc_info:
            RelatedCollectionsService(similarity_threshold=-0.1)
        assert exc_info.value.field == "similarity_threshold"
        assert "0.0" in exc_info.value.message

    def test_invalid_threshold_above_one(self) -> None:
        """Should reject threshold above 1.0."""
        with pytest.raises(CollectionValidationError) as exc_info:
            RelatedCollectionsService(similarity_threshold=1.5)
        assert exc_info.value.field == "similarity_threshold"
        assert "1.0" in exc_info.value.message

    def test_invalid_max_results_zero(self) -> None:
        """Should reject max_results of 0."""
        with pytest.raises(CollectionValidationError) as exc_info:
            RelatedCollectionsService(max_results=0)
        assert exc_info.value.field == "max_results"
        assert "at least 1" in exc_info.value.message

    def test_invalid_max_results_negative(self) -> None:
        """Should reject negative max_results."""
        with pytest.raises(CollectionValidationError) as exc_info:
            RelatedCollectionsService(max_results=-5)
        assert exc_info.value.field == "max_results"


# ---------------------------------------------------------------------------
# Test: Jaccard Similarity Calculation
# ---------------------------------------------------------------------------


class TestJaccardSimilarity:
    """Tests for Jaccard similarity coefficient calculation."""

    def test_identical_sets(self, service: RelatedCollectionsService) -> None:
        """Identical sets should have similarity of 1.0."""
        labels = {"a", "b", "c"}
        similarity = service.calculate_jaccard_similarity(labels, labels.copy())
        assert similarity == 1.0

    def test_disjoint_sets(self, service: RelatedCollectionsService) -> None:
        """Completely disjoint sets should have similarity of 0.0."""
        set_a = {"a", "b", "c"}
        set_b = {"x", "y", "z"}
        similarity = service.calculate_jaccard_similarity(set_a, set_b)
        assert similarity == 0.0

    def test_partial_overlap(self, service: RelatedCollectionsService) -> None:
        """Partially overlapping sets should have correct Jaccard coefficient."""
        # J(A, B) = |A ∩ B| / |A ∪ B|
        # A = {a, b, c}, B = {b, c, d}
        # Intersection = {b, c} = 2 elements
        # Union = {a, b, c, d} = 4 elements
        # Jaccard = 2/4 = 0.5
        set_a = {"a", "b", "c"}
        set_b = {"b", "c", "d"}
        similarity = service.calculate_jaccard_similarity(set_a, set_b)
        assert similarity == 0.5

    def test_subset_relationship(self, service: RelatedCollectionsService) -> None:
        """Subset should give correct Jaccard coefficient."""
        # A = {a, b}, B = {a, b, c, d}
        # Intersection = {a, b} = 2
        # Union = {a, b, c, d} = 4
        # Jaccard = 2/4 = 0.5
        set_a = {"a", "b"}
        set_b = {"a", "b", "c", "d"}
        similarity = service.calculate_jaccard_similarity(set_a, set_b)
        assert similarity == 0.5

    def test_both_empty_sets(self, service: RelatedCollectionsService) -> None:
        """Both empty sets should return 0.0 (avoid division by zero)."""
        similarity = service.calculate_jaccard_similarity(set(), set())
        assert similarity == 0.0

    def test_one_empty_set(self, service: RelatedCollectionsService) -> None:
        """One empty set should return 0.0."""
        set_a = {"a", "b", "c"}
        similarity = service.calculate_jaccard_similarity(set_a, set())
        assert similarity == 0.0

        similarity = service.calculate_jaccard_similarity(set(), set_a)
        assert similarity == 0.0

    def test_single_element_overlap(self, service: RelatedCollectionsService) -> None:
        """Single element overlap should calculate correctly."""
        # A = {x, y, z}, B = {x, a, b}
        # Intersection = {x} = 1
        # Union = {x, y, z, a, b} = 5
        # Jaccard = 1/5 = 0.2
        set_a = {"x", "y", "z"}
        set_b = {"x", "a", "b"}
        similarity = service.calculate_jaccard_similarity(set_a, set_b)
        assert similarity == pytest.approx(0.2, rel=1e-6)

    def test_commutative_property(self, service: RelatedCollectionsService) -> None:
        """Jaccard similarity should be commutative: J(A,B) = J(B,A)."""
        set_a = {"tech", "blog", "reviews"}
        set_b = {"tech", "products", "reviews", "news"}

        similarity_ab = service.calculate_jaccard_similarity(set_a, set_b)
        similarity_ba = service.calculate_jaccard_similarity(set_b, set_a)

        assert similarity_ab == similarity_ba


# ---------------------------------------------------------------------------
# Test: Overlap Details Calculation
# ---------------------------------------------------------------------------


class TestOverlapDetails:
    """Tests for calculate_overlap_details method."""

    def test_overlap_details_basic(self, service: RelatedCollectionsService) -> None:
        """Should calculate correct overlap details."""
        source = {"a", "b", "c"}
        target = {"b", "c", "d"}

        overlapping, unique_source, unique_target = service.calculate_overlap_details(
            source, target
        )

        assert overlapping == {"b", "c"}
        assert unique_source == {"a"}
        assert unique_target == {"d"}

    def test_overlap_details_no_overlap(self, service: RelatedCollectionsService) -> None:
        """Should handle no overlap case."""
        source = {"a", "b"}
        target = {"x", "y"}

        overlapping, unique_source, unique_target = service.calculate_overlap_details(
            source, target
        )

        assert overlapping == set()
        assert unique_source == {"a", "b"}
        assert unique_target == {"x", "y"}

    def test_overlap_details_complete_overlap(
        self, service: RelatedCollectionsService
    ) -> None:
        """Should handle complete overlap case."""
        labels = {"a", "b", "c"}

        overlapping, unique_source, unique_target = service.calculate_overlap_details(
            labels, labels.copy()
        )

        assert overlapping == labels
        assert unique_source == set()
        assert unique_target == set()

    def test_overlap_details_empty_sets(
        self, service: RelatedCollectionsService
    ) -> None:
        """Should handle empty sets."""
        overlapping, unique_source, unique_target = service.calculate_overlap_details(
            set(), set()
        )

        assert overlapping == set()
        assert unique_source == set()
        assert unique_target == set()


# ---------------------------------------------------------------------------
# Test: find_related Method
# ---------------------------------------------------------------------------


class TestFindRelated:
    """Tests for the find_related method."""

    def test_find_related_basic(
        self,
        service: RelatedCollectionsService,
        sample_collections: list[Collection],
        electronics_labels: set[str],
    ) -> None:
        """Should find related collections sorted by similarity."""
        result = service.find_related(
            source_labels=electronics_labels,
            candidate_collections=sample_collections,
            project_id="proj-1",
        )

        assert result.success is True
        assert result.source_labels == electronics_labels
        assert result.total_candidates == len(sample_collections)
        assert result.project_id == "proj-1"
        assert result.duration_ms >= 0

        # Electronics Products (c1) should be the best match
        # It has: electronics, gadgets, tech, products
        # Source: electronics, gadgets, tech, devices
        # Intersection: electronics, gadgets, tech = 3
        # Union: electronics, gadgets, tech, products, devices = 5
        # Jaccard = 3/5 = 0.6
        if result.matches:
            assert result.matches[0].collection.id == "c1"
            assert result.matches[0].similarity_score >= 0.5

    def test_find_related_empty_source_labels(
        self,
        service: RelatedCollectionsService,
        sample_collections: list[Collection],
    ) -> None:
        """Empty source labels should return error result."""
        result = service.find_related(
            source_labels=set(),
            candidate_collections=sample_collections,
            project_id="proj-1",
        )

        assert result.success is False
        assert result.error is not None
        assert "empty" in result.error.lower()
        assert result.matches == []

    def test_find_related_empty_candidates(
        self,
        service: RelatedCollectionsService,
        electronics_labels: set[str],
    ) -> None:
        """Empty candidate list should return success with no matches."""
        result = service.find_related(
            source_labels=electronics_labels,
            candidate_collections=[],
            project_id="proj-1",
        )

        assert result.success is True
        assert result.matches == []
        assert result.total_candidates == 0

    def test_find_related_respects_threshold(
        self,
        service_strict: RelatedCollectionsService,
        sample_collections: list[Collection],
    ) -> None:
        """Should filter out collections below threshold."""
        # With strict threshold of 0.5, only high-similarity matches should pass
        source_labels = {"electronics", "tech"}

        result = service_strict.find_related(
            source_labels=source_labels,
            candidate_collections=sample_collections,
        )

        assert result.success is True
        # All matches should have similarity >= 0.5
        for match in result.matches:
            assert match.similarity_score >= 0.5

    def test_find_related_custom_threshold_override(
        self,
        service: RelatedCollectionsService,
        sample_collections: list[Collection],
    ) -> None:
        """Should allow threshold override per call."""
        source_labels = {"electronics", "gadgets", "tech"}

        # Call with very strict threshold
        result = service.find_related(
            source_labels=source_labels,
            candidate_collections=sample_collections,
            similarity_threshold=0.8,
        )

        assert result.success is True
        # Only very similar collections should match
        for match in result.matches:
            assert match.similarity_score >= 0.8

    def test_find_related_respects_max_results(
        self,
        service: RelatedCollectionsService,
        sample_collections: list[Collection],
    ) -> None:
        """Should limit results to max_results."""
        # Use very low threshold to get many matches
        result = service.find_related(
            source_labels={"products", "blog", "tech"},
            candidate_collections=sample_collections,
            similarity_threshold=0.01,
            max_results=2,
        )

        assert result.success is True
        assert len(result.matches) <= 2

    def test_find_related_excludes_collection_ids(
        self,
        service: RelatedCollectionsService,
        sample_collections: list[Collection],
        electronics_labels: set[str],
    ) -> None:
        """Should exclude specified collection IDs."""
        # Exclude the best match (c1)
        result = service.find_related(
            source_labels=electronics_labels,
            candidate_collections=sample_collections,
            exclude_collection_ids={"c1"},
        )

        assert result.success is True
        # c1 should not be in results
        match_ids = {m.collection.id for m in result.matches}
        assert "c1" not in match_ids

    def test_find_related_skips_empty_label_collections(
        self,
        service: RelatedCollectionsService,
        sample_collections: list[Collection],
        electronics_labels: set[str],
    ) -> None:
        """Should skip collections with empty labels."""
        result = service.find_related(
            source_labels=electronics_labels,
            candidate_collections=sample_collections,
            similarity_threshold=0.0,  # Accept all
        )

        assert result.success is True
        # c6 (Empty Collection) should not appear in matches
        match_ids = {m.collection.id for m in result.matches}
        assert "c6" not in match_ids
        # But it should be counted in filtered_count
        assert result.filtered_count >= 1

    def test_find_related_sorted_by_similarity_descending(
        self,
        service: RelatedCollectionsService,
        sample_collections: list[Collection],
    ) -> None:
        """Results should be sorted by similarity in descending order."""
        result = service.find_related(
            source_labels={"tech", "blog", "products"},
            candidate_collections=sample_collections,
            similarity_threshold=0.0,
        )

        assert result.success is True
        if len(result.matches) >= 2:
            for i in range(len(result.matches) - 1):
                assert (
                    result.matches[i].similarity_score
                    >= result.matches[i + 1].similarity_score
                )

    def test_find_related_includes_overlap_details(
        self,
        service: RelatedCollectionsService,
        sample_collections: list[Collection],
        electronics_labels: set[str],
    ) -> None:
        """Each match should include correct overlap details."""
        result = service.find_related(
            source_labels=electronics_labels,
            candidate_collections=sample_collections,
        )

        assert result.success is True
        for match in result.matches:
            # Verify overlap consistency
            all_labels = (
                match.overlapping_labels
                | match.unique_to_source
                | match.unique_to_match
            )
            expected_union = electronics_labels | match.collection.labels
            assert all_labels == expected_union

            # Verify unique sets are actually unique
            assert match.overlapping_labels & match.unique_to_source == set()
            assert match.overlapping_labels & match.unique_to_match == set()

    def test_find_related_tracks_duration(
        self,
        service: RelatedCollectionsService,
        sample_collections: list[Collection],
        electronics_labels: set[str],
    ) -> None:
        """Should track operation duration."""
        result = service.find_related(
            source_labels=electronics_labels,
            candidate_collections=sample_collections,
        )

        assert result.success is True
        assert result.duration_ms >= 0
        assert isinstance(result.duration_ms, float)


# ---------------------------------------------------------------------------
# Test: find_related_by_collection Method
# ---------------------------------------------------------------------------


class TestFindRelatedByCollection:
    """Tests for the find_related_by_collection convenience method."""

    def test_find_related_by_collection_basic(
        self,
        service: RelatedCollectionsService,
        sample_collections: list[Collection],
    ) -> None:
        """Should find related collections using source Collection object."""
        source = sample_collections[0]  # Electronics Products

        result = service.find_related_by_collection(
            source_collection=source,
            candidate_collections=sample_collections,
        )

        assert result.success is True
        assert result.source_collection_id == source.id
        assert result.source_labels == source.labels
        assert result.project_id == source.project_id

    def test_find_related_by_collection_excludes_self(
        self,
        service: RelatedCollectionsService,
        sample_collections: list[Collection],
    ) -> None:
        """Should exclude source collection by default."""
        source = sample_collections[0]  # c1

        result = service.find_related_by_collection(
            source_collection=source,
            candidate_collections=sample_collections,
        )

        assert result.success is True
        match_ids = {m.collection.id for m in result.matches}
        assert source.id not in match_ids

    def test_find_related_by_collection_include_self(
        self,
        service: RelatedCollectionsService,
        sample_collections: list[Collection],
    ) -> None:
        """Should include source when exclude_self=False."""
        source = sample_collections[0]  # c1

        result = service.find_related_by_collection(
            source_collection=source,
            candidate_collections=sample_collections,
            exclude_self=False,
            similarity_threshold=0.0,  # Include all
        )

        assert result.success is True
        match_ids = {m.collection.id for m in result.matches}
        # Self should be included and have similarity 1.0
        assert source.id in match_ids
        self_match = next(m for m in result.matches if m.collection.id == source.id)
        assert self_match.similarity_score == 1.0

    def test_find_related_by_collection_custom_project_id(
        self,
        service: RelatedCollectionsService,
        sample_collections: list[Collection],
    ) -> None:
        """Should use custom project_id when provided."""
        source = sample_collections[0]

        result = service.find_related_by_collection(
            source_collection=source,
            candidate_collections=sample_collections,
            project_id="custom-project",
        )

        assert result.success is True
        assert result.project_id == "custom-project"


# ---------------------------------------------------------------------------
# Test: rank_by_similarity Method
# ---------------------------------------------------------------------------


class TestRankBySimilarity:
    """Tests for the rank_by_similarity method."""

    def test_rank_by_similarity_basic(
        self,
        service: RelatedCollectionsService,
        sample_collections: list[Collection],
        electronics_labels: set[str],
    ) -> None:
        """Should rank all collections by similarity."""
        ranked = service.rank_by_similarity(
            source_labels=electronics_labels,
            collections=sample_collections,
            project_id="proj-1",
        )

        assert len(ranked) == len(sample_collections)
        # Should include tuples of (collection, similarity)
        for collection, similarity in ranked:
            assert isinstance(collection, Collection)
            assert isinstance(similarity, float)
            assert 0.0 <= similarity <= 1.0

    def test_rank_by_similarity_sorted_descending(
        self,
        service: RelatedCollectionsService,
        sample_collections: list[Collection],
        electronics_labels: set[str],
    ) -> None:
        """Should be sorted by similarity in descending order."""
        ranked = service.rank_by_similarity(
            source_labels=electronics_labels,
            collections=sample_collections,
        )

        if len(ranked) >= 2:
            for i in range(len(ranked) - 1):
                assert ranked[i][1] >= ranked[i + 1][1]

    def test_rank_by_similarity_empty_source_labels(
        self,
        service: RelatedCollectionsService,
        sample_collections: list[Collection],
    ) -> None:
        """Empty source labels should return empty list."""
        ranked = service.rank_by_similarity(
            source_labels=set(),
            collections=sample_collections,
        )

        assert ranked == []

    def test_rank_by_similarity_empty_collections(
        self,
        service: RelatedCollectionsService,
        electronics_labels: set[str],
    ) -> None:
        """Empty collections should return empty list."""
        ranked = service.rank_by_similarity(
            source_labels=electronics_labels,
            collections=[],
        )

        assert ranked == []

    def test_rank_by_similarity_no_threshold_filter(
        self,
        service: RelatedCollectionsService,
        sample_collections: list[Collection],
    ) -> None:
        """Should include all collections regardless of similarity."""
        # Use labels that have low overlap with most collections
        source_labels = {"unique", "labels", "here"}

        ranked = service.rank_by_similarity(
            source_labels=source_labels,
            collections=sample_collections,
        )

        # All collections should be included, even with 0 similarity
        assert len(ranked) == len(sample_collections)


# ---------------------------------------------------------------------------
# Test: find_clusters Method
# ---------------------------------------------------------------------------


class TestFindClusters:
    """Tests for the find_clusters clustering method."""

    def test_find_clusters_basic(
        self,
        service: RelatedCollectionsService,
    ) -> None:
        """Should cluster similar collections together."""
        collections = [
            Collection(id="a1", name="A1", labels={"x", "y", "z"}),
            Collection(id="a2", name="A2", labels={"x", "y", "z", "w"}),  # Similar to a1
            Collection(id="b1", name="B1", labels={"m", "n", "o"}),
            Collection(id="b2", name="B2", labels={"m", "n", "o", "p"}),  # Similar to b1
            Collection(id="c1", name="C1", labels={"q"}),  # Alone
        ]

        clusters = service.find_clusters(
            collections=collections,
            cluster_threshold=0.5,
            project_id="proj-1",
        )

        # Should have clusters grouping similar collections
        assert len(clusters) >= 1
        # Total collections across all clusters should equal input
        total = sum(len(c) for c in clusters)
        assert total == len(collections)

    def test_find_clusters_empty_input(
        self,
        service: RelatedCollectionsService,
    ) -> None:
        """Empty input should return empty clusters."""
        clusters = service.find_clusters(
            collections=[],
            cluster_threshold=0.5,
        )

        assert clusters == []

    def test_find_clusters_all_different(
        self,
        service: RelatedCollectionsService,
    ) -> None:
        """Collections with no overlap should each be in their own cluster."""
        collections = [
            Collection(id="c1", name="C1", labels={"a", "b"}),
            Collection(id="c2", name="C2", labels={"c", "d"}),
            Collection(id="c3", name="C3", labels={"e", "f"}),
        ]

        clusters = service.find_clusters(
            collections=collections,
            cluster_threshold=0.5,
        )

        # Each collection in its own cluster (no overlap >= 0.5)
        assert len(clusters) == 3
        for cluster in clusters:
            assert len(cluster) == 1

    def test_find_clusters_all_identical(
        self,
        service: RelatedCollectionsService,
    ) -> None:
        """Identical collections should be in one cluster."""
        labels = {"shared", "labels"}
        collections = [
            Collection(id="c1", name="C1", labels=labels.copy()),
            Collection(id="c2", name="C2", labels=labels.copy()),
            Collection(id="c3", name="C3", labels=labels.copy()),
        ]

        clusters = service.find_clusters(
            collections=collections,
            cluster_threshold=0.5,
        )

        # All in one cluster (similarity = 1.0)
        assert len(clusters) == 1
        assert len(clusters[0]) == 3

    def test_find_clusters_respects_threshold(
        self,
        service: RelatedCollectionsService,
    ) -> None:
        """Should use cluster_threshold for grouping decisions."""
        collections = [
            Collection(id="c1", name="C1", labels={"a", "b", "c", "d"}),
            Collection(
                id="c2", name="C2", labels={"a", "b", "x", "y"}
            ),  # 2/6 = 0.33 similarity
        ]

        # With high threshold, they should be separate
        clusters_strict = service.find_clusters(
            collections=collections,
            cluster_threshold=0.8,
        )
        assert len(clusters_strict) == 2

        # With low threshold, they should be together
        clusters_loose = service.find_clusters(
            collections=collections,
            cluster_threshold=0.3,
        )
        assert len(clusters_loose) == 1

    def test_find_clusters_greedy_behavior(
        self,
        service: RelatedCollectionsService,
    ) -> None:
        """Should use greedy clustering (first come, first served)."""
        # A is similar to both B and C, but B and C are not similar
        collections = [
            Collection(id="a", name="A", labels={"x", "y"}),
            Collection(id="b", name="B", labels={"x", "z"}),  # Similar to A
            Collection(id="c", name="C", labels={"y", "w"}),  # Similar to A
        ]

        clusters = service.find_clusters(
            collections=collections,
            cluster_threshold=0.3,
        )

        # With greedy approach, A clusters first, pulling in B and C
        # Verify each collection appears exactly once
        all_ids = set()
        for cluster in clusters:
            for c in cluster:
                assert c.id not in all_ids
                all_ids.add(c.id)
        assert all_ids == {"a", "b", "c"}


# ---------------------------------------------------------------------------
# Test: Exception Classes
# ---------------------------------------------------------------------------


class TestExceptionClasses:
    """Tests for RelatedCollections exception classes."""

    def test_related_collections_error_base(self) -> None:
        """RelatedCollectionsError should be base exception."""
        error = RelatedCollectionsError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_collection_validation_error(self) -> None:
        """CollectionValidationError should contain field and value info."""
        error = CollectionValidationError(
            field="similarity_threshold",
            value=2.0,
            message="Must be between 0.0 and 1.0",
        )
        assert error.field == "similarity_threshold"
        assert error.value == 2.0
        assert error.message == "Must be between 0.0 and 1.0"
        assert "similarity_threshold" in str(error)

    def test_collection_not_found_error(self) -> None:
        """CollectionNotFoundError should contain collection info."""
        error = CollectionNotFoundError(
            collection_id="missing-123",
            project_id="proj-1",
        )
        assert error.collection_id == "missing-123"
        assert error.project_id == "proj-1"
        assert "missing-123" in str(error)

    def test_collection_not_found_error_without_project(self) -> None:
        """CollectionNotFoundError should work without project_id."""
        error = CollectionNotFoundError(collection_id="missing-123")
        assert error.collection_id == "missing-123"
        assert error.project_id is None

    def test_exception_hierarchy(self) -> None:
        """All exceptions should inherit from RelatedCollectionsError."""
        assert issubclass(CollectionValidationError, RelatedCollectionsError)
        assert issubclass(CollectionNotFoundError, RelatedCollectionsError)


# ---------------------------------------------------------------------------
# Test: Singleton and Convenience Functions
# ---------------------------------------------------------------------------


class TestSingletonAndConvenience:
    """Tests for singleton accessor and convenience functions."""

    def test_get_related_collections_service_singleton(self) -> None:
        """get_related_collections_service should return singleton."""
        # Clear the global instance first
        import app.services.related_collections as rc_module

        original = rc_module._related_collections_service
        rc_module._related_collections_service = None

        try:
            service1 = get_related_collections_service()
            service2 = get_related_collections_service()
            assert service1 is service2
        finally:
            # Restore original
            rc_module._related_collections_service = original

    def test_find_related_collections_convenience(
        self,
        sample_collections: list[Collection],
        electronics_labels: set[str],
    ) -> None:
        """find_related_collections should use default service."""
        result = find_related_collections(
            source_labels=electronics_labels,
            candidate_collections=sample_collections,
            project_id="proj-1",
        )

        assert result.success is True
        assert len(result.matches) > 0 or result.filtered_count > 0

    def test_find_related_collections_with_custom_params(
        self,
        sample_collections: list[Collection],
    ) -> None:
        """find_related_collections should accept custom parameters."""
        result = find_related_collections(
            source_labels={"tech", "blog"},
            candidate_collections=sample_collections,
            similarity_threshold=0.3,
            max_results=3,
            project_id="custom-proj",
        )

        assert result.success is True
        assert len(result.matches) <= 3


# ---------------------------------------------------------------------------
# Test: Edge Cases and Boundary Conditions
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_single_element_sets(
        self,
        service: RelatedCollectionsService,
    ) -> None:
        """Should handle single-element label sets."""
        result = service.find_related(
            source_labels={"single"},
            candidate_collections=[
                Collection(id="c1", name="C1", labels={"single"}),
                Collection(id="c2", name="C2", labels={"other"}),
            ],
            similarity_threshold=0.0,
        )

        assert result.success is True
        # c1 should have similarity 1.0
        c1_match = next(
            (m for m in result.matches if m.collection.id == "c1"), None
        )
        assert c1_match is not None
        assert c1_match.similarity_score == 1.0

    def test_large_label_sets(
        self,
        service: RelatedCollectionsService,
    ) -> None:
        """Should handle large label sets efficiently."""
        # Create sets with 100 labels each
        labels_a = {f"label_{i}" for i in range(100)}
        labels_b = {f"label_{i}" for i in range(50, 150)}  # 50% overlap

        result = service.find_related(
            source_labels=labels_a,
            candidate_collections=[
                Collection(id="c1", name="C1", labels=labels_b),
            ],
            similarity_threshold=0.0,
        )

        assert result.success is True
        # Jaccard = 50/150 = 0.333...
        if result.matches:
            assert result.matches[0].similarity_score == pytest.approx(1 / 3, rel=1e-6)

    def test_unicode_labels(
        self,
        service: RelatedCollectionsService,
    ) -> None:
        """Should handle unicode characters in labels."""
        result = service.find_related(
            source_labels={"日本語", "emoji😀", "Ñoño"},
            candidate_collections=[
                Collection(id="c1", name="C1", labels={"日本語", "中文"}),
                Collection(id="c2", name="C2", labels={"emoji😀", "emoji🎉"}),
            ],
            similarity_threshold=0.0,
        )

        assert result.success is True
        assert len(result.matches) == 2

    def test_whitespace_labels(
        self,
        service: RelatedCollectionsService,
    ) -> None:
        """Should handle labels with whitespace."""
        result = service.find_related(
            source_labels={"multi word label", "  spaces  "},
            candidate_collections=[
                Collection(id="c1", name="C1", labels={"multi word label", "other"}),
            ],
            similarity_threshold=0.0,
        )

        assert result.success is True
        assert len(result.matches) == 1

    def test_case_sensitivity(
        self,
        service: RelatedCollectionsService,
    ) -> None:
        """Labels should be case-sensitive."""
        result = service.find_related(
            source_labels={"Label", "LABEL", "label"},
            candidate_collections=[
                Collection(id="c1", name="C1", labels={"Label"}),
                Collection(id="c2", name="C2", labels={"label"}),
            ],
            similarity_threshold=0.0,
        )

        assert result.success is True
        # Each match should have different overlap
        c1_match = next(m for m in result.matches if m.collection.id == "c1")
        c2_match = next(m for m in result.matches if m.collection.id == "c2")

        assert "Label" in c1_match.overlapping_labels
        assert "label" in c2_match.overlapping_labels
        assert c1_match.similarity_score == c2_match.similarity_score  # Both 1/3

    def test_many_candidates_performance(
        self,
        service: RelatedCollectionsService,
    ) -> None:
        """Should handle many candidate collections."""
        # Create 100 candidate collections
        candidates = [
            Collection(
                id=f"c{i}",
                name=f"Collection {i}",
                labels={"common", f"label_{i}", f"label_{i+1}"},
            )
            for i in range(100)
        ]

        result = service.find_related(
            source_labels={"common", "label_50"},
            candidate_collections=candidates,
            similarity_threshold=0.0,
            max_results=10,
        )

        assert result.success is True
        assert len(result.matches) <= 10
        assert result.total_candidates == 100
