"""Deterministic AI trope quality checks for generated content.

Runs pure string analysis to detect common AI writing patterns without
API costs. All checks are informational — content is NOT regenerated
automatically. Results are stored in PageContent.qa_results JSONB field.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.models.page_content import PageContent

# Content fields to check
CONTENT_FIELDS = ("page_title", "meta_description", "top_description", "bottom_description")

# Common AI opener phrases (case-insensitive match at start of sentence)
AI_OPENER_PATTERNS = [
    r"\bIn today'?s\b",
    r"\bWhether you'?re\b",
    r"\bLook no further\b",
    r"\bIn the world of\b",
    r"\bWhen it comes to\b",
]

# Compiled regex for triplet list pattern: "X, Y, and Z"
# Matches: word(s), word(s), and word(s)
TRIPLET_PATTERN = re.compile(
    r"\b\w[\w\s]*?,\s+\w[\w\s]*?,\s+and\s+\w[\w\s]*?\b",
    re.IGNORECASE,
)

# Tier 1: Universal banned AI words (never use)
TIER1_AI_WORDS = [
    "delve", "delving", "unpack", "uncover",
    "unlock", "unleash", "harness", "leverage", "tap into",
    "embark", "navigate", "landscape", "realm", "at the forefront",
    "game-changer", "revolutionary", "transformative", "cutting-edge",
    "groundbreaking", "unprecedented",
    "crucial", "essential", "vital", "pivotal", "critical",
]

# Tier 2: AI words allowed max 1 per piece
TIER2_AI_WORDS = [
    "indeed", "furthermore", "moreover", "therefore", "additionally",
    "consequently", "subsequently", "accordingly", "notably", "significantly",
    "robust", "seamless", "comprehensive", "streamline", "enhance",
    "optimize", "elevate", "curated", "tailored", "bespoke", "nuanced", "intricate",
]

# Negation/contrast pattern: "It's not (just) X, it's Y"
NEGATION_PATTERN = re.compile(
    r"[Ii]t'?s\s+not\s+(?:just\s+)?[^,]+,\s+it'?s\s+",
)


@dataclass
class QualityIssue:
    """A single quality check issue."""

    type: str
    field: str
    description: str
    context: str

    def to_dict(self) -> dict[str, str]:
        return {
            "type": self.type,
            "field": self.field,
            "description": self.description,
            "context": self.context,
        }


@dataclass
class QualityResult:
    """Result of running all quality checks on a PageContent."""

    passed: bool
    issues: list[QualityIssue] = field(default_factory=list)
    checked_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "issues": [issue.to_dict() for issue in self.issues],
            "checked_at": self.checked_at,
        }


def run_quality_checks(content: PageContent, brand_config: dict[str, Any]) -> QualityResult:
    """Run all deterministic quality checks on generated content.

    Checks:
    1. Banned words from brand config vocabulary
    2. Em dash characters
    3. AI opener patterns
    4. Excessive triplet lists (>2 instances)
    5. Excessive rhetorical questions outside FAQ (>1)
    6. Tier 1 AI words (universal banned list)
    7. Tier 2 AI words (max 1 per piece)
    8. Negation/contrast pattern (max 1 per piece)
    9. Competitor brand names from vocabulary.competitors

    Args:
        content: PageContent with generated fields.
        brand_config: The BrandConfig.v2_schema dict.

    Returns:
        QualityResult with pass/fail and list of issues.
        Also stores result in content.qa_results.
    """
    issues: list[QualityIssue] = []

    # Gather field values
    fields = _get_content_fields(content)

    # Check 1: Banned words
    issues.extend(_check_banned_words(fields, brand_config))

    # Check 2: Em dashes
    issues.extend(_check_em_dashes(fields))

    # Check 3: AI opener patterns
    issues.extend(_check_ai_openers(fields))

    # Check 4: Excessive triplet lists
    issues.extend(_check_triplet_lists(fields))

    # Check 5: Excessive rhetorical questions
    issues.extend(_check_rhetorical_questions(fields))

    # Check 6: Tier 1 AI words
    issues.extend(_check_tier1_ai_words(fields))

    # Check 7: Tier 2 AI words (max 1 per piece)
    issues.extend(_check_tier2_ai_words(fields))

    # Check 8: Negation/contrast pattern (max 1 per piece)
    issues.extend(_check_negation_contrast(fields))

    # Check 9: Competitor brand names
    issues.extend(_check_competitor_names(fields, brand_config))

    result = QualityResult(
        passed=len(issues) == 0,
        issues=issues,
        checked_at=datetime.now(UTC).isoformat(),
    )

    # Store in PageContent.qa_results
    content.qa_results = result.to_dict()

    return result


def _get_content_fields(content: PageContent) -> dict[str, str]:
    """Extract content fields as a dict, skipping None values."""
    result: dict[str, str] = {}
    for field_name in CONTENT_FIELDS:
        value = getattr(content, field_name, None)
        if value:
            result[field_name] = value
    return result


def _strip_html_tags(text: str) -> str:
    """Strip HTML tags from text for clean context strings."""
    return re.sub(r"<[^>]+>", " ", text).replace("  ", " ").strip()


def _extract_context(text: str, start: int, end: int, pad: int = 30) -> str:
    """Extract context around a match, stripping HTML and adding ellipsis."""
    ctx_start = max(0, start - pad)
    ctx_end = min(len(text), end + pad)
    raw = text[ctx_start:ctx_end].strip()
    return f"...{_strip_html_tags(raw)}..."


def _check_banned_words(
    fields: dict[str, str],
    brand_config: dict[str, Any],
) -> list[QualityIssue]:
    """Check 1: Flag any words from brand config's banned_words list."""
    issues: list[QualityIssue] = []

    vocabulary = brand_config.get("vocabulary", {})
    if not isinstance(vocabulary, dict):
        return issues

    banned_words: list[str] = vocabulary.get("banned_words", [])
    if not banned_words:
        return issues

    for field_name, text in fields.items():
        for word in banned_words:
            pattern = re.compile(r"\b" + re.escape(word) + r"\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                issues.append(
                    QualityIssue(
                        type="banned_word",
                        field=field_name,
                        description=f'Banned word "{word}" detected',
                        context=_extract_context(text, match.start(), match.end()),
                    )
                )

    return issues


def _check_em_dashes(fields: dict[str, str]) -> list[QualityIssue]:
    """Check 2: Flag any em dash character (—) in any field."""
    issues: list[QualityIssue] = []

    for field_name, text in fields.items():
        for match in re.finditer("—", text):
            issues.append(
                QualityIssue(
                    type="em_dash",
                    field=field_name,
                    description="Em dash character detected",
                    context=_extract_context(text, match.start(), match.end()),
                )
            )

    return issues


def _check_ai_openers(fields: dict[str, str]) -> list[QualityIssue]:
    """Check 3: Flag common AI opener phrases."""
    issues: list[QualityIssue] = []

    for field_name, text in fields.items():
        for pattern_str in AI_OPENER_PATTERNS:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            for match in pattern.finditer(text):
                issues.append(
                    QualityIssue(
                        type="ai_pattern",
                        field=field_name,
                        description=f'AI opener pattern detected: "{_strip_html_tags(match.group())}"',
                        context=_extract_context(text, match.start(), match.end(), pad=40),
                    )
                )

    return issues


def _check_triplet_lists(fields: dict[str, str]) -> list[QualityIssue]:
    """Check 4: Flag each 'X, Y, and Z' pattern instance if total exceeds 2."""
    issues: list[QualityIssue] = []
    all_matches: list[tuple[str, re.Match]] = []

    for field_name, text in fields.items():
        for match in TRIPLET_PATTERN.finditer(text):
            all_matches.append((field_name, match))

    if len(all_matches) > 2:
        for field_name, match in all_matches:
            text = fields[field_name]
            issues.append(
                QualityIssue(
                    type="triplet_excess",
                    field=field_name,
                    description=f"Triplet list ({len(all_matches)} total, max 2)",
                    context=_extract_context(text, match.start(), match.end()),
                )
            )

    return issues


def _check_rhetorical_questions(fields: dict[str, str]) -> list[QualityIssue]:
    """Check 5: Flag each rhetorical question outside FAQ if total exceeds 1."""
    issues: list[QualityIssue] = []
    all_questions: list[tuple[str, re.Match]] = []

    for field_name, text in fields.items():
        check_text = text
        if field_name == "bottom_description":
            check_text = _strip_faq_section(text)

        for match in re.finditer(r"[^.!?\n]*\?", check_text):
            question = match.group().strip()
            if len(question) > 5:
                all_questions.append((field_name, match))

    if len(all_questions) > 1:
        for field_name, match in all_questions:
            text = fields[field_name]
            if field_name == "bottom_description":
                text = _strip_faq_section(text)
            issues.append(
                QualityIssue(
                    type="rhetorical_excess",
                    field=field_name,
                    description=f"Rhetorical question ({len(all_questions)} total, max 1)",
                    context=_extract_context(text, match.start(), match.end()),
                )
            )

    return issues


def _strip_faq_section(html: str) -> str:
    """Remove FAQ section from HTML content for rhetorical question checking.

    Looks for common FAQ heading patterns and removes everything from
    the FAQ heading to the end of the content (or next major heading).
    """
    # Match FAQ headings like <h2>FAQ</h2>, <h2>Frequently Asked Questions</h2>, etc.
    # Use [^<]* instead of .*? to avoid matching across multiple tags
    faq_pattern = re.compile(
        r"<h[23][^>]*>[^<]*(?:FAQ|Frequently\s+Asked\s+Questions)[^<]*</h[23]>",
        re.IGNORECASE,
    )
    match = faq_pattern.search(html)
    if match:
        # Return everything before the FAQ section
        return html[: match.start()]
    return html


def _check_tier1_ai_words(fields: dict[str, str]) -> list[QualityIssue]:
    """Check 6: Flag any Tier 1 AI words (universal banned list)."""
    issues: list[QualityIssue] = []

    for field_name, text in fields.items():
        for word in TIER1_AI_WORDS:
            pattern = re.compile(r"\b" + re.escape(word) + r"\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                issues.append(
                    QualityIssue(
                        type="tier1_ai_word",
                        field=field_name,
                        description=f'Tier 1 AI word "{word}" detected',
                        context=_extract_context(text, match.start(), match.end()),
                    )
                )

    return issues


def _check_tier2_ai_words(fields: dict[str, str]) -> list[QualityIssue]:
    """Check 7: Flag each Tier 2 AI word if total exceeds 1."""
    issues: list[QualityIssue] = []
    found: list[tuple[str, str, re.Match]] = []

    for field_name, text in fields.items():
        for word in TIER2_AI_WORDS:
            pattern = re.compile(r"\b" + re.escape(word) + r"\b", re.IGNORECASE)
            match = pattern.search(text)
            if match:
                found.append((field_name, word, match))

    if len(found) > 1:
        for field_name, word, match in found:
            text = fields[field_name]
            issues.append(
                QualityIssue(
                    type="tier2_ai_excess",
                    field=field_name,
                    description=f'Tier 2 AI word "{word}" ({len(found)} total, max 1)',
                    context=_extract_context(text, match.start(), match.end()),
                )
            )

    return issues


def _check_negation_contrast(fields: dict[str, str]) -> list[QualityIssue]:
    """Check 8: Flag each negation/contrast pattern if total exceeds 1."""
    issues: list[QualityIssue] = []
    all_matches: list[tuple[str, re.Match]] = []

    for field_name, text in fields.items():
        for match in NEGATION_PATTERN.finditer(text):
            all_matches.append((field_name, match))

    if len(all_matches) > 1:
        for field_name, match in all_matches:
            text = fields[field_name]
            issues.append(
                QualityIssue(
                    type="negation_contrast",
                    field=field_name,
                    description=f"Negation/contrast pattern ({len(all_matches)} total, max 1)",
                    context=_extract_context(text, match.start(), match.end()),
                )
            )

    return issues


def _check_competitor_names(
    fields: dict[str, str],
    brand_config: dict[str, Any],
) -> list[QualityIssue]:
    """Check 9: Flag any competitor brand names found in content."""
    issues: list[QualityIssue] = []

    vocabulary = brand_config.get("vocabulary", {})
    if not isinstance(vocabulary, dict):
        return issues

    competitors: list[str] = vocabulary.get("competitors", [])
    if not competitors:
        return issues

    for field_name, text in fields.items():
        for name in competitors:
            pattern = re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                issues.append(
                    QualityIssue(
                        type="competitor_name",
                        field=field_name,
                        description=f'Competitor name "{name}" detected',
                        context=_extract_context(text, match.start(), match.end()),
                    )
                )

    return issues
