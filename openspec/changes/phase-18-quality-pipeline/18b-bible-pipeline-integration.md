# 18b: Bible Pipeline Integration

## Overview

Wire vertical knowledge bibles into the content generation pipeline at two integration points:

1. **Prompt injection** -- Matched bible `content_md` is injected as a `## Domain Knowledge` section in the user prompt so Claude writes domain-accurate content from the start.
2. **QA checks** -- Matched bible `qa_rules` drive four new deterministic checks that catch domain-specific errors the generic 13 checks cannot detect.

Both integration points apply to all three content pipelines: onboarding pages, blog posts, and the recheck endpoint. The blog pipeline's `_run_blog_quality_checks` wrapper also gets bible checks.

**Prerequisite:** 18a (Bible Data Layer) must be complete. This plan assumes the following exist:
- `backend/app/models/vertical_bible.py` -- `VerticalBible` SQLAlchemy model with `project_id`, `name`, `slug`, `content_md`, `trigger_keywords` (JSONB array), `qa_rules` (JSONB dict), `sort_order`, `is_active`
- `backend/app/services/vertical_bible.py` -- CRUD service with `match_bibles(project_id, keyword) -> list[VerticalBible]` that does word-boundary substring matching of `trigger_keywords` against the page keyword

---

## Decisions (Planner vs. Advocate Debate)

### 1. Token limit risk from bible injection

**Planner:** Inject matched bibles' `content_md` into the user prompt between `## SEO Targets` and `## Brand Voice`. Cap at 8000 characters total.

**Advocate:** What is the current prompt size? The system prompt is ~2,000 chars. The user prompt varies: `## Task` (~100), `## Page Context` (~300), `## SEO Targets` (500-3,000 depending on POP data), `## Brand Voice` (~200), `## Output Format` (~800). Typical total: ~3,500-6,400 chars. Adding 8,000 chars of bible content nearly doubles the prompt. Claude Sonnet 4.5 has a 200k context window, so token limits are not a concern. But longer prompts increase cost and latency.

**Resolution:** 8,000 char max guard is correct. This is ~2,000 tokens, adding ~$0.006 per page at Sonnet's $3/1M input pricing -- negligible. Typical bible `content_md` will be 2,000-5,000 chars. Multiple bibles concatenate with `sort_order` priority, and the guard truncates at 8,000. Log a warning if truncation occurs so operators know to trim their bibles.

### 2. Sentence-level co-occurrence: too aggressive or too loose?

**Planner:** Split content into sentences, check if a term and its wrong context co-occur in the same sentence.

**Advocate:** Sentence splitting is fragile with HTML content. What about `<p>` and `<li>` boundaries? "Membrane" in one `<li>` and "ink savings" in the next `<li>` inside the same `<ul>` would be a miss. Also, regex sentence splitting fails on abbreviations ("Dr. Smith uses...").

**Resolution:** Strip HTML tags first, then split on `(?<=[.!?])\s+` as a simple sentence boundary. This catches the vast majority of cases. We accept false negatives for cross-sentence violations (better to miss some than produce false positives). The LLM judge in Phase 18e will catch cross-sentence issues. For `<li>` elements, the HTML stripping naturally joins them into flowing text, so "saves ink. membrane" from adjacent list items would be separate sentences -- correctly not flagged as same-sentence co-occurrence.

### 3. Partial matches ("needle config" matching "needle configuration")

**Planner:** Use `re.escape(term)` with `\b` word boundaries for preferred_terms and banned_claims.

**Advocate:** "needle config" would NOT match "needle configuration" because `\b` after "config" requires a word boundary, and the "u" in "configuration" is a word character. This is correct behavior -- we want exact term matching. If the operator wants to catch both, they add both to the `instead_of` list. Alternatively, we could omit the trailing `\b` for multi-word phrases.

**Resolution:** Use `\b` on both sides for single words. For multi-word `instead_of` phrases, use `\b` at the start and `\b` at the end. This means "needle config" matches "needle config" but not "needle configuration". This is the safer choice -- false positives are worse than false negatives for domain-specific checks. Document this in the bible editor help text (Phase 18c concern).

### 4. Bible checks: warnings or errors?

**Planner:** All bible checks should have `confidence = 1.0` like other Tier 1 checks.

**Advocate:** These are human-authored rules that may be overly broad or stale. A "banned_claim" rule might trigger on legitimate usage. Making them errors (same as `tier1_ai_word`) means they fail the QA pass, which could frustrate operators.

**Resolution:** Bible checks are errors (confidence 1.0) and cause `passed=false` just like other Tier 1 checks. Rationale: the operator explicitly created these rules to enforce domain accuracy. If a rule is too aggressive, the fix is to edit or delete the rule, not to silently ignore it. The "Domain Checks" section in the Quality Panel (Phase 18d) will clearly show which bible triggered each issue, making it easy to trace back and edit the rule.

### 5. Empty or malformed qa_rules

**Advocate:** What if `qa_rules` is `null`, `{}`, has unexpected keys, or has rules with missing fields?

**Resolution:** Every `_check_bible_*` function receives the full `qa_rules` dict and extracts its own key (e.g., `qa_rules.get("preferred_terms", [])`). Each rule dict is validated defensively: skip any rule missing required fields. Log a warning for malformed rules but never crash the pipeline. Empty `qa_rules` simply means zero bible QA issues -- the checks return empty lists.

### 6. ReDoS risk from user-provided qa_rules

**Advocate:** If `qa_rules` contain regex-hostile strings (e.g., `"(a+)+$"`), could `re.compile(re.escape(term))` cause ReDoS?

**Resolution:** We use `re.escape()` on all user-provided terms before compiling. `re.escape()` escapes all regex metacharacters, making the pattern literal. There is zero ReDoS risk because the compiled pattern is a simple string literal with word boundaries. No user-provided regex is ever executed.

### 7. Multiple bibles matching -- do checks accumulate?

**Planner:** All matched bibles contribute QA rules. Issues from different bibles accumulate.

**Advocate:** This is correct. If "Tattoo Needles" bible flags "membrane saves ink" and "Tattoo Inks" bible flags "solvent-free" as banned, both appear in the issues list. The `bibles_matched` list in `qa_results` tracks which bibles were checked.

**Resolution:** Yes, accumulate. Each `QualityIssue` description includes the bible name for traceability (e.g., `'Bible "Tattoo Cartridge Needles": wrong term "needle configuration" -- use "needle grouping"'`).

### 8. Naming consistency

**Advocate:** Existing checks follow `_check_{type}(fields, ...)`. The new checks should follow the same pattern.

**Resolution:** New functions:
- `_check_bible_preferred_terms(fields, qa_rules, bible_name)`
- `_check_bible_banned_claims(fields, qa_rules, bible_name)`
- `_check_bible_wrong_attribution(fields, qa_rules, bible_name)`
- `_check_bible_term_context(fields, qa_rules, bible_name)`

All accept the same `fields: dict[str, str]` first argument. They return `list[QualityIssue]` just like every other check.

### 9. HTML content -- strip tags before checking?

**Advocate:** `bottom_description` and blog `content` contain HTML. Do we check raw HTML or stripped text?

**Resolution:** Check the raw HTML text (same as all existing checks). The existing checks like `_check_banned_words` already operate on raw HTML and it works correctly because word-boundary regex matches work through HTML tags. The `_extract_context` helper already strips HTML from the context snippet shown to operators. Consistency with existing checks is more important than theoretical purity.

### 10. Where exactly does bible data flow?

**Advocate:** The current `_process_single_page` loads `brand_config` once and passes it through. Bibles need `project_id` and `keyword` to match. Where do we load them?

**Resolution:** Load bibles at the same level as `brand_config` -- in the read-only session at the top of `run_content_pipeline()`. The matched bibles depend on the keyword, which varies per page, so we must match per-page. But loading all active bibles for a project once (they're lightweight) and matching per-page in `_process_single_page` is more efficient than N database queries. Pass `project_bibles: list[VerticalBible]` through the pipeline, then match per-page using `keyword`.

---

## Prompt Injection (content_writing.py)

### New function: `_build_domain_knowledge_section`

**Location:** After `_build_brand_voice_section` (line 988), before `_build_output_format_section` (line 991).

```python
# Maximum characters for all bible content_md combined
BIBLE_PROMPT_MAX_CHARS = 8000


def _build_domain_knowledge_section(matched_bibles: list[Any]) -> str | None:
    """Build the ## Domain Knowledge section from matched vertical bibles.

    Concatenates content_md from matched bibles (sorted by sort_order),
    with an 8000-char guard to prevent prompt bloat.

    Args:
        matched_bibles: List of VerticalBible objects matched for this page's keyword.

    Returns:
        Prompt section string, or None if no bibles matched.
    """
    if not matched_bibles:
        return None

    lines = [
        "## Domain Knowledge",
        "The following domain expertise MUST inform your writing. Follow these "
        "rules exactly -- incorrect claims or wrong terminology will be flagged:",
        "",
    ]

    total_chars = 0
    truncated = False

    for bible in matched_bibles:
        content_md = getattr(bible, "content_md", "") or ""
        if not content_md.strip():
            continue

        bible_name = getattr(bible, "name", "Unknown")

        # Check if adding this bible would exceed the limit
        section = f"### {bible_name}\n{content_md.strip()}\n"
        if total_chars + len(section) > BIBLE_PROMPT_MAX_CHARS:
            # Truncate to fit remaining budget
            remaining = BIBLE_PROMPT_MAX_CHARS - total_chars
            if remaining > 200:  # Only add if we have meaningful space
                section = section[:remaining] + "\n[...truncated]"
                lines.append(section)
                truncated = True
            break

        lines.append(section)
        total_chars += len(section)

    # Only return if we actually added content
    if total_chars == 0:
        return None

    if truncated:
        logger.warning(
            "Bible content truncated to fit prompt budget",
            extra={
                "total_chars": total_chars,
                "max_chars": BIBLE_PROMPT_MAX_CHARS,
                "bible_count": len(matched_bibles),
            },
        )

    return "\n".join(lines)
```

### Signature changes

#### `build_content_prompt` (line 162)

**Before:**
```python
def build_content_prompt(
    page: CrawledPage,
    keyword: str,
    brand_config: dict[str, Any],
    content_brief: ContentBrief | None = None,
) -> PromptPair:
```

**After:**
```python
def build_content_prompt(
    page: CrawledPage,
    keyword: str,
    brand_config: dict[str, Any],
    content_brief: ContentBrief | None = None,
    matched_bibles: list[Any] | None = None,
) -> PromptPair:
```

Implementation change at line 185:
```python
    system_prompt = _build_system_prompt(brand_config)
    user_prompt = _build_user_prompt(page, keyword, brand_config, content_brief, matched_bibles)
    return PromptPair(system_prompt=system_prompt, user_prompt=user_prompt)
```

#### `build_blog_content_prompt` (line 189)

**Before:**
```python
def build_blog_content_prompt(
    blog_post: BlogPost,
    keyword: str,
    brand_config: dict[str, Any],
    content_brief: ContentBrief | None = None,
    trend_context: dict[str, Any] | None = None,
) -> PromptPair:
```

**After:**
```python
def build_blog_content_prompt(
    blog_post: BlogPost,
    keyword: str,
    brand_config: dict[str, Any],
    content_brief: ContentBrief | None = None,
    trend_context: dict[str, Any] | None = None,
    matched_bibles: list[Any] | None = None,
) -> PromptPair:
```

Implementation change at line 214:
```python
    user_prompt = _build_blog_user_prompt(
        blog_post,
        keyword,
        brand_config,
        content_brief,
        trend_context=trend_context,
        matched_bibles=matched_bibles,
    )
```

### Injection point in `_build_user_prompt` (line 342)

**Current section ordering (lines 360-379):**
```python
    sections: list[str] = []
    # ## Task
    sections.append(_build_task_section(keyword))
    # ## Page Context
    sections.append(_build_page_context_section(page))
    # ## SEO Targets
    sections.append(_build_seo_targets_section(keyword, content_brief, brand_config))
    # ## Brand Voice
    brand_voice = _build_brand_voice_section(brand_config)
    if brand_voice:
        sections.append(brand_voice)
    # ## Output Format
    sections.append(_build_output_format_section(content_brief, brand_config))
    return "\n\n".join(sections)
```

**New ordering:**
```python
    sections: list[str] = []
    # ## Task
    sections.append(_build_task_section(keyword))
    # ## Page Context
    sections.append(_build_page_context_section(page))
    # ## SEO Targets
    sections.append(_build_seo_targets_section(keyword, content_brief, brand_config))
    # ## Domain Knowledge (from matched bibles)
    domain_knowledge = _build_domain_knowledge_section(matched_bibles or [])
    if domain_knowledge:
        sections.append(domain_knowledge)
    # ## Brand Voice
    brand_voice = _build_brand_voice_section(brand_config)
    if brand_voice:
        sections.append(brand_voice)
    # ## Output Format
    sections.append(_build_output_format_section(content_brief, brand_config))
    return "\n\n".join(sections)
```

The `_build_user_prompt` signature changes to accept `matched_bibles`:

```python
def _build_user_prompt(
    page: CrawledPage,
    keyword: str,
    brand_config: dict[str, Any],
    content_brief: ContentBrief | None,
    matched_bibles: list[Any] | None = None,
) -> str:
```

### Same change for `_build_blog_user_prompt` (line 382)

**New signature:**
```python
def _build_blog_user_prompt(
    blog_post: BlogPost,
    keyword: str,
    brand_config: dict[str, Any],
    content_brief: ContentBrief | None,
    trend_context: dict[str, Any] | None = None,
    matched_bibles: list[Any] | None = None,
) -> str:
```

**New injection point** (between `## SEO Targets` at line 415 and `## Recent Trends` at line 417):

```python
    # ## SEO Targets (reuse existing function)
    sections.append(_build_seo_targets_section(keyword, content_brief, brand_config))

    # ## Domain Knowledge (from matched bibles)
    domain_knowledge = _build_domain_knowledge_section(matched_bibles or [])
    if domain_knowledge:
        sections.append(domain_knowledge)

    # ## Recent Trends & Data (from Perplexity)
    freshness = _build_freshness_section(trend_context)
```

### Callers of `build_content_prompt`

1. **`content_writing.py:generate_content`** (line 1155) -- currently:
   ```python
   prompts = build_content_prompt(crawled_page, keyword, brand_config, content_brief)
   ```
   This function does not have access to `matched_bibles`. The bibles must be passed down from the pipeline. Add `matched_bibles` parameter to `generate_content`:

   **Before (line 1120):**
   ```python
   async def generate_content(
       db: AsyncSession,
       crawled_page: CrawledPage,
       content_brief: ContentBrief | None,
       brand_config: dict[str, Any],
       keyword: str,
   ) -> ContentWritingResult:
   ```

   **After:**
   ```python
   async def generate_content(
       db: AsyncSession,
       crawled_page: CrawledPage,
       content_brief: ContentBrief | None,
       brand_config: dict[str, Any],
       keyword: str,
       matched_bibles: list[Any] | None = None,
   ) -> ContentWritingResult:
   ```

   And line 1155:
   ```python
   prompts = build_content_prompt(crawled_page, keyword, brand_config, content_brief, matched_bibles)
   ```

2. **`content_outline.py`** -- `generate_outline` and `generate_content_from_outline` also call `build_content_prompt`. These should get the same `matched_bibles` parameter. This is a straightforward pass-through change.

3. **`blog_content_generation.py:_generate_blog_content`** (line 790) -- currently:
   ```python
   prompts = build_blog_content_prompt(
       blog_post,
       keyword,
       brand_config,
       content_brief,
       trend_context=trend_context,
   )
   ```
   Add `matched_bibles=matched_bibles` parameter.

---

## Bible QA Checks (content_quality.py)

### New helper: `_split_sentences`

```python
def _split_sentences(text: str) -> list[str]:
    """Split text into sentences for co-occurrence checks.

    Strips HTML tags first, then splits on sentence-ending punctuation
    followed by whitespace. Handles common abbreviations gracefully
    (Mr., Dr., etc. are rare in SEO content).

    Args:
        text: Raw content text (may contain HTML).

    Returns:
        List of sentence strings.
    """
    plain = _strip_html_tags(text)
    # Split on sentence-ending punctuation followed by whitespace or end of string
    sentences = re.split(r'(?<=[.!?])\s+', plain)
    return [s.strip() for s in sentences if s.strip()]
```

**Location:** After `_extract_context` (line 222), before `_check_banned_words` (line 225).

### Check 14: `_check_bible_preferred_terms`

```python
def _check_bible_preferred_terms(
    fields: dict[str, str],
    qa_rules: dict[str, Any],
    bible_name: str,
) -> list[QualityIssue]:
    """Check 14: Flag wrong terms where a preferred alternative exists.

    Uses the qa_rules.preferred_terms list. Each rule has:
    - "use": the preferred term
    - "instead_of": the wrong term to detect

    Regex: word-boundary match on the "instead_of" term (case-insensitive).
    """
    issues: list[QualityIssue] = []

    preferred_terms = qa_rules.get("preferred_terms", [])
    if not isinstance(preferred_terms, list):
        return issues

    for rule in preferred_terms:
        if not isinstance(rule, dict):
            continue
        use_term = rule.get("use", "")
        instead_of = rule.get("instead_of", "")
        if not use_term or not instead_of:
            continue

        pattern = re.compile(r"\b" + re.escape(instead_of) + r"\b", re.IGNORECASE)

        for field_name, text in fields.items():
            for match in pattern.finditer(text):
                issues.append(
                    QualityIssue(
                        type="bible_preferred_term",
                        field=field_name,
                        description=(
                            f'[{bible_name}] Wrong term "{instead_of}" '
                            f'-- use "{use_term}" instead'
                        ),
                        context=_extract_context(text, match.start(), match.end()),
                    )
                )

    return issues
```

### Check 15: `_check_bible_banned_claims`

```python
def _check_bible_banned_claims(
    fields: dict[str, str],
    qa_rules: dict[str, Any],
    bible_name: str,
) -> list[QualityIssue]:
    """Check 15: Flag banned claims that co-occur with a context term.

    Uses the qa_rules.banned_claims list. Each rule has:
    - "claim": the banned phrase to detect
    - "context": a context term that must appear in the same sentence
    - "reason": explanation of why the claim is wrong

    If "context" is empty/missing, the claim is flagged anywhere it appears.
    If "context" is set, both claim and context must appear in the same sentence.
    """
    issues: list[QualityIssue] = []

    banned_claims = qa_rules.get("banned_claims", [])
    if not isinstance(banned_claims, list):
        return issues

    for rule in banned_claims:
        if not isinstance(rule, dict):
            continue
        claim = rule.get("claim", "")
        if not claim:
            continue
        context_term = rule.get("context", "")
        reason = rule.get("reason", "")

        claim_pattern = re.compile(re.escape(claim), re.IGNORECASE)

        for field_name, text in fields.items():
            if not context_term:
                # No context required -- flag claim anywhere
                for match in claim_pattern.finditer(text):
                    issues.append(
                        QualityIssue(
                            type="bible_banned_claim",
                            field=field_name,
                            description=(
                                f'[{bible_name}] Banned claim "{claim}"'
                                + (f" -- {reason}" if reason else "")
                            ),
                            context=_extract_context(
                                text, match.start(), match.end()
                            ),
                        )
                    )
            else:
                # Context required -- check same-sentence co-occurrence
                context_pattern = re.compile(
                    re.escape(context_term), re.IGNORECASE
                )
                for sentence in _split_sentences(text):
                    has_claim = claim_pattern.search(sentence)
                    has_context = context_pattern.search(sentence)
                    if has_claim and has_context:
                        issues.append(
                            QualityIssue(
                                type="bible_banned_claim",
                                field=field_name,
                                description=(
                                    f'[{bible_name}] Banned claim "{claim}" '
                                    f'with context "{context_term}"'
                                    + (f" -- {reason}" if reason else "")
                                ),
                                context=f"...{_strip_html_tags(sentence[:80])}...",
                            )
                        )

    return issues
```

### Check 16: `_check_bible_wrong_attribution`

```python
def _check_bible_wrong_attribution(
    fields: dict[str, str],
    qa_rules: dict[str, Any],
    bible_name: str,
) -> list[QualityIssue]:
    """Check 16: Flag features attributed to the wrong component.

    Uses the qa_rules.feature_attribution list. Each rule has:
    - "feature": the feature term (e.g., "membrane")
    - "correct_component": what it belongs to (e.g., "cartridge needle")
    - "wrong_components": list of wrong components (e.g., ["tattoo pen", "tattoo ink"])

    Flags when the feature and any wrong component appear in the same sentence.
    """
    issues: list[QualityIssue] = []

    attributions = qa_rules.get("feature_attribution", [])
    if not isinstance(attributions, list):
        return issues

    for rule in attributions:
        if not isinstance(rule, dict):
            continue
        feature = rule.get("feature", "")
        correct = rule.get("correct_component", "")
        wrong_components = rule.get("wrong_components", [])
        if not feature or not isinstance(wrong_components, list):
            continue

        feature_pattern = re.compile(
            r"\b" + re.escape(feature) + r"\b", re.IGNORECASE
        )

        for wrong_comp in wrong_components:
            if not wrong_comp:
                continue
            wrong_pattern = re.compile(
                r"\b" + re.escape(wrong_comp) + r"\b", re.IGNORECASE
            )

            for field_name, text in fields.items():
                for sentence in _split_sentences(text):
                    has_feature = feature_pattern.search(sentence)
                    has_wrong = wrong_pattern.search(sentence)
                    if has_feature and has_wrong:
                        issues.append(
                            QualityIssue(
                                type="bible_wrong_attribution",
                                field=field_name,
                                description=(
                                    f'[{bible_name}] "{feature}" attributed to '
                                    f'"{wrong_comp}" -- belongs to "{correct}"'
                                ),
                                context=f"...{_strip_html_tags(sentence[:80])}...",
                            )
                        )

    return issues
```

### Check 17: `_check_bible_term_context`

```python
def _check_bible_term_context(
    fields: dict[str, str],
    qa_rules: dict[str, Any],
    bible_name: str,
) -> list[QualityIssue]:
    """Check 17: Flag terms used with wrong contextual associations.

    Uses the qa_rules.term_context_rules list. Each rule has:
    - "term": the domain term to monitor (e.g., "membrane")
    - "correct_context": list of correct associations (informational only)
    - "wrong_contexts": list of wrong associations to flag
    - "explanation": why the wrong context is incorrect

    Flags when the term and any wrong context appear in the same sentence.
    """
    issues: list[QualityIssue] = []

    context_rules = qa_rules.get("term_context_rules", [])
    if not isinstance(context_rules, list):
        return issues

    for rule in context_rules:
        if not isinstance(rule, dict):
            continue
        term = rule.get("term", "")
        wrong_contexts = rule.get("wrong_contexts", [])
        explanation = rule.get("explanation", "")
        if not term or not isinstance(wrong_contexts, list):
            continue

        term_pattern = re.compile(
            r"\b" + re.escape(term) + r"\b", re.IGNORECASE
        )

        for wrong_ctx in wrong_contexts:
            if not wrong_ctx:
                continue
            wrong_pattern = re.compile(
                re.escape(wrong_ctx), re.IGNORECASE
            )

            for field_name, text in fields.items():
                for sentence in _split_sentences(text):
                    has_term = term_pattern.search(sentence)
                    has_wrong = wrong_pattern.search(sentence)
                    if has_term and has_wrong:
                        issues.append(
                            QualityIssue(
                                type="bible_term_context",
                                field=field_name,
                                description=(
                                    f'[{bible_name}] "{term}" used with '
                                    f'wrong context "{wrong_ctx}"'
                                    + (f" -- {explanation}" if explanation else "")
                                ),
                                context=f"...{_strip_html_tags(sentence[:80])}...",
                            )
                        )

    return issues
```

### Integration into `run_quality_checks` (line 134)

**Before (lines 134-199):**
```python
def run_quality_checks(
    content: PageContent, brand_config: dict[str, Any]
) -> QualityResult:
```

**After:**
```python
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
    14-17. Bible QA rule checks (if bibles matched)

    Args:
        content: PageContent with generated fields.
        brand_config: The BrandConfig.v2_schema dict.
        matched_bibles: Optional list of VerticalBible objects matched for this page.

    Returns:
        QualityResult with pass/fail and list of issues.
        Also stores result in content.qa_results.
    """
    issues: list[QualityIssue] = []

    # Gather field values
    fields = _get_content_fields(content)

    # Check 1-9: Standard checks (unchanged)
    issues.extend(_check_banned_words(fields, brand_config))
    issues.extend(_check_em_dashes(fields))
    issues.extend(_check_ai_openers(fields))
    issues.extend(_check_triplet_lists(fields))
    issues.extend(_check_rhetorical_questions(fields))
    issues.extend(_check_tier1_ai_words(fields))
    issues.extend(_check_tier2_ai_words(fields))
    issues.extend(_check_negation_contrast(fields))
    issues.extend(_check_competitor_names(fields, brand_config))

    # Checks 14-17: Bible QA rule checks
    bibles_matched: list[str] = []
    if matched_bibles:
        for bible in matched_bibles:
            bible_name = getattr(bible, "name", "Unknown")
            qa_rules = getattr(bible, "qa_rules", None) or {}
            if not isinstance(qa_rules, dict):
                continue
            bibles_matched.append(getattr(bible, "slug", bible_name))
            issues.extend(_check_bible_preferred_terms(fields, qa_rules, bible_name))
            issues.extend(_check_bible_banned_claims(fields, qa_rules, bible_name))
            issues.extend(_check_bible_wrong_attribution(fields, qa_rules, bible_name))
            issues.extend(_check_bible_term_context(fields, qa_rules, bible_name))

    result = QualityResult(
        passed=len(issues) == 0,
        issues=issues,
        checked_at=datetime.now(UTC).isoformat(),
    )

    # Store in PageContent.qa_results
    result_dict = result.to_dict()
    if bibles_matched:
        result_dict["bibles_matched"] = bibles_matched
    content.qa_results = result_dict

    return result
```

### Integration into `run_blog_quality_checks` (line 676)

**Before (lines 676-715):**
```python
def run_blog_quality_checks(
    fields: dict[str, str],
    brand_config: dict[str, Any],
) -> QualityResult:
```

**After:**
```python
def run_blog_quality_checks(
    fields: dict[str, str],
    brand_config: dict[str, Any],
    matched_bibles: list[Any] | None = None,
) -> QualityResult:
    """Run all quality checks including blog-specific checks.

    Runs the 9 standard checks plus 4 blog-specific checks (13 total),
    plus bible QA checks if bibles matched (up to 17 total).

    Args:
        fields: Dict of field_name -> text content to check.
        brand_config: The BrandConfig.v2_schema dict.
        matched_bibles: Optional list of VerticalBible objects matched for this post.

    Returns:
        QualityResult with pass/fail and list of issues.
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

    # Blog-specific checks (10-13)
    issues.extend(_check_tier3_phrases(fields))
    issues.extend(_check_empty_signposts(fields))
    issues.extend(_check_missing_direct_answer(fields))
    issues.extend(_check_business_jargon(fields))

    # Bible QA rule checks (14-17)
    bibles_matched: list[str] = []
    if matched_bibles:
        for bible in matched_bibles:
            bible_name = getattr(bible, "name", "Unknown")
            qa_rules = getattr(bible, "qa_rules", None) or {}
            if not isinstance(qa_rules, dict):
                continue
            bibles_matched.append(getattr(bible, "slug", bible_name))
            issues.extend(_check_bible_preferred_terms(fields, qa_rules, bible_name))
            issues.extend(_check_bible_banned_claims(fields, qa_rules, bible_name))
            issues.extend(_check_bible_wrong_attribution(fields, qa_rules, bible_name))
            issues.extend(_check_bible_term_context(fields, qa_rules, bible_name))

    result = QualityResult(
        passed=len(issues) == 0,
        issues=issues,
        checked_at=datetime.now(UTC).isoformat(),
    )

    if bibles_matched:
        result_dict = result.to_dict()
        result_dict["bibles_matched"] = bibles_matched
        # Store as dict for serialization; callers that need QualityResult
        # still get the returned object
        result._bibles_matched = bibles_matched  # stash for callers

    return result
```

**Note:** The `bibles_matched` metadata for `run_blog_quality_checks` is stored differently because this function returns a `QualityResult` (not writing to `PageContent.qa_results` directly). The caller in `blog_content_generation.py` does `blog_post.qa_results = qa_result.to_dict()`, so we need to amend `QualityResult.to_dict()` or handle it at the caller.

**Better approach:** Add an optional `bibles_matched` field to `QualityResult`:

```python
@dataclass
class QualityResult:
    """Result of running all quality checks on a PageContent."""

    passed: bool
    issues: list[QualityIssue] = field(default_factory=list)
    checked_at: str = ""
    bibles_matched: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "passed": self.passed,
            "issues": [issue.to_dict() for issue in self.issues],
            "checked_at": self.checked_at,
        }
        if self.bibles_matched:
            result["bibles_matched"] = self.bibles_matched
        return result
```

Then in both `run_quality_checks` and `run_blog_quality_checks`, set `result.bibles_matched = bibles_matched` before returning.

---

## Pipeline Wiring (content_generation.py)

### New function: `_load_project_bibles`

**Location:** After `_load_brand_config` (line 620), as a new function.

```python
async def _load_project_bibles(
    db: AsyncSession,
    project_id: str,
) -> list[Any]:
    """Load all active vertical bibles for a project.

    Returns empty list if no bibles exist (pipeline degrades gracefully).
    Bibles are sorted by sort_order for consistent prompt injection ordering.
    """
    try:
        from app.models.vertical_bible import VerticalBible

        stmt = (
            select(VerticalBible)
            .where(
                VerticalBible.project_id == project_id,
                VerticalBible.is_active.is_(True),
            )
            .order_by(VerticalBible.sort_order)
        )
        result = await db.execute(stmt)
        bibles = list(result.scalars().all())

        if bibles:
            logger.info(
                "Loaded project bibles",
                extra={"project_id": project_id, "bible_count": len(bibles)},
            )
        return bibles
    except Exception:
        # Graceful degradation: if VerticalBible table doesn't exist yet
        # (migration not run), just return empty list
        logger.warning(
            "Failed to load project bibles (table may not exist yet)",
            extra={"project_id": project_id},
            exc_info=True,
        )
        return []
```

### New helper: `_match_bibles_for_keyword`

```python
def _match_bibles_for_keyword(
    project_bibles: list[Any],
    keyword: str,
) -> list[Any]:
    """Match bibles against a keyword using trigger_keywords word-boundary matching.

    Args:
        project_bibles: All active bibles for the project.
        keyword: The page's primary keyword.

    Returns:
        List of matched VerticalBible objects, sorted by sort_order.
    """
    if not project_bibles or not keyword:
        return []

    keyword_lower = keyword.lower()
    matched = []

    for bible in project_bibles:
        trigger_keywords = getattr(bible, "trigger_keywords", []) or []
        if not isinstance(trigger_keywords, list):
            continue

        for trigger in trigger_keywords:
            if not isinstance(trigger, str) or not trigger:
                continue
            # Word-boundary match: trigger keyword must appear as a whole
            # word/phrase within the page keyword
            pattern = re.compile(r"\b" + re.escape(trigger.lower()) + r"\b")
            if pattern.search(keyword_lower):
                matched.append(bible)
                break  # One match is enough for this bible

    return matched
```

**Note:** Add `import re` at the top of `content_generation.py` (it's not currently imported there).

### Wiring into `run_content_pipeline` (line 70)

**At line 113-115, add bible loading alongside brand_config:**

```python
    # Load approved pages and brand config in a read-only session
    async with db_manager.session_factory() as session:
        pages_data = await _load_approved_pages(session, project_id, batch=batch)
        brand_config = await _load_brand_config(session, project_id)
        project_bibles = await _load_project_bibles(session, project_id)
```

**At line 171, pass `project_bibles` to `_process_single_page`:**

```python
            return await _process_single_page(
                page_data=page_data,
                brand_config=brand_config,
                force_refresh=force_refresh,
                refresh_briefs=False,
                outline_first=outline_first,
                project_bibles=project_bibles,
            )
```

### Wiring into `_process_single_page` (line 642)

**Add parameter:**
```python
async def _process_single_page(
    page_data: dict[str, Any],
    brand_config: dict[str, Any],
    force_refresh: bool,
    refresh_briefs: bool = False,
    outline_first: bool = False,
    project_bibles: list[Any] | None = None,
) -> PipelinePageResult:
```

**Match bibles for this page's keyword (after line 656):**
```python
    keyword: str = page_data["keyword"]
    # ... existing code ...

    # Match bibles for this keyword
    matched_bibles = _match_bibles_for_keyword(project_bibles or [], keyword)
    if matched_bibles:
        logger.info(
            "Bibles matched for page",
            extra={
                "page_id": page_id,
                "keyword": keyword[:50],
                "matched": [getattr(b, "slug", "") for b in matched_bibles],
            },
        )
```

**Pass matched_bibles to outline generation (line 741):**
```python
                outline_result = await generate_outline(
                    db=db,
                    crawled_page=crawled_page,
                    content_brief=content_brief,
                    brand_config=brand_config,
                    keyword=keyword,
                    matched_bibles=matched_bibles,
                )
```

**Pass matched_bibles to content generation (line 775):**
```python
            writing_result = await generate_content(
                db=db,
                crawled_page=crawled_page,
                content_brief=content_brief,
                brand_config=brand_config,
                keyword=keyword,
                matched_bibles=matched_bibles,
            )
```

**Pass matched_bibles to quality checks (line 807):**
```python
            run_quality_checks(written_content, brand_config, matched_bibles)
```

### Wiring into `run_generate_from_outline` (line 215)

This function also needs bibles. After loading brand_config at line 295:

```python
            # Load brand config
            brand_config = await _load_brand_config(db, project_id)

            # Load and match bibles
            project_bibles = await _load_project_bibles(db, project_id)
            matched_bibles = _match_bibles_for_keyword(project_bibles, keyword)
```

Pass to `generate_content_from_outline` at line 306:
```python
            content_result = await generate_content_from_outline(
                db=db,
                crawled_page=crawled_page,
                content_brief=crawled_page.content_brief,
                brand_config=brand_config,
                keyword=keyword,
                outline_json=page_content.outline_json,
                matched_bibles=matched_bibles,
            )
```

Pass to quality checks at line 330:
```python
                run_quality_checks(written_content, brand_config, matched_bibles)
```

---

## Blog Pipeline (blog_content_generation.py)

### Loading bibles

**At line 146-148 (inside `run_blog_content_pipeline`):**

```python
    # Load approved posts and brand config in a read-only session
    async with db_manager.session_factory() as session:
        posts_data = await _load_approved_posts(session, campaign_id)
        brand_config = await _load_brand_config(session, campaign_id)
        project_bibles = await _load_project_bibles_for_campaign(session, campaign_id)
```

**New function:**
```python
async def _load_project_bibles_for_campaign(
    db: AsyncSession,
    campaign_id: str,
) -> list[Any]:
    """Load all active vertical bibles for the campaign's project.

    Returns empty list if no bibles exist.
    """
    try:
        from app.models.vertical_bible import VerticalBible

        stmt = (
            select(VerticalBible)
            .join(BlogCampaign, BlogCampaign.project_id == VerticalBible.project_id)
            .where(
                BlogCampaign.id == campaign_id,
                VerticalBible.is_active.is_(True),
            )
            .order_by(VerticalBible.sort_order)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except Exception:
        logger.warning(
            "Failed to load project bibles for campaign",
            extra={"campaign_id": campaign_id},
            exc_info=True,
        )
        return []
```

### Pass through to `_process_single_post`

**At line 175:**
```python
            return await _process_single_post(
                post_data=post_data,
                brand_config=brand_config,
                force_refresh=force_refresh,
                refresh_briefs=refresh_briefs,
                project_bibles=project_bibles,
            )
```

**Update `_process_single_post` signature (line 435):**
```python
async def _process_single_post(
    post_data: dict[str, Any],
    brand_config: dict[str, Any],
    force_refresh: bool,
    refresh_briefs: bool = False,
    project_bibles: list[Any] | None = None,
) -> BlogPipelinePostResult:
```

**Match bibles per keyword and pass through:**

After line 448 (where `keyword` is set):
```python
    # Match bibles for this keyword
    from app.services.content_generation import _match_bibles_for_keyword
    matched_bibles = _match_bibles_for_keyword(project_bibles or [], keyword)
```

**Pass to `_generate_blog_content` at line 507:**
```python
            write_result = await _generate_blog_content(
                db=db,
                blog_post=blog_post,
                keyword=keyword,
                brand_config=brand_config,
                content_brief=content_brief,
                trend_context=trend_context,
                matched_bibles=matched_bibles,
            )
```

**Update `_generate_blog_content` signature (line 777):**
```python
async def _generate_blog_content(
    db: AsyncSession,
    blog_post: BlogPost,
    keyword: str,
    brand_config: dict[str, Any],
    content_brief: Any | None,
    trend_context: dict[str, Any] | None = None,
    matched_bibles: list[Any] | None = None,
) -> dict[str, Any]:
```

**At line 790:**
```python
    prompts = build_blog_content_prompt(
        blog_post,
        keyword,
        brand_config,
        content_brief,
        trend_context=trend_context,
        matched_bibles=matched_bibles,
    )
```

### Quality checks with bibles

**Pass matched_bibles to quality checks at line 571:**
```python
            qa_result = _run_blog_quality_checks(blog_post, brand_config, matched_bibles)
```

**Update `_run_blog_quality_checks` (line 1036):**
```python
def _run_blog_quality_checks(
    blog_post: BlogPost,
    brand_config: dict[str, Any],
    matched_bibles: list[Any] | None = None,
) -> QualityResult:
    """Run deterministic quality checks on blog post content.

    Uses run_blog_quality_checks from content_quality.py which runs all 9
    standard checks plus 4 blog-specific checks (13 total), plus bible
    checks if bibles matched (up to 17 total).
    """
    fields: dict[str, str] = {}
    for field_name in BLOG_CONTENT_FIELDS:
        value = getattr(blog_post, field_name, None)
        if value:
            fields[field_name] = value

    return run_blog_quality_checks(fields, brand_config, matched_bibles)
```

---

## Recheck Endpoint (content_generation API)

### Onboarding recheck: `backend/app/api/v1/content_generation.py`

**At line 719-727 (recheck_content function), after loading brand_config, add bible loading and matching:**

```python
    # Load brand config v2_schema
    brand_stmt = select(BrandConfig).where(BrandConfig.project_id == project_id)
    brand_result = await db.execute(brand_stmt)
    brand_config_row = brand_result.scalar_one_or_none()
    brand_config = brand_config_row.v2_schema if brand_config_row else {}

    # Load and match bibles for this page's keyword
    matched_bibles: list[Any] = []
    try:
        from app.services.content_generation import (
            _load_project_bibles,
            _match_bibles_for_keyword,
        )

        project_bibles = await _load_project_bibles(db, project_id)

        # Get keyword for this page
        from app.models.page_keywords import PageKeywords as PK
        kw_stmt = select(PK).where(PK.crawled_page_id == page_id)
        kw_result = await db.execute(kw_stmt)
        page_kw = kw_result.scalar_one_or_none()
        keyword = page_kw.primary_keyword if page_kw else ""

        matched_bibles = _match_bibles_for_keyword(project_bibles, keyword)
    except Exception:
        logger.warning(
            "Failed to load bibles for recheck, continuing without",
            extra={"project_id": project_id, "page_id": page_id},
            exc_info=True,
        )

    # Re-run quality checks (mutates content.qa_results)
    content = page.page_content
    run_quality_checks(content, brand_config or {}, matched_bibles)
```

**Note:** `PageKeywords` is already imported at the top of this file (line 28). We need to alias it or use it directly. Actually, checking the imports at line 28: `from app.models.page_keywords import PageKeywords` -- it's already imported. So we just use it directly:

```python
    # Get keyword for this page
    kw_stmt = select(PageKeywords).where(PageKeywords.crawled_page_id == page_id)
    kw_result = await db.execute(kw_stmt)
    page_kw = kw_result.scalar_one_or_none()
    keyword = page_kw.primary_keyword if page_kw else ""
```

### Blog recheck: `backend/app/api/v1/blogs.py`

**At line 843-846, after loading brand_config, add bible matching:**

```python
    # Load brand config
    brand_config = brand_config_row.v2_schema if brand_config_row else {}

    # Load and match bibles
    matched_bibles: list[Any] = []
    try:
        from app.services.content_generation import (
            _load_project_bibles,
            _match_bibles_for_keyword,
        )
        project_bibles = await _load_project_bibles(db, proj_id)
        matched_bibles = _match_bibles_for_keyword(project_bibles, post.primary_keyword)
    except Exception:
        logger.warning(
            "Failed to load bibles for blog recheck",
            extra={"post_id": post_id},
            exc_info=True,
        )

    # Re-run quality checks
    from app.services.blog_content_generation import _run_blog_quality_checks
    qa_result = _run_blog_quality_checks(post, brand_config or {}, matched_bibles)
    post.qa_results = qa_result.to_dict()
```

---

## Test Plan

All tests go in `backend/tests/services/test_content_quality.py`.

### Test helper: fake bible

```python
class _FakeBible:
    """Stand-in for VerticalBible for pure function tests."""

    def __init__(
        self,
        name: str = "Test Bible",
        slug: str = "test-bible",
        qa_rules: dict[str, Any] | None = None,
        content_md: str = "",
        trigger_keywords: list[str] | None = None,
        sort_order: int = 0,
        is_active: bool = True,
    ) -> None:
        self.name = name
        self.slug = slug
        self.qa_rules = qa_rules or {}
        self.content_md = content_md
        self.trigger_keywords = trigger_keywords or []
        self.sort_order = sort_order
        self.is_active = is_active
```

### Check 14: bible_preferred_term tests

```python
class TestCheckBiblePreferredTerms:
    """Tests for bible preferred term detection."""

    def test_detects_wrong_term(self) -> None:
        """Flags the wrong term when a preferred alternative exists."""
        fields = {"bottom_description": "Choose the right needle configuration for your setup."}
        qa_rules = {
            "preferred_terms": [
                {"use": "needle grouping", "instead_of": "needle configuration"}
            ]
        }
        issues = _check_bible_preferred_terms(fields, qa_rules, "Cartridge Needles")
        assert len(issues) == 1
        assert issues[0].type == "bible_preferred_term"
        assert "needle configuration" in issues[0].description
        assert "needle grouping" in issues[0].description
        assert "Cartridge Needles" in issues[0].description

    def test_passes_with_correct_term(self) -> None:
        """Correct term does not trigger the check."""
        fields = {"bottom_description": "Choose the right needle grouping for your setup."}
        qa_rules = {
            "preferred_terms": [
                {"use": "needle grouping", "instead_of": "needle configuration"}
            ]
        }
        issues = _check_bible_preferred_terms(fields, qa_rules, "Cartridge Needles")
        assert len(issues) == 0

    def test_case_insensitive(self) -> None:
        """Detection is case-insensitive."""
        fields = {"bottom_description": "The Needle Configuration matters."}
        qa_rules = {
            "preferred_terms": [
                {"use": "needle grouping", "instead_of": "needle configuration"}
            ]
        }
        issues = _check_bible_preferred_terms(fields, qa_rules, "Test")
        assert len(issues) == 1

    def test_word_boundary(self) -> None:
        """Partial matches are not flagged (e.g., 'config' does not match 'configured')."""
        fields = {"bottom_description": "The system is configured properly."}
        qa_rules = {
            "preferred_terms": [
                {"use": "set up", "instead_of": "config"}
            ]
        }
        issues = _check_bible_preferred_terms(fields, qa_rules, "Test")
        assert len(issues) == 0

    def test_empty_rules(self) -> None:
        """Empty preferred_terms list produces no issues."""
        fields = {"bottom_description": "Any content here."}
        issues = _check_bible_preferred_terms(fields, {}, "Test")
        assert len(issues) == 0

    def test_malformed_rule_skipped(self) -> None:
        """Rules missing required fields are silently skipped."""
        fields = {"bottom_description": "Any content."}
        qa_rules = {"preferred_terms": [{"use": "something"}]}  # missing "instead_of"
        issues = _check_bible_preferred_terms(fields, qa_rules, "Test")
        assert len(issues) == 0
```

### Check 15: bible_banned_claim tests

```python
class TestCheckBibleBannedClaims:
    """Tests for bible banned claim detection."""

    def test_detects_claim_with_context(self) -> None:
        """Flags banned claim when claim and context co-occur in same sentence."""
        fields = {
            "bottom_description": "We are the only brand to offer membrane cartridges on the market."
        }
        qa_rules = {
            "banned_claims": [
                {
                    "claim": "only brand to offer",
                    "context": "membrane",
                    "reason": "All major brands include membranes",
                }
            ]
        }
        issues = _check_bible_banned_claims(fields, qa_rules, "Needles")
        assert len(issues) == 1
        assert issues[0].type == "bible_banned_claim"
        assert "only brand to offer" in issues[0].description
        assert "All major brands" in issues[0].description

    def test_no_flag_when_context_absent(self) -> None:
        """No flag when claim appears but context term is in a different sentence."""
        fields = {
            "bottom_description": (
                "We are the only brand to offer this design. "
                "The membrane prevents backflow."
            )
        }
        qa_rules = {
            "banned_claims": [
                {"claim": "only brand to offer", "context": "membrane", "reason": ""}
            ]
        }
        issues = _check_bible_banned_claims(fields, qa_rules, "Needles")
        assert len(issues) == 0

    def test_flags_claim_without_context_requirement(self) -> None:
        """Flags claim anywhere when no context is specified."""
        fields = {"bottom_description": "This saves ink during the tattooing process."}
        qa_rules = {
            "banned_claims": [
                {"claim": "saves ink", "context": "", "reason": "Membranes prevent backflow"}
            ]
        }
        issues = _check_bible_banned_claims(fields, qa_rules, "Needles")
        assert len(issues) == 1

    def test_empty_rules(self) -> None:
        """Empty banned_claims list produces no issues."""
        issues = _check_bible_banned_claims(
            {"content": "anything"}, {"banned_claims": []}, "Test"
        )
        assert len(issues) == 0
```

### Check 16: bible_wrong_attribution tests

```python
class TestCheckBibleWrongAttribution:
    """Tests for bible wrong attribution detection."""

    def test_detects_wrong_attribution(self) -> None:
        """Flags feature attributed to wrong component in same sentence."""
        fields = {
            "bottom_description": "The membrane technology in tattoo pens prevents contamination."
        }
        qa_rules = {
            "feature_attribution": [
                {
                    "feature": "membrane",
                    "correct_component": "cartridge needle",
                    "wrong_components": ["tattoo pen", "tattoo ink"],
                }
            ]
        }
        issues = _check_bible_wrong_attribution(fields, qa_rules, "Needles")
        assert len(issues) == 1
        assert issues[0].type == "bible_wrong_attribution"
        assert "membrane" in issues[0].description
        assert "tattoo pen" in issues[0].description
        assert "cartridge needle" in issues[0].description

    def test_passes_correct_attribution(self) -> None:
        """No flag when feature is attributed to correct component."""
        fields = {
            "bottom_description": "The membrane in each cartridge needle prevents contamination."
        }
        qa_rules = {
            "feature_attribution": [
                {
                    "feature": "membrane",
                    "correct_component": "cartridge needle",
                    "wrong_components": ["tattoo pen"],
                }
            ]
        }
        issues = _check_bible_wrong_attribution(fields, qa_rules, "Needles")
        assert len(issues) == 0

    def test_no_flag_different_sentences(self) -> None:
        """No flag when feature and wrong component are in different sentences."""
        fields = {
            "bottom_description": (
                "The membrane prevents cross-contamination. "
                "Tattoo pens provide the power for the needle."
            )
        }
        qa_rules = {
            "feature_attribution": [
                {
                    "feature": "membrane",
                    "correct_component": "cartridge needle",
                    "wrong_components": ["tattoo pen"],
                }
            ]
        }
        issues = _check_bible_wrong_attribution(fields, qa_rules, "Needles")
        assert len(issues) == 0
```

### Check 17: bible_term_context tests

```python
class TestCheckBibleTermContext:
    """Tests for bible term context detection."""

    def test_detects_wrong_context(self) -> None:
        """Flags term used with wrong contextual association."""
        fields = {
            "bottom_description": "The membrane saves ink during extended sessions."
        }
        qa_rules = {
            "term_context_rules": [
                {
                    "term": "membrane",
                    "correct_context": ["recoil", "machine protection"],
                    "wrong_contexts": ["ink savings", "saves ink"],
                    "explanation": "Membranes prevent backflow, they don't save ink",
                }
            ]
        }
        issues = _check_bible_term_context(fields, qa_rules, "Needles")
        assert len(issues) == 1
        assert issues[0].type == "bible_term_context"
        assert "membrane" in issues[0].description
        assert "saves ink" in issues[0].description

    def test_passes_correct_context(self) -> None:
        """No flag when term used with correct context."""
        fields = {
            "bottom_description": "The membrane provides recoil protection for the machine."
        }
        qa_rules = {
            "term_context_rules": [
                {
                    "term": "membrane",
                    "correct_context": ["recoil"],
                    "wrong_contexts": ["saves ink"],
                    "explanation": "",
                }
            ]
        }
        issues = _check_bible_term_context(fields, qa_rules, "Needles")
        assert len(issues) == 0

    def test_no_flag_different_sentences(self) -> None:
        """No flag when term and wrong context are in different sentences."""
        fields = {
            "bottom_description": (
                "The membrane is an important safety feature. "
                "Using quality ink saves ink over time."
            )
        }
        qa_rules = {
            "term_context_rules": [
                {
                    "term": "membrane",
                    "correct_context": [],
                    "wrong_contexts": ["saves ink"],
                    "explanation": "",
                }
            ]
        }
        issues = _check_bible_term_context(fields, qa_rules, "Needles")
        assert len(issues) == 0

    def test_empty_rules(self) -> None:
        """Empty term_context_rules produces no issues."""
        issues = _check_bible_term_context(
            {"content": "anything"}, {}, "Test"
        )
        assert len(issues) == 0
```

### Integration tests

```python
class TestRunQualityChecksWithBibles:
    """Tests for run_quality_checks with bible integration."""

    def test_backward_compat_no_bibles(self) -> None:
        """Existing behavior unchanged when no bibles passed."""
        pc = _make_page_content(
            page_title="Winter Boots",
            bottom_description="<p>Great boots for winter.</p>",
        )
        result = run_quality_checks(pc, {})
        assert result.passed is True
        assert "bibles_matched" not in (pc.qa_results or {})

    def test_bible_issues_cause_failure(self) -> None:
        """Bible QA violations cause passed=False."""
        pc = _make_page_content(
            bottom_description="Choose the right needle configuration for lining.",
        )
        bible = _FakeBible(
            name="Cartridge Needles",
            slug="cartridge-needles",
            qa_rules={
                "preferred_terms": [
                    {"use": "needle grouping", "instead_of": "needle configuration"}
                ]
            },
        )
        result = run_quality_checks(pc, {}, matched_bibles=[bible])
        assert result.passed is False
        assert any(i.type == "bible_preferred_term" for i in result.issues)
        assert pc.qa_results["bibles_matched"] == ["cartridge-needles"]

    def test_multiple_bibles_accumulate(self) -> None:
        """Issues from multiple bibles accumulate."""
        pc = _make_page_content(
            bottom_description="The needle configuration with membrane saves ink.",
        )
        bible1 = _FakeBible(
            name="Bible A",
            slug="bible-a",
            qa_rules={
                "preferred_terms": [
                    {"use": "needle grouping", "instead_of": "needle configuration"}
                ]
            },
        )
        bible2 = _FakeBible(
            name="Bible B",
            slug="bible-b",
            qa_rules={
                "banned_claims": [
                    {"claim": "saves ink", "context": "", "reason": "Wrong claim"}
                ]
            },
        )
        result = run_quality_checks(pc, {}, matched_bibles=[bible1, bible2])
        assert result.passed is False
        types = {i.type for i in result.issues}
        assert "bible_preferred_term" in types
        assert "bible_banned_claim" in types
        assert set(pc.qa_results["bibles_matched"]) == {"bible-a", "bible-b"}


class TestRunBlogQualityChecksWithBibles:
    """Tests for run_blog_quality_checks with bible integration."""

    def test_backward_compat_no_bibles(self) -> None:
        """Existing behavior unchanged when no bibles passed."""
        fields = {"content": "Great boots for winter hiking."}
        result = run_blog_quality_checks(fields, {})
        assert result.passed is True

    def test_bible_checks_run_alongside_blog_checks(self) -> None:
        """Bible checks run in addition to all 13 standard+blog checks."""
        fields = {
            "content": "Choose the right needle configuration. In conclusion, it matters."
        }
        bible = _FakeBible(
            name="Needles",
            slug="needles",
            qa_rules={
                "preferred_terms": [
                    {"use": "needle grouping", "instead_of": "needle configuration"}
                ]
            },
        )
        result = run_blog_quality_checks(fields, {}, matched_bibles=[bible])
        assert result.passed is False
        types = {i.type for i in result.issues}
        assert "bible_preferred_term" in types
        assert "tier3_banned_phrase" in types  # "In conclusion"
```

### Prompt injection tests

These go in a new test file or section: `backend/tests/services/test_content_writing.py` (add to existing if it exists, create if not).

```python
class TestBuildDomainKnowledgeSection:
    """Tests for _build_domain_knowledge_section."""

    def test_returns_none_no_bibles(self) -> None:
        """Returns None when no bibles matched."""
        result = _build_domain_knowledge_section([])
        assert result is None

    def test_builds_section_with_single_bible(self) -> None:
        """Builds section with one bible's content_md."""
        bible = _FakeBible(
            name="Tattoo Needles",
            content_md="Cartridge needles are pre-assembled modules.",
        )
        result = _build_domain_knowledge_section([bible])
        assert result is not None
        assert "## Domain Knowledge" in result
        assert "### Tattoo Needles" in result
        assert "Cartridge needles are pre-assembled modules." in result

    def test_truncates_at_max_chars(self) -> None:
        """Truncates combined content at BIBLE_PROMPT_MAX_CHARS."""
        bible = _FakeBible(
            name="Long Bible",
            content_md="x" * 10000,
        )
        result = _build_domain_knowledge_section([bible])
        assert result is not None
        assert len(result) < 10000 + 500  # overhead for headers
        assert "[...truncated]" in result

    def test_skips_empty_content(self) -> None:
        """Skips bibles with empty content_md."""
        bible = _FakeBible(name="Empty", content_md="")
        result = _build_domain_knowledge_section([bible])
        assert result is None

    def test_multiple_bibles_concatenated(self) -> None:
        """Multiple bibles are concatenated in order."""
        b1 = _FakeBible(name="Bible One", content_md="First content.")
        b2 = _FakeBible(name="Bible Two", content_md="Second content.")
        result = _build_domain_knowledge_section([b1, b2])
        assert "### Bible One" in result
        assert "### Bible Two" in result
        # b1 should come before b2
        assert result.index("Bible One") < result.index("Bible Two")
```

### Sentence splitting tests

```python
class TestSplitSentences:
    """Tests for _split_sentences helper."""

    def test_basic_split(self) -> None:
        """Splits on periods followed by space."""
        result = _split_sentences("First sentence. Second sentence.")
        assert len(result) == 2
        assert result[0] == "First sentence."
        assert result[1] == "Second sentence."

    def test_strips_html(self) -> None:
        """Strips HTML tags before splitting."""
        result = _split_sentences("<p>First.</p> <p>Second.</p>")
        assert len(result) == 2

    def test_handles_exclamation_and_question(self) -> None:
        """Splits on ! and ? as well."""
        result = _split_sentences("Really? Yes! Done.")
        assert len(result) == 3

    def test_empty_string(self) -> None:
        """Empty string returns empty list."""
        result = _split_sentences("")
        assert result == []
```

---

## Files to Modify (with line-level detail)

### `backend/app/services/content_writing.py`

| Line(s) | Change |
|---------|--------|
| After line 25 (imports) | No new imports needed (already has `re`, `Any`) |
| After line 34 | Add `BIBLE_PROMPT_MAX_CHARS = 8000` constant |
| 162-186 | Add `matched_bibles` param to `build_content_prompt`, pass to `_build_user_prompt` |
| 189-221 | Add `matched_bibles` param to `build_blog_content_prompt`, pass to `_build_blog_user_prompt` |
| 342-379 | Add `matched_bibles` param to `_build_user_prompt`, inject `## Domain Knowledge` between SEO Targets and Brand Voice |
| 382-435 | Add `matched_bibles` param to `_build_blog_user_prompt`, inject `## Domain Knowledge` between SEO Targets and Recent Trends |
| After 988 | Add `_build_domain_knowledge_section()` function (~40 lines) |
| 1120-1126 | Add `matched_bibles` param to `generate_content`, pass to `build_content_prompt` at line 1155 |

**Estimated delta:** +80 lines

### `backend/app/services/content_quality.py`

| Line(s) | Change |
|---------|--------|
| 100-131 | Add `bibles_matched: list[str]` field to `QualityResult`, update `to_dict()` |
| 134-199 | Add `matched_bibles` param to `run_quality_checks`, add bible check loop after check 9 |
| After 222 | Add `_split_sentences()` helper (~15 lines) |
| After 470 (end of existing checks) | Add `_check_bible_preferred_terms` (~30 lines) |
| After above | Add `_check_bible_banned_claims` (~45 lines) |
| After above | Add `_check_bible_wrong_attribution` (~40 lines) |
| After above | Add `_check_bible_term_context` (~40 lines) |
| 676-715 | Add `matched_bibles` param to `run_blog_quality_checks`, add bible check loop |

**Estimated delta:** +200 lines

### `backend/app/services/content_generation.py`

| Line(s) | Change |
|---------|--------|
| Top imports | Add `import re` |
| After 639 | Add `_load_project_bibles()` async function (~25 lines) |
| After above | Add `_match_bibles_for_keyword()` function (~25 lines) |
| 113-115 | Add `_load_project_bibles` call in `run_content_pipeline` |
| 171 | Pass `project_bibles` to `_process_single_page` |
| 642-648 | Add `project_bibles` param to `_process_single_page`, match bibles per keyword |
| 741 | Pass `matched_bibles` to `generate_outline` |
| 775 | Pass `matched_bibles` to `generate_content` |
| 807 | Pass `matched_bibles` to `run_quality_checks` |
| 295 | Load bibles in `run_generate_from_outline` |
| 306 | Pass `matched_bibles` to `generate_content_from_outline` |
| 330 | Pass `matched_bibles` to `run_quality_checks` in outline path |

**Estimated delta:** +65 lines

### `backend/app/services/blog_content_generation.py`

| Line(s) | Change |
|---------|--------|
| After 339 | Add `_load_project_bibles_for_campaign()` function (~25 lines) |
| 146-148 | Load bibles alongside brand_config |
| 175 | Pass `project_bibles` to `_process_single_post` |
| 435-449 | Add `project_bibles` param, match bibles per keyword |
| 507-514 | Pass `matched_bibles` to `_generate_blog_content` |
| 571 | Pass `matched_bibles` to `_run_blog_quality_checks` |
| 777-784 | Add `matched_bibles` param to `_generate_blog_content`, pass to prompt builder |
| 1036-1052 | Add `matched_bibles` param to `_run_blog_quality_checks`, pass to `run_blog_quality_checks` |

**Estimated delta:** +45 lines

### `backend/app/api/v1/content_generation.py`

| Line(s) | Change |
|---------|--------|
| 719-727 | In `recheck_content`, load bibles + match keyword, pass to `run_quality_checks` |

**Estimated delta:** +20 lines

### `backend/app/api/v1/blogs.py`

| Line(s) | Change |
|---------|--------|
| 843-846 | In `recheck_blog_post_content`, load bibles + match keyword, pass to `_run_blog_quality_checks` |

**Estimated delta:** +15 lines

### `backend/tests/services/test_content_quality.py`

| Line(s) | Change |
|---------|--------|
| Imports (line 16-34) | Add imports for new functions |
| After line 42 | Add `_FakeBible` helper class |
| End of file | Add 7 new test classes (~250 lines total) |

**Estimated delta:** +280 lines

### `backend/app/services/content_outline.py` (if it exists)

| Change |
|--------|
| Add `matched_bibles` param to `generate_outline` and `generate_content_from_outline`, pass through to prompt building |

**Estimated delta:** +10 lines

---

## Verification Checklist

### Backward Compatibility
- [ ] `run_quality_checks(content, brand_config)` still works without `matched_bibles` (default `None`)
- [ ] `run_blog_quality_checks(fields, brand_config)` still works without `matched_bibles`
- [ ] `build_content_prompt(page, kw, bc, brief)` still works without `matched_bibles`
- [ ] `build_blog_content_prompt(post, kw, bc, brief)` still works without `matched_bibles`
- [ ] `generate_content(db, page, brief, bc, kw)` still works without `matched_bibles`
- [ ] All existing tests in `test_content_quality.py` pass unchanged
- [ ] Pipeline runs normally when `vertical_bibles` table is empty
- [ ] Pipeline runs normally when `VerticalBible` model doesn't exist yet (graceful import failure in `_load_project_bibles`)

### Bible Prompt Injection
- [ ] Matched bible `content_md` appears in `## Domain Knowledge` section
- [ ] Section appears between `## SEO Targets` and `## Brand Voice` (collection pages)
- [ ] Section appears between `## SEO Targets` and `## Recent Trends` (blog posts)
- [ ] No `## Domain Knowledge` section when no bibles match
- [ ] Multiple bibles concatenated in `sort_order` order
- [ ] Content truncated at 8,000 chars with `[...truncated]` marker
- [ ] Empty `content_md` bibles are skipped

### Bible QA Checks
- [ ] `bible_preferred_term` detected with correct issue type, field, context
- [ ] `bible_banned_claim` with context requires same-sentence co-occurrence
- [ ] `bible_banned_claim` without context flags anywhere
- [ ] `bible_wrong_attribution` requires same-sentence co-occurrence
- [ ] `bible_term_context` requires same-sentence co-occurrence
- [ ] All checks are case-insensitive
- [ ] All checks use word-boundary matching where appropriate
- [ ] Issues include bible name in description for traceability
- [ ] `bibles_matched` list stored in `qa_results` JSONB
- [ ] Malformed `qa_rules` handled gracefully (no crashes)
- [ ] Empty `qa_rules` produces zero issues

### Pipeline Integration
- [ ] Bibles loaded once per pipeline run (not per page)
- [ ] Bibles matched per-page using keyword
- [ ] Matched bibles passed to prompt building and quality checks
- [ ] Blog pipeline loads bibles via campaign -> project relationship
- [ ] Recheck endpoint loads and matches bibles
- [ ] Blog recheck endpoint loads and matches bibles
- [ ] `run_generate_from_outline` gets bible treatment

### Test Coverage
- [ ] Each of the 4 bible check types has positive and negative tests
- [ ] Word boundary matching tested
- [ ] Case insensitivity tested
- [ ] Empty/malformed rules tested
- [ ] Multiple bibles accumulation tested
- [ ] `_split_sentences` tested with HTML, multiple punctuation types
- [ ] `_build_domain_knowledge_section` tested with truncation
- [ ] Integration tests for `run_quality_checks` with bibles
- [ ] Integration tests for `run_blog_quality_checks` with bibles
