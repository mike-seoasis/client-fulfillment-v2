# 18a: Bible Data Layer

## Overview

Build the complete backend data layer for Vertical Knowledge Bibles: database model, Alembic migration, Pydantic schemas, CRUD service with bible matching logic, REST API endpoints, markdown import/export with frontmatter parsing, and comprehensive tests.

This is the foundation for Phases 18b-18h. Everything else -- prompt injection, QA rule checks, the frontend editor, transcript generation -- depends on bibles existing in the database with a clean API.

**Scope:** Pure backend. No frontend. No pipeline integration (that is 18b). No LLM calls. Fully testable via API and unit tests.

---

## Decisions (from Planner/Advocate Debate)

### 1. JSONB vs Normalized Tables for `qa_rules`

**Planner position:** Use a single JSONB column. The master plan specifies it. The rules are always read as a batch (never queried individually across bibles), and the structure maps to 4 typed arrays that are naturally document-shaped.

**Advocate challenge:** What if we need to query "show me all bibles that have a banned_claims rule mentioning 'membrane'"? JSONB `@>` queries are ugly and slow without GIN indexes. A normalized `bible_qa_rules` table with `rule_type`, `term`, `context` columns would be cleaner for that.

**Resolution: Keep JSONB.** Reasoning:
- We never need cross-bible rule queries. The only access pattern is: load a bible -> read its rules. The quality pipeline loads matched bibles and iterates their rules in Python.
- A normalized table would mean 4 different rule shapes in one table (preferred_terms has `use`/`instead_of`, banned_claims has `claim`/`context`/`reason`, etc.) -- either ugly nullable columns or a polymorphic pattern.
- JSONB is validated at the Pydantic schema layer before storage, giving us type safety without DB complexity.
- Add a GIN index on `qa_rules` just in case future needs arise. Cheap insurance.

### 2. JSONB vs Normalized Table for `trigger_keywords`

**Planner position:** JSONB array, same as `labels` on CrawledPage.

**Advocate challenge:** The matching algorithm needs to check every bible's keywords against a primary keyword. With a normalized `bible_trigger_keywords` table, we could do a single SQL query with `WHERE keyword ILIKE '%cartridge%'` instead of loading all bibles and iterating in Python.

**Resolution: Keep JSONB array.** Reasoning:
- Expected scale: ~5-50 bibles per project, each with ~3-15 keywords. Total: ~750 keyword checks max. This is trivially fast in Python (<1ms).
- The matching algorithm needs word-boundary regex, not SQL LIKE. We'd still need Python post-filtering.
- JSONB array with GIN index allows `?` (contains) operator if we ever need SQL-side filtering.
- A normalized table adds a join to every bible query for marginal benefit at our scale.

### 3. Word-Boundary Regex vs Fuzzy Matching for Bible Matching

**Planner position:** Word-boundary regex (`\b{keyword}\b`) against the page's primary keyword. Simple, fast, deterministic.

**Advocate challenge:** What about:
- "cartridge needles" (plural) vs trigger keyword "cartridge needle" (singular)?
- "needle cartridge" (word order swap)?
- Typos in trigger keywords or primary keywords?

**Resolution: Substring containment, not word-boundary regex.** The matching check should be: does any trigger keyword appear as a substring in the primary keyword (case-insensitive), OR does the primary keyword appear as a substring in any trigger keyword? This handles plurals naturally ("cartridge needle" matches "best cartridge needles for lining" because "cartridge needle" is a substring of "cartridge needles"). Word order matters (intentionally -- "needle cartridge" is a different concept). No fuzzy matching -- bibles are created by humans who know the exact terms. If a keyword doesn't match, the human adds the missing trigger keyword.

**Implementation detail:** Also check against the page's secondary keywords (if available) for broader matching. The master plan says "trigger_keywords against page's primary_keyword" but checking secondary keywords catches more cases at zero cost.

### 4. Token Limits for Prompt Injection

**Advocate challenge:** What happens when 5 bibles match and each has 8,000 chars of `content_md`? That is 40K chars (~10K tokens) injected into an already-large prompt. Could blow context windows.

**Resolution: Enforce a total character budget.** The master plan specifies `max_chars` guard of ~8,000 chars total across all matched bibles. Implementation:
- Sort matched bibles by `sort_order` (priority).
- Concatenate `content_md` until hitting 8,000 chars.
- Truncate with a "...[truncated]" marker.
- Store the char limit as a constant `BIBLE_INJECTION_MAX_CHARS = 8000` in the service.
- This is a 18b concern (prompt injection) but the service method `get_matched_bibles()` should return bibles in sort_order so 18b can truncate naturally.

### 5. Concurrent Edit Handling

**Advocate challenge:** Two operators editing the same bible simultaneously. One saves, the other overwrites.

**Resolution: Last-write-wins with `updated_at` optimistic locking (deferred).** For MVP:
- Last write wins. This is an internal tool with 2-5 operators. The probability of concurrent bible edits is near zero.
- The `updated_at` timestamp is returned in the API response. Frontend can check if it changed before saving and warn the user. But this is a frontend concern (18c), not 18a.
- No database-level locking needed for MVP.

### 6. Slug Collisions

**Advocate challenge:** What if two bibles have the same name? The slug generator will produce the same slug.

**Resolution:** Unique constraint on `(project_id, slug)`. If a collision occurs:
1. Append `-2`, `-3`, etc. to the slug.
2. The API returns the generated slug so the user sees it.
3. Users can override the slug in the update endpoint.

### 7. Frontmatter Parsing Edge Cases

**Advocate challenge:** YAML frontmatter can break on:
- Missing `---` delimiters
- Colons in values (YAML interprets them as key-value separators)
- Unicode characters
- Empty frontmatter
- No frontmatter at all (just markdown)

**Resolution:**
- Use `python-frontmatter` library (already battle-tested, tiny dependency).
- If parsing fails, treat the entire file as `content_md` with no metadata.
- Validate parsed frontmatter fields with Pydantic before using them.
- Return clear error messages for malformed input rather than silently dropping fields.

---

## Model Definition

**File:** `backend/app/models/vertical_bible.py`

```python
"""VerticalBible model for domain-specific knowledge bibles.

A VerticalBible stores domain expertise for a project vertical:
- content_md: Markdown knowledge doc injected into generation prompts
- trigger_keywords: JSONB array of keywords that activate this bible
- qa_rules: JSONB dict of structured quality check rules
- sort_order: Priority when multiple bibles match (lower = higher priority)
- is_active: Enable/disable without deleting
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VerticalBible(Base):
    """Vertical knowledge bible for domain-specific content generation.

    Attributes:
        id: UUID primary key
        project_id: FK to projects table
        name: Display name (e.g., "Tattoo Cartridge Needles")
        slug: URL-safe identifier, unique per project
        content_md: Full markdown knowledge doc (injected into prompts)
        trigger_keywords: JSONB array of keywords that activate this bible
        qa_rules: JSONB dict of structured rules for quality checks
        sort_order: Priority when multiple bibles match (lower = higher priority)
        is_active: Whether this bible is active for matching
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated

    Example trigger_keywords:
        ["cartridge needle", "membrane", "needle grouping", "round liner"]

    Example qa_rules structure:
        {
            "preferred_terms": [
                {"use": "needle grouping", "instead_of": "needle configuration"}
            ],
            "banned_claims": [
                {"claim": "only brand to offer", "context": "membrane",
                 "reason": "All major brands include membranes"}
            ],
            "feature_attribution": [
                {"feature": "membrane", "correct_component": "cartridge needle",
                 "wrong_components": ["tattoo pen", "tattoo ink"]}
            ],
            "term_context_rules": [
                {"term": "membrane",
                 "correct_context": ["recoil", "machine protection"],
                 "wrong_contexts": ["ink savings", "ink efficiency"],
                 "explanation": "Membranes prevent backflow, not ink savings"}
            ]
        }
    """

    __tablename__ = "vertical_bibles"

    # Unique constraint on (project_id, slug)
    __table_args__ = (
        sa.UniqueConstraint("project_id", "slug", name="uq_vertical_bibles_project_slug"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )

    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    content_md: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default=text("''"),
    )

    trigger_keywords: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    qa_rules: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<VerticalBible(id={self.id!r}, name={self.name!r}, slug={self.slug!r})>"
```

**Note:** The `__table_args__` requires `import sqlalchemy as sa` at the top. Follow the exact pattern from the codebase -- check if other models use `sa.UniqueConstraint` or inline it differently. Looking at existing models, none use `__table_args__` with UniqueConstraint (they use `unique=True` on individual columns). Since our constraint is composite, we need:

```python
import sqlalchemy as sa
```

at the top of the file, alongside the existing imports.

---

## Schemas

**File:** `backend/app/schemas/vertical_bible.py`

```python
"""Pydantic schemas for Vertical Knowledge Bibles.

Defines request/response models for bible CRUD endpoints,
including QA rule structures and markdown import/export.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# =============================================================================
# QA RULE SUB-SCHEMAS
# =============================================================================


class PreferredTermRule(BaseModel):
    """A preferred term substitution rule."""

    use: str = Field(..., min_length=1, description="Preferred term to use")
    instead_of: str = Field(..., min_length=1, description="Term to avoid")


class BannedClaimRule(BaseModel):
    """A banned claim rule."""

    claim: str = Field(..., min_length=1, description="Claim text to ban")
    context: str = Field("", description="Context keyword the claim relates to")
    reason: str = Field("", description="Why this claim is banned")


class FeatureAttributionRule(BaseModel):
    """A feature attribution rule."""

    feature: str = Field(..., min_length=1, description="Feature name")
    correct_component: str = Field(
        ..., min_length=1, description="Component the feature belongs to"
    )
    wrong_components: list[str] = Field(
        default_factory=list,
        description="Components the feature should NOT be attributed to",
    )


class TermContextRule(BaseModel):
    """A term-context co-occurrence rule."""

    term: str = Field(..., min_length=1, description="Term to check context for")
    correct_context: list[str] = Field(
        default_factory=list, description="Terms that should appear with this term"
    )
    wrong_contexts: list[str] = Field(
        default_factory=list, description="Terms that should NOT appear with this term"
    )
    explanation: str = Field("", description="Why this context mapping matters")


class QARulesSchema(BaseModel):
    """Structured QA rules for a bible."""

    preferred_terms: list[PreferredTermRule] = Field(default_factory=list)
    banned_claims: list[BannedClaimRule] = Field(default_factory=list)
    feature_attribution: list[FeatureAttributionRule] = Field(default_factory=list)
    term_context_rules: list[TermContextRule] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


# =============================================================================
# CREATE / UPDATE SCHEMAS
# =============================================================================


class VerticalBibleCreate(BaseModel):
    """Request schema for creating a new bible."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Display name for the bible",
        examples=["Tattoo Cartridge Needles"],
    )
    slug: str | None = Field(
        None,
        max_length=255,
        description="URL-safe slug (auto-generated from name if not provided)",
        examples=["tattoo-cartridge-needles"],
    )
    content_md: str = Field(
        "",
        description="Markdown knowledge document",
    )
    trigger_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords that activate this bible",
        examples=[["cartridge needle", "membrane", "round liner"]],
    )
    qa_rules: QARulesSchema = Field(
        default_factory=QARulesSchema,
        description="Structured QA rules",
    )
    sort_order: int = Field(
        0,
        ge=0,
        description="Priority order (lower = higher priority)",
    )
    is_active: bool = Field(
        True,
        description="Whether this bible is active",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return v.strip()

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip().lower()
            if not v:
                return None
        return v

    @field_validator("trigger_keywords")
    @classmethod
    def validate_keywords(cls, v: list[str]) -> list[str]:
        """Strip whitespace and remove empty strings."""
        return [kw.strip().lower() for kw in v if kw.strip()]


class VerticalBibleUpdate(BaseModel):
    """Request schema for updating an existing bible.

    All fields are optional -- only provided fields are updated.
    """

    name: str | None = Field(None, min_length=1, max_length=255)
    slug: str | None = Field(None, max_length=255)
    content_md: str | None = Field(None)
    trigger_keywords: list[str] | None = Field(None)
    qa_rules: QARulesSchema | None = Field(None)
    sort_order: int | None = Field(None, ge=0)
    is_active: bool | None = Field(None)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Name cannot be empty")
        return v

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip().lower()
            if not v:
                raise ValueError("Slug cannot be empty")
        return v

    @field_validator("trigger_keywords")
    @classmethod
    def validate_keywords(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            return [kw.strip().lower() for kw in v if kw.strip()]
        return v


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================


class VerticalBibleResponse(BaseModel):
    """Response schema for a single bible."""

    id: str
    project_id: str
    name: str
    slug: str
    content_md: str
    trigger_keywords: list[str]
    qa_rules: dict[str, Any]
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VerticalBibleListResponse(BaseModel):
    """Response schema for listing bibles."""

    items: list[VerticalBibleResponse]
    total: int = Field(ge=0)


class VerticalBibleSummary(BaseModel):
    """Lightweight bible summary for list views."""

    id: str
    name: str
    slug: str
    keyword_count: int
    is_active: bool
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VerticalBibleListSummaryResponse(BaseModel):
    """Response schema for bible list with summaries."""

    items: list[VerticalBibleSummary]
    total: int = Field(ge=0)


# =============================================================================
# IMPORT / EXPORT SCHEMAS
# =============================================================================


class VerticalBibleImportRequest(BaseModel):
    """Request schema for importing a bible from markdown with frontmatter."""

    markdown: str = Field(
        ...,
        min_length=1,
        description="Full markdown content including YAML frontmatter",
    )
    is_active: bool = Field(True, description="Whether to activate immediately")


class VerticalBibleExportResponse(BaseModel):
    """Response schema for exporting a bible as markdown."""

    markdown: str = Field(..., description="Full markdown with YAML frontmatter")
    filename: str = Field(..., description="Suggested filename (slug.md)")


# =============================================================================
# MATCHING SCHEMAS
# =============================================================================


class BibleMatchResult(BaseModel):
    """Result of matching bibles against a keyword."""

    bible_id: str
    bible_name: str
    bible_slug: str
    matched_keywords: list[str] = Field(
        description="Which trigger keywords matched"
    )
```

---

## Service Layer

**File:** `backend/app/services/vertical_bible.py`

### Method Signatures

```python
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
        Raises HTTPException 409 if slug collision after retries."""

    @staticmethod
    async def get_bible(
        db: AsyncSession,
        project_id: str,
        bible_id: str,
    ) -> VerticalBible:
        """Get a single bible by ID. Raises HTTPException 404 if not found."""

    @staticmethod
    async def get_bible_by_slug(
        db: AsyncSession,
        project_id: str,
        slug: str,
    ) -> VerticalBible:
        """Get a single bible by slug. Raises HTTPException 404 if not found."""

    @staticmethod
    async def list_bibles(
        db: AsyncSession,
        project_id: str,
        active_only: bool = False,
    ) -> list[VerticalBible]:
        """List all bibles for a project, ordered by sort_order then name."""

    @staticmethod
    async def update_bible(
        db: AsyncSession,
        project_id: str,
        bible_id: str,
        data: VerticalBibleUpdate,
    ) -> VerticalBible:
        """Update a bible. Only provided fields are changed.
        Raises HTTPException 404 if not found.
        Raises HTTPException 409 if slug collision."""

    @staticmethod
    async def delete_bible(
        db: AsyncSession,
        project_id: str,
        bible_id: str,
    ) -> None:
        """Delete a bible. Raises HTTPException 404 if not found."""

    # ---- MATCHING ----

    @staticmethod
    async def match_bibles(
        db: AsyncSession,
        project_id: str,
        primary_keyword: str,
        secondary_keywords: list[str] | None = None,
    ) -> list[VerticalBible]:
        """Find all active bibles whose trigger keywords match the given keywords.
        Returns bibles sorted by sort_order (ascending).
        Only returns active bibles (is_active=True)."""

    # ---- IMPORT / EXPORT ----

    @staticmethod
    async def import_from_markdown(
        db: AsyncSession,
        project_id: str,
        markdown: str,
        is_active: bool = True,
    ) -> VerticalBible:
        """Parse a markdown file with YAML frontmatter and create a bible.
        Raises HTTPException 422 if frontmatter is missing required fields."""

    @staticmethod
    def export_to_markdown(bible: VerticalBible) -> str:
        """Serialize a bible to markdown with YAML frontmatter.
        Returns the complete markdown string."""

    # ---- HELPERS ----

    @staticmethod
    def generate_slug(name: str) -> str:
        """Generate a URL-safe slug from a name.
        'Tattoo Cartridge Needles' -> 'tattoo-cartridge-needles'"""

    @staticmethod
    async def _ensure_unique_slug(
        db: AsyncSession,
        project_id: str,
        slug: str,
        exclude_bible_id: str | None = None,
    ) -> str:
        """Ensure slug is unique for the project. Appends -2, -3, etc. if needed."""
```

### Bible Matching Algorithm (Complete Implementation)

```python
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

    This is O(bibles * keywords * triggers) but at our scale (~50 bibles,
    ~10 triggers each, ~5 secondary keywords) = ~2500 string comparisons.
    Trivially fast (<1ms).

    Args:
        db: Database session.
        project_id: UUID of the project.
        primary_keyword: The page's primary keyword.
        secondary_keywords: Optional list of secondary/LSI keywords.

    Returns:
        List of matched VerticalBible objects, sorted by sort_order.
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
        all_page_keywords.extend(kw.strip().lower() for kw in secondary_keywords if kw.strip())

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
```

### Slug Generation

```python
import re
import unicodedata

@staticmethod
def generate_slug(name: str) -> str:
    """Generate a URL-safe slug from a name.

    Examples:
        'Tattoo Cartridge Needles' -> 'tattoo-cartridge-needles'
        'Ink & Pigment Guide' -> 'ink-pigment-guide'
        'Crème Brûlée Recipe' -> 'creme-brulee-recipe'
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
```

### Frontmatter Parser (Import)

```python
import yaml

@staticmethod
async def import_from_markdown(
    db: AsyncSession,
    project_id: str,
    markdown: str,
    is_active: bool = True,
) -> VerticalBible:
    """Parse markdown with YAML frontmatter and create a bible.

    Expected format:
        ---
        name: Tattoo Cartridge Needles
        slug: tattoo-cartridge-needles  # optional
        trigger_keywords:
          - cartridge needle
          - membrane
        qa_rules:                        # optional
          preferred_terms:
            - use: "needle grouping"
              instead_of: "needle configuration"
        sort_order: 0                    # optional, default 0
        ---

        ## Domain Overview
        Content here...

    If frontmatter is missing 'name', raises HTTPException 422.
    If frontmatter is malformed, treats entire text as content_md.
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
    body = text[end_idx + 3:].strip()

    try:
        frontmatter = yaml.safe_load(yaml_str)
        if not isinstance(frontmatter, dict):
            return {}, text
        return frontmatter, body
    except yaml.YAMLError:
        return {}, text
```

### Frontmatter Serializer (Export)

```python
@staticmethod
def export_to_markdown(bible: VerticalBible) -> str:
    """Serialize a bible to markdown with YAML frontmatter.

    Output format:
        ---
        name: Tattoo Cartridge Needles
        slug: tattoo-cartridge-needles
        trigger_keywords:
          - cartridge needle
          - membrane
        qa_rules:
          preferred_terms:
            - use: "needle grouping"
              instead_of: "needle configuration"
        sort_order: 0
        ---

        ## Domain Overview
        ...
    """
    frontmatter: dict[str, Any] = {
        "name": bible.name,
        "slug": bible.slug,
        "trigger_keywords": bible.trigger_keywords or [],
    }

    # Only include qa_rules if non-empty
    qa_rules = bible.qa_rules or {}
    if any(qa_rules.get(key) for key in [
        "preferred_terms", "banned_claims",
        "feature_attribution", "term_context_rules",
    ]):
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
```

---

## API Endpoints

**File:** `backend/app/api/v1/bibles.py`

| Method | Path | Description | Status | Response Model |
|--------|------|-------------|--------|----------------|
| `POST` | `/projects/{project_id}/bibles` | Create a bible | 201 | `VerticalBibleResponse` |
| `GET` | `/projects/{project_id}/bibles` | List project bibles | 200 | `VerticalBibleListResponse` |
| `GET` | `/projects/{project_id}/bibles/{bible_id}` | Get single bible | 200 | `VerticalBibleResponse` |
| `PUT` | `/projects/{project_id}/bibles/{bible_id}` | Full update | 200 | `VerticalBibleResponse` |
| `PATCH` | `/projects/{project_id}/bibles/{bible_id}` | Partial update | 200 | `VerticalBibleResponse` |
| `DELETE` | `/projects/{project_id}/bibles/{bible_id}` | Delete bible | 204 | None |
| `POST` | `/projects/{project_id}/bibles/import` | Import from .md | 201 | `VerticalBibleResponse` |
| `GET` | `/projects/{project_id}/bibles/{bible_id}/export` | Export as .md | 200 | `VerticalBibleExportResponse` |

### Router Implementation

```python
"""Bible CRUD API router.

REST endpoints for managing vertical knowledge bibles per project.
"""

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.vertical_bible import (
    VerticalBibleCreate,
    VerticalBibleExportResponse,
    VerticalBibleImportRequest,
    VerticalBibleListResponse,
    VerticalBibleResponse,
    VerticalBibleUpdate,
)
from app.services.project import ProjectService
from app.services.vertical_bible import VerticalBibleService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}/bibles", tags=["Bibles"])


@router.post(
    "",
    response_model=VerticalBibleResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Project not found"},
        409: {"description": "Slug collision"},
    },
)
async def create_bible(
    project_id: str,
    request: VerticalBibleCreate,
    db: AsyncSession = Depends(get_session),
) -> VerticalBibleResponse:
    """Create a new knowledge bible for a project."""
    await ProjectService.get_project(db, project_id)
    bible = await VerticalBibleService.create_bible(db, project_id, request)
    await db.commit()
    return VerticalBibleResponse.model_validate(bible)


@router.get(
    "",
    response_model=VerticalBibleListResponse,
    responses={404: {"description": "Project not found"}},
)
async def list_bibles(
    project_id: str,
    active_only: bool = False,
    db: AsyncSession = Depends(get_session),
) -> VerticalBibleListResponse:
    """List all bibles for a project."""
    await ProjectService.get_project(db, project_id)
    bibles = await VerticalBibleService.list_bibles(db, project_id, active_only)
    return VerticalBibleListResponse(
        items=[VerticalBibleResponse.model_validate(b) for b in bibles],
        total=len(bibles),
    )


@router.get(
    "/{bible_id}",
    response_model=VerticalBibleResponse,
    responses={404: {"description": "Bible not found"}},
)
async def get_bible(
    project_id: str,
    bible_id: str,
    db: AsyncSession = Depends(get_session),
) -> VerticalBibleResponse:
    """Get a single bible by ID."""
    bible = await VerticalBibleService.get_bible(db, project_id, bible_id)
    return VerticalBibleResponse.model_validate(bible)


@router.put(
    "/{bible_id}",
    response_model=VerticalBibleResponse,
    responses={
        404: {"description": "Bible not found"},
        409: {"description": "Slug collision"},
    },
)
async def update_bible(
    project_id: str,
    bible_id: str,
    request: VerticalBibleUpdate,
    db: AsyncSession = Depends(get_session),
) -> VerticalBibleResponse:
    """Update a bible (full or partial update)."""
    bible = await VerticalBibleService.update_bible(db, project_id, bible_id, request)
    await db.commit()
    return VerticalBibleResponse.model_validate(bible)


@router.patch(
    "/{bible_id}",
    response_model=VerticalBibleResponse,
    responses={
        404: {"description": "Bible not found"},
        409: {"description": "Slug collision"},
    },
)
async def patch_bible(
    project_id: str,
    bible_id: str,
    request: VerticalBibleUpdate,
    db: AsyncSession = Depends(get_session),
) -> VerticalBibleResponse:
    """Partially update a bible (same as PUT, only provided fields change)."""
    bible = await VerticalBibleService.update_bible(db, project_id, bible_id, request)
    await db.commit()
    return VerticalBibleResponse.model_validate(bible)


@router.delete(
    "/{bible_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Bible not found"}},
)
async def delete_bible(
    project_id: str,
    bible_id: str,
    db: AsyncSession = Depends(get_session),
) -> None:
    """Delete a bible."""
    await VerticalBibleService.delete_bible(db, project_id, bible_id)
    await db.commit()


@router.post(
    "/import",
    response_model=VerticalBibleResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Project not found"},
        422: {"description": "Invalid frontmatter"},
    },
)
async def import_bible(
    project_id: str,
    request: VerticalBibleImportRequest,
    db: AsyncSession = Depends(get_session),
) -> VerticalBibleResponse:
    """Import a bible from markdown with YAML frontmatter."""
    await ProjectService.get_project(db, project_id)
    bible = await VerticalBibleService.import_from_markdown(
        db, project_id, request.markdown, request.is_active
    )
    await db.commit()
    return VerticalBibleResponse.model_validate(bible)


@router.get(
    "/{bible_id}/export",
    response_model=VerticalBibleExportResponse,
    responses={404: {"description": "Bible not found"}},
)
async def export_bible(
    project_id: str,
    bible_id: str,
    db: AsyncSession = Depends(get_session),
) -> VerticalBibleExportResponse:
    """Export a bible as markdown with YAML frontmatter."""
    bible = await VerticalBibleService.get_bible(db, project_id, bible_id)
    markdown = VerticalBibleService.export_to_markdown(bible)
    return VerticalBibleExportResponse(
        markdown=markdown,
        filename=f"{bible.slug}.md",
    )
```

---

## Bible Matching Algorithm

Already defined in the Service Layer section above. Key properties:

1. **Bidirectional substring matching:** `trigger_keyword in page_keyword OR page_keyword in trigger_keyword`
2. **Case-insensitive:** All comparisons on lowercased strings.
3. **Checks primary + secondary keywords:** Broader matching at zero cost.
4. **Returns sorted by `sort_order`:** Higher priority bibles first for truncation in 18b.
5. **Only active bibles:** `is_active=True` filter.
6. **O(B x T x K)** where B=bibles (~50), T=triggers per bible (~10), K=page keywords (~5). Total ~2500 string comparisons, <1ms.

### Why substring, not word-boundary regex:

- "cartridge needle" (trigger) matches "best cartridge needles for lining" (primary keyword) because `"cartridge needle" in "best cartridge needles for lining"` is True.
- Word-boundary regex `\bcartridge needle\b` would NOT match "cartridge needles" because of the trailing "s".
- Substring is simpler, faster, and handles plurals naturally.

---

## Import/Export (.md Frontmatter)

### Import Format

```markdown
---
name: Tattoo Cartridge Needles
slug: tattoo-cartridge-needles
trigger_keywords:
  - cartridge needle
  - membrane
  - needle grouping
  - round liner
  - taper
qa_rules:
  preferred_terms:
    - use: "needle grouping"
      instead_of: "needle configuration"
    - use: "round liner"
      instead_of: "RL needle"
  banned_claims:
    - claim: "only brand to offer"
      context: membrane
      reason: "All major cartridge brands include membranes"
  feature_attribution:
    - feature: membrane
      correct_component: "cartridge needle"
      wrong_components:
        - "tattoo pen"
        - "tattoo ink"
  term_context_rules:
    - term: membrane
      correct_context:
        - recoil
        - machine protection
        - health compliance
      wrong_contexts:
        - ink savings
        - ink efficiency
      explanation: "Membranes prevent backflow, they don't save ink"
sort_order: 0
---

## Domain Overview
Cartridge needles are pre-assembled needle modules that snap into a pen grip...

## Correct Terminology
| Use This | Not This | Why |
|----------|----------|-----|
| needle grouping | needle configuration | Industry standard |

## What NOT to Say
- "Membrane saves ink" -- prevents backflow, doesn't reduce consumption
- "Only [brand] offers membrane cartridges" -- industry standard
```

### Export Format

Same as import. The `export_to_markdown()` method produces a round-trippable format: `export -> import -> export` produces the same output.

### Error Handling

| Scenario | Behavior |
|----------|----------|
| No `---` delimiters | Entire text becomes `content_md`, name must be provided separately (422 error on import) |
| Malformed YAML | Entire text becomes `content_md` (422 error because no name) |
| Missing `name` in frontmatter | 422 error with message "Frontmatter must include 'name' field" |
| Missing `trigger_keywords` | Defaults to empty list |
| Missing `qa_rules` | Defaults to empty `QARulesSchema()` |
| Invalid `qa_rules` structure | Falls back to empty `QARulesSchema()` (logged as warning) |
| Colons in YAML values | Handled by `yaml.safe_load` if values are quoted |
| Unicode in content | Fully supported (YAML `allow_unicode=True`) |

---

## Test Plan

**Files:**
- `backend/tests/services/test_vertical_bible.py` -- Unit tests for service layer
- `backend/tests/api/test_bibles.py` -- Integration tests for API endpoints

### Service Layer Unit Tests (`test_vertical_bible.py`)

#### Slug Generation

| Test | Input | Expected Output |
|------|-------|-----------------|
| `test_slug_from_simple_name` | "Tattoo Cartridge Needles" | "tattoo-cartridge-needles" |
| `test_slug_strips_special_chars` | "Ink & Pigment Guide!" | "ink-pigment-guide" |
| `test_slug_handles_unicode` | "Creme Brulee Recipe" | "creme-brulee-recipe" |
| `test_slug_collapses_hyphens` | "Too   Many   Spaces" | "too-many-spaces" |
| `test_slug_empty_name_fallback` | "!!!" | "bible" |

#### Bible Matching

| Test | Setup | Primary Keyword | Expected |
|------|-------|----------------|----------|
| `test_match_exact_keyword` | Bible with trigger "cartridge needle" | "cartridge needle" | Matches |
| `test_match_substring_in_primary` | Bible with trigger "cartridge needle" | "best cartridge needles for lining" | Matches (trigger is substring of primary) |
| `test_match_primary_in_trigger` | Bible with trigger "tattoo cartridge needle guide" | "cartridge needle" | Matches (primary is substring of trigger) |
| `test_no_match_unrelated` | Bible with trigger "cartridge needle" | "best tattoo inks" | No match |
| `test_match_case_insensitive` | Bible with trigger "Cartridge Needle" | "CARTRIDGE NEEDLE guide" | Matches |
| `test_match_via_secondary_keyword` | Bible with trigger "membrane" | primary="needle guide", secondary=["membrane types"] | Matches via secondary |
| `test_inactive_bible_excluded` | Bible with is_active=False | matching keyword | No match |
| `test_empty_trigger_keywords_no_match` | Bible with trigger_keywords=[] | any keyword | No match |
| `test_multiple_bibles_sorted_by_order` | Bible A (sort_order=1), Bible B (sort_order=0) | keyword matching both | Returns [B, A] |
| `test_no_bibles_returns_empty` | No bibles | any keyword | [] |

#### Frontmatter Parsing

| Test | Input | Expected |
|------|-------|----------|
| `test_parse_valid_frontmatter` | Complete .md with all fields | All fields extracted correctly |
| `test_parse_minimal_frontmatter` | Just `name` in frontmatter | Name set, defaults for everything else |
| `test_parse_no_frontmatter` | Plain markdown, no `---` | `({}, full_text)` |
| `test_parse_broken_yaml` | `---\ninvalid: : yaml\n---\nContent` | `({}, full_text)` |
| `test_parse_missing_closing_delimiter` | `---\nname: Test\nContent` (no closing `---`) | `({}, full_text)` |
| `test_parse_unicode_content` | Frontmatter + unicode body | Content preserved |
| `test_parse_empty_string` | "" | `({}, "")` |

#### Frontmatter Export

| Test | Input | Expected |
|------|-------|----------|
| `test_export_roundtrip` | Create bible, export, parse frontmatter | Matches original data |
| `test_export_includes_qa_rules` | Bible with qa_rules | `qa_rules` in YAML |
| `test_export_omits_empty_qa_rules` | Bible with empty qa_rules | `qa_rules` key absent |
| `test_export_includes_nonzero_sort_order` | sort_order=5 | `sort_order: 5` in YAML |
| `test_export_omits_zero_sort_order` | sort_order=0 | `sort_order` key absent |

#### CRUD Operations

| Test | Description |
|------|-------------|
| `test_create_bible_auto_slug` | Create without slug, slug auto-generated from name |
| `test_create_bible_custom_slug` | Create with explicit slug, uses that slug |
| `test_create_bible_slug_collision_appends_suffix` | Two bibles same name, second gets `-2` suffix |
| `test_get_bible_not_found` | Get nonexistent ID raises 404 |
| `test_list_bibles_ordered` | List returns bibles ordered by sort_order |
| `test_list_bibles_active_only` | `active_only=True` excludes inactive |
| `test_update_bible_partial` | Update only name, other fields unchanged |
| `test_update_bible_slug_collision` | Changing slug to existing slug raises 409 |
| `test_delete_bible` | Delete removes from DB |
| `test_delete_bible_not_found` | Delete nonexistent ID raises 404 |

### API Integration Tests (`test_bibles.py`)

These use the FastAPI test client with a real database session.

| Test | Method | Path | Expected |
|------|--------|------|----------|
| `test_create_bible_201` | POST | `/projects/{pid}/bibles` | 201, returns bible |
| `test_create_bible_404_project` | POST | `/projects/fake/bibles` | 404 |
| `test_list_bibles_200` | GET | `/projects/{pid}/bibles` | 200, returns list |
| `test_list_bibles_empty` | GET | `/projects/{pid}/bibles` (no bibles) | 200, `{items: [], total: 0}` |
| `test_get_bible_200` | GET | `/projects/{pid}/bibles/{bid}` | 200, returns bible |
| `test_get_bible_404` | GET | `/projects/{pid}/bibles/fake` | 404 |
| `test_update_bible_200` | PUT | `/projects/{pid}/bibles/{bid}` | 200, returns updated |
| `test_patch_bible_200` | PATCH | `/projects/{pid}/bibles/{bid}` | 200, partial update |
| `test_delete_bible_204` | DELETE | `/projects/{pid}/bibles/{bid}` | 204 |
| `test_import_bible_201` | POST | `/projects/{pid}/bibles/import` | 201, returns bible |
| `test_import_bible_422_no_name` | POST | `/projects/{pid}/bibles/import` (no name) | 422 |
| `test_export_bible_200` | GET | `/projects/{pid}/bibles/{bid}/export` | 200, returns markdown |
| `test_export_import_roundtrip` | Export -> Import | Same data | Identical fields |

---

## Files to Create

| File | Purpose |
|------|---------|
| `backend/app/models/vertical_bible.py` | SQLAlchemy model |
| `backend/alembic/versions/0033_create_vertical_bibles.py` | Alembic migration |
| `backend/app/schemas/vertical_bible.py` | Pydantic schemas |
| `backend/app/services/vertical_bible.py` | CRUD service + matching + import/export |
| `backend/app/api/v1/bibles.py` | API router |
| `backend/tests/services/test_vertical_bible.py` | Service unit tests |
| `backend/tests/api/test_bibles.py` | API integration tests |

---

## Files to Modify

| File | Change |
|------|--------|
| `backend/app/models/__init__.py` | Add `from app.models.vertical_bible import VerticalBible` and add to `__all__` |
| `backend/app/api/v1/__init__.py` | Add `from app.api.v1.bibles import router as bibles_router` and `router.include_router(bibles_router)` |
| `backend/pyproject.toml` | Add `pyyaml` dependency (if not already present) |

---

## Migration

**File:** `backend/alembic/versions/0033_create_vertical_bibles.py`

```python
"""Create vertical_bibles table.

Revision ID: 0033
Revises: 0032
Create Date: 2026-03-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vertical_bibles",
        sa.Column("id", UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("content_md", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("trigger_keywords", JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("qa_rules", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "slug", name="uq_vertical_bibles_project_slug"),
    )
    op.create_index("ix_vertical_bibles_project_id", "vertical_bibles", ["project_id"])
    op.create_index("ix_vertical_bibles_slug", "vertical_bibles", ["slug"])
    op.create_index(
        "ix_vertical_bibles_trigger_keywords",
        "vertical_bibles",
        ["trigger_keywords"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_vertical_bibles_qa_rules",
        "vertical_bibles",
        ["qa_rules"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_vertical_bibles_qa_rules", table_name="vertical_bibles")
    op.drop_index("ix_vertical_bibles_trigger_keywords", table_name="vertical_bibles")
    op.drop_index("ix_vertical_bibles_slug", table_name="vertical_bibles")
    op.drop_index("ix_vertical_bibles_project_id", table_name="vertical_bibles")
    op.drop_table("vertical_bibles")
```

---

## Dependency Check

**PyYAML:** Needed for frontmatter parsing/serialization. Check if it is already in the dependency tree:

```bash
cd backend && uv pip show pyyaml
```

If not present, add to `backend/pyproject.toml` dependencies:

```toml
"pyyaml>=6.0",
```

Note: PyYAML is a very common transitive dependency (used by many libraries). It may already be installed. Verify before adding.

---

## Verification Checklist

- [ ] Migration runs successfully (`alembic upgrade head`)
- [ ] `POST /projects/{id}/bibles` creates a bible with auto-generated slug
- [ ] `GET /projects/{id}/bibles` returns list sorted by sort_order
- [ ] `GET /projects/{id}/bibles/{bid}` returns full bible with all fields
- [ ] `PUT /projects/{id}/bibles/{bid}` updates all provided fields
- [ ] `PATCH /projects/{id}/bibles/{bid}` updates only provided fields
- [ ] `DELETE /projects/{id}/bibles/{bid}` removes the bible (204)
- [ ] `POST /projects/{id}/bibles/import` parses frontmatter and creates bible
- [ ] `GET /projects/{id}/bibles/{bid}/export` returns valid markdown with frontmatter
- [ ] Export -> Import roundtrip produces equivalent bible
- [ ] Unique constraint on `(project_id, slug)` enforced (409 on collision)
- [ ] Slug auto-suffixing works (-2, -3) on collision
- [ ] `match_bibles()` returns correct bibles for a given keyword
- [ ] `match_bibles()` handles substring matching ("cartridge needle" matches "best cartridge needles")
- [ ] `match_bibles()` excludes inactive bibles
- [ ] `match_bibles()` returns bibles sorted by sort_order
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Model registered in `models/__init__.py`
- [ ] Router registered in `api/v1/__init__.py`
- [ ] No regressions in existing tests
