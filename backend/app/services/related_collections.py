"""RelatedCollectionsService for finding related page collections via label overlap.

Provides intelligent discovery of related page collections using label overlap
scoring (Jaccard similarity). Collections are groups of pages that share common
labels, and this service finds other collections with similar thematic content.

The algorithm uses Jaccard coefficient to measure label set similarity:
    J(A, B) = |A ∩ B| / |A ∪ B|

This produces scores between 0.0 (no overlap) and 1.0 (identical labels).

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import time
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Threshold for logging slow operations (in milliseconds)
SLOW_OPERATION_THRESHOLD_MS = 1000

# Default similarity threshold for considering collections "related"
DEFAULT_SIMILARITY_THRESHOLD = 0.1

# Maximum number of related collections to return by default
DEFAULT_MAX_RESULTS = 10


class RelatedCollectionsError(Exception):
    """Base exception for RelatedCollectionsService errors."""

    pass


class CollectionValidationError(RelatedCollectionsError):
    """Raised when collection validation fails."""

    def __init__(self, field: str, value: Any, message: str):
        self.field = field
        self.value = value
        self.message = message
        super().__init__(f"Validation failed for '{field}': {message}")


class CollectionNotFoundError(RelatedCollectionsError):
    """Raised when a collection is not found."""

    def __init__(self, collection_id: str, project_id: str | None = None):
        self.collection_id = collection_id
        self.project_id = project_id
        super().__init__(f"Collection not found: {collection_id}")


@dataclass
class Collection:
    """Represents a collection of pages with shared labels.

    Attributes:
        id: Unique collection identifier
        name: Human-readable collection name
        labels: Set of labels/tags for this collection
        page_count: Number of pages in the collection
        category: Optional dominant category (e.g., 'product', 'blog')
        project_id: Parent project ID
        metadata: Additional collection metadata
    """

    id: str
    name: str
    labels: set[str]
    page_count: int = 0
    category: str | None = None
    project_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RelatedCollectionMatch:
    """A collection match with similarity score and overlap details.

    Attributes:
        collection: The matched collection
        similarity_score: Jaccard similarity coefficient (0.0 to 1.0)
        overlapping_labels: Labels shared between the collections
        unique_to_source: Labels only in the source collection
        unique_to_match: Labels only in the matched collection
    """

    collection: Collection
    similarity_score: float
    overlapping_labels: set[str]
    unique_to_source: set[str]
    unique_to_match: set[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "collection_id": self.collection.id,
            "collection_name": self.collection.name,
            "similarity_score": round(self.similarity_score, 4),
            "overlapping_labels": sorted(self.overlapping_labels),
            "unique_to_source": sorted(self.unique_to_source),
            "unique_to_match": sorted(self.unique_to_match),
            "overlap_count": len(self.overlapping_labels),
            "category": self.collection.category,
            "page_count": self.collection.page_count,
        }


@dataclass
class RelatedCollectionsResult:
    """Result of finding related collections.

    Attributes:
        success: Whether the operation succeeded
        source_collection_id: The source collection ID
        source_labels: Labels from the source collection
        matches: List of related collection matches, sorted by similarity
        total_candidates: Total collections considered
        filtered_count: Collections below similarity threshold
        error: Error message if failed
        duration_ms: Total time taken
        project_id: Project ID (for logging context)
    """

    success: bool
    source_collection_id: str
    source_labels: set[str] = field(default_factory=set)
    matches: list[RelatedCollectionMatch] = field(default_factory=list)
    total_candidates: int = 0
    filtered_count: int = 0
    error: str | None = None
    duration_ms: float = 0.0
    project_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "source_collection_id": self.source_collection_id,
            "source_labels": sorted(self.source_labels),
            "matches": [m.to_dict() for m in self.matches],
            "match_count": len(self.matches),
            "total_candidates": self.total_candidates,
            "filtered_count": self.filtered_count,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


class RelatedCollectionsService:
    """Service for finding related page collections via label overlap scoring.

    Uses Jaccard similarity coefficient to measure label overlap between
    collections. Higher scores indicate more similar collections.

    The Jaccard coefficient formula:
        J(A, B) = |A ∩ B| / |A ∪ B|

    Where:
        - A ∩ B is the intersection (common labels)
        - A ∪ B is the union (all unique labels from both)

    Example usage:
        service = RelatedCollectionsService()

        # Find collections related to a product collection
        result = service.find_related(
            source_labels={"e-commerce", "widgets", "electronics"},
            candidate_collections=[collection1, collection2, ...],
            project_id="abc-123",
        )

        for match in result.matches:
            print(f"{match.collection.name}: {match.similarity_score:.2%}")
            print(f"  Shared labels: {match.overlapping_labels}")

    Example with threshold:
        # Only return collections with >30% label overlap
        result = service.find_related(
            source_labels={"blog", "tech", "tutorials"},
            candidate_collections=all_collections,
            similarity_threshold=0.3,
            max_results=5,
        )
    """

    def __init__(
        self,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> None:
        """Initialize the related collections service.

        Args:
            similarity_threshold: Minimum Jaccard similarity to consider related
            max_results: Maximum number of related collections to return
        """
        logger.debug(
            "RelatedCollectionsService.__init__ called",
            extra={
                "similarity_threshold": similarity_threshold,
                "max_results": max_results,
            },
        )

        if not 0.0 <= similarity_threshold <= 1.0:
            logger.warning(
                "Validation failed: similarity_threshold out of range",
                extra={
                    "field": "similarity_threshold",
                    "rejected_value": similarity_threshold,
                    "valid_range": "0.0-1.0",
                },
            )
            raise CollectionValidationError(
                "similarity_threshold",
                similarity_threshold,
                "Must be between 0.0 and 1.0",
            )

        if max_results < 1:
            logger.warning(
                "Validation failed: max_results too low",
                extra={
                    "field": "max_results",
                    "rejected_value": max_results,
                    "min_value": 1,
                },
            )
            raise CollectionValidationError(
                "max_results",
                max_results,
                "Must be at least 1",
            )

        self._similarity_threshold = similarity_threshold
        self._max_results = max_results

        logger.debug(
            "RelatedCollectionsService initialized",
            extra={
                "similarity_threshold": similarity_threshold,
                "max_results": max_results,
            },
        )

    @property
    def similarity_threshold(self) -> float:
        """Get the default similarity threshold."""
        return self._similarity_threshold

    @property
    def max_results(self) -> int:
        """Get the default max results limit."""
        return self._max_results

    def calculate_jaccard_similarity(
        self,
        labels_a: set[str],
        labels_b: set[str],
    ) -> float:
        """Calculate Jaccard similarity coefficient between two label sets.

        The Jaccard coefficient measures the similarity between two sets:
            J(A, B) = |A ∩ B| / |A ∪ B|

        Args:
            labels_a: First set of labels
            labels_b: Second set of labels

        Returns:
            Jaccard similarity coefficient (0.0 to 1.0)
            Returns 0.0 if both sets are empty
        """
        if not labels_a and not labels_b:
            return 0.0

        intersection = labels_a & labels_b
        union = labels_a | labels_b

        if not union:
            return 0.0

        return len(intersection) / len(union)

    def calculate_overlap_details(
        self,
        source_labels: set[str],
        target_labels: set[str],
    ) -> tuple[set[str], set[str], set[str]]:
        """Calculate detailed overlap information between label sets.

        Args:
            source_labels: Labels from the source collection
            target_labels: Labels from the target collection

        Returns:
            Tuple of (overlapping, unique_to_source, unique_to_target)
        """
        overlapping = source_labels & target_labels
        unique_to_source = source_labels - target_labels
        unique_to_target = target_labels - source_labels
        return overlapping, unique_to_source, unique_to_target

    def find_related(
        self,
        source_labels: set[str],
        candidate_collections: list[Collection],
        source_collection_id: str = "source",
        similarity_threshold: float | None = None,
        max_results: int | None = None,
        project_id: str | None = None,
        exclude_collection_ids: set[str] | None = None,
    ) -> RelatedCollectionsResult:
        """Find collections related to the source by label overlap.

        Calculates Jaccard similarity between the source labels and each
        candidate collection's labels, returning matches above the threshold
        sorted by similarity score (descending).

        Args:
            source_labels: Labels from the source collection
            candidate_collections: Collections to compare against
            source_collection_id: ID of the source collection (for logging)
            similarity_threshold: Minimum similarity to include (overrides default)
            max_results: Maximum matches to return (overrides default)
            project_id: Project ID for logging context
            exclude_collection_ids: Collection IDs to exclude from results

        Returns:
            RelatedCollectionsResult with sorted matches and metadata
        """
        start_time = time.monotonic()
        threshold = similarity_threshold or self._similarity_threshold
        limit = max_results or self._max_results
        exclude_ids = exclude_collection_ids or set()

        logger.debug(
            "find_related() called",
            extra={
                "project_id": project_id,
                "source_collection_id": source_collection_id,
                "source_label_count": len(source_labels),
                "candidate_count": len(candidate_collections),
                "similarity_threshold": threshold,
                "max_results": limit,
                "exclude_count": len(exclude_ids),
            },
        )

        # Validate inputs
        if not source_labels:
            logger.warning(
                "Validation failed: empty source labels",
                extra={
                    "project_id": project_id,
                    "source_collection_id": source_collection_id,
                    "field": "source_labels",
                    "rejected_value": "empty set",
                },
            )
            duration_ms = (time.monotonic() - start_time) * 1000
            return RelatedCollectionsResult(
                success=False,
                source_collection_id=source_collection_id,
                source_labels=source_labels,
                error="Source labels cannot be empty",
                duration_ms=round(duration_ms, 2),
                project_id=project_id,
            )

        try:
            matches: list[RelatedCollectionMatch] = []
            filtered_count = 0

            # Calculate similarity for each candidate
            for collection in candidate_collections:
                # Skip excluded collections
                if collection.id in exclude_ids:
                    logger.debug(
                        "Skipping excluded collection",
                        extra={
                            "project_id": project_id,
                            "collection_id": collection.id,
                        },
                    )
                    continue

                # Skip if collection has no labels
                if not collection.labels:
                    filtered_count += 1
                    continue

                # Calculate Jaccard similarity
                similarity = self.calculate_jaccard_similarity(
                    source_labels,
                    collection.labels,
                )

                # Apply threshold filter
                if similarity < threshold:
                    filtered_count += 1
                    continue

                # Calculate overlap details
                overlapping, unique_source, unique_target = (
                    self.calculate_overlap_details(source_labels, collection.labels)
                )

                matches.append(
                    RelatedCollectionMatch(
                        collection=collection,
                        similarity_score=similarity,
                        overlapping_labels=overlapping,
                        unique_to_source=unique_source,
                        unique_to_match=unique_target,
                    )
                )

            # Sort by similarity (descending) and limit results
            matches.sort(key=lambda m: m.similarity_score, reverse=True)
            matches = matches[:limit]

            duration_ms = (time.monotonic() - start_time) * 1000

            # Log state transition: search complete
            logger.info(
                "Related collections search complete",
                extra={
                    "project_id": project_id,
                    "source_collection_id": source_collection_id,
                    "source_label_count": len(source_labels),
                    "total_candidates": len(candidate_collections),
                    "matches_found": len(matches),
                    "filtered_below_threshold": filtered_count,
                    "similarity_threshold": threshold,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow related collections search",
                    extra={
                        "project_id": project_id,
                        "source_collection_id": source_collection_id,
                        "candidate_count": len(candidate_collections),
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return RelatedCollectionsResult(
                success=True,
                source_collection_id=source_collection_id,
                source_labels=source_labels,
                matches=matches,
                total_candidates=len(candidate_collections),
                filtered_count=filtered_count,
                duration_ms=round(duration_ms, 2),
                project_id=project_id,
            )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Related collections search failed with exception",
                extra={
                    "project_id": project_id,
                    "source_collection_id": source_collection_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
                exc_info=True,
            )
            return RelatedCollectionsResult(
                success=False,
                source_collection_id=source_collection_id,
                source_labels=source_labels,
                error=str(e),
                duration_ms=round(duration_ms, 2),
                project_id=project_id,
            )

    def find_related_by_collection(
        self,
        source_collection: Collection,
        candidate_collections: list[Collection],
        similarity_threshold: float | None = None,
        max_results: int | None = None,
        project_id: str | None = None,
        exclude_self: bool = True,
    ) -> RelatedCollectionsResult:
        """Find collections related to a source Collection object.

        Convenience method that extracts labels from the source collection
        and automatically excludes it from results.

        Args:
            source_collection: The source Collection object
            candidate_collections: Collections to compare against
            similarity_threshold: Minimum similarity to include
            max_results: Maximum matches to return
            project_id: Project ID for logging (defaults to collection's)
            exclude_self: Whether to exclude source from results (default True)

        Returns:
            RelatedCollectionsResult with sorted matches and metadata
        """
        logger.debug(
            "find_related_by_collection() called",
            extra={
                "project_id": project_id or source_collection.project_id,
                "source_collection_id": source_collection.id,
                "source_collection_name": source_collection.name,
                "source_label_count": len(source_collection.labels),
                "candidate_count": len(candidate_collections),
                "exclude_self": exclude_self,
            },
        )

        exclude_ids = {source_collection.id} if exclude_self else set()

        return self.find_related(
            source_labels=source_collection.labels,
            candidate_collections=candidate_collections,
            source_collection_id=source_collection.id,
            similarity_threshold=similarity_threshold,
            max_results=max_results,
            project_id=project_id or source_collection.project_id,
            exclude_collection_ids=exclude_ids,
        )

    def rank_by_similarity(
        self,
        source_labels: set[str],
        collections: list[Collection],
        project_id: str | None = None,
    ) -> list[tuple[Collection, float]]:
        """Rank all collections by similarity without filtering.

        Returns all collections sorted by Jaccard similarity, without
        applying any threshold. Useful for analysis and debugging.

        Args:
            source_labels: Labels to compare against
            collections: Collections to rank
            project_id: Project ID for logging

        Returns:
            List of (collection, similarity_score) tuples, sorted descending
        """
        start_time = time.monotonic()
        logger.debug(
            "rank_by_similarity() called",
            extra={
                "project_id": project_id,
                "source_label_count": len(source_labels),
                "collection_count": len(collections),
            },
        )

        if not source_labels:
            logger.warning(
                "Validation failed: empty source labels for ranking",
                extra={
                    "project_id": project_id,
                    "field": "source_labels",
                    "rejected_value": "empty set",
                },
            )
            return []

        ranked: list[tuple[Collection, float]] = []

        for collection in collections:
            similarity = self.calculate_jaccard_similarity(
                source_labels,
                collection.labels,
            )
            ranked.append((collection, similarity))

        # Sort by similarity descending
        ranked.sort(key=lambda x: x[1], reverse=True)

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.debug(
            "rank_by_similarity() completed",
            extra={
                "project_id": project_id,
                "collection_count": len(collections),
                "duration_ms": round(duration_ms, 2),
            },
        )

        if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
            logger.warning(
                "Slow collection ranking",
                extra={
                    "project_id": project_id,
                    "collection_count": len(collections),
                    "duration_ms": round(duration_ms, 2),
                },
            )

        return ranked

    def find_clusters(
        self,
        collections: list[Collection],
        cluster_threshold: float = 0.5,
        project_id: str | None = None,
    ) -> list[list[Collection]]:
        """Find clusters of highly similar collections.

        Groups collections that have similarity above the cluster threshold.
        Uses a simple greedy clustering approach.

        Args:
            collections: Collections to cluster
            cluster_threshold: Minimum similarity to be in same cluster
            project_id: Project ID for logging

        Returns:
            List of collection clusters (each cluster is a list of collections)
        """
        start_time = time.monotonic()
        logger.debug(
            "find_clusters() called",
            extra={
                "project_id": project_id,
                "collection_count": len(collections),
                "cluster_threshold": cluster_threshold,
            },
        )

        if not collections:
            return []

        # Track which collections are already clustered
        clustered: set[str] = set()
        clusters: list[list[Collection]] = []

        for collection in collections:
            if collection.id in clustered:
                continue

            # Start a new cluster with this collection
            cluster = [collection]
            clustered.add(collection.id)

            # Find all similar collections not yet clustered
            for other in collections:
                if other.id in clustered:
                    continue

                similarity = self.calculate_jaccard_similarity(
                    collection.labels,
                    other.labels,
                )

                if similarity >= cluster_threshold:
                    cluster.append(other)
                    clustered.add(other.id)

            clusters.append(cluster)

        duration_ms = (time.monotonic() - start_time) * 1000

        # Log state transition: clustering complete
        logger.info(
            "Collection clustering complete",
            extra={
                "project_id": project_id,
                "collection_count": len(collections),
                "cluster_count": len(clusters),
                "cluster_threshold": cluster_threshold,
                "duration_ms": round(duration_ms, 2),
            },
        )

        if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
            logger.warning(
                "Slow collection clustering",
                extra={
                    "project_id": project_id,
                    "collection_count": len(collections),
                    "duration_ms": round(duration_ms, 2),
                },
            )

        return clusters


# Global RelatedCollectionsService instance
_related_collections_service: RelatedCollectionsService | None = None


def get_related_collections_service() -> RelatedCollectionsService:
    """Get the default RelatedCollectionsService instance (singleton).

    Returns:
        Default RelatedCollectionsService instance.
    """
    global _related_collections_service
    if _related_collections_service is None:
        _related_collections_service = RelatedCollectionsService()
    return _related_collections_service


def find_related_collections(
    source_labels: set[str],
    candidate_collections: list[Collection],
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    max_results: int = DEFAULT_MAX_RESULTS,
    project_id: str | None = None,
) -> RelatedCollectionsResult:
    """Convenience function to find related collections.

    Uses the default RelatedCollectionsService singleton.

    Args:
        source_labels: Labels from the source collection
        candidate_collections: Collections to compare against
        similarity_threshold: Minimum Jaccard similarity to include
        max_results: Maximum matches to return
        project_id: Project ID for logging

    Returns:
        RelatedCollectionsResult with sorted matches and metadata

    Example:
        >>> result = find_related_collections(
        ...     source_labels={"e-commerce", "widgets", "electronics"},
        ...     candidate_collections=[c1, c2, c3],
        ...     similarity_threshold=0.2,
        ... )
        >>> print(f"Found {len(result.matches)} related collections")
        >>> for match in result.matches:
        ...     print(f"  {match.collection.name}: {match.similarity_score:.1%}")
    """
    service = get_related_collections_service()
    return service.find_related(
        source_labels=source_labels,
        candidate_collections=candidate_collections,
        similarity_threshold=similarity_threshold,
        max_results=max_results,
        project_id=project_id,
    )
