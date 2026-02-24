"""Content signal detection for confidence boosting.

Detects signals in page content (title, headings, body text) that can boost
confidence in URL-based page categorization. Works alongside URLCategorizer
to provide more accurate category assignments.

Signal Types:
- TITLE: Patterns found in page title (e.g., "Shop", "Blog", "Privacy Policy")
- HEADING: Patterns found in H1/H2 headings
- SCHEMA: JSON-LD schema types (Product, Article, FAQPage, etc.)
- META: Meta description content patterns
- BREADCRUMB: Breadcrumb trail patterns

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.logging import get_logger

logger = get_logger("content_signals")

# Threshold for logging slow operations (in milliseconds)
SLOW_OPERATION_THRESHOLD_MS = 1000


class SignalType(Enum):
    """Types of content signals that can be detected."""

    TITLE = "title"
    HEADING = "heading"
    SCHEMA = "schema"
    META = "meta"
    BREADCRUMB = "breadcrumb"
    BODY = "body"


@dataclass
class ContentSignal:
    """A detected content signal that indicates a category.

    Attributes:
        signal_type: The type of signal (title, heading, schema, etc.)
        category: The category this signal indicates
        confidence_boost: How much to boost confidence (0.0 to 1.0)
        matched_text: The text that matched the signal pattern
        pattern: The pattern that matched (for debugging)
    """

    signal_type: SignalType
    category: str
    confidence_boost: float
    matched_text: str
    pattern: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert signal to dictionary for serialization."""
        return {
            "signal_type": self.signal_type.value,
            "category": self.category,
            "confidence_boost": self.confidence_boost,
            "matched_text": self.matched_text[:200] if self.matched_text else "",
            "pattern": self.pattern,
        }


@dataclass
class ContentAnalysis:
    """Result of content signal analysis.

    Attributes:
        url_category: The category from URL-based detection
        url_confidence: Base confidence from URL pattern matching (0.0 to 1.0)
        signals: List of detected content signals
        boosted_confidence: Final confidence after applying signal boosts
        final_category: The final category (may differ from url_category if signals override)
    """

    url_category: str
    url_confidence: float
    signals: list[ContentSignal] = field(default_factory=list)
    boosted_confidence: float = 0.0
    final_category: str = ""

    def __post_init__(self) -> None:
        """Set defaults if not provided."""
        if not self.final_category:
            self.final_category = self.url_category
        if self.boosted_confidence == 0.0:
            self.boosted_confidence = self.url_confidence

    def to_dict(self) -> dict[str, Any]:
        """Convert analysis to dictionary for serialization."""
        return {
            "url_category": self.url_category,
            "url_confidence": self.url_confidence,
            "signals": [s.to_dict() for s in self.signals],
            "boosted_confidence": self.boosted_confidence,
            "final_category": self.final_category,
            "signal_count": len(self.signals),
        }


@dataclass
class SignalPattern:
    """A pattern for detecting content signals.

    Attributes:
        category: The category this pattern indicates
        patterns: List of regex patterns to match
        signal_type: Type of content where this pattern applies
        confidence_boost: How much to boost confidence when matched
        priority: Higher priority patterns are checked first
    """

    category: str
    patterns: list[str]
    signal_type: SignalType
    confidence_boost: float = 0.2
    priority: int = 0

    def __post_init__(self) -> None:
        """Compile regex patterns for efficiency."""
        self._compiled_patterns: list[re.Pattern[str]] = []
        for pattern in self.patterns:
            try:
                self._compiled_patterns.append(re.compile(pattern, re.IGNORECASE))
            except re.error as e:
                logger.warning(
                    "Invalid regex pattern in signal pattern",
                    extra={
                        "category": self.category,
                        "pattern": pattern,
                        "signal_type": self.signal_type.value,
                        "error": str(e),
                    },
                )

    def matches(self, text: str) -> tuple[bool, str | None, str | None]:
        """Check if text matches any pattern.

        Args:
            text: The text to check

        Returns:
            Tuple of (matches, matched_text, pattern_str)
        """
        if not text:
            return False, None, None

        for i, compiled in enumerate(self._compiled_patterns):
            match = compiled.search(text)
            if match:
                return True, match.group(0), self.patterns[i]

        return False, None, None


# Default signal patterns for each category
# These patterns are checked against content (title, headings, etc.)
DEFAULT_SIGNAL_PATTERNS: list[SignalPattern] = [
    # Homepage signals
    SignalPattern(
        category="homepage",
        patterns=[
            r"\bhome\s*page\b",
            r"\bwelcome\s+to\b",
            r"^home$",
            r"\bofficial\s+site\b",
        ],
        signal_type=SignalType.TITLE,
        confidence_boost=0.3,
        priority=100,
    ),
    # Product signals - title patterns
    SignalPattern(
        category="product",
        patterns=[
            r"\bbuy\s+now\b",
            r"\badd\s+to\s+cart\b",
            r"\bproduct\s+details?\b",
            r"\bin\s+stock\b",
            r"\bout\s+of\s+stock\b",
            r"\bfree\s+shipping\b",
            r"\$\d+\.?\d*",  # Price pattern
            r"£\d+\.?\d*",
            r"€\d+\.?\d*",
            r"\bsku\s*[:#]?\s*\w+",
            r"\bmodel\s*[:#]?\s*\w+",
        ],
        signal_type=SignalType.BODY,
        confidence_boost=0.25,
        priority=80,
    ),
    # Product signals - schema
    SignalPattern(
        category="product",
        patterns=[
            r'"@type"\s*:\s*"Product"',
            r'"@type"\s*:\s*"IndividualProduct"',
            r'"@type"\s*:\s*"ProductGroup"',
        ],
        signal_type=SignalType.SCHEMA,
        confidence_boost=0.4,
        priority=85,
    ),
    # Collection/category signals
    SignalPattern(
        category="collection",
        patterns=[
            r"\bshop\s+all\b",
            r"\bview\s+all\b",
            r"\bshow\s+all\b",
            r"\bfilter\s+by\b",
            r"\bsort\s+by\b",
            r"\bresults?\s*found\b",
            r"\d+\s+products?\b",
            r"\d+\s+items?\b",
            r"\bcollection\b",
            r"\bcategory\b",
        ],
        signal_type=SignalType.BODY,
        confidence_boost=0.2,
        priority=70,
    ),
    SignalPattern(
        category="collection",
        patterns=[
            r'"@type"\s*:\s*"CollectionPage"',
            r'"@type"\s*:\s*"ItemList"',
        ],
        signal_type=SignalType.SCHEMA,
        confidence_boost=0.35,
        priority=75,
    ),
    # Blog/article signals
    SignalPattern(
        category="blog",
        patterns=[
            r"\bposted\s+(on|by)\b",
            r"\bpublished\s+(on|by)\b",
            r"\bwritten\s+by\b",
            r"\bauthor\s*:\s*\w+",
            r"\bread\s+more\b",
            r"\bmin(ute)?\s+read\b",
            r"\bshare\s+this\b",
            r"\bcomments?\s*\(\d+\)",
            r"\btags?\s*:",
        ],
        signal_type=SignalType.BODY,
        confidence_boost=0.25,
        priority=60,
    ),
    SignalPattern(
        category="blog",
        patterns=[
            r'"@type"\s*:\s*"Article"',
            r'"@type"\s*:\s*"BlogPosting"',
            r'"@type"\s*:\s*"NewsArticle"',
        ],
        signal_type=SignalType.SCHEMA,
        confidence_boost=0.4,
        priority=65,
    ),
    SignalPattern(
        category="blog",
        patterns=[
            r"\bblog\b",
            r"\barticle\b",
            r"\bpost\b",
            r"\bnews\b",
            r"\bstory\b",
        ],
        signal_type=SignalType.TITLE,
        confidence_boost=0.2,
        priority=55,
    ),
    # Policy signals
    SignalPattern(
        category="policy",
        patterns=[
            r"\bprivacy\s+policy\b",
            r"\bterms\s+(of\s+)?(service|use)\b",
            r"\bterms\s+and\s+conditions\b",
            r"\brefund\s+policy\b",
            r"\breturn\s+policy\b",
            r"\bshipping\s+policy\b",
            r"\bcookie\s+policy\b",
            r"\bgdpr\b",
            r"\bccpa\b",
            r"\blegal\s+notice\b",
            r"\bdisclaimer\b",
        ],
        signal_type=SignalType.TITLE,
        confidence_boost=0.35,
        priority=50,
    ),
    SignalPattern(
        category="policy",
        patterns=[
            r"\bwe\s+collect\b",
            r"\bpersonal\s+data\b",
            r"\bpersonal\s+information\b",
            r"\bdata\s+protection\b",
            r"\bcookies?\s+we\s+use\b",
            r"\byour\s+rights\b",
            r"\beffective\s+date\b",
            r"\blast\s+updated\b",
        ],
        signal_type=SignalType.BODY,
        confidence_boost=0.2,
        priority=45,
    ),
    # About signals
    SignalPattern(
        category="about",
        patterns=[
            r"\babout\s+us\b",
            r"\bwho\s+we\s+are\b",
            r"\bour\s+story\b",
            r"\bour\s+mission\b",
            r"\bour\s+team\b",
            r"\bour\s+history\b",
            r"\bcompany\s+info(rmation)?\b",
            r"\bmeet\s+the\s+team\b",
        ],
        signal_type=SignalType.TITLE,
        confidence_boost=0.3,
        priority=40,
    ),
    SignalPattern(
        category="about",
        patterns=[
            r'"@type"\s*:\s*"AboutPage"',
            r'"@type"\s*:\s*"Organization"',
        ],
        signal_type=SignalType.SCHEMA,
        confidence_boost=0.3,
        priority=42,
    ),
    # Contact signals
    SignalPattern(
        category="contact",
        patterns=[
            r"\bcontact\s+us\b",
            r"\bget\s+in\s+touch\b",
            r"\breach\s+out\b",
            r"\bsend\s+(us\s+)?a\s+message\b",
            r"\bemail\s+us\b",
            r"\bcall\s+us\b",
        ],
        signal_type=SignalType.TITLE,
        confidence_boost=0.3,
        priority=40,
    ),
    SignalPattern(
        category="contact",
        patterns=[
            r"\bphone\s*:\s*[\d\-\+\(\)\s]+",
            r"\bemail\s*:\s*\S+@\S+",
            r"\baddress\s*:",
            r"\bopening\s+hours\b",
            r"\bbusiness\s+hours\b",
            r"\blocation\s*:",
        ],
        signal_type=SignalType.BODY,
        confidence_boost=0.2,
        priority=35,
    ),
    SignalPattern(
        category="contact",
        patterns=[
            r'"@type"\s*:\s*"ContactPage"',
            r'"@type"\s*:\s*"LocalBusiness"',
        ],
        signal_type=SignalType.SCHEMA,
        confidence_boost=0.35,
        priority=42,
    ),
    # FAQ signals
    SignalPattern(
        category="faq",
        patterns=[
            r"\bfaq\b",
            r"\bfrequently\s+asked\s+questions\b",
            r"\bhelp\s+center\b",
            r"\bsupport\s+center\b",
            r"\bknowledge\s+base\b",
        ],
        signal_type=SignalType.TITLE,
        confidence_boost=0.3,
        priority=35,
    ),
    SignalPattern(
        category="faq",
        patterns=[
            r'"@type"\s*:\s*"FAQPage"',
            r'"@type"\s*:\s*"Question"',
        ],
        signal_type=SignalType.SCHEMA,
        confidence_boost=0.4,
        priority=38,
    ),
    SignalPattern(
        category="faq",
        patterns=[
            r"\bhow\s+do\s+I\b",
            r"\bhow\s+can\s+I\b",
            r"\bwhat\s+is\s+the\b",
            r"\bwhat\s+are\s+the\b",
            r"\bwhere\s+can\s+I\b",
            r"\bcan\s+I\s+\w+\?",
        ],
        signal_type=SignalType.HEADING,
        confidence_boost=0.15,
        priority=30,
    ),
    # Account signals
    SignalPattern(
        category="account",
        patterns=[
            r"\blog\s*in\b",
            r"\bsign\s*in\b",
            r"\bsign\s*up\b",
            r"\bregister\b",
            r"\bcreate\s+account\b",
            r"\bmy\s+account\b",
            r"\bforgot\s+password\b",
            r"\breset\s+password\b",
        ],
        signal_type=SignalType.TITLE,
        confidence_boost=0.3,
        priority=30,
    ),
    SignalPattern(
        category="account",
        patterns=[
            r"\busername\s*:",
            r"\bpassword\s*:",
            r"\bemail\s+address\b",
            r"\bremember\s+me\b",
            r"\bstay\s+signed\s+in\b",
        ],
        signal_type=SignalType.BODY,
        confidence_boost=0.2,
        priority=25,
    ),
    # Cart/checkout signals
    SignalPattern(
        category="cart",
        patterns=[
            r"\bshopping\s+cart\b",
            r"\bshopping\s+bag\b",
            r"\byour\s+cart\b",
            r"\byour\s+bag\b",
            r"\bcheckout\b",
            r"\border\s+summary\b",
            r"\bcart\s+total\b",
        ],
        signal_type=SignalType.TITLE,
        confidence_boost=0.35,
        priority=30,
    ),
    SignalPattern(
        category="cart",
        patterns=[
            r"\bproceed\s+to\s+checkout\b",
            r"\bcontinue\s+to\s+checkout\b",
            r"\bpayment\s+method\b",
            r"\bshipping\s+address\b",
            r"\bbilling\s+address\b",
            r"\bplace\s+order\b",
            r"\bsubtotal\s*:",
        ],
        signal_type=SignalType.BODY,
        confidence_boost=0.25,
        priority=28,
    ),
    # Search signals
    SignalPattern(
        category="search",
        patterns=[
            r"\bsearch\s+results?\b",
            r"\bno\s+results?\s+found\b",
            r"\bshowing\s+\d+\s+results?\b",
            r"\bresults?\s+for\s*[\"']",
        ],
        signal_type=SignalType.BODY,
        confidence_boost=0.3,
        priority=20,
    ),
    SignalPattern(
        category="search",
        patterns=[
            r'"@type"\s*:\s*"SearchResultsPage"',
        ],
        signal_type=SignalType.SCHEMA,
        confidence_boost=0.4,
        priority=22,
    ),
]


class ContentSignalDetector:
    """Detects content signals that boost categorization confidence.

    The detector analyzes page content (title, headings, body, schema) to find
    signals that indicate the page category. These signals provide confidence
    boosts to the URL-based categorization.

    Example usage:
        detector = ContentSignalDetector()

        # Analyze content
        analysis = detector.analyze(
            url_category="product",
            url_confidence=0.7,
            title="Buy Widget Pro - Free Shipping",
            headings=["Product Details", "Add to Cart"],
            body_text="Buy now for $29.99. In stock. Free shipping...",
        )

        # Check results
        print(f"Category: {analysis.final_category}")  # "product"
        print(f"Confidence: {analysis.boosted_confidence}")  # 0.95+
    """

    def __init__(
        self,
        patterns: list[SignalPattern] | None = None,
        max_boost: float = 0.95,
        min_override_boost: float = 0.5,
    ) -> None:
        """Initialize the detector with patterns.

        Args:
            patterns: List of SignalPattern objects. Uses DEFAULT_SIGNAL_PATTERNS if None.
            max_boost: Maximum confidence value after boosting (default 0.95)
            min_override_boost: Minimum boost needed for signals to override URL category (default 0.5)
        """
        logger.debug(
            "ContentSignalDetector.__init__ called",
            extra={
                "pattern_count": len(patterns) if patterns else len(DEFAULT_SIGNAL_PATTERNS),
                "max_boost": max_boost,
                "min_override_boost": min_override_boost,
            },
        )

        self._patterns = patterns if patterns is not None else DEFAULT_SIGNAL_PATTERNS.copy()
        self._max_boost = max_boost
        self._min_override_boost = min_override_boost

        # Sort patterns by priority (highest first)
        self._patterns.sort(key=lambda p: p.priority, reverse=True)

        # Group patterns by signal type for efficient lookup
        self._patterns_by_type: dict[SignalType, list[SignalPattern]] = {}
        for pattern in self._patterns:
            if pattern.signal_type not in self._patterns_by_type:
                self._patterns_by_type[pattern.signal_type] = []
            self._patterns_by_type[pattern.signal_type].append(pattern)

        logger.debug(
            "ContentSignalDetector initialized",
            extra={
                "pattern_count": len(self._patterns),
                "signal_types": list(self._patterns_by_type.keys()),
            },
        )

    @property
    def patterns(self) -> list[SignalPattern]:
        """Get the signal patterns (read-only copy)."""
        return self._patterns.copy()

    @property
    def max_boost(self) -> float:
        """Get the maximum boost value."""
        return self._max_boost

    def add_pattern(self, pattern: SignalPattern) -> None:
        """Add a new signal pattern.

        Args:
            pattern: The SignalPattern to add.
        """
        logger.debug(
            "Adding signal pattern",
            extra={
                "category": pattern.category,
                "signal_type": pattern.signal_type.value,
                "pattern_count": len(pattern.patterns),
                "priority": pattern.priority,
            },
        )

        self._patterns.append(pattern)
        self._patterns.sort(key=lambda p: p.priority, reverse=True)

        # Update grouped patterns
        if pattern.signal_type not in self._patterns_by_type:
            self._patterns_by_type[pattern.signal_type] = []
        self._patterns_by_type[pattern.signal_type].append(pattern)

    def detect_signals(
        self,
        title: str | None = None,
        headings: list[str] | None = None,
        body_text: str | None = None,
        schema_json: str | None = None,
        meta_description: str | None = None,
        breadcrumbs: list[str] | None = None,
    ) -> list[ContentSignal]:
        """Detect content signals in the provided content.

        Args:
            title: Page title
            headings: List of heading texts (H1, H2, etc.)
            body_text: Body text content (may be truncated for efficiency)
            schema_json: JSON-LD schema content as string
            meta_description: Meta description content
            breadcrumbs: Breadcrumb trail texts

        Returns:
            List of detected ContentSignal objects
        """
        start_time = time.monotonic()
        logger.debug(
            "detect_signals() called",
            extra={
                "has_title": title is not None,
                "heading_count": len(headings) if headings else 0,
                "has_body": body_text is not None,
                "has_schema": schema_json is not None,
                "has_meta": meta_description is not None,
                "breadcrumb_count": len(breadcrumbs) if breadcrumbs else 0,
            },
        )

        signals: list[ContentSignal] = []

        try:
            # Check title patterns
            if title:
                signals.extend(self._check_patterns(
                    title, SignalType.TITLE, "title"
                ))

            # Check heading patterns
            if headings:
                combined_headings = " ".join(headings)
                signals.extend(self._check_patterns(
                    combined_headings, SignalType.HEADING, "headings"
                ))

            # Check body patterns (limit to first 10000 chars for efficiency)
            if body_text:
                truncated_body = body_text[:10000]
                signals.extend(self._check_patterns(
                    truncated_body, SignalType.BODY, "body"
                ))

            # Check schema patterns
            if schema_json:
                signals.extend(self._check_patterns(
                    schema_json, SignalType.SCHEMA, "schema"
                ))

            # Check meta description patterns
            if meta_description:
                signals.extend(self._check_patterns(
                    meta_description, SignalType.META, "meta"
                ))

            # Check breadcrumb patterns
            if breadcrumbs:
                combined_breadcrumbs = " > ".join(breadcrumbs)
                signals.extend(self._check_patterns(
                    combined_breadcrumbs, SignalType.BREADCRUMB, "breadcrumbs"
                ))

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Signal detection completed",
                extra={
                    "signal_count": len(signals),
                    "categories_detected": list({s.category for s in signals}),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow signal detection",
                    extra={
                        "duration_ms": round(duration_ms, 2),
                        "body_length": len(body_text) if body_text else 0,
                    },
                )

            return signals

        except Exception as e:
            logger.error(
                "Signal detection failed with exception",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            return signals

    def _check_patterns(
        self,
        text: str,
        signal_type: SignalType,
        source: str,
    ) -> list[ContentSignal]:
        """Check text against patterns of a specific type.

        Args:
            text: Text to check
            signal_type: Type of signal patterns to check
            source: Source name for logging

        Returns:
            List of detected signals
        """
        signals: list[ContentSignal] = []

        patterns = self._patterns_by_type.get(signal_type, [])
        if not patterns:
            return signals

        for pattern in patterns:
            matches, matched_text, pattern_str = pattern.matches(text)
            if matches and matched_text:
                signal = ContentSignal(
                    signal_type=signal_type,
                    category=pattern.category,
                    confidence_boost=pattern.confidence_boost,
                    matched_text=matched_text,
                    pattern=pattern_str,
                )
                signals.append(signal)

                logger.debug(
                    "Content signal detected",
                    extra={
                        "source": source,
                        "signal_type": signal_type.value,
                        "category": pattern.category,
                        "matched_text": matched_text[:100] if matched_text else "",
                        "confidence_boost": pattern.confidence_boost,
                    },
                )

        return signals

    def analyze(
        self,
        url_category: str,
        url_confidence: float = 0.5,
        title: str | None = None,
        headings: list[str] | None = None,
        body_text: str | None = None,
        schema_json: str | None = None,
        meta_description: str | None = None,
        breadcrumbs: list[str] | None = None,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> ContentAnalysis:
        """Analyze content and compute boosted confidence.

        Combines URL-based categorization with content signals to produce
        a final category and confidence score.

        Args:
            url_category: Category from URL-based detection
            url_confidence: Base confidence from URL pattern matching
            title: Page title
            headings: List of heading texts
            body_text: Body text content
            schema_json: JSON-LD schema content
            meta_description: Meta description content
            breadcrumbs: Breadcrumb trail texts
            project_id: Optional project ID for logging
            page_id: Optional page ID for logging

        Returns:
            ContentAnalysis with signals and boosted confidence
        """
        start_time = time.monotonic()
        logger.debug(
            "analyze() called",
            extra={
                "url_category": url_category,
                "url_confidence": url_confidence,
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        try:
            # Detect signals
            signals = self.detect_signals(
                title=title,
                headings=headings,
                body_text=body_text,
                schema_json=schema_json,
                meta_description=meta_description,
                breadcrumbs=breadcrumbs,
            )

            # Calculate boosted confidence
            boosted_confidence = url_confidence
            final_category = url_category

            # Group signals by category
            category_boosts: dict[str, float] = {}
            for signal in signals:
                if signal.category not in category_boosts:
                    category_boosts[signal.category] = 0.0
                category_boosts[signal.category] += signal.confidence_boost

            # Apply boosts for matching category
            if url_category in category_boosts:
                boosted_confidence += category_boosts[url_category]
                boosted_confidence = min(boosted_confidence, self._max_boost)

            # Check if a different category has stronger signals
            if category_boosts:
                max_boost_category = max(category_boosts.items(), key=lambda x: x[1])
                if (
                    max_boost_category[0] != url_category
                    and max_boost_category[1] >= self._min_override_boost
                ):
                    # Override category if signals are strong enough
                    final_category = max_boost_category[0]
                    boosted_confidence = min(
                        url_confidence + max_boost_category[1],
                        self._max_boost,
                    )

                    logger.info(
                        "Category override by content signals",
                        extra={
                            "project_id": project_id,
                            "page_id": page_id,
                            "url_category": url_category,
                            "final_category": final_category,
                            "signal_boost": max_boost_category[1],
                            "boosted_confidence": round(boosted_confidence, 3),
                        },
                    )

            analysis = ContentAnalysis(
                url_category=url_category,
                url_confidence=url_confidence,
                signals=signals,
                boosted_confidence=round(boosted_confidence, 3),
                final_category=final_category,
            )

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Content analysis completed",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "url_category": url_category,
                    "final_category": final_category,
                    "url_confidence": url_confidence,
                    "boosted_confidence": analysis.boosted_confidence,
                    "signal_count": len(signals),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow content analysis",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return analysis

        except Exception as e:
            logger.error(
                "Content analysis failed with exception",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "url_category": url_category,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            # Return basic analysis on error
            return ContentAnalysis(
                url_category=url_category,
                url_confidence=url_confidence,
                boosted_confidence=url_confidence,
                final_category=url_category,
            )

    def get_patterns_for_category(self, category: str) -> list[SignalPattern]:
        """Get all patterns that can indicate a specific category.

        Args:
            category: The category to look up

        Returns:
            List of SignalPattern objects for that category
        """
        return [p for p in self._patterns if p.category == category]


# Default instance for convenience
_default_detector: ContentSignalDetector | None = None


def get_content_signal_detector() -> ContentSignalDetector:
    """Get the default ContentSignalDetector instance (singleton).

    Returns:
        Default ContentSignalDetector instance.
    """
    global _default_detector
    if _default_detector is None:
        _default_detector = ContentSignalDetector()
    return _default_detector


def analyze_content_signals(
    url_category: str,
    url_confidence: float = 0.5,
    title: str | None = None,
    headings: list[str] | None = None,
    body_text: str | None = None,
    schema_json: str | None = None,
    meta_description: str | None = None,
    breadcrumbs: list[str] | None = None,
    project_id: str | None = None,
    page_id: str | None = None,
) -> ContentAnalysis:
    """Convenience function to analyze content signals.

    Args:
        url_category: Category from URL-based detection
        url_confidence: Base confidence from URL pattern matching
        title: Page title
        headings: List of heading texts
        body_text: Body text content
        schema_json: JSON-LD schema content
        meta_description: Meta description content
        breadcrumbs: Breadcrumb trail texts
        project_id: Optional project ID for logging
        page_id: Optional page ID for logging

    Returns:
        ContentAnalysis with signals and boosted confidence

    Example:
        >>> analysis = analyze_content_signals(
        ...     url_category="other",
        ...     url_confidence=0.3,
        ...     title="Privacy Policy | Example Corp",
        ...     body_text="We collect personal data... GDPR compliant...",
        ... )
        >>> print(analysis.final_category)
        'policy'
        >>> print(analysis.boosted_confidence)
        0.85
    """
    detector = get_content_signal_detector()
    return detector.analyze(
        url_category=url_category,
        url_confidence=url_confidence,
        title=title,
        headings=headings,
        body_text=body_text,
        schema_json=schema_json,
        meta_description=meta_description,
        breadcrumbs=breadcrumbs,
        project_id=project_id,
        page_id=page_id,
    )


# Signal type constants for validation
VALID_SIGNAL_TYPES = frozenset(s.value for s in SignalType)
