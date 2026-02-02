"""Content Scoring Service for comprehensive content quality analysis.

Implements a multi-factor content scoring algorithm that evaluates:
- Word count metrics (length, sentence count, paragraph count)
- Semantic relevance (TF-IDF based term importance)
- Readability scores (Flesch-Kincaid, average sentence length)
- Keyword density (target keyword frequency analysis)
- Entity coverage (named entity extraction and coverage)

Features:
- Pure Python implementation (no external ML dependencies)
- Configurable scoring weights
- Comprehensive error logging per requirements
- Component-level and aggregate scoring

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
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Threshold for logging slow operations (in milliseconds)
SLOW_OPERATION_THRESHOLD_MS = 1000

# Scoring configuration defaults
DEFAULT_TARGET_WORD_COUNT_MIN = 300
DEFAULT_TARGET_WORD_COUNT_MAX = 2000
DEFAULT_TARGET_KEYWORD_DENSITY_MIN = 0.5  # 0.5%
DEFAULT_TARGET_KEYWORD_DENSITY_MAX = 2.5  # 2.5%
DEFAULT_TARGET_READABILITY_MIN = 30.0  # Flesch reading ease
DEFAULT_TARGET_READABILITY_MAX = 70.0  # Flesch reading ease

# Scoring weights (sum to 1.0)
DEFAULT_SCORING_WEIGHTS = {
    "word_count": 0.15,
    "semantic": 0.25,
    "readability": 0.20,
    "keyword_density": 0.25,
    "entity_coverage": 0.15,
}

# Standard English stop words for semantic analysis
STOP_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "about",
        "above",
        "after",
        "again",
        "against",
        "all",
        "am",
        "an",
        "and",
        "any",
        "are",
        "aren't",
        "as",
        "at",
        "be",
        "because",
        "been",
        "before",
        "being",
        "below",
        "between",
        "both",
        "but",
        "by",
        "can",
        "can't",
        "cannot",
        "could",
        "couldn't",
        "did",
        "didn't",
        "do",
        "does",
        "doesn't",
        "doing",
        "don't",
        "down",
        "during",
        "each",
        "few",
        "for",
        "from",
        "further",
        "had",
        "hadn't",
        "has",
        "hasn't",
        "have",
        "haven't",
        "having",
        "he",
        "he'd",
        "he'll",
        "he's",
        "her",
        "here",
        "here's",
        "hers",
        "herself",
        "him",
        "himself",
        "his",
        "how",
        "how's",
        "i",
        "i'd",
        "i'll",
        "i'm",
        "i've",
        "if",
        "in",
        "into",
        "is",
        "isn't",
        "it",
        "it's",
        "its",
        "itself",
        "let's",
        "me",
        "more",
        "most",
        "mustn't",
        "my",
        "myself",
        "no",
        "nor",
        "not",
        "of",
        "off",
        "on",
        "once",
        "only",
        "or",
        "other",
        "ought",
        "our",
        "ours",
        "ourselves",
        "out",
        "over",
        "own",
        "same",
        "shan't",
        "she",
        "she'd",
        "she'll",
        "she's",
        "should",
        "shouldn't",
        "so",
        "some",
        "such",
        "than",
        "that",
        "that's",
        "the",
        "their",
        "theirs",
        "them",
        "themselves",
        "then",
        "there",
        "there's",
        "these",
        "they",
        "they'd",
        "they'll",
        "they're",
        "they've",
        "this",
        "those",
        "through",
        "to",
        "too",
        "under",
        "until",
        "up",
        "very",
        "was",
        "wasn't",
        "we",
        "we'd",
        "we'll",
        "we're",
        "we've",
        "were",
        "weren't",
        "what",
        "what's",
        "when",
        "when's",
        "where",
        "where's",
        "which",
        "while",
        "who",
        "who's",
        "whom",
        "why",
        "why's",
        "with",
        "won't",
        "would",
        "wouldn't",
        "you",
        "you'd",
        "you'll",
        "you're",
        "you've",
        "your",
        "yours",
        "yourself",
        "yourselves",
        # Additional common words
        "also",
        "just",
        "like",
        "get",
        "got",
        "will",
        "one",
        "two",
        "three",
        "may",
        "might",
        "shall",
        "need",
        "use",
        "used",
        "using",
        "make",
        "made",
        "makes",
        "making",
        "way",
        "ways",
        "well",
        "good",
        "new",
        "know",
        "see",
        "time",
        "take",
        "come",
        "back",
        "now",
        "even",
        "want",
        "first",
        "still",
        "many",
        "much",
        "right",
        "think",
        "say",
        "said",
        "says",
        "look",
        "going",
        "day",
        "thing",
        "things",
    }
)

# Common named entity patterns (simplified for pure Python implementation)
ENTITY_PATTERNS = {
    "product": re.compile(
        r"\b(?:product|item|model|version|edition|series)\b",
        re.IGNORECASE,
    ),
    "brand": re.compile(
        r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b",
    ),
    "number": re.compile(
        r"\b\d+(?:\.\d+)?(?:\s*(?:percent|%|inches|in|cm|mm|ft|lbs?|kg|oz|ml|l|grams?|g))?\b",
        re.IGNORECASE,
    ),
    "money": re.compile(
        r"\$\d+(?:,\d{3})*(?:\.\d{2})?|\b\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:dollars?|USD|EUR|GBP)\b",
        re.IGNORECASE,
    ),
    "date": re.compile(
        r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
        r"Dec(?:ember)?)\s+\d{1,2}(?:,?\s+\d{4})?\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b",
        re.IGNORECASE,
    ),
    "location": re.compile(
        r"\b(?:USA|US|UK|Canada|Australia|Germany|France|Japan|China|"
        r"New\s+York|Los\s+Angeles|Chicago|London|Paris|Tokyo|Berlin)\b",
        re.IGNORECASE,
    ),
}


class ContentScoreServiceError(Exception):
    """Base exception for ContentScoreService errors."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        self.project_id = project_id
        self.page_id = page_id
        super().__init__(message)


class ContentScoreValidationError(ContentScoreServiceError):
    """Raised when input validation fails."""

    def __init__(
        self,
        field_name: str,
        value: Any,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        self.field_name = field_name
        self.value = value
        super().__init__(
            f"Validation failed for '{field_name}': {message}",
            project_id=project_id,
            page_id=page_id,
        )


@dataclass
class WordCountScore:
    """Word count scoring component.

    Attributes:
        word_count: Total number of words
        sentence_count: Total number of sentences
        paragraph_count: Total number of paragraphs
        avg_words_per_sentence: Average words per sentence
        score: Normalized score (0.0 to 1.0)
    """

    word_count: int = 0
    sentence_count: int = 0
    paragraph_count: int = 0
    avg_words_per_sentence: float = 0.0
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "paragraph_count": self.paragraph_count,
            "avg_words_per_sentence": round(self.avg_words_per_sentence, 2),
            "score": round(self.score, 4),
        }


@dataclass
class SemanticScore:
    """Semantic relevance scoring component.

    Attributes:
        top_terms: List of most important terms with scores
        term_diversity: Ratio of unique terms to total words
        content_depth: Measure of topic coverage depth
        score: Normalized score (0.0 to 1.0)
    """

    top_terms: list[tuple[str, float]] = field(default_factory=list)
    term_diversity: float = 0.0
    content_depth: float = 0.0
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "top_terms": [
                {"term": term, "score": round(score, 4)}
                for term, score in self.top_terms[:10]
            ],
            "term_diversity": round(self.term_diversity, 4),
            "content_depth": round(self.content_depth, 4),
            "score": round(self.score, 4),
        }


@dataclass
class ReadabilityScore:
    """Readability scoring component.

    Attributes:
        flesch_reading_ease: Flesch Reading Ease score (0-100)
        flesch_kincaid_grade: Flesch-Kincaid Grade Level
        avg_syllables_per_word: Average syllables per word
        score: Normalized score (0.0 to 1.0)
    """

    flesch_reading_ease: float = 0.0
    flesch_kincaid_grade: float = 0.0
    avg_syllables_per_word: float = 0.0
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "flesch_reading_ease": round(self.flesch_reading_ease, 2),
            "flesch_kincaid_grade": round(self.flesch_kincaid_grade, 2),
            "avg_syllables_per_word": round(self.avg_syllables_per_word, 2),
            "score": round(self.score, 4),
        }


@dataclass
class KeywordDensityScore:
    """Keyword density scoring component.

    Attributes:
        primary_keyword: The target primary keyword
        primary_density: Density of primary keyword (percentage)
        secondary_keywords: List of secondary keywords with densities
        total_keyword_occurrences: Total keyword mentions
        score: Normalized score (0.0 to 1.0)
    """

    primary_keyword: str = ""
    primary_density: float = 0.0
    secondary_keywords: list[tuple[str, float]] = field(default_factory=list)
    total_keyword_occurrences: int = 0
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "primary_keyword": self.primary_keyword,
            "primary_density": round(self.primary_density, 4),
            "secondary_keywords": [
                {"keyword": kw, "density": round(density, 4)}
                for kw, density in self.secondary_keywords
            ],
            "total_keyword_occurrences": self.total_keyword_occurrences,
            "score": round(self.score, 4),
        }


@dataclass
class EntityCoverageScore:
    """Entity coverage scoring component.

    Attributes:
        entities: Dictionary of entity types to found entities
        entity_count: Total number of entities found
        entity_types_covered: Number of distinct entity types
        coverage_ratio: Ratio of entity types found to total possible
        score: Normalized score (0.0 to 1.0)
    """

    entities: dict[str, list[str]] = field(default_factory=dict)
    entity_count: int = 0
    entity_types_covered: int = 0
    coverage_ratio: float = 0.0
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "entities": {
                etype: list(set(entities))[:5]  # Dedupe and limit
                for etype, entities in self.entities.items()
            },
            "entity_count": self.entity_count,
            "entity_types_covered": self.entity_types_covered,
            "coverage_ratio": round(self.coverage_ratio, 4),
            "score": round(self.score, 4),
        }


@dataclass
class ContentScoreInput:
    """Input data for content scoring.

    Attributes:
        content: The main content text to analyze
        primary_keyword: Target primary keyword
        secondary_keywords: List of secondary keywords to check
        target_word_count_min: Minimum target word count
        target_word_count_max: Maximum target word count
        project_id: Project ID for logging
        page_id: Page ID for logging
    """

    content: str
    primary_keyword: str = ""
    secondary_keywords: list[str] = field(default_factory=list)
    target_word_count_min: int = DEFAULT_TARGET_WORD_COUNT_MIN
    target_word_count_max: int = DEFAULT_TARGET_WORD_COUNT_MAX
    project_id: str | None = None
    page_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging (sanitized)."""
        return {
            "content_length": len(self.content),
            "primary_keyword": self.primary_keyword,
            "secondary_keyword_count": len(self.secondary_keywords),
            "target_word_count_min": self.target_word_count_min,
            "target_word_count_max": self.target_word_count_max,
            "project_id": self.project_id,
            "page_id": self.page_id,
        }


@dataclass
class ContentScoreResult:
    """Result of content scoring analysis.

    Attributes:
        success: Whether analysis succeeded
        overall_score: Weighted aggregate score (0.0 to 1.0)
        word_count_score: Word count component score
        semantic_score: Semantic relevance component score
        readability_score: Readability component score
        keyword_density_score: Keyword density component score
        entity_coverage_score: Entity coverage component score
        passed: Whether content meets quality threshold
        error: Error message if failed
        duration_ms: Total time taken in milliseconds
        project_id: Project ID for logging
        page_id: Page ID for logging
    """

    success: bool
    overall_score: float = 0.0
    word_count_score: WordCountScore | None = None
    semantic_score: SemanticScore | None = None
    readability_score: ReadabilityScore | None = None
    keyword_density_score: KeywordDensityScore | None = None
    entity_coverage_score: EntityCoverageScore | None = None
    passed: bool = False
    error: str | None = None
    duration_ms: float = 0.0
    project_id: str | None = None
    page_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "overall_score": round(self.overall_score, 4),
            "word_count_score": (
                self.word_count_score.to_dict() if self.word_count_score else None
            ),
            "semantic_score": (
                self.semantic_score.to_dict() if self.semantic_score else None
            ),
            "readability_score": (
                self.readability_score.to_dict() if self.readability_score else None
            ),
            "keyword_density_score": (
                self.keyword_density_score.to_dict()
                if self.keyword_density_score
                else None
            ),
            "entity_coverage_score": (
                self.entity_coverage_score.to_dict()
                if self.entity_coverage_score
                else None
            ),
            "passed": self.passed,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
        }


class ContentScoreService:
    """Service for comprehensive content quality scoring.

    .. deprecated::
        This service is deprecated in favor of :class:`POPContentScoreService`
        which provides SERP-based scoring via the PageOptimizer Pro API.
        This service is retained as a fallback when POP is unavailable.

        Migration path:
        1. Enable shadow mode: ``POP_SHADOW_MODE=true``
        2. Validate scoring accuracy via shadow comparison metrics
        3. Enable POP scoring: ``USE_POP_SCORING=true``
        4. Monitor fallback rate

        See ``backend/docs/POP_INTEGRATION.md`` for full migration details.

    Analyzes content across multiple dimensions:
    - Word count and structure
    - Semantic relevance and depth
    - Readability and accessibility
    - Keyword density and optimization
    - Named entity coverage

    Example usage:
        service = ContentScoreService()
        result = await service.score_content(
            input_data=ContentScoreInput(
                content="Your content here...",
                primary_keyword="target keyword",
                secondary_keywords=["related", "terms"],
            ),
        )
        print(f"Overall score: {result.overall_score}")
    """

    # Regex patterns for text analysis
    _word_pattern = re.compile(r"\b[a-zA-Z][a-zA-Z0-9]*(?:'[a-zA-Z]+)?\b")
    _sentence_pattern = re.compile(r"[.!?]+(?:\s|$)")
    _paragraph_pattern = re.compile(r"\n\s*\n")
    _syllable_pattern = re.compile(r"[aeiouy]+", re.IGNORECASE)

    def __init__(
        self,
        scoring_weights: dict[str, float] | None = None,
        pass_threshold: float = 0.6,
    ) -> None:
        """Initialize content score service.

        Args:
            scoring_weights: Custom weights for scoring components
            pass_threshold: Minimum score to pass (default 0.6)
        """
        self.scoring_weights = scoring_weights or DEFAULT_SCORING_WEIGHTS.copy()
        self.pass_threshold = pass_threshold

        # Validate weights sum to 1.0
        weight_sum = sum(self.scoring_weights.values())
        if not 0.99 <= weight_sum <= 1.01:
            logger.warning(
                "Scoring weights do not sum to 1.0, normalizing",
                extra={"weight_sum": weight_sum},
            )
            for key in self.scoring_weights:
                self.scoring_weights[key] /= weight_sum

        logger.debug(
            "ContentScoreService initialized",
            extra={
                "scoring_weights": self.scoring_weights,
                "pass_threshold": self.pass_threshold,
            },
        )

    def _strip_html_tags(self, text: str) -> str:
        """Remove HTML tags from text for analysis."""
        return re.sub(r"<[^>]+>", " ", text)

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into lowercase words."""
        if not text:
            return []
        tokens = self._word_pattern.findall(text.lower())
        return [t for t in tokens if len(t) > 2]

    def _count_syllables(self, word: str) -> int:
        """Count syllables in a word (approximate)."""
        word = word.lower()
        if len(word) <= 3:
            return 1

        # Count vowel groups
        syllables = len(self._syllable_pattern.findall(word))

        # Adjust for silent e
        if word.endswith("e"):
            syllables = max(1, syllables - 1)

        # Adjust for common patterns
        if word.endswith("le") and len(word) > 2 and word[-3] not in "aeiou":
            syllables += 1

        return max(1, syllables)

    def _compute_word_count_score(
        self,
        text: str,
        target_min: int,
        target_max: int,
        project_id: str | None,
        page_id: str | None,
    ) -> WordCountScore:
        """Compute word count metrics and score.

        Args:
            text: Content text to analyze
            target_min: Minimum target word count
            target_max: Maximum target word count
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            WordCountScore with metrics and normalized score
        """
        clean_text = self._strip_html_tags(text)

        # Count words
        words = self._tokenize(clean_text)
        word_count = len(words)

        # Count sentences
        sentences = self._sentence_pattern.split(clean_text)
        sentence_count = len([s for s in sentences if s.strip()])
        sentence_count = max(1, sentence_count)

        # Count paragraphs
        paragraphs = self._paragraph_pattern.split(clean_text)
        paragraph_count = len([p for p in paragraphs if p.strip()])
        paragraph_count = max(1, paragraph_count)

        # Average words per sentence
        avg_words_per_sentence = (
            word_count / sentence_count if sentence_count > 0 else 0
        )

        # Calculate score based on target range
        if word_count < target_min:
            # Below minimum - penalize proportionally
            score = word_count / target_min
        elif word_count > target_max:
            # Above maximum - slight penalty
            excess = word_count - target_max
            penalty = min(0.3, excess / target_max)
            score = 1.0 - penalty
        else:
            # Within range - full score
            score = 1.0

        # Bonus for good sentence length (15-25 words avg)
        if 15 <= avg_words_per_sentence <= 25:
            score = min(1.0, score + 0.1)
        elif avg_words_per_sentence > 35:
            score = max(0.0, score - 0.1)

        logger.debug(
            "Word count score computed",
            extra={
                "word_count": word_count,
                "sentence_count": sentence_count,
                "paragraph_count": paragraph_count,
                "avg_words_per_sentence": round(avg_words_per_sentence, 2),
                "score": round(score, 4),
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        return WordCountScore(
            word_count=word_count,
            sentence_count=sentence_count,
            paragraph_count=paragraph_count,
            avg_words_per_sentence=avg_words_per_sentence,
            score=max(0.0, min(1.0, score)),
        )

    def _compute_semantic_score(
        self,
        text: str,
        project_id: str | None,
        page_id: str | None,
    ) -> SemanticScore:
        """Compute semantic relevance using TF-IDF-like analysis.

        Args:
            text: Content text to analyze
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            SemanticScore with term analysis and normalized score
        """
        clean_text = self._strip_html_tags(text)
        words = self._tokenize(clean_text)

        if not words:
            return SemanticScore(score=0.0)

        # Filter stop words
        content_words = [w for w in words if w not in STOP_WORDS]

        if not content_words:
            return SemanticScore(score=0.2)  # Minimal score for stop-word-only content

        # Calculate term frequency
        word_counts = Counter(content_words)
        total_words = len(content_words)

        # Calculate term scores (TF with position weighting)
        term_scores: dict[str, float] = {}
        for word, count in word_counts.items():
            # Basic TF
            tf = count / total_words
            # Add bigram bonus if word appears with consistent neighbors
            # Simplified: just use TF normalized
            term_scores[word] = tf

        # Sort by score
        sorted_terms = sorted(term_scores.items(), key=lambda x: -x[1])
        top_terms = sorted_terms[:20]

        # Calculate term diversity (unique words / total words)
        term_diversity = len(word_counts) / len(words) if words else 0

        # Calculate content depth (based on vocabulary richness)
        # More unique terms = deeper content
        unique_ratio = len(word_counts) / max(1, len(words))
        if unique_ratio > 0.6:
            content_depth = 1.0
        elif unique_ratio > 0.4:
            content_depth = 0.8
        elif unique_ratio > 0.2:
            content_depth = 0.6
        else:
            content_depth = 0.4

        # Calculate overall semantic score
        # Good semantic content has diverse vocabulary and clear topic focus
        score = (term_diversity * 0.4) + (content_depth * 0.4)

        # Bonus for having strong topic terms (high frequency terms)
        if top_terms and top_terms[0][1] > 0.02:  # Top term appears 2%+ of content
            score += 0.2

        score = min(1.0, score)

        logger.debug(
            "Semantic score computed",
            extra={
                "unique_terms": len(word_counts),
                "total_content_words": total_words,
                "term_diversity": round(term_diversity, 4),
                "content_depth": round(content_depth, 4),
                "score": round(score, 4),
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        return SemanticScore(
            top_terms=top_terms,
            term_diversity=term_diversity,
            content_depth=content_depth,
            score=score,
        )

    def _compute_readability_score(
        self,
        text: str,
        project_id: str | None,
        page_id: str | None,
    ) -> ReadabilityScore:
        """Compute Flesch-Kincaid readability scores.

        Flesch Reading Ease formula:
        206.835 - 1.015 × (words/sentences) - 84.6 × (syllables/words)

        Flesch-Kincaid Grade Level formula:
        0.39 × (words/sentences) + 11.8 × (syllables/words) - 15.59

        Args:
            text: Content text to analyze
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            ReadabilityScore with Flesch scores and normalized score
        """
        clean_text = self._strip_html_tags(text)
        words = self._tokenize(clean_text)

        if not words:
            return ReadabilityScore(score=0.0)

        word_count = len(words)

        # Count sentences
        sentences = self._sentence_pattern.split(clean_text)
        sentence_count = len([s for s in sentences if s.strip()])
        sentence_count = max(1, sentence_count)

        # Count syllables
        total_syllables = sum(self._count_syllables(word) for word in words)

        # Calculate averages
        avg_words_per_sentence = word_count / sentence_count
        avg_syllables_per_word = total_syllables / word_count if word_count > 0 else 0

        # Flesch Reading Ease (0-100, higher = easier)
        flesch_reading_ease = (
            206.835 - (1.015 * avg_words_per_sentence) - (84.6 * avg_syllables_per_word)
        )
        flesch_reading_ease = max(0, min(100, flesch_reading_ease))

        # Flesch-Kincaid Grade Level
        flesch_kincaid_grade = (
            (0.39 * avg_words_per_sentence) + (11.8 * avg_syllables_per_word) - 15.59
        )
        flesch_kincaid_grade = max(0, flesch_kincaid_grade)

        # Calculate score based on readability target
        # Target: 30-70 on Flesch scale (fairly easy to standard)
        if (
            DEFAULT_TARGET_READABILITY_MIN
            <= flesch_reading_ease
            <= DEFAULT_TARGET_READABILITY_MAX
        ):
            score = 1.0
        elif flesch_reading_ease < DEFAULT_TARGET_READABILITY_MIN:
            # Too difficult - penalize
            diff = DEFAULT_TARGET_READABILITY_MIN - flesch_reading_ease
            score = max(0.3, 1.0 - (diff / 50))
        else:
            # Too easy - slight penalty
            diff = flesch_reading_ease - DEFAULT_TARGET_READABILITY_MAX
            score = max(0.7, 1.0 - (diff / 60))

        logger.debug(
            "Readability score computed",
            extra={
                "word_count": word_count,
                "sentence_count": sentence_count,
                "total_syllables": total_syllables,
                "flesch_reading_ease": round(flesch_reading_ease, 2),
                "flesch_kincaid_grade": round(flesch_kincaid_grade, 2),
                "score": round(score, 4),
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        return ReadabilityScore(
            flesch_reading_ease=flesch_reading_ease,
            flesch_kincaid_grade=flesch_kincaid_grade,
            avg_syllables_per_word=avg_syllables_per_word,
            score=score,
        )

    def _compute_keyword_density_score(
        self,
        text: str,
        primary_keyword: str,
        secondary_keywords: list[str],
        project_id: str | None,
        page_id: str | None,
    ) -> KeywordDensityScore:
        """Compute keyword density and optimization score.

        Target density: 0.5% - 2.5% for primary keyword

        Args:
            text: Content text to analyze
            primary_keyword: Target primary keyword
            secondary_keywords: List of secondary keywords
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            KeywordDensityScore with density metrics and normalized score
        """
        clean_text = self._strip_html_tags(text).lower()
        words = self._tokenize(clean_text)
        word_count = len(words)

        if not word_count:
            return KeywordDensityScore(score=0.0)

        if not primary_keyword:
            # No keyword specified - partial score based on content existence
            return KeywordDensityScore(score=0.5)

        primary_keyword_lower = primary_keyword.lower()

        # Count primary keyword occurrences
        # Handle multi-word keywords
        primary_keyword_words = primary_keyword_lower.split()
        if len(primary_keyword_words) == 1:
            primary_count = sum(1 for w in words if w == primary_keyword_lower)
        else:
            # Count phrase occurrences
            primary_count = clean_text.count(primary_keyword_lower)

        # Calculate density as percentage
        primary_density = (primary_count * 100) / word_count if word_count > 0 else 0

        # Process secondary keywords
        secondary_densities: list[tuple[str, float]] = []
        total_occurrences = primary_count

        for kw in secondary_keywords:
            kw_lower = kw.lower()
            kw_words = kw_lower.split()
            if len(kw_words) == 1:
                kw_count = sum(1 for w in words if w == kw_lower)
            else:
                kw_count = clean_text.count(kw_lower)
            density = (kw_count * 100) / word_count if word_count > 0 else 0
            secondary_densities.append((kw, density))
            total_occurrences += kw_count

        # Calculate score based on primary keyword density
        if primary_density < DEFAULT_TARGET_KEYWORD_DENSITY_MIN:
            # Under-optimized
            score = primary_density / DEFAULT_TARGET_KEYWORD_DENSITY_MIN
        elif primary_density > DEFAULT_TARGET_KEYWORD_DENSITY_MAX:
            # Over-optimized (keyword stuffing)
            excess = primary_density - DEFAULT_TARGET_KEYWORD_DENSITY_MAX
            score = max(0.3, 1.0 - (excess / 2))
        else:
            # Optimal range
            score = 1.0

        # Bonus for secondary keyword presence
        secondary_present = sum(1 for _, d in secondary_densities if d > 0)
        if secondary_keywords and secondary_present > 0:
            coverage = secondary_present / len(secondary_keywords)
            score = min(1.0, score + (coverage * 0.1))

        logger.debug(
            "Keyword density score computed",
            extra={
                "word_count": word_count,
                "primary_keyword": primary_keyword,
                "primary_count": primary_count,
                "primary_density": round(primary_density, 4),
                "secondary_keywords_found": secondary_present,
                "total_occurrences": total_occurrences,
                "score": round(score, 4),
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        return KeywordDensityScore(
            primary_keyword=primary_keyword,
            primary_density=primary_density,
            secondary_keywords=secondary_densities,
            total_keyword_occurrences=total_occurrences,
            score=max(0.0, min(1.0, score)),
        )

    def _compute_entity_coverage_score(
        self,
        text: str,
        project_id: str | None,
        page_id: str | None,
    ) -> EntityCoverageScore:
        """Compute named entity extraction and coverage score.

        Args:
            text: Content text to analyze
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            EntityCoverageScore with entity analysis and normalized score
        """
        clean_text = self._strip_html_tags(text)

        if not clean_text.strip():
            return EntityCoverageScore(score=0.0)

        entities: dict[str, list[str]] = {}
        total_entities = 0

        for entity_type, pattern in ENTITY_PATTERNS.items():
            matches = pattern.findall(clean_text)
            if matches:
                entities[entity_type] = [str(m) for m in matches]
                total_entities += len(matches)

        entity_types_covered = len(entities)
        total_types = len(ENTITY_PATTERNS)

        # Calculate coverage ratio
        coverage_ratio = entity_types_covered / total_types if total_types > 0 else 0

        # Calculate score
        # Having entities is good, having diverse entities is better
        if entity_types_covered == 0:
            score = 0.3  # Minimal content without entities
        elif entity_types_covered == 1:
            score = 0.5
        elif entity_types_covered == 2:
            score = 0.7
        else:
            score = 0.8 + (coverage_ratio * 0.2)

        # Bonus for entity density
        words = self._tokenize(clean_text)
        if words:
            entity_density = total_entities / len(words)
            if 0.02 <= entity_density <= 0.1:
                score = min(1.0, score + 0.1)

        logger.debug(
            "Entity coverage score computed",
            extra={
                "entity_types_covered": entity_types_covered,
                "total_entities": total_entities,
                "coverage_ratio": round(coverage_ratio, 4),
                "entities_by_type": {k: len(v) for k, v in entities.items()},
                "score": round(score, 4),
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        return EntityCoverageScore(
            entities=entities,
            entity_count=total_entities,
            entity_types_covered=entity_types_covered,
            coverage_ratio=coverage_ratio,
            score=max(0.0, min(1.0, score)),
        )

    async def score_content(
        self,
        input_data: ContentScoreInput,
    ) -> ContentScoreResult:
        """Score content across all quality dimensions.

        Performs comprehensive content analysis including:
        1. Word count and structure metrics
        2. Semantic relevance and topic depth
        3. Readability (Flesch-Kincaid scores)
        4. Keyword density optimization
        5. Named entity coverage

        Args:
            input_data: Content and parameters to analyze

        Returns:
            ContentScoreResult with component scores and overall score
        """
        start_time = time.monotonic()
        project_id = input_data.project_id
        page_id = input_data.page_id

        logger.debug(
            "score_content() called",
            extra={
                "content_length": len(input_data.content),
                "primary_keyword": input_data.primary_keyword,
                "secondary_keyword_count": len(input_data.secondary_keywords),
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        # Validate inputs
        if not input_data.content or not input_data.content.strip():
            logger.warning(
                "Validation failed: empty content",
                extra={
                    "field": "content",
                    "rejected_value": "",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            return ContentScoreResult(
                success=False,
                error="Content cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        try:
            # Log phase transition
            logger.info(
                "Content scoring started",
                extra={
                    "phase": "content_scoring",
                    "status": "in_progress",
                    "content_length": len(input_data.content),
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            # Compute all component scores
            word_count_score = self._compute_word_count_score(
                text=input_data.content,
                target_min=input_data.target_word_count_min,
                target_max=input_data.target_word_count_max,
                project_id=project_id,
                page_id=page_id,
            )

            semantic_score = self._compute_semantic_score(
                text=input_data.content,
                project_id=project_id,
                page_id=page_id,
            )

            readability_score = self._compute_readability_score(
                text=input_data.content,
                project_id=project_id,
                page_id=page_id,
            )

            keyword_density_score = self._compute_keyword_density_score(
                text=input_data.content,
                primary_keyword=input_data.primary_keyword,
                secondary_keywords=input_data.secondary_keywords,
                project_id=project_id,
                page_id=page_id,
            )

            entity_coverage_score = self._compute_entity_coverage_score(
                text=input_data.content,
                project_id=project_id,
                page_id=page_id,
            )

            # Calculate weighted overall score
            overall_score = (
                (word_count_score.score * self.scoring_weights["word_count"])
                + (semantic_score.score * self.scoring_weights["semantic"])
                + (readability_score.score * self.scoring_weights["readability"])
                + (
                    keyword_density_score.score
                    * self.scoring_weights["keyword_density"]
                )
                + (
                    entity_coverage_score.score
                    * self.scoring_weights["entity_coverage"]
                )
            )

            passed = overall_score >= self.pass_threshold

            duration_ms = (time.monotonic() - start_time) * 1000

            # Log completion
            logger.info(
                "Content scoring completed",
                extra={
                    "phase": "content_scoring",
                    "status": "completed",
                    "overall_score": round(overall_score, 4),
                    "word_count_score": round(word_count_score.score, 4),
                    "semantic_score": round(semantic_score.score, 4),
                    "readability_score": round(readability_score.score, 4),
                    "keyword_density_score": round(keyword_density_score.score, 4),
                    "entity_coverage_score": round(entity_coverage_score.score, 4),
                    "passed": passed,
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            # Log slow operation
            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow content scoring operation",
                    extra={
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                        "content_length": len(input_data.content),
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )

            return ContentScoreResult(
                success=True,
                overall_score=overall_score,
                word_count_score=word_count_score,
                semantic_score=semantic_score,
                readability_score=readability_score,
                keyword_density_score=keyword_density_score,
                entity_coverage_score=entity_coverage_score,
                passed=passed,
                duration_ms=round(duration_ms, 2),
                project_id=project_id,
                page_id=page_id,
            )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Content scoring exception",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "page_id": page_id,
                },
                exc_info=True,
            )
            return ContentScoreResult(
                success=False,
                error=f"Unexpected error: {e!s}",
                duration_ms=round(duration_ms, 2),
                project_id=project_id,
                page_id=page_id,
            )

    async def score_content_batch(
        self,
        inputs: list[ContentScoreInput],
        project_id: str | None = None,
    ) -> list[ContentScoreResult]:
        """Score multiple content items.

        Args:
            inputs: List of content items to score
            project_id: Project ID for logging

        Returns:
            List of ContentScoreResult, one per input
        """
        start_time = time.monotonic()

        logger.info(
            "Batch content scoring started",
            extra={
                "input_count": len(inputs),
                "project_id": project_id,
            },
        )

        if not inputs:
            return []

        results: list[ContentScoreResult] = []
        for input_data in inputs:
            result = await self.score_content(input_data)
            results.append(result)

        duration_ms = (time.monotonic() - start_time) * 1000
        success_count = sum(1 for r in results if r.success)
        passed_count = sum(1 for r in results if r.passed)

        logger.info(
            "Batch content scoring completed",
            extra={
                "input_count": len(inputs),
                "success_count": success_count,
                "failure_count": len(inputs) - success_count,
                "passed_count": passed_count,
                "failed_count": len(inputs) - passed_count,
                "duration_ms": round(duration_ms, 2),
                "project_id": project_id,
            },
        )

        if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
            logger.warning(
                "Slow batch content scoring operation",
                extra={
                    "input_count": len(inputs),
                    "duration_ms": round(duration_ms, 2),
                    "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    "project_id": project_id,
                },
            )

        return results


# Global ContentScoreService instance
_content_score_service: ContentScoreService | None = None


def get_content_score_service() -> ContentScoreService:
    """Get the default ContentScoreService instance (singleton).

    Returns:
        Default ContentScoreService instance.
    """
    global _content_score_service
    if _content_score_service is None:
        _content_score_service = ContentScoreService()
        logger.info("ContentScoreService singleton created")
    return _content_score_service


async def score_content(
    content: str,
    primary_keyword: str = "",
    secondary_keywords: list[str] | None = None,
    project_id: str | None = None,
    page_id: str | None = None,
) -> ContentScoreResult:
    """Convenience function to score content.

    Uses the default ContentScoreService singleton.

    Args:
        content: Content text to analyze
        primary_keyword: Target primary keyword
        secondary_keywords: List of secondary keywords
        project_id: Project ID for logging
        page_id: Page ID for logging

    Returns:
        ContentScoreResult with component scores and overall score

    Example:
        >>> result = await score_content(
        ...     content="Your product description here...",
        ...     primary_keyword="leather wallet",
        ...     secondary_keywords=["genuine leather", "bifold"],
        ...     project_id="proj-123",
        ... )
        >>> print(f"Score: {result.overall_score}")
    """
    service = get_content_score_service()
    input_data = ContentScoreInput(
        content=content,
        primary_keyword=primary_keyword,
        secondary_keywords=secondary_keywords or [],
        project_id=project_id,
        page_id=page_id,
    )
    return await service.score_content(input_data)
