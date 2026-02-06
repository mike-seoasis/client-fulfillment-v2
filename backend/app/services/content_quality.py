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
        text_lower = text.lower()
        for word in banned_words:
            word_lower = word.lower()
            # Use word boundary matching for accurate detection
            pattern = re.compile(r"\b" + re.escape(word_lower) + r"\b", re.IGNORECASE)
            if pattern.search(text_lower):
                # Find surrounding context
                match = pattern.search(text)
                if match:
                    start = max(0, match.start() - 30)
                    end = min(len(text), match.end() + 30)
                    context = text[start:end].strip()
                    issues.append(
                        QualityIssue(
                            type="banned_word",
                            field=field_name,
                            description=f'Banned word "{word}" detected',
                            context=f"...{context}...",
                        )
                    )

    return issues


def _check_em_dashes(fields: dict[str, str]) -> list[QualityIssue]:
    """Check 2: Flag any em dash character (—) in any field."""
    issues: list[QualityIssue] = []

    for field_name, text in fields.items():
        for match in re.finditer("—", text):
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()
            issues.append(
                QualityIssue(
                    type="em_dash",
                    field=field_name,
                    description="Em dash character detected",
                    context=f"...{context}...",
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
                start = max(0, match.start() - 10)
                end = min(len(text), match.end() + 40)
                context = text[start:end].strip()
                issues.append(
                    QualityIssue(
                        type="ai_pattern",
                        field=field_name,
                        description=f'AI opener pattern detected: "{match.group()}"',
                        context=f"...{context}...",
                    )
                )

    return issues


def _check_triplet_lists(fields: dict[str, str]) -> list[QualityIssue]:
    """Check 4: Flag if more than 2 'X, Y, and Z' pattern instances across all fields."""
    issues: list[QualityIssue] = []
    all_matches: list[tuple[str, str]] = []  # (field_name, matched_text)

    for field_name, text in fields.items():
        for match in TRIPLET_PATTERN.finditer(text):
            all_matches.append((field_name, match.group().strip()))

    if len(all_matches) > 2:
        examples = [f"{fname}: \"{matched}\"" for fname, matched in all_matches[:3]]
        issues.append(
            QualityIssue(
                type="triplet_excess",
                field="multiple",
                description=f"Excessive triplet lists: {len(all_matches)} instances (max 2)",
                context="; ".join(examples),
            )
        )

    return issues


def _check_rhetorical_questions(fields: dict[str, str]) -> list[QualityIssue]:
    """Check 5: Flag if more than 1 rhetorical question outside FAQ section."""
    issues: list[QualityIssue] = []
    all_questions: list[tuple[str, str]] = []  # (field_name, question_text)

    for field_name, text in fields.items():
        # Strip FAQ section from bottom_description before checking
        check_text = text
        if field_name == "bottom_description":
            check_text = _strip_faq_section(text)

        # Find sentences ending with ? that are not in FAQ context
        for match in re.finditer(r"[^.!?\n]*\?", check_text):
            question = match.group().strip()
            if len(question) > 5:  # Skip trivially short matches
                all_questions.append((field_name, question))

    if len(all_questions) > 1:
        examples = [f"{fname}: \"{q}\"" for fname, q in all_questions[:3]]
        issues.append(
            QualityIssue(
                type="rhetorical_excess",
                field="multiple",
                description=f"Excessive rhetorical questions: {len(all_questions)} found outside FAQ (max 1)",
                context="; ".join(examples),
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
