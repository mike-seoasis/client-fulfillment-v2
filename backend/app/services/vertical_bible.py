"""Service layer for Vertical Knowledge Bibles.

Provides CRUD operations, bible matching logic, and markdown import/export
with YAML frontmatter parsing.
"""

import json
import re
import unicodedata
from typing import Any

import yaml  # type: ignore[import-untyped]
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.claude import get_claude
from app.models.vertical_bible import VerticalBible
from app.schemas.vertical_bible import (
    BiblePreviewResponse,
    QARulesSchema,
    VerticalBibleCreate,
    VerticalBibleUpdate,
)

logger = get_logger(__name__)


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from markdown text.

    Returns (frontmatter_dict, body_content).
    If no valid frontmatter found, returns ({}, full_text).
    """
    text = text.strip()

    if not text.startswith("---"):
        return {}, text

    # Find the closing ---
    end_idx = text.find("---", 3)
    if end_idx == -1:
        return {}, text

    yaml_str = text[3:end_idx].strip()
    body = text[end_idx + 3 :].strip()

    try:
        frontmatter = yaml.safe_load(yaml_str)
        if not isinstance(frontmatter, dict):
            return {}, text
        return frontmatter, body
    except yaml.YAMLError:
        return {}, text


class VerticalBibleService:
    """Service for managing vertical knowledge bibles."""

    # ---- CRUD ----

    @staticmethod
    async def create_bible(
        db: AsyncSession,
        project_id: str,
        data: VerticalBibleCreate,
    ) -> VerticalBible:
        """Create a new bible. Auto-generates slug from name if not provided.

        Raises HTTPException 409 if slug collision after retries.
        """
        slug = data.slug or VerticalBibleService.generate_slug(data.name)
        slug = await VerticalBibleService._ensure_unique_slug(db, project_id, slug)

        bible = VerticalBible(
            project_id=project_id,
            name=data.name,
            slug=slug,
            content_md=data.content_md,
            trigger_keywords=data.trigger_keywords,
            qa_rules=data.qa_rules.model_dump(),
            sort_order=data.sort_order,
            is_active=data.is_active,
        )

        db.add(bible)
        await db.flush()
        await db.refresh(bible)

        return bible

    @staticmethod
    async def get_bible(
        db: AsyncSession,
        project_id: str,
        bible_id: str,
    ) -> VerticalBible:
        """Get a single bible by ID. Raises HTTPException 404 if not found."""
        stmt = select(VerticalBible).where(
            VerticalBible.project_id == project_id,
            VerticalBible.id == bible_id,
        )
        result = await db.execute(stmt)
        bible = result.scalar_one_or_none()

        if bible is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bible with id '{bible_id}' not found",
            )

        return bible

    @staticmethod
    async def get_bible_by_slug(
        db: AsyncSession,
        project_id: str,
        slug: str,
    ) -> VerticalBible:
        """Get a single bible by slug. Raises HTTPException 404 if not found."""
        stmt = select(VerticalBible).where(
            VerticalBible.project_id == project_id,
            VerticalBible.slug == slug,
        )
        result = await db.execute(stmt)
        bible = result.scalar_one_or_none()

        if bible is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bible with slug '{slug}' not found",
            )

        return bible

    @staticmethod
    async def list_bibles(
        db: AsyncSession,
        project_id: str,
        active_only: bool = False,
    ) -> list[VerticalBible]:
        """List all bibles for a project, ordered by sort_order then name."""
        stmt = (
            select(VerticalBible)
            .where(VerticalBible.project_id == project_id)
            .order_by(VerticalBible.sort_order, VerticalBible.name)
        )
        if active_only:
            stmt = stmt.where(VerticalBible.is_active == True)  # noqa: E712

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update_bible(
        db: AsyncSession,
        project_id: str,
        bible_id: str,
        data: VerticalBibleUpdate,
    ) -> VerticalBible:
        """Update a bible. Only provided fields are changed.

        Raises HTTPException 404 if not found.
        Raises HTTPException 409 if slug collision.
        """
        bible = await VerticalBibleService.get_bible(db, project_id, bible_id)

        update_data = data.model_dump(exclude_unset=True)

        # Handle slug uniqueness check
        if "slug" in update_data:
            update_data["slug"] = await VerticalBibleService._ensure_unique_slug(
                db, project_id, update_data["slug"], exclude_bible_id=bible_id
            )

        # Serialize qa_rules if present
        if "qa_rules" in update_data and update_data["qa_rules"] is not None:
            update_data["qa_rules"] = data.qa_rules.model_dump()  # type: ignore[union-attr]

        for field, value in update_data.items():
            setattr(bible, field, value)

        await db.flush()
        await db.refresh(bible)

        return bible

    @staticmethod
    async def delete_bible(
        db: AsyncSession,
        project_id: str,
        bible_id: str,
    ) -> None:
        """Delete a bible. Raises HTTPException 404 if not found."""
        bible = await VerticalBibleService.get_bible(db, project_id, bible_id)
        await db.delete(bible)
        await db.flush()

    # ---- MATCHING ----

    @staticmethod
    async def match_bibles(
        db: AsyncSession,
        project_id: str,
        primary_keyword: str,
        secondary_keywords: list[str] | None = None,
    ) -> list[VerticalBible]:
        """Find active bibles whose trigger keywords match the page's keywords.

        Matching algorithm:
        - For each active bible, check if any trigger_keyword is a case-insensitive
          substring of the primary_keyword, OR if the primary_keyword is a substring
          of any trigger_keyword.
        - Also check against secondary_keywords if provided.
        - Returns matched bibles sorted by sort_order (ascending).
        """
        # Load all active bibles for this project
        stmt = (
            select(VerticalBible)
            .where(
                VerticalBible.project_id == project_id,
                VerticalBible.is_active == True,  # noqa: E712
            )
            .order_by(VerticalBible.sort_order, VerticalBible.name)
        )
        result = await db.execute(stmt)
        bibles = list(result.scalars().all())

        if not bibles:
            return []

        # Normalize the page keywords for comparison
        primary_lower = primary_keyword.strip().lower()
        all_page_keywords = [primary_lower]
        if secondary_keywords:
            all_page_keywords.extend(
                kw.strip().lower() for kw in secondary_keywords if kw.strip()
            )

        matched: list[VerticalBible] = []

        for bible in bibles:
            trigger_kws: list[str] = bible.trigger_keywords or []
            if not trigger_kws:
                continue

            is_match = False
            for trigger in trigger_kws:
                trigger_lower = trigger.strip().lower()
                if not trigger_lower:
                    continue

                for page_kw in all_page_keywords:
                    # Bidirectional substring: trigger in page_kw OR page_kw in trigger
                    if trigger_lower in page_kw or page_kw in trigger_lower:
                        is_match = True
                        break

                if is_match:
                    break

            if is_match:
                matched.append(bible)

        return matched

    # ---- IMPORT / EXPORT ----

    @staticmethod
    async def import_from_markdown(
        db: AsyncSession,
        project_id: str,
        markdown: str,
        is_active: bool = True,
    ) -> VerticalBible:
        """Parse markdown with YAML frontmatter and create a bible.

        Raises HTTPException 422 if frontmatter is missing required fields.
        """
        frontmatter, content = _parse_frontmatter(markdown)

        if not frontmatter.get("name"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Frontmatter must include 'name' field",
            )

        # Build create schema from frontmatter
        name = str(frontmatter["name"]).strip()
        slug = frontmatter.get("slug")
        trigger_keywords = frontmatter.get("trigger_keywords", [])
        if not isinstance(trigger_keywords, list):
            trigger_keywords = []

        qa_rules_raw = frontmatter.get("qa_rules", {})
        if not isinstance(qa_rules_raw, dict):
            qa_rules_raw = {}

        # Validate qa_rules through Pydantic
        try:
            qa_rules = QARulesSchema(**qa_rules_raw)
        except Exception:
            qa_rules = QARulesSchema()

        sort_order = int(frontmatter.get("sort_order", 0))

        create_data = VerticalBibleCreate(
            name=name,
            slug=slug if isinstance(slug, str) else None,
            content_md=content.strip(),
            trigger_keywords=[str(kw) for kw in trigger_keywords],
            qa_rules=qa_rules,
            sort_order=sort_order,
            is_active=is_active,
        )

        return await VerticalBibleService.create_bible(db, project_id, create_data)

    @staticmethod
    def export_to_markdown(bible: VerticalBible) -> str:
        """Serialize a bible to markdown with YAML frontmatter."""
        frontmatter: dict[str, Any] = {
            "name": bible.name,
            "slug": bible.slug,
            "trigger_keywords": bible.trigger_keywords or [],
        }

        # Only include qa_rules if non-empty
        qa_rules = bible.qa_rules or {}
        if any(
            qa_rules.get(key)
            for key in [
                "preferred_terms",
                "banned_claims",
                "feature_attribution",
                "term_context_rules",
            ]
        ):
            frontmatter["qa_rules"] = qa_rules

        if bible.sort_order != 0:
            frontmatter["sort_order"] = bible.sort_order

        yaml_str = yaml.dump(
            frontmatter,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

        return f"---\n{yaml_str}---\n\n{bible.content_md}"

    # ---- PREVIEW ----

    @staticmethod
    async def build_preview(
        db: AsyncSession,
        project_id: str,
        bible: VerticalBible,
    ) -> "BiblePreviewResponse":
        """Build a preview showing prompt injection and matching pages.

        Returns the formatted Domain Knowledge section as it would appear in
        content generation prompts, plus a list of project pages whose primary
        keyword matches any of the bible's trigger keywords.
        """
        from app.models.crawled_page import CrawledPage
        from app.models.page_keywords import PageKeywords
        from app.schemas.vertical_bible import (
            BiblePreviewMatchedPage,
            BiblePreviewResponse,
        )

        # Build prompt section preview
        content = (bible.content_md or "").strip()
        if content:
            prompt_section = f"## Domain Knowledge\n\n{content}"
        else:
            prompt_section = "## Domain Knowledge\n\n(No content yet)"

        # Find matching pages
        trigger_keywords = bible.trigger_keywords or []
        matched_pages: list[BiblePreviewMatchedPage] = []

        # Count total pages with keywords in the project
        count_stmt = (
            select(CrawledPage.id)
            .join(PageKeywords, PageKeywords.crawled_page_id == CrawledPage.id)
            .where(CrawledPage.project_id == project_id)
        )
        count_result = await db.execute(count_stmt)
        total_pages = len(count_result.all())

        if trigger_keywords:
            # Load all pages with keywords for this project
            stmt = (
                select(
                    CrawledPage.id,
                    CrawledPage.normalized_url,
                    PageKeywords.primary_keyword,
                )
                .join(PageKeywords, PageKeywords.crawled_page_id == CrawledPage.id)
                .where(CrawledPage.project_id == project_id)
                .order_by(PageKeywords.primary_keyword)
            )
            result = await db.execute(stmt)
            rows = result.all()

            for page_id, url, keyword in rows:
                if not keyword:
                    continue
                keyword_lower = keyword.strip().lower()
                for trigger in trigger_keywords:
                    trigger_lower = trigger.strip().lower()
                    if not trigger_lower or len(trigger_lower) < 3:
                        continue
                    if trigger_lower in keyword_lower or keyword_lower in trigger_lower:
                        matched_pages.append(
                            BiblePreviewMatchedPage(
                                page_id=str(page_id),
                                url=url,
                                keyword=keyword,
                                matched_trigger=trigger,
                            )
                        )
                        break  # One match per page is enough

        return BiblePreviewResponse(
            prompt_section=prompt_section,
            matched_pages=matched_pages,
            total_pages_in_project=total_pages,
        )

    # ---- HELPERS ----

    @staticmethod
    def generate_slug(name: str) -> str:
        """Generate a URL-safe slug from a name.

        Examples:
            'Tattoo Cartridge Needles' -> 'tattoo-cartridge-needles'
            'Ink & Pigment Guide' -> 'ink-pigment-guide'
        """
        # Normalize unicode characters
        slug = unicodedata.normalize("NFKD", name)
        # Remove non-ASCII characters
        slug = slug.encode("ascii", "ignore").decode("ascii")
        # Lowercase
        slug = slug.lower()
        # Replace non-alphanumeric with hyphens
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        # Remove leading/trailing hyphens
        slug = slug.strip("-")
        # Collapse multiple hyphens
        slug = re.sub(r"-+", "-", slug)
        return slug or "bible"

    @staticmethod
    async def _ensure_unique_slug(
        db: AsyncSession,
        project_id: str,
        slug: str,
        exclude_bible_id: str | None = None,
    ) -> str:
        """Ensure slug is unique within the project.

        If 'tattoo-cartridge-needles' exists, tries:
        - 'tattoo-cartridge-needles-2'
        - 'tattoo-cartridge-needles-3'
        Up to 100 attempts, then raises HTTPException 409.
        """
        candidate = slug
        for suffix in range(1, 101):
            stmt = select(VerticalBible.id).where(
                VerticalBible.project_id == project_id,
                VerticalBible.slug == candidate,
            )
            if exclude_bible_id:
                stmt = stmt.where(VerticalBible.id != exclude_bible_id)

            result = await db.execute(stmt)
            if result.scalar_one_or_none() is None:
                return candidate

            candidate = f"{slug}-{suffix + 1}"

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Could not generate unique slug for '{slug}'",
        )


# =============================================================================
# TRANSCRIPT EXTRACTION
# =============================================================================

TRANSCRIPT_EXTRACTION_MODEL = "claude-sonnet-4-5"
TRANSCRIPT_EXTRACTION_MAX_TOKENS = 8192
TRANSCRIPT_EXTRACTION_TEMPERATURE = 0.2
TRANSCRIPT_EXTRACTION_TIMEOUT = 120.0
TRANSCRIPT_MAX_CHARS = 100_000

EXTRACTION_SYSTEM_PROMPT = """You are a domain knowledge extraction specialist. Your task is to analyze an interview transcript with a domain expert and extract structured knowledge that will be used to:
1. Train an AI content writer to write accurately about this topic
2. Create quality assurance rules that catch factual errors in generated content

You must produce a JSON object with the exact schema specified. Be thorough but precise -- every rule you create will be checked against real content, so false positives (rules that trigger on correct content) are worse than missing a rule."""


def _build_extraction_user_prompt(transcript: str, vertical_name: str) -> str:
    """Build the user prompt for transcript extraction."""
    return f'''## Task

Analyze the following transcript of a domain expert interview about "{vertical_name}" and extract structured knowledge into a bible document.

## Transcript

{transcript}

## Extraction Instructions

From the transcript above, extract:

1. **trigger_keywords**: A list of 5-15 specific terms, product names, or phrases that would indicate a piece of content is about this topic. These should be terms that appear naturally in content about this subject. Be specific -- "cartridge needle" is good, "needle" alone is too broad.

2. **content_md**: A structured markdown document following this exact format:

```markdown
## Domain Overview
[2-3 paragraph summary of the domain knowledge from the expert. Write in authoritative third person. Include the key facts, relationships, and context an AI writer would need to write accurately about this topic.]

## Correct Terminology
| Use This | Not This | Why |
|----------|----------|-----|
[Extract preferred terms vs. incorrect/outdated terms mentioned in the transcript. Only include terms the expert explicitly corrected or emphasized.]

## Feature-to-Benefit Mapping
| Feature | Benefit | How to Write It |
|---------|---------|-----------------|
[Extract features and their correct benefits as described by the expert. The "How to Write It" column should be a short example sentence.]

## What NOT to Say
[Bulleted list of common misconceptions, incorrect claims, or misleading statements the expert warned about. Format each as: "Incorrect claim" -- correct explanation]

## Component Relationships
[Bulleted list of how components/products relate to each other. Format: "X relates to Y as follows: explanation". Only include relationships the expert explicitly described.]
```

3. **qa_rules**: Structured rules for automated quality checking. Extract ONLY rules that are clearly supported by the transcript -- do not invent rules the expert didn't discuss.

## Output Format

Return ONLY a valid JSON object with this exact structure. No markdown code fences. No text before or after the JSON.

{{
  "name": "{vertical_name}",
  "slug": "[lowercase-hyphenated version of the name]",
  "trigger_keywords": ["keyword1", "keyword2"],
  "content_md": "[Full markdown document as specified above]",
  "qa_rules": {{
    "preferred_terms": [
      {{
        "use": "[correct term]",
        "instead_of": "[incorrect term]"
      }}
    ],
    "banned_claims": [
      {{
        "claim": "[the incorrect claim text to match]",
        "context": "[the topic/term this relates to]",
        "reason": "[why this claim is wrong]"
      }}
    ],
    "feature_attribution": [
      {{
        "feature": "[the feature name]",
        "correct_component": "[what component/product this feature belongs to]",
        "wrong_components": ["component it does NOT belong to"]
      }}
    ],
    "term_context_rules": [
      {{
        "term": "[the term]",
        "correct_context": ["correct associated concept"],
        "wrong_contexts": ["incorrect associated concept"],
        "explanation": "[why the wrong context is wrong]"
      }}
    ]
  }}
}}

Rules for extraction:
- If the transcript doesn't contain information for a qa_rules category, use an empty array for that category.
- Do not fabricate rules -- only extract what the expert actually said or clearly implied.
- The slug should be URL-safe: lowercase, hyphens instead of spaces, no special characters.
- content_md should be 500-3000 characters. Be comprehensive but not redundant.
- trigger_keywords should be specific enough to avoid false matches (e.g., "cartridge needle" not just "needle").'''


def _validate_qa_rules(raw_rules: dict[str, Any]) -> dict[str, list[str]]:
    """Validate and sanitize extracted qa_rules against the expected schema.

    Strips any rule entries that don't match expected structure. Returns a
    validated dict with all four rule categories (empty lists for missing ones).
    """
    if not isinstance(raw_rules, dict):
        return {
            "preferred_terms": [],
            "banned_claims": [],
            "feature_attribution": [],
            "term_context_rules": [],
        }

    validated: dict[str, list[str]] = {
        "preferred_terms": [],
        "banned_claims": [],
        "feature_attribution": [],
        "term_context_rules": [],
    }

    # Validate preferred_terms
    preferred_raw = raw_rules.get("preferred_terms", [])
    if not isinstance(preferred_raw, list):
        preferred_raw = []
    for rule in preferred_raw:
        if (
            isinstance(rule, dict)
            and isinstance(rule.get("use"), str)
            and isinstance(rule.get("instead_of"), str)
            and rule["use"].strip()
            and rule["instead_of"].strip()
        ):
            validated["preferred_terms"].append(
                {
                    "use": rule["use"].strip(),
                    "instead_of": rule["instead_of"].strip(),
                }
            )
        else:
            logger.warning(
                "Stripped invalid preferred_term rule",
                extra={"rule": str(rule)[:200]},
            )

    # Validate banned_claims
    banned_raw = raw_rules.get("banned_claims", [])
    if not isinstance(banned_raw, list):
        banned_raw = []
    for rule in banned_raw:
        if (
            isinstance(rule, dict)
            and isinstance(rule.get("claim"), str)
            and isinstance(rule.get("context"), str)
            and isinstance(rule.get("reason"), str)
            and rule["claim"].strip()
        ):
            validated["banned_claims"].append(
                {
                    "claim": rule["claim"].strip(),
                    "context": rule["context"].strip(),
                    "reason": rule["reason"].strip(),
                }
            )
        else:
            logger.warning(
                "Stripped invalid banned_claim rule",
                extra={"rule": str(rule)[:200]},
            )

    # Validate feature_attribution
    feature_raw = raw_rules.get("feature_attribution", [])
    if not isinstance(feature_raw, list):
        feature_raw = []
    for rule in feature_raw:
        if (
            isinstance(rule, dict)
            and isinstance(rule.get("feature"), str)
            and isinstance(rule.get("correct_component"), str)
            and isinstance(rule.get("wrong_components"), list)
            and rule["feature"].strip()
        ):
            wrong = [
                w.strip()
                for w in rule["wrong_components"]
                if isinstance(w, str) and w.strip()
            ]
            validated["feature_attribution"].append(
                {
                    "feature": rule["feature"].strip(),
                    "correct_component": rule["correct_component"].strip(),
                    "wrong_components": wrong,
                }
            )
        else:
            logger.warning(
                "Stripped invalid feature_attribution rule",
                extra={"rule": str(rule)[:200]},
            )

    # Validate term_context_rules
    term_raw = raw_rules.get("term_context_rules", [])
    if not isinstance(term_raw, list):
        term_raw = []
    for rule in term_raw:
        if (
            isinstance(rule, dict)
            and isinstance(rule.get("term"), str)
            and isinstance(rule.get("correct_context"), list)
            and isinstance(rule.get("wrong_contexts"), list)
            and isinstance(rule.get("explanation"), str)
            and rule["term"].strip()
        ):
            correct = [
                c.strip()
                for c in rule["correct_context"]
                if isinstance(c, str) and c.strip()
            ]
            wrong = [
                w.strip()
                for w in rule["wrong_contexts"]
                if isinstance(w, str) and w.strip()
            ]
            validated["term_context_rules"].append(
                {
                    "term": rule["term"].strip(),
                    "correct_context": correct,
                    "wrong_contexts": wrong,
                    "explanation": rule["explanation"].strip(),
                }
            )
        else:
            logger.warning(
                "Stripped invalid term_context_rule",
                extra={"rule": str(rule)[:200]},
            )

    return validated


def _parse_extraction_response(text: str) -> dict[str, Any] | None:
    """Parse Claude's extraction response as JSON.

    Handles markdown code fences, BOM characters, and surrounding text.
    Returns None if unparseable.
    """
    cleaned = text.strip()

    # Strip BOM if present
    cleaned = cleaned.lstrip("\ufeff")

    # Strip markdown code fences
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]  # Remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    # Try direct parse first
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    # Try to extract JSON object if surrounded by other text (non-greedy)
    if not cleaned.startswith("{"):
        match = re.search(r"\{[\s\S]*?\}", cleaned)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass

    # Last resort: find the first { and try progressively larger slices
    first_brace = cleaned.find("{")
    if first_brace >= 0:
        # Find matching closing brace by trying json.loads from the first {
        substr = cleaned[first_brace:]
        try:
            parsed = json.loads(substr)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

    return None


async def generate_bible_from_transcript(
    transcript: str,
    vertical_name: str,
    project_id: str,
    db: AsyncSession,
) -> VerticalBible:
    """Extract a structured knowledge bible from a domain expert transcript.

    Calls Claude Sonnet to analyze the transcript, extract domain knowledge,
    terminology rules, and QA rules. Creates the bible in the database with
    is_active=False (draft state) for operator review.

    Raises:
        ValueError: If transcript exceeds max length or is empty.
        RuntimeError: If Claude API call fails or response cannot be parsed.
    """
    # Input validation and sanitization
    transcript = transcript.strip().replace("\x00", "")
    vertical_name = vertical_name.strip().replace("\x00", "")

    if not transcript:
        raise ValueError("Transcript cannot be empty")
    if not vertical_name:
        raise ValueError("Vertical name cannot be empty")
    if len(transcript) > TRANSCRIPT_MAX_CHARS:
        raise ValueError(
            f"Transcript exceeds maximum length of {TRANSCRIPT_MAX_CHARS:,} characters "
            f"(received {len(transcript):,}). Try trimming irrelevant sections."
        )

    logger.info(
        "Starting bible extraction from transcript",
        extra={
            "project_id": project_id,
            "vertical_name": vertical_name,
            "transcript_chars": len(transcript),
        },
    )

    # Build prompts
    user_prompt = _build_extraction_user_prompt(transcript, vertical_name)

    # Call Claude — use the global singleton client (shared circuit breaker
    # and connection pool) with per-call overrides for model/tokens/timeout.
    # max_retries=1: this is a long-running expensive call (~60-120s).
    # Retrying on timeout would triple the wait time with no benefit.
    client = await get_claude()
    result = await client.complete(
        user_prompt=user_prompt,
        system_prompt=EXTRACTION_SYSTEM_PROMPT,
        model=TRANSCRIPT_EXTRACTION_MODEL,
        max_tokens=TRANSCRIPT_EXTRACTION_MAX_TOKENS,
        temperature=TRANSCRIPT_EXTRACTION_TEMPERATURE,
        timeout=TRANSCRIPT_EXTRACTION_TIMEOUT,
        max_retries=1,
    )

    if not result.success:
        logger.error(
            "Claude API call failed for transcript extraction",
            extra={
                "project_id": project_id,
                "error": result.error,
                "status_code": result.status_code,
            },
        )
        raise RuntimeError("AI extraction failed. Please try again later.")

    logger.info(
        "Claude transcript extraction call complete",
        extra={
            "project_id": project_id,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "duration_ms": round(result.duration_ms),
        },
    )

    # Parse JSON response
    parsed = _parse_extraction_response(result.text or "")
    if parsed is None:
        logger.error(
            "Failed to parse extraction response as JSON",
            extra={
                "project_id": project_id,
                "response_snippet": (result.text or "")[:500],
            },
        )
        raise RuntimeError(
            "AI extraction returned an invalid response. Please try again."
        )

    # Validate and sanitize
    name = parsed.get("name", vertical_name).strip() or vertical_name
    slug = parsed.get("slug", "").strip() or VerticalBibleService.generate_slug(
        vertical_name
    )
    trigger_keywords = [
        kw.strip()
        for kw in parsed.get("trigger_keywords", [])
        if isinstance(kw, str) and kw.strip()
    ]
    content_md = parsed.get("content_md", "").strip().replace("\x00", "")
    raw_qa_rules = parsed.get("qa_rules", {})
    qa_rules = _validate_qa_rules(
        raw_qa_rules if isinstance(raw_qa_rules, dict) else {}
    )

    if not content_md:
        raise RuntimeError(
            "AI extraction returned empty content. The transcript may not contain "
            "enough domain-specific information. Please try with a more detailed transcript."
        )

    # Ensure slug uniqueness within the project (reuse existing service method)
    slug = await VerticalBibleService._ensure_unique_slug(db, project_id, slug)

    # Create bible as draft (is_active=False)
    bible = VerticalBible(
        project_id=project_id,
        name=name,
        slug=slug,
        trigger_keywords=trigger_keywords,
        content_md=content_md,
        qa_rules=qa_rules,
        is_active=False,
        sort_order=0,
    )
    db.add(bible)
    await db.flush()
    await db.refresh(bible)

    logger.info(
        "Bible draft created from transcript extraction",
        extra={
            "project_id": project_id,
            "bible_id": str(bible.id),
            "bible_name": name,
            "slug": slug,
            "keyword_count": len(trigger_keywords),
            "qa_rule_count": sum(len(v) for v in qa_rules.values()),
            "content_md_chars": len(content_md),
        },
    )

    return bible
