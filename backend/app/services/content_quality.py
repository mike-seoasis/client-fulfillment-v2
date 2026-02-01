"""Phase 5C: Content quality service with AI trope detection.

Analyzes generated content for AI-sounding patterns by detecting:
- Banned words (instant AI detection)
- Banned phrases
- Em dashes (—)
- Triplet patterns ("X. Y. Z.")
- Negation patterns ("aren't just X, they're Y")
- Rhetorical questions as openers
- Limited-use word frequency

Features:
- Deterministic pattern matching (no LLM calls)
- Quality scoring with detailed feedback
- Batch checking support
- Suggestions for improvement

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
import traceback
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Constants
SLOW_OPERATION_THRESHOLD_MS = 1000
DEFAULT_MAX_CONCURRENT = 10  # QA checks are fast, can run more concurrently

# Quality thresholds
QUALITY_SCORE_PASS_THRESHOLD = 80.0
MAX_LIMITED_USE_WORDS_PER_PAGE = 1


# =============================================================================
# BANNED ELEMENTS CONFIGURATION
# =============================================================================

# Instant AI detection - these words must never appear
BANNED_WORDS = frozenset([
    "delve",
    "unlock",
    "unleash",
    "journey",
    "game-changer",
    "gamechanger",
    "revolutionary",
    "crucial",
    "cutting-edge",
    "elevate",
    "leverage",
    "synergy",
    "innovative",
    "paradigm",
    "holistic",
    "empower",
    "transformative",
])

# Banned phrases - instant AI detection
BANNED_PHRASES = [
    "in today's fast-paced world",
    "it's important to note",
    "when it comes to",
    "at the end of the day",
    "look no further",
    "whether you're looking for",
]

# Limited use words - max 1 per page
LIMITED_USE_WORDS = frozenset([
    "indeed",
    "furthermore",
    "moreover",
    "robust",
    "seamless",
    "comprehensive",
    "enhance",
    "optimize",
    "streamline",
])

# Scoring weights for quality calculation
SCORING_WEIGHTS = {
    "banned_word": -20,  # Per occurrence
    "banned_phrase": -25,  # Per occurrence
    "em_dash": -10,  # Per occurrence
    "triplet_pattern": -15,  # Per occurrence
    "negation_pattern": -15,  # Per occurrence
    "rhetorical_question": -15,  # Per occurrence
    "limited_use_excess": -5,  # Per excess occurrence beyond 1
}


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class WordMatch:
    """A detected word with its location."""

    word: str
    count: int
    positions: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "word": self.word,
            "count": self.count,
            "positions": self.positions,
        }


@dataclass
class PhraseMatch:
    """A detected phrase with its location."""

    phrase: str
    count: int
    positions: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "phrase": self.phrase,
            "count": self.count,
            "positions": self.positions,
        }


@dataclass
class PatternMatch:
    """A detected pattern with context."""

    pattern_type: str
    matched_text: str
    position: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "pattern_type": self.pattern_type,
            "matched_text": self.matched_text,
            "position": self.position,
        }


@dataclass
class TropeDetectionResult:
    """Results of AI trope detection analysis."""

    # Detected issues
    found_banned_words: list[WordMatch] = field(default_factory=list)
    found_banned_phrases: list[PhraseMatch] = field(default_factory=list)
    found_em_dashes: int = 0
    found_triplet_patterns: list[PatternMatch] = field(default_factory=list)
    found_negation_patterns: list[PatternMatch] = field(default_factory=list)
    found_rhetorical_questions: int = 0
    limited_use_words: dict[str, int] = field(default_factory=dict)

    # Quality assessment
    overall_score: float = 100.0
    is_approved: bool = True
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "found_banned_words": [w.to_dict() for w in self.found_banned_words],
            "found_banned_phrases": [p.to_dict() for p in self.found_banned_phrases],
            "found_em_dashes": self.found_em_dashes,
            "found_triplet_patterns": [p.to_dict() for p in self.found_triplet_patterns],
            "found_negation_patterns": [p.to_dict() for p in self.found_negation_patterns],
            "found_rhetorical_questions": self.found_rhetorical_questions,
            "limited_use_words": self.limited_use_words,
            "overall_score": round(self.overall_score, 2),
            "is_approved": self.is_approved,
            "suggestions": self.suggestions,
        }


@dataclass
class ContentQualityInput:
    """Input data for content quality checking."""

    h1: str
    title_tag: str
    meta_description: str
    top_description: str
    bottom_description: str
    project_id: str | None = None
    page_id: str | None = None
    content_id: str | None = None

    def get_all_text(self) -> str:
        """Get all content fields combined for analysis."""
        return " ".join([
            self.h1,
            self.title_tag,
            self.meta_description,
            self.top_description,
            self.bottom_description,
        ])

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging (sanitized)."""
        return {
            "h1_length": len(self.h1),
            "title_tag_length": len(self.title_tag),
            "meta_description_length": len(self.meta_description),
            "top_description_length": len(self.top_description),
            "bottom_description_length": len(self.bottom_description),
            "project_id": self.project_id,
            "page_id": self.page_id,
            "content_id": self.content_id,
        }


@dataclass
class ContentQualityResult:
    """Result of Phase 5C content quality check."""

    success: bool
    content_id: str | None = None
    trope_detection: TropeDetectionResult | None = None
    passed_qa: bool = False
    error: str | None = None
    duration_ms: float = 0.0
    project_id: str | None = None
    page_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "content_id": self.content_id,
            "trope_detection": self.trope_detection.to_dict() if self.trope_detection else None,
            "passed_qa": self.passed_qa,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
            "project_id": self.project_id,
            "page_id": self.page_id,
        }


# =============================================================================
# EXCEPTIONS
# =============================================================================


class ContentQualityServiceError(Exception):
    """Base exception for content quality service errors."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.page_id = page_id


class ContentQualityValidationError(ContentQualityServiceError):
    """Raised when validation fails."""

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


class ContentQualityService:
    """Service for Phase 5C AI trope detection and quality scoring.

    Analyzes generated content for AI-sounding patterns that would
    immediately flag the content as machine-generated:
    - Banned words (delve, unlock, journey, etc.)
    - Banned phrases ("In today's fast-paced world", etc.)
    - Em dashes (should be split into sentences)
    - Triplet patterns ("Fast. Simple. Powerful.")
    - Negation patterns ("aren't just X, they're Y")
    - Rhetorical questions as openers
    - Overuse of limited-use words (max 1 per page)

    Usage:
        service = ContentQualityService()
        result = await service.check_content_quality(
            input_data=ContentQualityInput(
                h1="Premium Leather Wallets",
                title_tag="Premium Leather Wallets | Brand",
                meta_description="...",
                top_description="...",
                bottom_description="...",
            ),
        )
    """

    def __init__(self) -> None:
        """Initialize content quality service."""
        # Pre-compile regex patterns for performance
        self._em_dash_pattern = re.compile(r"—")

        # Triplet pattern: "Word. Word. Word." (3+ consecutive short sentences)
        self._triplet_pattern = re.compile(
            r"(?<![a-zA-Z])([A-Z][a-z]+)\.\s+([A-Z][a-z]+)\.\s+([A-Z][a-z]+)\.",
        )

        # Negation pattern: "aren't just X, they're Y" or "more than just X"
        self._negation_patterns = [
            re.compile(r"(?:aren't|isn't|wasn't|weren't)\s+just\s+\w+[^.]*,\s+(?:they're|it's|he's|she's)", re.IGNORECASE),
            re.compile(r"more\s+than\s+just\s+(?:a\s+)?\w+", re.IGNORECASE),
            re.compile(r"not\s+(?:just|only)\s+(?:a\s+)?\w+[^.]*,\s+(?:but|it's|they're)", re.IGNORECASE),
        ]

        # Rhetorical question at start of text or paragraph
        self._rhetorical_question_pattern = re.compile(
            r"(?:^|<p>|<h[1-6]>)\s*(?:Are you|Do you|Have you|Want to|Looking for|Wondering|Ready to|Need to|Tired of)[^?]*\?",
            re.IGNORECASE,
        )

        # Word boundary pattern for exact word matching
        self._word_boundary = re.compile(r"\b\w+\b")

        logger.debug("ContentQualityService initialized")

    def _strip_html_tags(self, text: str) -> str:
        """Remove HTML tags from text for analysis.

        Args:
            text: Text with potential HTML tags

        Returns:
            Clean text without HTML tags
        """
        return re.sub(r"<[^>]+>", " ", text)

    def _detect_banned_words(
        self,
        text: str,
        project_id: str | None,
        page_id: str | None,
    ) -> list[WordMatch]:
        """Find all banned words with positions.

        Args:
            text: Text to analyze
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            List of WordMatch with word, count, and positions
        """
        clean_text = self._strip_html_tags(text).lower()
        found: dict[str, WordMatch] = {}

        for match in self._word_boundary.finditer(clean_text):
            word = match.group().lower()
            # Handle hyphenated versions
            normalized_word = word.replace("-", "")

            if word in BANNED_WORDS or normalized_word in BANNED_WORDS:
                if word not in found:
                    found[word] = WordMatch(word=word, count=0, positions=[])
                found[word].count += 1
                found[word].positions.append(match.start())

        if found:
            logger.debug(
                "Banned words detected",
                extra={
                    "word_count": len(found),
                    "total_occurrences": sum(w.count for w in found.values()),
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

        return list(found.values())

    def _detect_banned_phrases(
        self,
        text: str,
        project_id: str | None,
        page_id: str | None,
    ) -> list[PhraseMatch]:
        """Find all banned phrases with positions.

        Args:
            text: Text to analyze
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            List of PhraseMatch with phrase, count, and positions
        """
        clean_text = self._strip_html_tags(text).lower()
        found: list[PhraseMatch] = []

        for phrase in BANNED_PHRASES:
            phrase_lower = phrase.lower()
            count = 0
            positions: list[int] = []
            start = 0

            while True:
                idx = clean_text.find(phrase_lower, start)
                if idx == -1:
                    break
                count += 1
                positions.append(idx)
                start = idx + len(phrase_lower)

            if count > 0:
                found.append(PhraseMatch(
                    phrase=phrase,
                    count=count,
                    positions=positions,
                ))

        if found:
            logger.debug(
                "Banned phrases detected",
                extra={
                    "phrase_count": len(found),
                    "total_occurrences": sum(p.count for p in found),
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

        return found

    def _detect_em_dashes(
        self,
        text: str,
        project_id: str | None,
        page_id: str | None,
    ) -> int:
        """Count em dash occurrences.

        Em dashes (—) are a strong AI indicator and should be replaced
        with sentence breaks or commas.

        Args:
            text: Text to analyze
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            Count of em dashes found
        """
        count = len(self._em_dash_pattern.findall(text))

        if count > 0:
            logger.debug(
                "Em dashes detected",
                extra={
                    "count": count,
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

        return count

    def _detect_triplet_patterns(
        self,
        text: str,
        project_id: str | None,
        page_id: str | None,
    ) -> list[PatternMatch]:
        """Find "X. Y. Z." triplet patterns.

        Three consecutive short single-word sentences are a common
        AI writing pattern: "Fast. Simple. Powerful."

        Args:
            text: Text to analyze
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            List of PatternMatch for each triplet found
        """
        clean_text = self._strip_html_tags(text)
        found: list[PatternMatch] = []

        for match in self._triplet_pattern.finditer(clean_text):
            found.append(PatternMatch(
                pattern_type="triplet",
                matched_text=match.group(),
                position=match.start(),
            ))

        if found:
            logger.debug(
                "Triplet patterns detected",
                extra={
                    "count": len(found),
                    "patterns": [p.matched_text for p in found],
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

        return found

    def _detect_negation_patterns(
        self,
        text: str,
        project_id: str | None,
        page_id: str | None,
    ) -> list[PatternMatch]:
        """Find negation patterns like "aren't just X, they're Y".

        These patterns are very common in AI-generated marketing copy.

        Args:
            text: Text to analyze
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            List of PatternMatch for each negation pattern found
        """
        clean_text = self._strip_html_tags(text)
        found: list[PatternMatch] = []

        for pattern in self._negation_patterns:
            for match in pattern.finditer(clean_text):
                found.append(PatternMatch(
                    pattern_type="negation",
                    matched_text=match.group(),
                    position=match.start(),
                ))

        if found:
            logger.debug(
                "Negation patterns detected",
                extra={
                    "count": len(found),
                    "patterns": [p.matched_text for p in found],
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

        return found

    def _detect_rhetorical_questions(
        self,
        text: str,
        project_id: str | None,
        page_id: str | None,
    ) -> int:
        """Count rhetorical questions used as openers.

        Starting paragraphs or sections with questions like
        "Are you looking for..." is a common AI pattern.

        Args:
            text: Text to analyze
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            Count of rhetorical question openers
        """
        count = len(self._rhetorical_question_pattern.findall(text))

        if count > 0:
            logger.debug(
                "Rhetorical questions detected",
                extra={
                    "count": count,
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

        return count

    def _detect_limited_use_words(
        self,
        text: str,
        project_id: str | None,
        page_id: str | None,
    ) -> dict[str, int]:
        """Count limited-use words (max 1 per page).

        These words aren't banned but should be used sparingly.
        More than one occurrence per page is suspicious.

        Args:
            text: Text to analyze
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            Dict mapping word to occurrence count
        """
        clean_text = self._strip_html_tags(text).lower()
        word_counts: dict[str, int] = {}

        for match in self._word_boundary.finditer(clean_text):
            word = match.group().lower()
            if word in LIMITED_USE_WORDS:
                word_counts[word] = word_counts.get(word, 0) + 1

        if word_counts:
            excess_words = {w: c for w, c in word_counts.items() if c > MAX_LIMITED_USE_WORDS_PER_PAGE}
            if excess_words:
                logger.debug(
                    "Limited-use words exceeded threshold",
                    extra={
                        "excess_words": excess_words,
                        "threshold": MAX_LIMITED_USE_WORDS_PER_PAGE,
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )

        return word_counts

    def _calculate_quality_score(
        self,
        detection: TropeDetectionResult,
    ) -> float:
        """Calculate overall quality score from detections.

        Starts at 100 and deducts points for each issue found.
        Score cannot go below 0.

        Args:
            detection: Trope detection results

        Returns:
            Quality score from 0-100
        """
        score = 100.0

        # Deduct for banned words
        for word_match in detection.found_banned_words:
            score += SCORING_WEIGHTS["banned_word"] * word_match.count

        # Deduct for banned phrases
        for phrase_match in detection.found_banned_phrases:
            score += SCORING_WEIGHTS["banned_phrase"] * phrase_match.count

        # Deduct for em dashes
        score += SCORING_WEIGHTS["em_dash"] * detection.found_em_dashes

        # Deduct for triplet patterns
        score += SCORING_WEIGHTS["triplet_pattern"] * len(detection.found_triplet_patterns)

        # Deduct for negation patterns
        score += SCORING_WEIGHTS["negation_pattern"] * len(detection.found_negation_patterns)

        # Deduct for rhetorical questions
        score += SCORING_WEIGHTS["rhetorical_question"] * detection.found_rhetorical_questions

        # Deduct for excess limited-use words
        for _word, count in detection.limited_use_words.items():
            excess = count - MAX_LIMITED_USE_WORDS_PER_PAGE
            if excess > 0:
                score += SCORING_WEIGHTS["limited_use_excess"] * excess

        return max(0.0, score)

    def _generate_suggestions(
        self,
        detection: TropeDetectionResult,
    ) -> list[str]:
        """Generate actionable suggestions for improvement.

        Args:
            detection: Trope detection results

        Returns:
            List of improvement suggestions
        """
        suggestions: list[str] = []

        # Banned words
        if detection.found_banned_words:
            words = [w.word for w in detection.found_banned_words]
            suggestions.append(
                f"Remove banned words: {', '.join(words)}. These immediately flag content as AI-generated."
            )

        # Banned phrases
        if detection.found_banned_phrases:
            phrases = [p.phrase for p in detection.found_banned_phrases]
            suggestions.append(
                f"Remove banned phrases: {', '.join(phrases)}. Use more specific, conversational language."
            )

        # Em dashes
        if detection.found_em_dashes > 0:
            suggestions.append(
                f"Replace {detection.found_em_dashes} em dash(es) with periods or commas. "
                "Em dashes are strong AI indicators."
            )

        # Triplet patterns
        if detection.found_triplet_patterns:
            suggestions.append(
                "Rewrite triplet patterns (X. Y. Z.) as complete sentences. "
                f"Found: {', '.join(p.matched_text for p in detection.found_triplet_patterns)}"
            )

        # Negation patterns
        if detection.found_negation_patterns:
            suggestions.append(
                "Rephrase negation patterns. Instead of 'aren't just X, they're Y', "
                "state benefits directly."
            )

        # Rhetorical questions
        if detection.found_rhetorical_questions > 0:
            suggestions.append(
                f"Remove {detection.found_rhetorical_questions} rhetorical question opener(s). "
                "Start with statements, not questions."
            )

        # Limited-use words
        excess_words = [
            w for w, c in detection.limited_use_words.items()
            if c > MAX_LIMITED_USE_WORDS_PER_PAGE
        ]
        if excess_words:
            suggestions.append(
                f"Reduce usage of: {', '.join(excess_words)}. "
                f"Max {MAX_LIMITED_USE_WORDS_PER_PAGE} occurrence(s) per page."
            )

        return suggestions

    async def check_content_quality(
        self,
        input_data: ContentQualityInput,
    ) -> ContentQualityResult:
        """Run all quality checks on generated content.

        Phase 5C content quality check:
        1. Detect banned words
        2. Detect banned phrases
        3. Detect em dashes
        4. Detect triplet patterns
        5. Detect negation patterns
        6. Detect rhetorical questions
        7. Count limited-use words
        8. Calculate quality score
        9. Generate improvement suggestions

        Args:
            input_data: Content to analyze

        Returns:
            ContentQualityResult with detection results and score
        """
        start_time = time.monotonic()
        project_id = input_data.project_id
        page_id = input_data.page_id
        content_id = input_data.content_id

        logger.debug(
            "Phase 5C content quality check starting",
            extra={
                "content_id": content_id,
                "h1_length": len(input_data.h1),
                "bottom_description_length": len(input_data.bottom_description),
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        # Validate inputs
        if not input_data.bottom_description or not input_data.bottom_description.strip():
            logger.warning(
                "Content quality validation failed - empty bottom_description",
                extra={
                    "field": "bottom_description",
                    "value": "",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            raise ContentQualityValidationError(
                "bottom_description",
                "",
                "Bottom description cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        try:
            # Log phase transition
            logger.info(
                "Phase 5C: Content quality check - in_progress",
                extra={
                    "content_id": content_id,
                    "phase": "5C",
                    "status": "in_progress",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            # Get all text for analysis
            all_text = input_data.get_all_text()

            # Run all detections
            detection = TropeDetectionResult(
                found_banned_words=self._detect_banned_words(all_text, project_id, page_id),
                found_banned_phrases=self._detect_banned_phrases(all_text, project_id, page_id),
                found_em_dashes=self._detect_em_dashes(all_text, project_id, page_id),
                found_triplet_patterns=self._detect_triplet_patterns(all_text, project_id, page_id),
                found_negation_patterns=self._detect_negation_patterns(all_text, project_id, page_id),
                found_rhetorical_questions=self._detect_rhetorical_questions(all_text, project_id, page_id),
                limited_use_words=self._detect_limited_use_words(all_text, project_id, page_id),
            )

            # Calculate score
            detection.overall_score = self._calculate_quality_score(detection)

            # Generate suggestions
            detection.suggestions = self._generate_suggestions(detection)

            # Determine if approved
            detection.is_approved = detection.overall_score >= QUALITY_SCORE_PASS_THRESHOLD

            duration_ms = (time.monotonic() - start_time) * 1000

            # Count total issues
            total_issues = (
                sum(w.count for w in detection.found_banned_words)
                + sum(p.count for p in detection.found_banned_phrases)
                + detection.found_em_dashes
                + len(detection.found_triplet_patterns)
                + len(detection.found_negation_patterns)
                + detection.found_rhetorical_questions
            )

            # Log completion
            logger.info(
                "Phase 5C: Content quality check - completed",
                extra={
                    "content_id": content_id,
                    "total_issues": total_issues,
                    "quality_score": round(detection.overall_score, 2),
                    "passed_qa": detection.is_approved,
                    "phase": "5C",
                    "status": "completed",
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow Phase 5C content quality check operation",
                    extra={
                        "content_id": content_id,
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )

            return ContentQualityResult(
                success=True,
                content_id=content_id,
                trope_detection=detection,
                passed_qa=detection.is_approved,
                duration_ms=duration_ms,
                project_id=project_id,
                page_id=page_id,
            )

        except ContentQualityValidationError:
            raise
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Phase 5C content quality check unexpected error",
                extra={
                    "content_id": content_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "page_id": page_id,
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return ContentQualityResult(
                success=False,
                content_id=content_id,
                error=f"Unexpected error: {e}",
                duration_ms=duration_ms,
                project_id=project_id,
                page_id=page_id,
            )

    async def check_content_quality_batch(
        self,
        inputs: list[ContentQualityInput],
        project_id: str | None = None,
    ) -> list[ContentQualityResult]:
        """Check quality for multiple content items.

        Note: This runs synchronously since QA checks are fast (no I/O).
        Parallelization overhead would exceed the benefit.

        Args:
            inputs: List of content items to check
            project_id: Project ID for logging

        Returns:
            List of ContentQualityResult, one per input
        """
        start_time = time.monotonic()

        logger.info(
            "Batch content quality check started",
            extra={
                "input_count": len(inputs),
                "project_id": project_id,
            },
        )

        if not inputs:
            return []

        results: list[ContentQualityResult] = []
        for input_data in inputs:
            result = await self.check_content_quality(input_data)
            results.append(result)

        duration_ms = (time.monotonic() - start_time) * 1000
        success_count = sum(1 for r in results if r.success)
        passed_qa_count = sum(1 for r in results if r.passed_qa)

        logger.info(
            "Batch content quality check complete",
            extra={
                "input_count": len(inputs),
                "success_count": success_count,
                "failure_count": len(inputs) - success_count,
                "passed_qa_count": passed_qa_count,
                "failed_qa_count": len(inputs) - passed_qa_count,
                "duration_ms": round(duration_ms, 2),
                "project_id": project_id,
            },
        )

        if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
            logger.warning(
                "Slow batch content quality check operation",
                extra={
                    "input_count": len(inputs),
                    "duration_ms": round(duration_ms, 2),
                    "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    "project_id": project_id,
                },
            )

        return results


# =============================================================================
# SINGLETON
# =============================================================================


_content_quality_service: ContentQualityService | None = None


def get_content_quality_service() -> ContentQualityService:
    """Get the global content quality service instance.

    Usage:
        from app.services.content_quality import get_content_quality_service
        service = get_content_quality_service()
        result = await service.check_content_quality(input_data)
    """
    global _content_quality_service
    if _content_quality_service is None:
        _content_quality_service = ContentQualityService()
        logger.info("ContentQualityService singleton created")
    return _content_quality_service


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


async def check_content_quality(
    h1: str,
    title_tag: str,
    meta_description: str,
    top_description: str,
    bottom_description: str,
    project_id: str | None = None,
    page_id: str | None = None,
    content_id: str | None = None,
) -> ContentQualityResult:
    """Convenience function for Phase 5C content quality check.

    Args:
        h1: Page H1 heading
        title_tag: Page title tag
        meta_description: Page meta description
        top_description: Above-the-fold description
        bottom_description: Full bottom description
        project_id: Project ID for logging
        page_id: Page ID for logging
        content_id: Content ID for tracking

    Returns:
        ContentQualityResult with detection results
    """
    service = get_content_quality_service()
    input_data = ContentQualityInput(
        h1=h1,
        title_tag=title_tag,
        meta_description=meta_description,
        top_description=top_description,
        bottom_description=bottom_description,
        project_id=project_id,
        page_id=page_id,
        content_id=content_id,
    )
    return await service.check_content_quality(input_data)
