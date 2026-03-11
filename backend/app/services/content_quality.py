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
CONTENT_FIELDS = (
    "page_title",
    "meta_description",
    "top_description",
    "bottom_description",
)

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
    "delve",
    "delving",
    "unpack",
    "uncover",
    "unlock",
    "unleash",
    "harness",
    "leverage",
    "tap into",
    "embark",
    "navigate",
    "landscape",
    "realm",
    "at the forefront",
    "game-changer",
    "revolutionary",
    "transformative",
    "cutting-edge",
    "groundbreaking",
    "unprecedented",
    "crucial",
    "essential",
    "vital",
    "pivotal",
    "critical",
]

# Tier 2: AI words allowed max 1 per piece
TIER2_AI_WORDS = [
    "indeed",
    "furthermore",
    "moreover",
    "therefore",
    "additionally",
    "consequently",
    "subsequently",
    "accordingly",
    "notably",
    "significantly",
    "robust",
    "seamless",
    "comprehensive",
    "streamline",
    "enhance",
    "optimize",
    "elevate",
    "curated",
    "tailored",
    "bespoke",
    "nuanced",
    "intricate",
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
    bibles_matched: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "passed": self.passed,
            "issues": [issue.to_dict() for issue in self.issues],
            "checked_at": self.checked_at,
        }
        if self.bibles_matched:
            d["bibles_matched"] = self.bibles_matched
        return d


def run_quality_checks(
    content: PageContent,
    brand_config: dict[str, Any],
    matched_bibles: list[Any] | None = None,
) -> QualityResult:
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

    # Checks 14-17: Bible-driven checks
    bible_names: list[str] = []
    if matched_bibles:
        for bible in matched_bibles:
            qa_rules = getattr(bible, "qa_rules", None) or {}
            name = getattr(bible, "name", "Bible")
            if qa_rules:
                issues.extend(_check_bible_preferred_terms(fields, qa_rules, name))
                issues.extend(_check_bible_banned_claims(fields, qa_rules, name))
                issues.extend(_check_bible_wrong_attribution(fields, qa_rules, name))
                issues.extend(_check_bible_term_context(fields, qa_rules, name))
                bible_names.append(name)

    result = QualityResult(
        passed=len(issues) == 0,
        issues=issues,
        checked_at=datetime.now(UTC).isoformat(),
        bibles_matched=bible_names,
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


def _word_boundary_pattern(term: str) -> str:
    """Build a regex pattern with correct word boundaries for the given term.

    Standard \\b only works at word-character boundaries. For terms that start
    or end with non-word characters (e.g., C++, .NET, Node.js), we use
    lookahead/lookbehind assertions instead.
    """
    escaped = re.escape(term)
    prefix = r"\b" if re.match(r"\w", term) else r"(?<!\w)"
    suffix = r"\b" if re.search(r"\w$", term) else r"(?!\w)"
    return prefix + escaped + suffix


def _strip_html_tags(text: str) -> str:
    """Strip HTML tags from text for clean context strings."""
    return re.sub(r"<[^>]+>", " ", text).replace("  ", " ").strip()


def _extract_context(text: str, start: int, end: int, pad: int = 30) -> str:
    """Extract context around a match, stripping HTML and adding ellipsis."""
    ctx_start = max(0, start - pad)
    ctx_end = min(len(text), end + pad)
    raw = text[ctx_start:ctx_end].strip()
    return f"...{_strip_html_tags(raw)}..."


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences after stripping HTML tags.

    Uses punctuation boundaries (.!?) to split, but avoids splitting on
    common abbreviations (Dr., Mr., Mrs., Ms., Inc., Ltd., Jr., Sr., vs.,
    e.g., i.e., U.S., etc.) and single uppercase initials (A. B. Smith).

    Returns non-empty sentences.
    """
    plain = _strip_html_tags(text)
    # Common abbreviations that should not trigger a sentence split
    _ABBREVS = (
        "Dr", "Mr", "Mrs", "Ms", "Prof", "Sr", "Jr", "Inc", "Ltd", "Corp",
        "vs", "etc", "approx", "dept", "est", "govt", "e\\.g", "i\\.e",
    )
    abbrev_pattern = (
        r"(?:"
        + "|".join(rf"(?<!\w){a}\." for a in _ABBREVS)
        + r"|(?<=[A-Z])\.(?=\s+[A-Z]\.)"  # single-letter initials like U.S.A.
        + r")"
    )
    # Replace abbreviation dots with a placeholder
    placeholder = "\x00"
    protected = re.sub(abbrev_pattern, lambda m: m.group().replace(".", placeholder), plain, flags=re.IGNORECASE)
    parts = re.split(r"(?<=[.!?])\s+", protected)
    # Restore placeholders
    return [s.replace(placeholder, ".").strip() for s in parts if s.replace(placeholder, ".").strip()]


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
                        context=_extract_context(
                            text, match.start(), match.end(), pad=40
                        ),
                    )
                )

    return issues


def _check_triplet_lists(fields: dict[str, str]) -> list[QualityIssue]:
    """Check 4: Flag each 'X, Y, and Z' pattern instance if total exceeds 2."""
    issues: list[QualityIssue] = []
    all_matches: list[tuple[str, re.Match[str]]] = []

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
    all_questions: list[tuple[str, re.Match[str]]] = []

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
    found: list[tuple[str, str, re.Match[str]]] = []

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
    all_matches: list[tuple[str, re.Match[str]]] = []

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


# ---------------------------------------------------------------------------
# Bible-driven quality checks (14-17)
# ---------------------------------------------------------------------------


def _check_bible_preferred_terms(
    fields: dict[str, str],
    qa_rules: dict[str, Any],
    bible_name: str,
) -> list[QualityIssue]:
    """Check 14: Flag deprecated terms that should use preferred alternatives.

    qa_rules key: preferred_terms — list of {use, instead_of} dicts.
    Matches word-boundary, case-insensitive.
    """
    issues: list[QualityIssue] = []
    preferred_terms = qa_rules.get("preferred_terms")
    if not isinstance(preferred_terms, list):
        return issues

    for entry in preferred_terms:
        if not isinstance(entry, dict):
            continue
        use = entry.get("use", "")
        instead_of = entry.get("instead_of", "")
        if not use or not instead_of or not isinstance(instead_of, str):
            continue

        pattern = re.compile(_word_boundary_pattern(instead_of), re.IGNORECASE)
        for field_name, text in fields.items():
            for match in pattern.finditer(text):
                issues.append(
                    QualityIssue(
                        type="bible_preferred_term",
                        field=field_name,
                        description=(
                            f'[{bible_name}] Use "{use}" instead of "{instead_of}"'
                        ),
                        context=_extract_context(text, match.start(), match.end()),
                    )
                )

    return issues


def _check_bible_banned_claims(
    fields: dict[str, str],
    qa_rules: dict[str, Any],
    bible_name: str,
) -> list[QualityIssue]:
    """Check 15: Flag banned claims that should not appear in content.

    qa_rules key: banned_claims — list of {claim, context, reason} dicts.
    If context is provided, both claim and context must appear in the same sentence.
    If no context, flag the claim anywhere.
    """
    issues: list[QualityIssue] = []
    banned_claims = qa_rules.get("banned_claims")
    if not isinstance(banned_claims, list):
        return issues

    for entry in banned_claims:
        if not isinstance(entry, dict):
            continue
        claim = entry.get("claim", "")
        if not claim or not isinstance(claim, str):
            continue
        context_word = entry.get("context", "")
        if not isinstance(context_word, str):
            context_word = ""
        reason = entry.get("reason", "")

        claim_pattern = re.compile(re.escape(claim), re.IGNORECASE)

        for field_name, text in fields.items():
            if context_word:
                # Same-sentence co-occurrence (substring match on context —
                # intentionally not word-boundary to allow plural forms
                # like "needle" matching "needles")
                for sentence in _split_sentences(text):
                    if claim_pattern.search(sentence) and re.search(
                        re.escape(context_word), sentence, re.IGNORECASE
                    ):
                        desc = f'[{bible_name}] Banned claim "{claim}" near "{context_word}"'
                        if reason:
                            desc += f" — {reason}"
                        issues.append(
                            QualityIssue(
                                type="bible_banned_claim",
                                field=field_name,
                                description=desc,
                                context=f"...{sentence[:80]}...",
                            )
                        )
            else:
                # Flag claim anywhere
                for match in claim_pattern.finditer(text):
                    desc = f'[{bible_name}] Banned claim "{claim}"'
                    if reason:
                        desc += f" — {reason}"
                    issues.append(
                        QualityIssue(
                            type="bible_banned_claim",
                            field=field_name,
                            description=desc,
                            context=_extract_context(
                                text, match.start(), match.end()
                            ),
                        )
                    )

    return issues


def _check_bible_wrong_attribution(
    fields: dict[str, str],
    qa_rules: dict[str, Any],
    bible_name: str,
) -> list[QualityIssue]:
    """Check 16: Flag wrong product/feature attribution.

    qa_rules key: feature_attribution — list of
    {feature, correct_component, wrong_components} dicts.
    Flags when feature and any wrong_component appear in the same sentence.
    """
    issues: list[QualityIssue] = []
    attributions = qa_rules.get("feature_attribution")
    if not isinstance(attributions, list):
        return issues

    for entry in attributions:
        if not isinstance(entry, dict):
            continue
        feature = entry.get("feature", "")
        correct = entry.get("correct_component", "")
        wrong_components = entry.get("wrong_components", [])
        if not feature or not isinstance(feature, str) or not isinstance(wrong_components, list):
            continue

        for field_name, text in fields.items():
            for sentence in _split_sentences(text):
                if not re.search(re.escape(feature), sentence, re.IGNORECASE):
                    continue
                for wrong in wrong_components:
                    if not isinstance(wrong, str) or not wrong:
                        continue
                    if re.search(re.escape(wrong), sentence, re.IGNORECASE):
                        issues.append(
                            QualityIssue(
                                type="bible_wrong_attribution",
                                field=field_name,
                                description=(
                                    f'[{bible_name}] "{feature}" belongs to '
                                    f'"{correct}", not "{wrong}"'
                                ),
                                context=f"...{sentence[:80]}...",
                            )
                        )

    return issues


def _check_bible_term_context(
    fields: dict[str, str],
    qa_rules: dict[str, Any],
    bible_name: str,
) -> list[QualityIssue]:
    """Check 17: Flag terms used in wrong context.

    qa_rules key: term_context_rules — list of
    {term, wrong_contexts, explanation} dicts.
    Flags when term and any wrong_context appear in the same sentence.
    """
    issues: list[QualityIssue] = []
    rules = qa_rules.get("term_context_rules")
    if not isinstance(rules, list):
        return issues

    for entry in rules:
        if not isinstance(entry, dict):
            continue
        term = entry.get("term", "")
        wrong_contexts = entry.get("wrong_contexts", [])
        explanation = entry.get("explanation", "")
        if not term or not isinstance(term, str) or not isinstance(wrong_contexts, list):
            continue

        for field_name, text in fields.items():
            for sentence in _split_sentences(text):
                if not re.search(
                    _word_boundary_pattern(term), sentence, re.IGNORECASE
                ):
                    continue
                for ctx in wrong_contexts:
                    if not isinstance(ctx, str) or not ctx:
                        continue
                    if re.search(re.escape(ctx), sentence, re.IGNORECASE):
                        desc = (
                            f'[{bible_name}] "{term}" used in wrong context '
                            f'near "{ctx}"'
                        )
                        if explanation:
                            desc += f" — {explanation}"
                        issues.append(
                            QualityIssue(
                                type="bible_term_context",
                                field=field_name,
                                description=desc,
                                context=f"...{sentence[:80]}...",
                            )
                        )

    return issues


# ---------------------------------------------------------------------------
# Blog-specific quality checks (Skill Bible integration)
# ---------------------------------------------------------------------------

# Tier 3: Banned phrases that signal AI-generated content
TIER3_OPENING_PHRASES = [
    "in today's fast-paced world",
    "in the digital age",
    "it's no secret that",
    "as we all know",
    "in a world where",
    "welcome to",
    "let's dive in",
    "let's unpack",
    "let's explore",
]

TIER3_FILLER_PHRASES = [
    "it's important to note that",
    "it's worth mentioning that",
    "it goes without saying",
    "needless to say",
    "at the end of the day",
    "due to the fact that",
    "in order to",
    "the fact of the matter is",
]

TIER3_CLOSING_PHRASES = [
    "in conclusion",
    "to summarize",
    "in summary",
    "the bottom line is",
    "all in all",
    "moving forward",
]

TIER3_HYPE_PHRASES = [
    "unlock the potential of",
    "unleash the power of",
    "pave the way for",
    "take it to the next level",
    "a testament to",
    "bridge the gap between",
    "foster a culture of",
]

ALL_TIER3_PHRASES = (
    TIER3_OPENING_PHRASES
    + TIER3_FILLER_PHRASES
    + TIER3_CLOSING_PHRASES
    + TIER3_HYPE_PHRASES
)

# Empty transition signposts that add no meaning
EMPTY_SIGNPOST_PHRASES = [
    "now, let's look at",
    "next, we'll explore",
    "with that in mind",
    "that said",
    "having established that",
    "let's now turn to",
    "moving on to",
]

# Tier 2 business jargon (always AI-sounding in blog content)
BUSINESS_JARGON_WORDS = [
    "synergy",
    "paradigm shift",
    "best-in-class",
    "state-of-the-art",
    "next-generation",
    "future-proof",
    "scalable",
    "agile",
    "holistic",
    "end-to-end",
    "value proposition",
    "pain points",
]


def _check_tier3_phrases(fields: dict[str, str]) -> list[QualityIssue]:
    """Check 10: Flag Tier 3 banned phrases (opening, filler, closing, hype)."""
    issues: list[QualityIssue] = []

    for field_name, text in fields.items():
        for phrase in ALL_TIER3_PHRASES:
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            for match in pattern.finditer(text):
                issues.append(
                    QualityIssue(
                        type="tier3_banned_phrase",
                        field=field_name,
                        description=f'Tier 3 banned phrase "{phrase}" detected',
                        context=_extract_context(text, match.start(), match.end()),
                    )
                )

    return issues


def _check_empty_signposts(fields: dict[str, str]) -> list[QualityIssue]:
    """Check 11: Flag empty transition signposts that add no meaning."""
    issues: list[QualityIssue] = []

    for field_name, text in fields.items():
        for phrase in EMPTY_SIGNPOST_PHRASES:
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            for match in pattern.finditer(text):
                issues.append(
                    QualityIssue(
                        type="empty_signpost",
                        field=field_name,
                        description=f'Empty signpost phrase "{phrase}" detected',
                        context=_extract_context(text, match.start(), match.end()),
                    )
                )

    return issues


def _check_missing_direct_answer(fields: dict[str, str]) -> list[QualityIssue]:
    """Check 12: For blog content, verify the article opens with a direct statement.

    Checks the first ~150 chars of the content field. Flags if it starts with
    a question or a known AI opener pattern instead of a direct answer.
    """
    issues: list[QualityIssue] = []

    content = fields.get("content", "")
    if not content:
        return issues

    # Strip HTML tags to get plain text, then take first 150 chars
    plain = re.sub(r"<[^>]+>", " ", content).strip()
    opening = plain[:150].strip()

    if not opening:
        return issues

    # Flag if opens with a question
    first_sentence_end = min(
        (opening.find(c) for c in ".!?" if opening.find(c) != -1),
        default=len(opening),
    )
    first_sentence = opening[: first_sentence_end + 1].strip()

    if first_sentence.endswith("?"):
        issues.append(
            QualityIssue(
                type="missing_direct_answer",
                field="content",
                description="Article opens with a question instead of a direct answer",
                context=f"...{first_sentence[:80]}...",
            )
        )
        return issues

    # Flag common AI opener patterns at the start
    ai_openers = [
        r"^in today'?s",
        r"^in the (?:digital|modern|fast)",
        r"^it'?s no secret",
        r"^as we all know",
        r"^in a world where",
        r"^welcome to",
    ]
    for pattern_str in ai_openers:
        if re.search(pattern_str, opening, re.IGNORECASE):
            issues.append(
                QualityIssue(
                    type="missing_direct_answer",
                    field="content",
                    description="Article opens with an AI pattern instead of a direct answer",
                    context=f"...{opening[:80]}...",
                )
            )
            break

    return issues


def _check_business_jargon(fields: dict[str, str]) -> list[QualityIssue]:
    """Check 13: Flag business jargon that sounds AI-generated in blog content."""
    issues: list[QualityIssue] = []

    for field_name, text in fields.items():
        for term in BUSINESS_JARGON_WORDS:
            pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                issues.append(
                    QualityIssue(
                        type="business_jargon",
                        field=field_name,
                        description=f'Business jargon "{term}" detected',
                        context=_extract_context(text, match.start(), match.end()),
                    )
                )

    return issues


def _run_standard_checks(
    fields: dict[str, str],
    brand_config: dict[str, Any],
    matched_bibles: list[Any] | None = None,
) -> tuple[list[QualityIssue], list[str]]:
    """Run the 9 standard checks + bible checks on a fields dict.

    Returns:
        Tuple of (issues, bible_names).
    """
    issues: list[QualityIssue] = []

    # Standard checks (1-9)
    issues.extend(_check_banned_words(fields, brand_config))
    issues.extend(_check_em_dashes(fields))
    issues.extend(_check_ai_openers(fields))
    issues.extend(_check_triplet_lists(fields))
    issues.extend(_check_rhetorical_questions(fields))
    issues.extend(_check_tier1_ai_words(fields))
    issues.extend(_check_tier2_ai_words(fields))
    issues.extend(_check_negation_contrast(fields))
    issues.extend(_check_competitor_names(fields, brand_config))

    # Checks 14-17: Bible-driven checks
    bible_names: list[str] = []
    if matched_bibles:
        for bible in matched_bibles:
            qa_rules = getattr(bible, "qa_rules", None) or {}
            name = getattr(bible, "name", "Bible")
            if qa_rules:
                issues.extend(_check_bible_preferred_terms(fields, qa_rules, name))
                issues.extend(_check_bible_banned_claims(fields, qa_rules, name))
                issues.extend(_check_bible_wrong_attribution(fields, qa_rules, name))
                issues.extend(_check_bible_term_context(fields, qa_rules, name))
                bible_names.append(name)

    return issues, bible_names


def run_fields_quality_checks(
    fields: dict[str, str],
    brand_config: dict[str, Any],
    matched_bibles: list[Any] | None = None,
) -> QualityResult:
    """Run the 9 standard quality checks on a fields dict (no blog-specific checks).

    Used for re-checking page content after auto-rewrite, where we need
    a fields-based check without blog-specific checks 10-13.

    Args:
        fields: Dict of field_name -> text content to check.
        brand_config: The BrandConfig.v2_schema dict.
        matched_bibles: Optional bible objects for domain-specific checks.

    Returns:
        QualityResult with pass/fail and list of issues.
    """
    issues, bible_names = _run_standard_checks(fields, brand_config, matched_bibles)

    return QualityResult(
        passed=len(issues) == 0,
        issues=issues,
        checked_at=datetime.now(UTC).isoformat(),
        bibles_matched=bible_names,
    )


def run_blog_quality_checks(
    fields: dict[str, str],
    brand_config: dict[str, Any],
    matched_bibles: list[Any] | None = None,
) -> QualityResult:
    """Run all quality checks including blog-specific checks.

    Runs the 9 standard checks plus 4 blog-specific checks (13 total).
    Designed to be called from blog_content_generation.py.

    Args:
        fields: Dict of field_name -> text content to check.
        brand_config: The BrandConfig.v2_schema dict.

    Returns:
        QualityResult with pass/fail and list of issues.
    """
    issues, bible_names = _run_standard_checks(fields, brand_config, matched_bibles)

    # Blog-specific checks (10-13)
    issues.extend(_check_tier3_phrases(fields))
    issues.extend(_check_empty_signposts(fields))
    issues.extend(_check_missing_direct_answer(fields))
    issues.extend(_check_business_jargon(fields))

    return QualityResult(
        passed=len(issues) == 0,
        issues=issues,
        checked_at=datetime.now(UTC).isoformat(),
        bibles_matched=bible_names,
    )
