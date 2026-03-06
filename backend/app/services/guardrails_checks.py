"""Guardrails AI Hub validators + custom LSI coverage check.

Extends the deterministic quality checks (1-13) with ML-based validators
(14-20) from Guardrails AI Hub plus a custom LSI term coverage check (21).

Two public entry points:
- run_guardrails_checks(): Full suite for page/blog content
- run_comment_guardrails(): Lightweight subset for Reddit comments

Graceful degradation: if guardrails-ai is not installed or the feature
flag is disabled, all functions return empty lists.
"""

import re
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Re-use QualityIssue from content_quality
from app.services.content_quality import QualityIssue, TIER1_AI_WORDS, strip_html_tags

# ---------------------------------------------------------------------------
# LSI coverage check (custom, no external deps)
# ---------------------------------------------------------------------------


def _check_lsi_coverage(
    combined_text: str,
    lsi_terms: list[dict[str, Any]],
    min_coverage: float,
) -> QualityIssue | None:
    """Check what % of POP LSI terms appear in the combined content.

    Args:
        combined_text: All content fields concatenated (plain text, lowered).
        lsi_terms: List of dicts with at least a "phrase" key.
        min_coverage: Minimum fraction (0-1) of terms that must appear.

    Returns:
        A QualityIssue if coverage is below threshold, else None.
    """
    if not lsi_terms:
        return None

    phrases = [t.get("phrase", "") for t in lsi_terms if t.get("phrase")]
    if not phrases:
        return None

    found = 0
    missing: list[str] = []
    for phrase in phrases:
        pattern = re.compile(r"\b" + re.escape(phrase.lower()) + r"\b")
        if pattern.search(combined_text):
            found += 1
        else:
            missing.append(phrase)

    coverage = found / len(phrases)

    if coverage >= min_coverage:
        return None

    # Show top missing terms (capped at 5 for readability)
    sample = ", ".join(missing[:5])
    suffix = f" (+{len(missing) - 5} more)" if len(missing) > 5 else ""

    return QualityIssue(
        type="lsi_coverage",
        field="all",
        description=(
            f"LSI coverage {coverage:.0%} below {min_coverage:.0%} threshold "
            f"({found}/{len(phrases)} terms found)"
        ),
        context=f"Missing: {sample}{suffix}",
    )


# ---------------------------------------------------------------------------
# Fuzzy ban list check (standalone, uses thefuzz)
# ---------------------------------------------------------------------------


def _check_fuzzy_ban_list(
    text: str,
    field_name: str,
    ban_words: list[str],
    threshold: int = 80,
) -> list[QualityIssue]:
    """Check for Levenshtein-distance matches on Tier 1 banned words.

    Catches misspellings and creative variations of banned words.
    Only flags words NOT already caught by the exact-match check in
    content_quality.py.
    """
    issues: list[QualityIssue] = []

    try:
        from thefuzz import fuzz
    except ImportError:
        return issues

    # Tokenize text into words
    words = re.findall(r"\b\w+\b", text.lower())
    # Build set of exact matches (already caught by deterministic checks)
    exact_set = {w.lower() for w in ban_words}

    for word in words:
        if word in exact_set:
            continue  # Already caught by exact check
        if len(word) < 4:
            continue  # Skip short words to avoid false positives

        for banned in ban_words:
            if len(banned) < 4:
                continue
            score = fuzz.ratio(word, banned.lower())
            if score >= threshold and score < 100:  # < 100 = not exact match
                issues.append(
                    QualityIssue(
                        type="gr_ban_list",
                        field=field_name,
                        description=(
                            f'Fuzzy match: "{word}" similar to banned word '
                            f'"{banned}" ({score}% match)'
                        ),
                        context=f"...{word}...",
                    )
                )
                break  # One match per word is enough

    return issues


# ---------------------------------------------------------------------------
# Reading level check (standalone, uses py-readability-metrics)
# ---------------------------------------------------------------------------


def _check_reading_level(
    text: str,
    field_name: str,
    min_grade: int,
    max_grade: int,
) -> list[QualityIssue]:
    """Check Flesch-Kincaid grade level of text."""
    issues: list[QualityIssue] = []

    # Skip short text — readability metrics are unreliable under ~100 words
    word_count = len(text.split())
    if word_count < 100:
        return issues

    try:
        from readability import Readability

        r = Readability(text)
        fk = r.flesch_kincaid()
        grade = fk.grade_level
    except ImportError:
        return issues
    except Exception:
        return issues

    if grade < min_grade or grade > max_grade:
        issues.append(
            QualityIssue(
                type="gr_reading_level",
                field=field_name,
                description=(
                    f"Reading level grade {grade:.1f} outside "
                    f"{min_grade}-{max_grade} range"
                ),
                context=f"Flesch-Kincaid grade level: {grade:.1f}",
            )
        )

    return issues


# ---------------------------------------------------------------------------
# Redundant sentences check (standalone, uses thefuzz)
# ---------------------------------------------------------------------------


def _check_redundant_sentences(
    text: str,
    field_name: str,
    threshold: int,
) -> list[QualityIssue]:
    """Flag sentence pairs with similarity above threshold."""
    issues: list[QualityIssue] = []

    try:
        from thefuzz import fuzz
    except ImportError:
        return issues

    # Split into sentences (simple heuristic)
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip()) > 20]

    for i, s1 in enumerate(sentences):
        if len(issues) >= 10:
            break
        for j, s2 in enumerate(sentences):
            if i >= j:
                continue
            if len(issues) >= 10:
                break

            score = fuzz.ratio(s1.lower(), s2.lower())
            if score >= threshold:
                issues.append(
                    QualityIssue(
                        type="gr_redundant",
                        field=field_name,
                        description=(
                            f"Redundant sentences ({score}% similar)"
                        ),
                        context=f"...{s1[:60]}... ≈ ...{s2[:60]}...",
                    )
                )

    return issues


# ---------------------------------------------------------------------------
# Profanity check (standalone)
# ---------------------------------------------------------------------------


def _check_profanity(text: str, field_name: str) -> list[QualityIssue]:
    """Check for profanity using alt-profanity-check."""
    try:
        from profanity_check import predict

        result = predict([text])
        if result[0] == 1:
            return [
                QualityIssue(
                    type="gr_profanity",
                    field=field_name,
                    description="Profanity detected in content",
                    context="",
                )
            ]
    except ImportError:
        pass
    except Exception:
        pass

    return []


# ---------------------------------------------------------------------------
# XSS / Web sanitization check (standalone)
# ---------------------------------------------------------------------------


def _check_xss(text: str, field_name: str) -> list[QualityIssue]:
    """Check for script injection / XSS in HTML content."""
    try:
        import bleach

        cleaned = bleach.clean(text, tags=[], strip=True)
        # If bleach removed content, there were disallowed tags
        if len(cleaned) < len(text) - 10:  # Allow minor whitespace diffs
            # Check specifically for script/event handler patterns
            if re.search(
                r"<script|javascript:|on\w+\s*=", text, re.IGNORECASE
            ):
                return [
                    QualityIssue(
                        type="gr_xss",
                        field=field_name,
                        description="Potential XSS/script injection detected in HTML",
                        context="",
                    )
                ]
    except ImportError:
        pass
    except Exception:
        pass

    return []


# ---------------------------------------------------------------------------
# Toxic language check (standalone, optional heavy deps)
# ---------------------------------------------------------------------------


_toxic_classifier: Any = None


def _get_toxic_classifier() -> Any:
    """Lazy-init and cache the toxic-bert classifier pipeline."""
    global _toxic_classifier
    if _toxic_classifier is not None:
        return _toxic_classifier
    from transformers import pipeline

    _toxic_classifier = pipeline(
        "text-classification",
        model="unitary/toxic-bert",
        top_k=None,
        truncation=True,
    )
    return _toxic_classifier


def _check_toxic_language(text: str, field_name: str) -> list[QualityIssue]:
    """Check for toxic language using toxic-bert model."""
    try:
        classifier = _get_toxic_classifier()
        results = classifier(text[:512])  # Truncate for model limits
        if results:
            for label_score in results[0]:
                label = label_score.get("label", "")
                score = label_score.get("score", 0)
                if label.lower() == "toxic" and score > 0.5:
                    return [
                        QualityIssue(
                            type="gr_toxic",
                            field=field_name,
                            description=f"Toxic language detected (confidence: {score:.0%})",
                            context="",
                        )
                    ]
    except ImportError:
        pass
    except Exception:
        pass

    return []


# ---------------------------------------------------------------------------
# Competitor NLP check (standalone)
# ---------------------------------------------------------------------------


def _check_competitors_nlp(
    text: str,
    field_name: str,
    competitors: list[str],
) -> list[QualityIssue]:
    """NLP-based competitor entity detection using NLTK NER.

    Supplements the exact-match competitor check in content_quality.py
    by catching competitor references that differ in case or spacing.
    """
    if not competitors:
        return []

    issues: list[QualityIssue] = []

    try:
        import nltk
        from nltk import ne_chunk, pos_tag, word_tokenize

        # Ensure required data is available
        for resource in ["punkt_tab", "averaged_perceptron_tagger_eng", "maxent_ne_chunker_tab", "words"]:
            try:
                nltk.data.find(f"tokenizers/{resource}" if "punkt" in resource else f"taggers/{resource}" if "tagger" in resource else f"chunkers/{resource}" if "chunker" in resource else f"corpora/{resource}")
            except LookupError:
                nltk.download(resource, quiet=True)

        # Extract named entities
        tokens = word_tokenize(text)
        tagged = pos_tag(tokens)
        tree = ne_chunk(tagged)

        entities: list[str] = []
        for subtree in tree:
            if hasattr(subtree, "label") and subtree.label() == "ORGANIZATION":
                entity = " ".join(word for word, tag in subtree.leaves())
                entities.append(entity)

        # Check if any entity fuzzy-matches a competitor
        competitor_lower = {c.lower() for c in competitors}
        for entity in entities:
            if entity.lower() in competitor_lower:
                issues.append(
                    QualityIssue(
                        type="gr_competitor",
                        field=field_name,
                        description=f'Competitor entity "{entity}" detected via NLP',
                        context=f"...{entity}...",
                    )
                )
    except ImportError:
        pass
    except Exception:
        pass

    return issues


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_guardrails_checks(
    fields: dict[str, str],
    brand_config: dict[str, Any],
    content_brief: dict[str, Any] | None = None,
) -> list[QualityIssue]:
    """Run Hub validators (14-20) + LSI coverage (21) on content fields.

    Args:
        fields: Dict of field_name -> text content.
        brand_config: BrandConfig.v2_schema dict.
        content_brief: Optional dict with lsi_terms list.

    Returns:
        List of QualityIssue instances (empty if disabled or not installed).
    """
    from app.core.config import get_settings

    settings = get_settings()

    if not settings.enable_guardrails_checks:
        return []

    issues: list[QualityIssue] = []

    # Extract competitor list from brand config
    vocabulary = brand_config.get("vocabulary", {})
    competitors: list[str] = []
    if isinstance(vocabulary, dict):
        competitors = vocabulary.get("competitors", []) or []

    # Run per-field checks
    for field_name, raw_text in fields.items():
        plain_text = strip_html_tags(raw_text)

        # 14: Competitor NLP check
        issues.extend(_check_competitors_nlp(plain_text, field_name, competitors))

        # 15: Reading level
        issues.extend(
            _check_reading_level(
                plain_text,
                field_name,
                settings.guardrails_reading_level_min,
                settings.guardrails_reading_level_max,
            )
        )

        # 16: Redundant sentences
        issues.extend(
            _check_redundant_sentences(
                plain_text,
                field_name,
                settings.guardrails_redundant_threshold,
            )
        )

        # 17: Fuzzy ban list
        issues.extend(
            _check_fuzzy_ban_list(plain_text, field_name, TIER1_AI_WORDS)
        )

        # 18: Profanity
        issues.extend(_check_profanity(plain_text, field_name))

        # 19: Toxic language (opt-in)
        if settings.enable_toxic_language_check:
            issues.extend(_check_toxic_language(plain_text, field_name))

        # 20: XSS / sanitization (check raw HTML, not stripped)
        issues.extend(_check_xss(raw_text, field_name))

    # 21: LSI coverage (across all fields combined)
    if content_brief:
        lsi_terms = content_brief.get("lsi_terms", [])
        if lsi_terms:
            combined = " ".join(
                strip_html_tags(t).lower() for t in fields.values()
            )
            lsi_issue = _check_lsi_coverage(
                combined, lsi_terms, settings.guardrails_lsi_coverage_min
            )
            if lsi_issue:
                issues.append(lsi_issue)

    return issues


def run_comment_guardrails(text: str) -> list[QualityIssue]:
    """Lightweight subset for Reddit comments: profanity, toxic, XSS only.

    Args:
        text: The comment text to check.

    Returns:
        List of QualityIssue instances.
    """
    from app.core.config import get_settings

    settings = get_settings()

    if not settings.enable_guardrails_checks:
        return []

    issues: list[QualityIssue] = []

    # 18: Profanity
    issues.extend(_check_profanity(text, "body"))

    # 19: Toxic language (opt-in)
    if settings.enable_toxic_language_check:
        issues.extend(_check_toxic_language(text, "body"))

    # 20: XSS
    issues.extend(_check_xss(text, "body"))

    return issues
