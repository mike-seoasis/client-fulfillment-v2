"""TF-IDF Analysis Service for term extraction from text content.

Implements Term Frequency-Inverse Document Frequency (TF-IDF) analysis
for extracting important terms from competitor content. Part of the
NLP optimization system for content scoring.

Features:
- Pure Python implementation (no scikit-learn dependency)
- Configurable n-gram support (unigrams and bigrams)
- English stop word filtering
- Term scoring and ranking
- Batch processing support
- Comprehensive error logging per requirements

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Threshold for logging slow operations (in milliseconds)
SLOW_OPERATION_THRESHOLD_MS = 1000

# TF-IDF configuration defaults
DEFAULT_MAX_FEATURES = 100
DEFAULT_MIN_DF = 1  # Minimum document frequency (number of documents)
DEFAULT_MAX_DF_RATIO = 0.85  # Maximum document frequency ratio (% of documents)
DEFAULT_TOP_N = 25  # Default number of top terms to return

# Standard English stop words
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


class TFIDFAnalysisServiceError(Exception):
    """Base exception for TFIDFAnalysisService errors."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
    ):
        self.project_id = project_id
        super().__init__(message)


class TFIDFValidationError(TFIDFAnalysisServiceError):
    """Raised when input validation fails."""

    def __init__(
        self,
        field: str,
        value: Any,
        message: str,
        project_id: str | None = None,
    ):
        self.field = field
        self.value = value
        self.message = message
        super().__init__(
            f"Validation failed for '{field}': {message}",
            project_id=project_id,
        )


@dataclass
class TermScore:
    """A single term with its TF-IDF score.

    Attributes:
        term: The extracted term (can be unigram or bigram)
        score: The TF-IDF score (0.0 to 1.0 normalized)
        doc_frequency: Number of documents containing this term
        term_frequency: Total occurrences across all documents
    """

    term: str
    score: float
    doc_frequency: int = 0
    term_frequency: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "term": self.term,
            "score": round(self.score, 4),
            "doc_frequency": self.doc_frequency,
            "term_frequency": self.term_frequency,
        }


@dataclass
class TFIDFAnalysisRequest:
    """Request for TF-IDF analysis.

    Attributes:
        documents: List of text documents to analyze
        top_n: Number of top terms to return (default: 25)
        include_bigrams: Whether to include bigrams (default: True)
        min_df: Minimum document frequency (default: 1)
        max_df_ratio: Maximum document frequency ratio (default: 0.85)
        project_id: Project ID for logging
    """

    documents: list[str]
    top_n: int = DEFAULT_TOP_N
    include_bigrams: bool = True
    min_df: int = DEFAULT_MIN_DF
    max_df_ratio: float = DEFAULT_MAX_DF_RATIO
    project_id: str | None = None


@dataclass
class TFIDFAnalysisResult:
    """Result of TF-IDF analysis.

    Attributes:
        success: Whether analysis succeeded
        terms: List of extracted terms with scores (sorted by score descending)
        term_count: Number of terms extracted
        document_count: Number of documents analyzed
        vocabulary_size: Total unique terms before filtering
        error: Error message if failed
        duration_ms: Total time taken in milliseconds
        project_id: Project ID (for logging context)
    """

    success: bool
    terms: list[TermScore] = field(default_factory=list)
    term_count: int = 0
    document_count: int = 0
    vocabulary_size: int = 0
    error: str | None = None
    duration_ms: float = 0.0
    project_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "success": self.success,
            "terms": [t.to_dict() for t in self.terms],
            "term_count": self.term_count,
            "document_count": self.document_count,
            "vocabulary_size": self.vocabulary_size,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
        }

    def get_term_list(self) -> list[str]:
        """Get just the term strings (convenience method)."""
        return [t.term for t in self.terms]


class TFIDFAnalysisService:
    """Service for TF-IDF analysis on text documents.

    Extracts important terms from a corpus of documents using
    Term Frequency-Inverse Document Frequency scoring. Commonly
    used to identify key terms from competitor content.

    Example usage:
        service = TFIDFAnalysisService()

        documents = [
            "Airtight coffee containers keep beans fresh",
            "Vacuum sealed coffee storage preserves aroma",
            "Best coffee canisters for freshness",
        ]

        result = await service.analyze(
            documents=documents,
            top_n=10,
            project_id="proj-123",
        )

        print(f"Top terms: {result.get_term_list()}")
        # ['coffee', 'airtight', 'vacuum sealed', 'freshness', ...]
    """

    # Regex for tokenization: matches word characters
    _token_pattern = re.compile(r"\b[a-zA-Z][a-zA-Z0-9]*(?:\'[a-zA-Z]+)?\b")

    def __init__(self) -> None:
        """Initialize the TF-IDF analysis service."""
        logger.debug("TFIDFAnalysisService.__init__ called")
        logger.debug("TFIDFAnalysisService initialized")

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into lowercase words.

        Args:
            text: Input text to tokenize

        Returns:
            List of lowercase tokens
        """
        if not text:
            return []

        # Find all word tokens
        tokens = self._token_pattern.findall(text.lower())

        # Filter out stop words and short tokens
        return [t for t in tokens if t not in STOP_WORDS and len(t) > 2]

    def _get_ngrams(
        self,
        tokens: list[str],
        include_bigrams: bool = True,
    ) -> list[str]:
        """Generate unigrams and optionally bigrams from tokens.

        Args:
            tokens: List of tokens
            include_bigrams: Whether to include bigrams

        Returns:
            List of n-grams (terms)
        """
        ngrams: list[str] = list(tokens)  # Unigrams

        if include_bigrams and len(tokens) >= 2:
            # Add bigrams
            for i in range(len(tokens) - 1):
                bigram = f"{tokens[i]} {tokens[i + 1]}"
                ngrams.append(bigram)

        return ngrams

    def _compute_tf(
        self,
        terms: list[str],
    ) -> dict[str, float]:
        """Compute Term Frequency for a document.

        Uses normalized term frequency: count / total_terms

        Args:
            terms: List of terms in the document

        Returns:
            Dictionary mapping term -> TF score
        """
        if not terms:
            return {}

        counts = Counter(terms)
        total = len(terms)

        return {term: count / total for term, count in counts.items()}

    def _compute_idf(
        self,
        doc_term_sets: list[set[str]],
        vocabulary: set[str],
    ) -> dict[str, float]:
        """Compute Inverse Document Frequency for vocabulary.

        Uses standard IDF formula: log(N / df) where:
        - N = total number of documents
        - df = number of documents containing the term

        Args:
            doc_term_sets: List of sets, each containing terms in a document
            vocabulary: Set of all unique terms

        Returns:
            Dictionary mapping term -> IDF score
        """
        n_docs = len(doc_term_sets)
        if n_docs == 0:
            return {}

        idf: dict[str, float] = {}

        for term in vocabulary:
            # Count documents containing this term
            df = sum(1 for doc_terms in doc_term_sets if term in doc_terms)
            if df > 0:
                # Standard IDF with smoothing to avoid division by zero
                idf[term] = math.log((n_docs + 1) / (df + 1)) + 1
            else:
                idf[term] = 0.0

        return idf

    def _filter_by_document_frequency(
        self,
        doc_term_sets: list[set[str]],
        vocabulary: set[str],
        min_df: int,
        max_df_ratio: float,
    ) -> tuple[set[str], dict[str, int]]:
        """Filter vocabulary by document frequency.

        Args:
            doc_term_sets: List of sets containing terms per document
            vocabulary: Set of all terms
            min_df: Minimum document frequency
            max_df_ratio: Maximum document frequency ratio

        Returns:
            Tuple of (filtered vocabulary, document frequency counts)
        """
        n_docs = len(doc_term_sets)
        max_df = int(n_docs * max_df_ratio)

        doc_freq: dict[str, int] = {}
        for term in vocabulary:
            df = sum(1 for doc_terms in doc_term_sets if term in doc_terms)
            doc_freq[term] = df

        # Filter vocabulary
        filtered = {
            term
            for term in vocabulary
            if min_df <= doc_freq[term] <= max_df
        }

        return filtered, doc_freq

    async def analyze(
        self,
        documents: list[str],
        top_n: int = DEFAULT_TOP_N,
        include_bigrams: bool = True,
        min_df: int = DEFAULT_MIN_DF,
        max_df_ratio: float = DEFAULT_MAX_DF_RATIO,
        project_id: str | None = None,
    ) -> TFIDFAnalysisResult:
        """Perform TF-IDF analysis on a corpus of documents.

        Extracts the most important terms based on their TF-IDF scores.
        Terms that appear frequently in few documents but not across
        all documents will score highest.

        Args:
            documents: List of text documents to analyze
            top_n: Number of top terms to return
            include_bigrams: Whether to include bigrams (two-word phrases)
            min_df: Minimum number of documents a term must appear in
            max_df_ratio: Maximum ratio of documents a term can appear in
            project_id: Project ID for logging

        Returns:
            TFIDFAnalysisResult with extracted terms and metadata
        """
        start_time = time.monotonic()
        logger.debug(
            "analyze() called",
            extra={
                "project_id": project_id,
                "document_count": len(documents),
                "top_n": top_n,
                "include_bigrams": include_bigrams,
                "min_df": min_df,
                "max_df_ratio": max_df_ratio,
            },
        )

        # Validate inputs
        if not documents:
            logger.warning(
                "Validation failed: empty documents list",
                extra={
                    "project_id": project_id,
                    "field": "documents",
                    "rejected_value": "[]",
                },
            )
            return TFIDFAnalysisResult(
                success=False,
                error="Documents list cannot be empty",
                project_id=project_id,
            )

        if top_n < 1:
            logger.warning(
                "Validation failed: invalid top_n",
                extra={
                    "project_id": project_id,
                    "field": "top_n",
                    "rejected_value": top_n,
                },
            )
            return TFIDFAnalysisResult(
                success=False,
                error="top_n must be at least 1",
                project_id=project_id,
            )

        if not 0.0 < max_df_ratio <= 1.0:
            logger.warning(
                "Validation failed: invalid max_df_ratio",
                extra={
                    "project_id": project_id,
                    "field": "max_df_ratio",
                    "rejected_value": max_df_ratio,
                },
            )
            return TFIDFAnalysisResult(
                success=False,
                error="max_df_ratio must be between 0 and 1",
                project_id=project_id,
            )

        try:
            # Log state transition
            logger.info(
                "TF-IDF analysis started",
                extra={
                    "project_id": project_id,
                    "phase": "tfidf_analysis",
                    "status": "in_progress",
                    "document_count": len(documents),
                },
            )

            # Tokenize all documents
            doc_terms: list[list[str]] = []
            doc_term_sets: list[set[str]] = []

            for i, doc in enumerate(documents):
                if not doc or not doc.strip():
                    logger.debug(
                        "Skipping empty document",
                        extra={
                            "project_id": project_id,
                            "document_index": i,
                        },
                    )
                    continue

                tokens = self._tokenize(doc)
                terms = self._get_ngrams(tokens, include_bigrams)
                doc_terms.append(terms)
                doc_term_sets.append(set(terms))

            if not doc_terms:
                logger.warning(
                    "No valid documents after tokenization",
                    extra={
                        "project_id": project_id,
                        "original_count": len(documents),
                    },
                )
                return TFIDFAnalysisResult(
                    success=False,
                    error="No valid documents with extractable terms",
                    document_count=len(documents),
                    project_id=project_id,
                )

            # Build vocabulary
            vocabulary: set[str] = set()
            for term_set in doc_term_sets:
                vocabulary.update(term_set)

            original_vocab_size = len(vocabulary)
            logger.debug(
                "Vocabulary built",
                extra={
                    "project_id": project_id,
                    "vocabulary_size": original_vocab_size,
                    "document_count": len(doc_terms),
                },
            )

            # Filter by document frequency
            filtered_vocab, doc_freq = self._filter_by_document_frequency(
                doc_term_sets=doc_term_sets,
                vocabulary=vocabulary,
                min_df=min_df,
                max_df_ratio=max_df_ratio,
            )

            logger.debug(
                "Vocabulary filtered by document frequency",
                extra={
                    "project_id": project_id,
                    "original_size": original_vocab_size,
                    "filtered_size": len(filtered_vocab),
                    "min_df": min_df,
                    "max_df_ratio": max_df_ratio,
                },
            )

            if not filtered_vocab:
                logger.warning(
                    "No terms remaining after filtering",
                    extra={
                        "project_id": project_id,
                        "original_vocab_size": original_vocab_size,
                    },
                )
                return TFIDFAnalysisResult(
                    success=True,
                    terms=[],
                    term_count=0,
                    document_count=len(doc_terms),
                    vocabulary_size=original_vocab_size,
                    project_id=project_id,
                )

            # Compute IDF for filtered vocabulary
            idf = self._compute_idf(doc_term_sets, filtered_vocab)

            # Compute TF-IDF and aggregate across documents
            # Using dict comprehension intentionally for type safety and explicit initialization
            tfidf_scores: dict[str, float] = {term: 0.0 for term in filtered_vocab}  # noqa: C420
            term_total_freq: dict[str, int] = {term: 0 for term in filtered_vocab}  # noqa: C420

            for terms in doc_terms:
                tf = self._compute_tf(terms)
                for term in filtered_vocab:
                    if term in tf:
                        tfidf_scores[term] += tf[term] * idf.get(term, 0.0)
                        term_total_freq[term] += terms.count(term)

            # Average TF-IDF scores across documents
            n_docs = len(doc_terms)
            for term in tfidf_scores:
                tfidf_scores[term] /= n_docs

            # Normalize scores to 0-1 range
            max_score = max(tfidf_scores.values()) if tfidf_scores else 1.0
            if max_score > 0:
                for term in tfidf_scores:
                    tfidf_scores[term] /= max_score

            # Sort and get top N terms
            sorted_terms = sorted(
                tfidf_scores.items(),
                key=lambda x: (-x[1], x[0]),  # Sort by score desc, then term asc
            )[:top_n]

            # Build result terms
            result_terms = [
                TermScore(
                    term=term,
                    score=score,
                    doc_frequency=doc_freq.get(term, 0),
                    term_frequency=term_total_freq.get(term, 0),
                )
                for term, score in sorted_terms
                if score > 0  # Only include terms with positive scores
            ]

            duration_ms = (time.monotonic() - start_time) * 1000

            # Log completion
            logger.info(
                "TF-IDF analysis completed",
                extra={
                    "project_id": project_id,
                    "phase": "tfidf_analysis",
                    "status": "completed",
                    "term_count": len(result_terms),
                    "document_count": n_docs,
                    "vocabulary_size": original_vocab_size,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            # Log slow operation warning
            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow TF-IDF analysis operation",
                    extra={
                        "project_id": project_id,
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                        "document_count": n_docs,
                        "vocabulary_size": original_vocab_size,
                    },
                )

            return TFIDFAnalysisResult(
                success=True,
                terms=result_terms,
                term_count=len(result_terms),
                document_count=n_docs,
                vocabulary_size=original_vocab_size,
                duration_ms=round(duration_ms, 2),
                project_id=project_id,
            )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "TF-IDF analysis exception",
                extra={
                    "project_id": project_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
                exc_info=True,
            )
            return TFIDFAnalysisResult(
                success=False,
                error=f"Unexpected error: {e!s}",
                duration_ms=round(duration_ms, 2),
                project_id=project_id,
            )

    async def analyze_request(
        self,
        request: TFIDFAnalysisRequest,
    ) -> TFIDFAnalysisResult:
        """Perform TF-IDF analysis using a request object.

        Convenience method that unpacks a TFIDFAnalysisRequest.

        Args:
            request: The analysis request

        Returns:
            TFIDFAnalysisResult with extracted terms
        """
        return await self.analyze(
            documents=request.documents,
            top_n=request.top_n,
            include_bigrams=request.include_bigrams,
            min_df=request.min_df,
            max_df_ratio=request.max_df_ratio,
            project_id=request.project_id,
        )

    async def find_missing_terms(
        self,
        competitor_documents: list[str],
        user_content: str,
        top_n: int = DEFAULT_TOP_N,
        project_id: str | None = None,
    ) -> TFIDFAnalysisResult:
        """Find important terms from competitors that are missing in user content.

        Extracts top TF-IDF terms from competitor documents and filters
        to only terms NOT present in the user's content.

        Args:
            competitor_documents: List of competitor text content
            user_content: User's content to check against
            top_n: Number of missing terms to return
            project_id: Project ID for logging

        Returns:
            TFIDFAnalysisResult with missing terms only
        """
        start_time = time.monotonic()
        logger.debug(
            "find_missing_terms() called",
            extra={
                "project_id": project_id,
                "competitor_count": len(competitor_documents),
                "user_content_length": len(user_content) if user_content else 0,
                "top_n": top_n,
            },
        )

        # Get top terms from competitors
        competitor_result = await self.analyze(
            documents=competitor_documents,
            top_n=top_n * 2,  # Get more terms so we have enough after filtering
            project_id=project_id,
        )

        if not competitor_result.success:
            return competitor_result

        # Tokenize user content to check for term presence
        user_tokens = set(self._tokenize(user_content))
        user_text_lower = user_content.lower() if user_content else ""

        # Filter to terms not in user content
        missing_terms: list[TermScore] = []
        for term in competitor_result.terms:
            term_words = term.term.split()

            # Check if term (or all its component words for bigrams) is missing
            is_missing = True
            if len(term_words) == 1:
                # Unigram: check if word is in user tokens
                is_missing = term_words[0] not in user_tokens
            else:
                # Bigram: check if the exact phrase is in user content
                is_missing = term.term not in user_text_lower

            if is_missing:
                missing_terms.append(term)
                if len(missing_terms) >= top_n:
                    break

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Missing terms analysis completed",
            extra={
                "project_id": project_id,
                "competitor_terms": len(competitor_result.terms),
                "missing_terms": len(missing_terms),
                "duration_ms": round(duration_ms, 2),
            },
        )

        return TFIDFAnalysisResult(
            success=True,
            terms=missing_terms,
            term_count=len(missing_terms),
            document_count=competitor_result.document_count,
            vocabulary_size=competitor_result.vocabulary_size,
            duration_ms=round(duration_ms, 2),
            project_id=project_id,
        )


# Global TFIDFAnalysisService instance
_tfidf_service: TFIDFAnalysisService | None = None


def get_tfidf_analysis_service() -> TFIDFAnalysisService:
    """Get the default TFIDFAnalysisService instance (singleton).

    Returns:
        Default TFIDFAnalysisService instance.
    """
    global _tfidf_service
    if _tfidf_service is None:
        _tfidf_service = TFIDFAnalysisService()
    return _tfidf_service


async def analyze_tfidf(
    documents: list[str],
    top_n: int = DEFAULT_TOP_N,
    include_bigrams: bool = True,
    project_id: str | None = None,
) -> TFIDFAnalysisResult:
    """Convenience function to perform TF-IDF analysis.

    Uses the default TFIDFAnalysisService singleton.

    Args:
        documents: List of text documents to analyze
        top_n: Number of top terms to return
        include_bigrams: Whether to include bigrams
        project_id: Project ID for logging

    Returns:
        TFIDFAnalysisResult with extracted terms

    Example:
        >>> result = await analyze_tfidf(
        ...     documents=[
        ...         "Coffee containers keep beans fresh",
        ...         "Airtight storage for coffee",
        ...     ],
        ...     top_n=10,
        ...     project_id="proj-123",
        ... )
        >>> print(result.get_term_list())
        ['coffee', 'airtight', 'beans', 'fresh', 'storage', ...]
    """
    service = get_tfidf_analysis_service()
    return await service.analyze(
        documents=documents,
        top_n=top_n,
        include_bigrams=include_bigrams,
        project_id=project_id,
    )


async def find_missing_terms(
    competitor_documents: list[str],
    user_content: str,
    top_n: int = DEFAULT_TOP_N,
    project_id: str | None = None,
) -> TFIDFAnalysisResult:
    """Convenience function to find missing terms.

    Uses the default TFIDFAnalysisService singleton.

    Args:
        competitor_documents: List of competitor text content
        user_content: User's content to check against
        top_n: Number of missing terms to return
        project_id: Project ID for logging

    Returns:
        TFIDFAnalysisResult with missing terms only

    Example:
        >>> result = await find_missing_terms(
        ...     competitor_documents=[
        ...         "Vacuum sealed coffee containers with CO2 valve",
        ...         "Airtight coffee storage preserves aroma and freshness",
        ...     ],
        ...     user_content="Coffee containers for your kitchen",
        ...     top_n=5,
        ...     project_id="proj-123",
        ... )
        >>> print(result.get_term_list())
        ['vacuum sealed', 'airtight', 'aroma', 'freshness', 'co2 valve']
    """
    service = get_tfidf_analysis_service()
    return await service.find_missing_terms(
        competitor_documents=competitor_documents,
        user_content=user_content,
        top_n=top_n,
        project_id=project_id,
    )
