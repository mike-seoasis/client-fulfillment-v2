"""Service layer for Vertical Knowledge Bibles.

Provides CRUD operations, bible matching logic, and markdown import/export
with YAML frontmatter parsing.
"""

import re
import unicodedata
from typing import Any

import yaml
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.vertical_bible import VerticalBible
from app.schemas.vertical_bible import (
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
