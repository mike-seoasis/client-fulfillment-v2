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

## 2026-02-14 - S11-006
- Added `build_blog_content_prompt()` function for blog-specific content generation prompts
- Files changed:
  - `backend/app/services/content_writing.py` — added `build_blog_content_prompt()`, `_build_blog_user_prompt()`, `_build_blog_context_section()`, `_build_blog_output_format_section()`; updated `_build_system_prompt()` to accept `content_type` param; added `BlogPost` import
- **Learnings:**
  - `_build_system_prompt()` was refactored to accept `content_type="collection"|"blog"` with a default of `"collection"` so existing callers are unaffected
  - Blog posts use 3-field JSON output (page_title, meta_description, content) vs collection pages' 4-field output (adds top_description, bottom_description)
  - `_build_seo_targets_section()` and `_build_brand_voice_section()` are fully reusable across content types — no changes needed
  - FAQ section in blog output format pulls `related_questions` from ContentBrief; falls back to generic FAQ instructions when no brief is available
  - Pre-existing mypy/ruff errors unchanged — no new errors introduced
---

## 2026-02-14 - S11-007
- Created blog content generation pipeline orchestrator following the content_generation.py pattern
- Files changed:
  - `backend/app/services/blog_content_generation.py` (new) — `run_blog_content_pipeline()` orchestrator with per-post brief→write→check pipeline, semaphore concurrency, error isolation, campaign status update
- **Learnings:**
  - Blog posts store content directly on `BlogPost` (title, meta_description, content) vs collection pages using a separate `PageContent` table — this means no `_ensure_page_content` helper needed
  - Blog content JSON uses 3 keys (page_title, meta_description, content) vs collection's 4 keys (adds top_description, bottom_description) — separate `_parse_blog_content_json` function needed
  - Blog posts don't have a CrawledPage, so POP brief fetching uses the POP client directly instead of `fetch_content_brief()` which requires a CrawledPage. Brief data stored in `BlogPost.pop_brief` JSONB
  - For QA checks: reused individual `_check_*` functions from `content_quality.py` directly rather than `run_quality_checks()` which is coupled to `PageContent` field names
  - `ContentBrief.__new__(ContentBrief)` used to create transient in-memory briefs from cached POP data without DB persistence
  - Campaign status auto-transitions to 'review' when all approved posts reach content_status='complete'
  - Pre-existing mypy errors (29 across 4 files) — none in new file
---

## 2026-02-14 - S11-008
- Created 7 blog content generation API endpoints following the content_generation.py trigger/poll pattern
- Files changed:
  - `backend/app/api/v1/blogs.py` — added 7 endpoints: POST generate-content (202+background), GET content-status, GET post content, PUT post content, POST approve-content, POST recheck, POST bulk-approve-content; added `_active_blog_generations` set and `_get_blog_post` helper
  - `backend/app/schemas/blog.py` — added `BlogContentTriggerResponse`, `BlogBulkApproveResponse` schemas; added `pop_brief` field to `BlogPostResponse`
  - `backend/app/schemas/__init__.py` — registered 2 new blog schemas
- **Learnings:**
  - Blog content generation uses the same trigger/poll pattern as content_generation.py: module-level `_active_blog_generations` set prevents duplicate runs, `BackgroundTasks.add_task()` starts the pipeline, content-status endpoint checks the set for "generating" state
  - The blog pipeline's `run_blog_content_pipeline()` takes a `db` parameter but ignores it (creates its own sessions) — pass `None` with `type: ignore` from the background task wrapper
  - `_run_blog_quality_checks()` from `blog_content_generation.py` is reused directly for the recheck endpoint — it returns a `QualityResult` with `.to_dict()` method
  - JSONB path filtering with `BlogPost.qa_results["passed"].as_boolean().is_(True)` works the same way for blog posts as for PageContent in the collection bulk-approve
  - Pre-existing mypy errors (58 across 10 files) — none in changed files
---

