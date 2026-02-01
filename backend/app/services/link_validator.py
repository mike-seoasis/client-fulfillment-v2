"""Phase 5C: Link validation service against collection registry.

Validates internal links from generated content against a registry of known
valid collection pages. Ensures all internal links point to real pages that
exist in the project's page collection.

Features:
- URL normalization for consistent comparison
- Batch link validation
- Detailed validation results with suggestions
- Registry-based validation (no database calls per link)

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import time
import traceback
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from app.core.logging import get_logger
from app.utils.url import URLNormalizationOptions, URLNormalizer

logger = get_logger(__name__)

# Constants
SLOW_OPERATION_THRESHOLD_MS = 1000
DEFAULT_MAX_BATCH_SIZE = 100

# Validation thresholds
VALIDATION_PASS_THRESHOLD = 100.0  # All links must be valid to pass


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class CollectionRegistryEntry:
    """An entry in the collection registry representing a valid page.

    Attributes:
        url: The canonical URL of the collection page
        name: Human-readable name of the collection
        labels: Set of labels/tags for this collection
        page_id: Optional page ID for tracking
    """

    url: str
    name: str
    labels: set[str] = field(default_factory=set)
    page_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "name": self.name,
            "labels": sorted(self.labels),
            "page_id": self.page_id,
        }


@dataclass
class CollectionRegistry:
    """Registry of valid collection pages for link validation.

    Attributes:
        entries: List of collection registry entries
        normalized_urls: Set of normalized URLs for fast lookup
        project_id: Project ID for logging context
    """

    entries: list[CollectionRegistryEntry] = field(default_factory=list)
    normalized_urls: set[str] = field(default_factory=set)
    project_id: str | None = None

    def __post_init__(self) -> None:
        """Build normalized URL set from entries."""
        self._rebuild_normalized_urls()

    def _rebuild_normalized_urls(self) -> None:
        """Rebuild the normalized URL set from entries."""
        normalizer = URLNormalizer(URLNormalizationOptions(
            remove_fragments=True,
            remove_trailing_slash=True,
            remove_query_params=True,
            lowercase_host=True,
        ))
        self.normalized_urls = set()
        for entry in self.entries:
            try:
                normalized = normalizer.normalize(entry.url)
                self.normalized_urls.add(normalized)
            except ValueError:
                # Skip invalid URLs in registry
                logger.warning(
                    "Invalid URL in collection registry, skipping",
                    extra={
                        "url": entry.url[:200] if entry.url else "",
                        "project_id": self.project_id,
                    },
                )

    def add_entry(self, entry: CollectionRegistryEntry) -> None:
        """Add an entry to the registry."""
        self.entries.append(entry)
        normalizer = URLNormalizer(URLNormalizationOptions(
            remove_fragments=True,
            remove_trailing_slash=True,
            remove_query_params=True,
            lowercase_host=True,
        ))
        try:
            normalized = normalizer.normalize(entry.url)
            self.normalized_urls.add(normalized)
        except ValueError:
            logger.warning(
                "Invalid URL added to collection registry",
                extra={
                    "url": entry.url[:200] if entry.url else "",
                    "project_id": self.project_id,
                },
            )

    def contains_url(self, url: str) -> bool:
        """Check if a URL exists in the registry.

        Args:
            url: URL to check (will be normalized)

        Returns:
            True if URL exists in registry
        """
        normalizer = URLNormalizer(URLNormalizationOptions(
            remove_fragments=True,
            remove_trailing_slash=True,
            remove_query_params=True,
            lowercase_host=True,
        ))
        try:
            normalized = normalizer.normalize(url)
            return normalized in self.normalized_urls
        except ValueError:
            return False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "entry_count": len(self.entries),
            "unique_urls": len(self.normalized_urls),
            "project_id": self.project_id,
        }


@dataclass
class LinkToValidate:
    """A link to be validated against the collection registry.

    Attributes:
        url: The URL of the link
        anchor_text: The anchor text of the link
        link_type: Type of link (e.g., 'related', 'priority', 'internal')
        source_content_id: ID of the content containing this link
        source_page_id: ID of the page containing this link
    """

    url: str
    anchor_text: str = ""
    link_type: str = "internal"
    source_content_id: str | None = None
    source_page_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "anchor_text": self.anchor_text,
            "link_type": self.link_type,
            "source_content_id": self.source_content_id,
            "source_page_id": self.source_page_id,
        }


@dataclass
class LinkValidationResult:
    """Result of validating a single link.

    Attributes:
        url: The original URL that was validated
        anchor_text: The anchor text of the link
        is_valid: Whether the link is valid (exists in registry)
        is_internal: Whether the link is internal to the site
        normalized_url: The normalized form of the URL
        error: Error message if validation failed
        suggestion: Suggestion for fixing invalid links
    """

    url: str
    anchor_text: str
    is_valid: bool
    is_internal: bool = True
    normalized_url: str | None = None
    error: str | None = None
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "anchor_text": self.anchor_text,
            "is_valid": self.is_valid,
            "is_internal": self.is_internal,
            "normalized_url": self.normalized_url,
            "error": self.error,
            "suggestion": self.suggestion,
        }


@dataclass
class LinkValidationBatchResult:
    """Result of validating multiple links.

    Attributes:
        success: Whether the validation completed successfully
        results: Individual validation results for each link
        total_links: Total number of links validated
        valid_count: Number of valid links
        invalid_count: Number of invalid links
        external_count: Number of external links (not validated)
        validation_score: Percentage of valid links (0-100)
        passed_validation: Whether all internal links are valid
        error: Error message if batch validation failed
        duration_ms: Total time taken
        project_id: Project ID for logging context
        page_id: Page ID for logging context
    """

    success: bool
    results: list[LinkValidationResult] = field(default_factory=list)
    total_links: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    external_count: int = 0
    validation_score: float = 100.0
    passed_validation: bool = True
    error: str | None = None
    duration_ms: float = 0.0
    project_id: str | None = None
    page_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "results": [r.to_dict() for r in self.results],
            "total_links": self.total_links,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
            "external_count": self.external_count,
            "validation_score": round(self.validation_score, 2),
            "passed_validation": self.passed_validation,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
            "project_id": self.project_id,
            "page_id": self.page_id,
        }


@dataclass
class LinkValidatorInput:
    """Input data for link validation.

    Attributes:
        links: Links to validate
        registry: Collection registry to validate against
        site_domain: Domain of the site (for determining internal links)
        project_id: Project ID for logging
        page_id: Page ID for logging
        content_id: Content ID for logging
    """

    links: list[LinkToValidate]
    registry: CollectionRegistry
    site_domain: str | None = None
    project_id: str | None = None
    page_id: str | None = None
    content_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging (sanitized)."""
        return {
            "link_count": len(self.links),
            "registry_size": len(self.registry.entries),
            "site_domain": self.site_domain,
            "project_id": self.project_id,
            "page_id": self.page_id,
            "content_id": self.content_id,
        }


# =============================================================================
# EXCEPTIONS
# =============================================================================


class LinkValidatorServiceError(Exception):
    """Base exception for link validator service errors."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.page_id = page_id


class LinkValidatorValidationError(LinkValidatorServiceError):
    """Raised when input validation fails."""

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


# =============================================================================
# SERVICE
# =============================================================================


class LinkValidatorService:
    """Service for Phase 5C link validation against collection registry.

    Validates internal links from generated content to ensure they point
    to valid collection pages in the project's registry.

    Usage:
        service = LinkValidatorService()

        # Build registry from known pages
        registry = CollectionRegistry(
            entries=[
                CollectionRegistryEntry(
                    url="https://example.com/collections/wallets",
                    name="Wallets",
                ),
                CollectionRegistryEntry(
                    url="https://example.com/collections/bags",
                    name="Bags",
                ),
            ],
            project_id="abc-123",
        )

        # Validate links
        result = await service.validate_links(
            input_data=LinkValidatorInput(
                links=[
                    LinkToValidate(
                        url="https://example.com/collections/wallets",
                        anchor_text="Shop Wallets",
                    ),
                ],
                registry=registry,
                site_domain="example.com",
                project_id="abc-123",
            ),
        )
    """

    def __init__(self) -> None:
        """Initialize link validator service."""
        self._url_normalizer = URLNormalizer(URLNormalizationOptions(
            remove_fragments=True,
            remove_trailing_slash=True,
            remove_query_params=True,
            lowercase_host=True,
        ))

        logger.debug("LinkValidatorService initialized")

    def _is_internal_link(
        self,
        url: str,
        site_domain: str | None,
    ) -> bool:
        """Check if a URL is internal to the site.

        Args:
            url: URL to check
            site_domain: Domain of the site

        Returns:
            True if URL is internal
        """
        if not site_domain:
            # If no domain specified, treat relative URLs as internal
            return not url.startswith(("http://", "https://"))

        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                # Relative URL - internal
                return True

            # Compare domains (case-insensitive)
            url_domain = parsed.netloc.lower()
            site_domain_lower = site_domain.lower()

            # Handle www prefix
            if url_domain.startswith("www."):
                url_domain = url_domain[4:]
            if site_domain_lower.startswith("www."):
                site_domain_lower = site_domain_lower[4:]

            return url_domain == site_domain_lower

        except Exception:
            return False

    def _make_absolute_url(
        self,
        url: str,
        site_domain: str | None,
    ) -> str:
        """Convert a relative URL to absolute.

        Args:
            url: URL to convert
            site_domain: Domain to use for absolute URL

        Returns:
            Absolute URL
        """
        if url.startswith(("http://", "https://")):
            return url

        if not site_domain:
            # Cannot make absolute without domain
            return url

        # Ensure domain has scheme
        if not site_domain.startswith(("http://", "https://")):
            site_domain = f"https://{site_domain}"

        # Join with path
        if url.startswith("/"):
            parsed = urlparse(site_domain)
            return f"{parsed.scheme}://{parsed.netloc}{url}"
        else:
            return f"{site_domain.rstrip('/')}/{url}"

    def _validate_single_link(
        self,
        link: LinkToValidate,
        registry: CollectionRegistry,
        site_domain: str | None,
        project_id: str | None,
        page_id: str | None,
    ) -> LinkValidationResult:
        """Validate a single link against the registry.

        Args:
            link: Link to validate
            registry: Collection registry
            site_domain: Site domain for internal link detection
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            LinkValidationResult with validation status
        """
        url = link.url
        anchor_text = link.anchor_text

        logger.debug(
            "Validating single link",
            extra={
                "url": url[:200] if url else "",
                "anchor_text": anchor_text[:100] if anchor_text else "",
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        # Check if URL is empty
        if not url or not url.strip():
            logger.warning(
                "Link validation failed - empty URL",
                extra={
                    "field": "url",
                    "rejected_value": "",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            return LinkValidationResult(
                url=url,
                anchor_text=anchor_text,
                is_valid=False,
                is_internal=True,
                error="URL is empty",
                suggestion="Provide a valid URL for the link",
            )

        # Check if link is internal
        is_internal = self._is_internal_link(url, site_domain)

        if not is_internal:
            # External links are not validated against registry
            logger.debug(
                "External link skipped",
                extra={
                    "url": url[:200],
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            return LinkValidationResult(
                url=url,
                anchor_text=anchor_text,
                is_valid=True,  # External links pass by default
                is_internal=False,
                normalized_url=None,
            )

        # Make URL absolute for comparison
        absolute_url = self._make_absolute_url(url, site_domain)

        # Normalize URL
        try:
            normalized_url = self._url_normalizer.normalize(absolute_url)
        except ValueError as e:
            logger.warning(
                "Link validation failed - invalid URL format",
                extra={
                    "url": url[:200],
                    "error": str(e),
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            return LinkValidationResult(
                url=url,
                anchor_text=anchor_text,
                is_valid=False,
                is_internal=True,
                error=f"Invalid URL format: {e}",
                suggestion="Ensure the URL is properly formatted",
            )

        # Check if URL exists in registry
        is_valid = registry.contains_url(absolute_url)

        if not is_valid:
            logger.warning(
                "Link validation failed - URL not in registry",
                extra={
                    "url": url[:200],
                    "normalized_url": normalized_url[:200],
                    "registry_size": len(registry.normalized_urls),
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            return LinkValidationResult(
                url=url,
                anchor_text=anchor_text,
                is_valid=False,
                is_internal=True,
                normalized_url=normalized_url,
                error="URL not found in collection registry",
                suggestion="Link to a valid collection page from the project",
            )

        logger.debug(
            "Link validated successfully",
            extra={
                "url": url[:200],
                "normalized_url": normalized_url[:200],
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        return LinkValidationResult(
            url=url,
            anchor_text=anchor_text,
            is_valid=True,
            is_internal=True,
            normalized_url=normalized_url,
        )

    async def validate_links(
        self,
        input_data: LinkValidatorInput,
    ) -> LinkValidationBatchResult:
        """Validate multiple links against the collection registry.

        Phase 5C link validation:
        1. Identify internal vs external links
        2. Normalize internal links for comparison
        3. Check each internal link against registry
        4. Calculate validation score
        5. Generate suggestions for invalid links

        Args:
            input_data: Input data containing links and registry

        Returns:
            LinkValidationBatchResult with validation results
        """
        start_time = time.monotonic()
        project_id = input_data.project_id
        page_id = input_data.page_id
        content_id = input_data.content_id

        logger.debug(
            "Phase 5C link validation starting",
            extra={
                "link_count": len(input_data.links),
                "registry_size": len(input_data.registry.entries),
                "site_domain": input_data.site_domain,
                "project_id": project_id,
                "page_id": page_id,
                "content_id": content_id,
            },
        )

        # Validate inputs
        if input_data.registry is None:
            logger.warning(
                "Link validation failed - no registry provided",
                extra={
                    "field": "registry",
                    "rejected_value": None,
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            raise LinkValidatorValidationError(
                "registry",
                None,
                "Collection registry cannot be None",
                project_id=project_id,
                page_id=page_id,
            )

        try:
            # Log phase transition
            logger.info(
                "Phase 5C: Link validation - in_progress",
                extra={
                    "link_count": len(input_data.links),
                    "phase": "5C",
                    "status": "in_progress",
                    "project_id": project_id,
                    "page_id": page_id,
                    "content_id": content_id,
                },
            )

            results: list[LinkValidationResult] = []
            valid_count = 0
            invalid_count = 0
            external_count = 0

            # Validate each link
            for link in input_data.links:
                result = self._validate_single_link(
                    link=link,
                    registry=input_data.registry,
                    site_domain=input_data.site_domain,
                    project_id=project_id,
                    page_id=page_id,
                )
                results.append(result)

                if not result.is_internal:
                    external_count += 1
                elif result.is_valid:
                    valid_count += 1
                else:
                    invalid_count += 1

            # Calculate validation score
            internal_count = len(input_data.links) - external_count
            if internal_count > 0:
                validation_score = (valid_count / internal_count) * 100
            else:
                validation_score = 100.0

            passed_validation = validation_score >= VALIDATION_PASS_THRESHOLD

            duration_ms = (time.monotonic() - start_time) * 1000

            # Log completion
            logger.info(
                "Phase 5C: Link validation - completed",
                extra={
                    "total_links": len(input_data.links),
                    "valid_count": valid_count,
                    "invalid_count": invalid_count,
                    "external_count": external_count,
                    "validation_score": round(validation_score, 2),
                    "passed_validation": passed_validation,
                    "phase": "5C",
                    "status": "completed",
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "page_id": page_id,
                    "content_id": content_id,
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow Phase 5C link validation operation",
                    extra={
                        "link_count": len(input_data.links),
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )

            return LinkValidationBatchResult(
                success=True,
                results=results,
                total_links=len(input_data.links),
                valid_count=valid_count,
                invalid_count=invalid_count,
                external_count=external_count,
                validation_score=validation_score,
                passed_validation=passed_validation,
                duration_ms=duration_ms,
                project_id=project_id,
                page_id=page_id,
            )

        except LinkValidatorValidationError:
            raise
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Phase 5C link validation unexpected error",
                extra={
                    "link_count": len(input_data.links) if input_data.links else 0,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "page_id": page_id,
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return LinkValidationBatchResult(
                success=False,
                error=f"Unexpected error: {e}",
                duration_ms=duration_ms,
                project_id=project_id,
                page_id=page_id,
            )


# =============================================================================
# SINGLETON
# =============================================================================


_link_validator_service: LinkValidatorService | None = None


def get_link_validator_service() -> LinkValidatorService:
    """Get the global link validator service instance.

    Usage:
        from app.services.link_validator import get_link_validator_service
        service = get_link_validator_service()
        result = await service.validate_links(input_data)
    """
    global _link_validator_service
    if _link_validator_service is None:
        _link_validator_service = LinkValidatorService()
        logger.info("LinkValidatorService singleton created")
    return _link_validator_service


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


async def validate_links(
    links: list[LinkToValidate],
    registry: CollectionRegistry,
    site_domain: str | None = None,
    project_id: str | None = None,
    page_id: str | None = None,
    content_id: str | None = None,
) -> LinkValidationBatchResult:
    """Convenience function for Phase 5C link validation.

    Args:
        links: Links to validate
        registry: Collection registry to validate against
        site_domain: Domain of the site (for determining internal links)
        project_id: Project ID for logging
        page_id: Page ID for logging
        content_id: Content ID for logging

    Returns:
        LinkValidationBatchResult with validation results
    """
    service = get_link_validator_service()
    input_data = LinkValidatorInput(
        links=links,
        registry=registry,
        site_domain=site_domain,
        project_id=project_id,
        page_id=page_id,
        content_id=content_id,
    )
    return await service.validate_links(input_data)


def build_registry_from_urls(
    urls: list[str],
    names: list[str] | None = None,
    project_id: str | None = None,
) -> CollectionRegistry:
    """Build a collection registry from a list of URLs.

    Convenience function for creating a registry from simple URL lists.

    Args:
        urls: List of valid collection URLs
        names: Optional list of names (same length as urls)
        project_id: Project ID for logging

    Returns:
        CollectionRegistry with entries for each URL

    Example:
        >>> registry = build_registry_from_urls(
        ...     urls=[
        ...         "https://example.com/collections/wallets",
        ...         "https://example.com/collections/bags",
        ...     ],
        ...     names=["Wallets", "Bags"],
        ...     project_id="abc-123",
        ... )
    """
    entries = []
    for i, url in enumerate(urls):
        name = names[i] if names and i < len(names) else f"Collection {i + 1}"
        entries.append(CollectionRegistryEntry(url=url, name=name))

    return CollectionRegistry(entries=entries, project_id=project_id)
