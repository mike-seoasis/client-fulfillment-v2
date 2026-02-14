# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **UUID columns**: Use `UUID(as_uuid=False)` with `Mapped[str]`, `default=lambda: str(uuid4())`, `server_default=text("gen_random_uuid()")`.
- **Timestamps**: `DateTime(timezone=True)` with `default=lambda: datetime.now(UTC)`, `server_default=text("now()")`. `updated_at` adds `onupdate=lambda: datetime.now(UTC)`.
- **Enum status fields**: Define `str, Enum` classes, use `.value` for `default=`, wrap in `text("'...'")` for `server_default=`.
- **Relationships**: Use `TYPE_CHECKING` guard for forward refs. Both sides need `back_populates`. Parent side uses `cascade="all, delete-orphan"`. For 1:1, use `unique=True` on FK column + `uselist=False` on the reverse relationship.
- **Models registration**: Import in `backend/app/models/__init__.py` and add to `__all__`.
- **Alembic merge migrations**: When multiple migrations share the same `down_revision` (forked heads), set `down_revision = ("rev_a", "rev_b")` on the new migration to merge them into a single head. Downgrade with explicit target revision, not `-1`.

---

## 2026-02-14 - S11-001
- Implemented BlogCampaign and BlogPost SQLAlchemy models
- Files changed:
  - `backend/app/models/blog.py` (new) — BlogCampaign + BlogPost models with enums
  - `backend/app/models/__init__.py` — registered both models
  - `backend/app/models/project.py` — added `blog_campaigns` relationship
  - `backend/app/models/keyword_cluster.py` — added `blog_campaign` relationship (1:1 via uselist=False)
- **Learnings:**
  - For 1:1 relationships: put `unique=True` on the FK column (BlogCampaign.cluster_id) and `uselist=False` on the reverse side (KeywordCluster.blog_campaign)
  - Pre-existing mypy error in `internal_link.py:243` (unparameterized `dict`) — not related to this change
  - ruff and import checks pass cleanly
---

## 2026-02-14 - S11-002
- Created Alembic migration for blog_campaigns and blog_posts tables
- Files changed:
  - `backend/alembic/versions/0026_create_blog_tables.py` (new) — migration creating both tables with all columns, indexes, FK constraints, and UNIQUE constraint on cluster_id
- **Learnings:**
  - Migration `da1ea5f253b0` (auto-generated, widening internal_links status) also descended from `0025`, creating a fork. Fixed by making `0026` a merge migration with `down_revision = ("0025", "da1ea5f253b0")` — this collapses the two branches into a single head.
  - For merge migrations, `alembic downgrade -1` fails with "Ambiguous walk" — must target a specific revision like `alembic downgrade da1ea5f253b0`.
  - `down_revision` type annotation for merge revisions: `str | tuple[str, ...] | None`
---

## 2026-02-14 - S11-003
- Created Pydantic v2 schemas for all blog API endpoints
- Files changed:
  - `backend/app/schemas/blog.py` (new) — 9 schema classes covering create, response, list, update, generation status, and export
  - `backend/app/schemas/__init__.py` — registered all 9 blog schemas with imports and `__all__`
- **Learnings:**
  - Schema registration pattern: import block at top of `__init__.py`, add to `__all__` list with a comment section header
  - Pre-existing mypy errors in `brand_config.py` and `config.py` — unrelated to this change
  - `BlogPostResponse` includes all model fields; content truncation for list views will be handled at the endpoint/service layer, not in the schema itself
  - Added `BlogPostGenerationStatusItem` as a sub-schema for per-post status within `BlogContentGenerationStatus`
---

## 2026-02-14 - S11-004
- Created BlogTopicDiscoveryService with 4-stage pipeline for discovering blog topics from POP briefs
- Files changed:
  - `backend/app/services/blog_topic_discovery.py` (new) — BlogTopicDiscoveryService class with 4 stages + orchestrator
- **Learnings:**
  - ContentBrief stores `related_searches` and `related_questions` as `list[str]` JSONB columns (simple string lists, not nested objects)
  - To get POP briefs for a cluster: ClusterPage.crawled_page_id → ContentBrief.page_id (two separate queries, not a direct join)
  - ClusterKeywordService uses `_enrich_with_volume` with `result.keywords` from DataForSEO — each keyword data object has `.keyword`, `.search_volume`, `.cpc`, `.competition`, `.competition_level` attributes
  - Blog topic slugs use 80-char max (vs 60 for collection pages) since blog titles tend to be longer
  - Pre-existing mypy errors in `brand_config.py`, `config.py`, `crawling.py` — unrelated to this change
---

## 2026-02-14 - S11-005
- Created blog campaign CRUD API endpoints following the clusters.py CRUD pattern
- Files changed:
  - `backend/app/api/v1/blogs.py` (new) — 6 endpoints: POST create, GET list, GET detail, PATCH post, POST approve, DELETE
  - `backend/app/api/v1/__init__.py` — registered blogs_router
- **Learnings:**
  - Blog creation endpoint mirrors cluster creation: inline pipeline with asyncio.wait_for timeout (90s)
  - For list endpoints with computed counts from different conditions (approved vs content_complete), a separate query for content_complete_count is cleaner than trying to fit multiple func.nullif conditions into a single grouped query
  - Cluster "completed content" validation uses status set {approved, content_generating, complete} — these are the statuses where POP briefs exist on approved pages
  - The discovery service handles its own commit/rollback, so the endpoint just needs to reload the campaign with selectinload after success
  - Pre-existing mypy errors (51 total across 7 files) — none in blogs.py
---

