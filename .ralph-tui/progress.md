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

## 2026-02-14 - S11-009
- Added blog scope to internal link planning: BLOG enum, build_blog_graph, target selection, pipeline, and 3 API endpoints
- Files changed:
  - `backend/app/models/internal_link.py` — added `BLOG = "blog"` to `LinkScope` enum
  - `backend/app/services/link_planning.py` — added `build_blog_graph()` method to `SiloLinkPlanner`, `select_targets_blog()` function, `run_blog_link_planning()` pipeline orchestrator, `get_blog_link_progress()` helper; imported `BlogCampaign`, `BlogPost`, `CrawlStatus`
  - `backend/app/api/v1/blogs.py` — added 3 endpoints: POST `plan-links` (trigger, 202+background), GET `link-status` (poll), GET `link-map` (results); added `_active_blog_link_plans` set and background task wrapper
  - `backend/app/schemas/blog.py` — added `BlogLinkPlanTriggerResponse`, `BlogLinkStatusResponse`, `BlogLinkMapItem`, `BlogLinkMapResponse` schemas
  - `backend/app/schemas/__init__.py` — registered 4 new blog link schemas
- **Learnings:**
  - Blog posts need CrawledPage bridging records (source='blog') to use InternalLink infrastructure — same pattern as `bulk_approve_cluster` which creates CrawledPage records (source='cluster') for cluster pages
  - Blog graph is directional: blogs link UP to cluster pages (parent mandatory first, then children) and SIDEWAYS to sibling blogs. Total budget 3-6 links per post. Links never cross the cluster silo boundary
  - Blog link planning pipeline is per-post (not per-campaign) since each blog post gets its own link budget and injection run. The background task creates its own DB session via `db_manager.session_factory()`
  - Edge type annotations: use `dict[str, Any]` not `dict[str, str]` when edge dicts contain optional values from model fields
  - Pre-existing mypy pattern: Pydantic models with `Field(None, ...)` defaults trigger "Missing named argument" mypy errors when not passed explicitly. Same pattern as `LinkPlanStatusResponse`, `WPProgressResponse`, etc. throughout the codebase
---

## 2026-02-14 - S11-010
- Created blog HTML export service and added 3 export API endpoints
- Files changed:
  - `backend/app/services/blog_export.py` (new) — BlogExportService with `generate_clean_html()` (strips highlights, data attrs, fixes H1→H2) and `generate_export_package()` (queries approved+complete posts, returns BlogExportItem list)
  - `backend/app/api/v1/blogs.py` — added 3 export endpoints: GET `/{blog_id}/export` (all approved posts), GET `/{blog_id}/posts/{post_id}/export` (single post), GET `/{blog_id}/posts/{post_id}/download` (HTML file with Content-Disposition)
- **Learnings:**
  - BeautifulSoup `span.unwrap()` is the server-side equivalent of Lexical's `insertBefore + remove` pattern for stripping highlight wrappers — much simpler than manual tree traversal
  - The `type: ignore[attr-defined]` on `from bs4 import BeautifulSoup` is NOT needed in this codebase (mypy flags it as unused-ignore). Other files like `link_injection.py` use it, but it's not required by current mypy config
  - Highlight spans in the Lexical editor render as `<span class="hl-keyword">`, `<span class="hl-keyword-var">`, `<span class="hl-lsi">`, `<span class="hl-trope">` — these are the 4 CSS classes to strip
  - FastAPI `Response` class is needed for the download endpoint (returns raw HTML with Content-Disposition header instead of JSON)
---

## 2026-02-14 - S11-012
- Added TypeScript types and API functions for all blog endpoints to the frontend API client
- Files changed:
  - `frontend/src/lib/api.ts` — added 14 interfaces (BlogCampaign, BlogPost, BlogCampaignCreate, BlogCampaignListItem, BlogPostUpdate, BlogContentUpdate, BlogPostGenerationStatusItem, BlogContentGenerationStatus, BlogContentTriggerResponse, BlogBulkApproveResponse, BlogExportItem, BlogLinkPlanTriggerResponse, BlogLinkStatusResponse, BlogLinkMapItem, BlogLinkMapResponse) and 18 API functions covering CRUD, content, links, and export
- **Learnings:**
  - Blog API functions follow exact same patterns as cluster/content functions: `apiClient.get/post/put/patch/delete` for JSON endpoints, raw `fetch` for blob downloads
  - The `bulkApproveBlogPosts` endpoint returns an untyped dict `{approved_count, campaign_status}` (not a named schema) — used inline type for the return
  - Blog link planning endpoints are per-post (not per-campaign), so `triggerBlogLinkPlanning`, `getBlogLinkStatus`, and `getBlogLinkMap` all take `postId` as a parameter
  - The `downloadBlogPostHtml` function mirrors the `exportProject` pattern: direct `fetch` → blob → hidden anchor download, with Content-Disposition header parsing
  - Pre-existing TS errors (3) in link map tests and GenerationProgress test — unrelated to this change
---

## 2026-02-14 - S11-013
- Created TanStack Query hooks for all blog operations (campaigns, content generation, link planning)
- Files changed:
  - `frontend/src/hooks/useBlogs.ts` (new) — 17 hooks: `blogKeys` factory (7 keys), 6 campaign hooks, 7 content hooks, 3 link hooks
- **Learnings:**
  - Blog hooks follow the exact same patterns as `useClusters.ts` and `useContentGeneration.ts`: query key factory, `useQuery` for reads, `useMutation` with `onSuccess` invalidation for writes
  - Polling pattern for content status: `refetchInterval: (query) => query.state.data?.overall_status === 'generating' ? 3000 : false` — same as `useContentGenerationStatus`
  - Link planning polling uses `status === 'planning'` (not 'generating') since link endpoints use different status values
  - Content approval mutations invalidate 3 query keys (post content, content status, campaign detail) since approval affects counts at multiple levels
  - Pre-existing TS errors (3) unchanged — none in new file
---

## 2026-02-14 - S11-014
- Added Blogs section to project detail page below New Content section
- Files changed:
  - `frontend/src/app/projects/[id]/page.tsx` — added `useBlogCampaigns` import, `PencilIcon`, `BlogCampaignStatusBadge`, `BlogCampaignCard` components, and full Blogs section with campaign grid + empty state
- **Learnings:**
  - Blog section follows exact same layout pattern as New Content section: header with icon + title + chip badge, description text, conditional grid/empty state
  - `BlogCampaignCard` mirrors `ClusterCard` styling: `bg-white rounded-sm border border-sand-500 p-4 shadow-sm hover:shadow-md transition-shadow`
  - `BlogCampaignListItem` provides `content_complete_count` (not `approved_count`) for tracking post completion — used for "X of Y posts done" display
  - Status badge colors: planning=cream, writing=lagoon, review=coral, complete=palm — matches the design spec
  - Pre-existing TS errors (3) unchanged — none in changed file
---

## 2026-02-14 - S11-015
- Created blog campaign creation page with cluster selection, progress animation, and error handling
- Files changed:
  - `frontend/src/app/projects/[id]/blogs/new/page.tsx` (new) — full creation page with cluster dropdown, 4-step progress indicator, error/retry, cancel
- **Learnings:**
  - `BlogCampaignListItem` has `cluster_name` (not `cluster_id`), so matching clusters to existing campaigns uses name-based Set matching
  - Cluster eligibility uses `COMPLETED_CONTENT_STATUSES` set (`approved`, `content_generating`, `complete`) — same as backend `_CLUSTER_COMPLETED_STATUSES`
  - Native `<select>` with `<optgroup>` and `disabled` options is the simplest pattern for showing eligible vs ineligible options without a custom dropdown component
  - Blog discovery takes 10-30s (longer than cluster ~5-10s), so progress step timers are spaced at 4s, 9s, 15s (4 steps vs cluster's 3)
  - Pre-existing TS errors (3) unchanged — none in new file
---

## 2026-02-14 - S11-016
- Created blog keywords step page with 5-step indicator, inline editing, approval toggles, and source page display
- Files changed:
  - `frontend/src/app/projects/[id]/blogs/[blogId]/page.tsx` (new) — BlogKeywordsPage with StepIndicator, BlogPostRow (inline editable keyword + slug, approve toggle, source page, volume), Approve All bulk action, Delete Campaign with 2-click confirmation, Generate Content navigation
- **Learnings:**
  - Blog posts are simpler than cluster pages: no parent/child roles, no CPC/competition/composite_score columns. Only columns: approve checkbox, topic keyword (editable), source page, volume, URL slug (editable)
  - `BlogPost.source_page_id` references `ClusterPage.id` — to show source page keyword, fetch the cluster via `campaign.cluster_id` and build a `Map<ClusterPage.id, ClusterPage.keyword>` lookup
  - `useBulkApproveBlogPosts` returns `{ approved_count, campaign_status }` — use `approved_count` for the toast message
  - Blog Approve All uses the dedicated `bulkApproveBlogPosts` API endpoint (not individual per-row mutations like clusters), which is cleaner
  - Column headers row added (unlike cluster page) since the Source Page column needs labeling for clarity
  - Pre-existing TS errors (3) unchanged — none in new file
---

## 2026-02-14 - S11-017
- Created blog content generation and review page with generation progress, pipeline indicators, polling, and tabbed review table
- Files changed:
  - `frontend/src/app/projects/[id]/blogs/[blogId]/content/page.tsx` (new) — BlogContentPage with StepIndicator (step 2: Content), generation trigger, progress bar with per-post PipelineIndicator (Brief → Write → Check → Done), polling via useBlogContentStatus, ReviewTable with Needs Review/Approved tabs showing keyword/word count/QA status/approval toggle/Edit link, Approve All Ready button, navigation (← Back to Keywords, Continue → to export)
- **Learnings:**
  - Blog content status uses `BlogPostGenerationStatusItem` with `content_status` field (not `status` like cluster's `PageGenerationStatusItem`) — different field name requires separate `getContentStep()` mapping
  - Blog pipeline is 4 steps (Brief → Write → Check → Done) vs cluster's 5 (adds Links step) — blog link planning is per-post and happens separately
  - Blog posts store content directly on `BlogPost` model (content, title, meta_description, qa_results, content_approved) vs clusters which use separate PageContent model — simpler data flow for review table
  - Word count derived client-side by stripping HTML tags from `BlogPost.content` — no dedicated word_count field on the model
  - Blog content approval uses `content_approved` field (not `is_approved` which is for keyword approval) — two separate approval concepts on BlogPost
  - `useBulkApproveBlogContent` returns `BlogBulkApproveResponse` with `approved_count` — different from keyword bulk approve which returns `{ approved_count, campaign_status }`
  - Pre-existing TS errors (3) unchanged — none in new file
---

## 2026-02-14 - S11-018
- Created blog content editor page with 3 fields (title, meta description, content), QA sidebar, and auto-save
- Files changed:
  - `frontend/src/app/projects/[id]/blogs/[blogId]/content/[postId]/page.tsx` (new) — BlogContentEditorPage with 3-field editor (Page Title with 70-char counter, Meta Description with 160-char counter, Content via ContentEditorWithSource Lexical editor), highlight toggle controls, sidebar (QualityStatusCard, FlaggedPassagesCard, ContentStatsCard, LsiTermsCard, HeadingOutlineCard), auto-save on blur with dirty field tracking, bottom action bar (auto-save status, Re-run Checks, Save Draft, Approve)
- **Learnings:**
  - Blog posts use `title`/`meta_description`/`content` field names in `BlogContentUpdate` (not `page_title`/`bottom_description` like cluster's `PageContent`)
  - Blog approval uses `content_approved` (not `is_approved` which is for keyword-level approval) — Approve button navigates back to content list
  - Blog QA issues reference `field === 'content'` (not `'bottom_description'`) for jump-to functionality in FlaggedPassagesCard
  - Blog brief data comes from `BlogPost.pop_brief` JSONB (not `content.brief` like cluster editor) — LSI terms and heading targets extracted from pop_brief
  - Blog editor reuses all existing content-editor components (ContentEditorWithSource, HighlightToggleControls, HighlightPlugin) with no modifications needed
  - Pre-existing TS errors (3) unchanged — none in new file
---

## 2026-02-14 - S11-019
- Created blog link planning trigger page and blog link map visualization page
- Files changed:
  - `frontend/src/app/projects/[id]/blogs/[blogId]/links/page.tsx` (new) — Link planning page with StepIndicator (step 3: Links), prerequisites checklist, Plan & Inject Links button, per-post sequential planning with progress indicator (4 steps: Building graph → Selecting targets → Injecting links → Validating), per-post status rows with polling, auto-redirect to link map on completion, blog-specific link rules card
  - `frontend/src/app/projects/[id]/blogs/[blogId]/links/map/page.tsx` (new) — Link map visualization with aggregated data from per-post link map endpoints, two sections: Cluster Pages (targets with inbound counts sorted by popularity) and Blog Posts (outbound links with anchor text, target keyword, placement method), stats header (total links, posts, avg/post), Re-plan Links button with confirmation dialog
- **Learnings:**
  - Blog link planning is per-post (not per-campaign like cluster links) — the planning page orchestrates sequential triggering of each eligible post's link planning, advancing to the next post when the current one completes or fails
  - Blog link map API (`BlogLinkMapResponse`) returns per-post data (blog_post_id, links[]), so the link map page uses a custom `useAggregatedBlogLinkMap` hook that fetches all eligible posts' link maps and aggregates cluster targets (with inbound counts) and blog post outbound links
  - Backend link planning steps: `building_graph` → `selecting_targets` → `injecting_links` → `validating` → `persisting` (5 actual steps, but UI shows 4 since persisting is instant)
  - The link map page doesn't need Toast state since Re-plan just navigates back to the planning page — removed unused state to satisfy ESLint
  - Pre-existing TS errors (3) unchanged — none in new files
---

## 2026-02-14 - S11-020
- Created blog HTML export page with per-post Copy HTML / Download .html actions and Copy All HTML bulk action
- Files changed:
  - `frontend/src/app/projects/[id]/blogs/[blogId]/export/page.tsx` (new) — Export page with StepIndicator (step 5: Export), ready count badge, approved post cards (keyword, slug, word count, title, meta description, Copy HTML with checkmark feedback, Download .html), unapproved posts grayed out at bottom, bottom bar with Back button and Copy All HTML button
  - `frontend/src/hooks/useBlogs.ts` — added `useBlogExport` query hook and `useDownloadBlogPostHtml` mutation hook; added `getBlogExport`, `downloadBlogPostHtml`, `BlogExportItem` imports from api.ts
- **Learnings:**
  - Export API returns only approved+content_complete posts as `BlogExportItem[]` — unapproved posts are derived by diffing campaign.posts against exported post IDs
  - CopyButton pattern from PromptInspector uses `navigator.clipboard.writeText()` with 2s auto-reset — adapted for per-card copy with toast notification callback
  - Download uses existing `downloadBlogPostHtml()` API function which handles Content-Disposition header parsing and hidden anchor download pattern
  - Copy All HTML concatenates posts with `<!-- POST: keyword -->` separator comments between each post
  - Pre-existing TS errors (3) unchanged — none in new/changed files
---

## 2026-02-14 - S11-011
- Created comprehensive backend tests for blog services and API (81 test cases total)
- Files changed:
  - `backend/tests/services/test_blog_topic_discovery.py` (new) — 19 tests: POP seed extraction (4), topic expansion (4), volume enrichment (4), filter/rank (3), slug generation (5), brand context (2)
  - `backend/tests/services/test_blog_content_generation.py` (new) — 20 tests: JSON parsing (8), quality checks (6), pipeline result dataclasses (6)
  - `backend/tests/services/test_blog_export.py` (new) — 15 tests: HTML cleaning (9), word counting (4), export package generation (2)
  - `backend/tests/api/test_blogs.py` (new) — 27 tests: campaign CRUD (8), post update (2), bulk approve (1), content generation trigger/poll (5), content CRUD (4), recheck (2), export (4)
- **Learnings:**
  - `KeywordCluster` requires `seed_keyword` field (NOT NULL) — test fixtures must include it
  - `ClusterPage` requires `role` field (NOT NULL, values: "parent" or "child") and `url_slug` — must be included in fixtures
  - Use `_FakeBlogPost` / `_FakePageContent` stand-in classes instead of real model instances for pure function tests to avoid SQLAlchemy identity map pollution in shared in-memory SQLite
  - Blog content JSON uses 3 keys (`page_title`, `meta_description`, `content`) vs collection's 4 keys — `_parse_blog_content_json` correctly rejects collection-format JSON
  - The `_run_blog_quality_checks` function reuses all individual check functions from `content_quality.py` but operates on blog field names (`title`, `meta_description`, `content`) instead of PageContent fields
  - Pre-existing test failures (26) across content_quality, crawling, cluster_api, link_pipeline, link_planning — none related to blog changes
---

## 2026-02-14 - S11-021
- Created comprehensive frontend component tests for all blog UI components (63 test cases across 7 test files)
- Files changed:
  - `frontend/src/hooks/__tests__/useBlogs.test.ts` (new) — 14 tests: blogKeys factory (7), query enabled/disabled (3), mutation API calls (3), content status polling (1)
  - `frontend/src/app/projects/[id]/__tests__/blogs.test.tsx` (new) — 9 tests: empty state (4), campaign cards (3), section header (2)
  - `frontend/src/app/projects/[id]/blogs/new/__tests__/page.test.tsx` (new) — 8 tests: loading/404 (2), form rendering (3), validation (2), submission (1)
  - `frontend/src/app/projects/[id]/blogs/[blogId]/__tests__/page.test.tsx` (new) — 8 tests: loading/404 (3), keyword rendering (3), approval (2)
  - `frontend/src/app/projects/[id]/blogs/[blogId]/content/__tests__/page.test.tsx` (new) — 8 tests: loading/404 (2), generation states (3), review table (3)
  - `frontend/src/app/projects/[id]/blogs/[blogId]/content/[postId]/__tests__/page.test.tsx` (new) — 8 tests: loading/error (2), editor layout (3), char counters (2), approval (1)
  - `frontend/src/app/projects/[id]/blogs/[blogId]/export/__tests__/page.test.tsx` (new) — 8 tests: loading/404 (2), export rendering (3), clipboard (2), unapproved section (1)
  - `frontend/src/app/projects/[id]/__tests__/clusters.test.tsx` — fixed pre-existing failure: added missing `useBlogCampaigns` mock
  - `frontend/src/app/projects/[id]/__tests__/linkStatus.test.tsx` — fixed pre-existing failure: added missing `useBlogCampaigns` mock
- **Learnings:**
  - Pre-existing `clusters.test.tsx` and `linkStatus.test.tsx` were failing because S11-014 added `useBlogCampaigns` to `ProjectDetailPage` but didn't update test mocks — fixed by adding the missing mock
  - For hook tests with `renderHook`, must wrap in `QueryClientProvider` with a fresh `QueryClient` per test (`retry: false` for predictable behavior)
  - Polling tests (useBlogContentStatus) need longer timeouts (~20s) to observe actual refetch behavior with real timers + `waitFor`
  - `navigator.clipboard.writeText` mock: `Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } })` in `beforeEach`
  - Components using `ContentEditorWithSource` (Lexical) need it mocked as a textarea — same pattern as cluster content editor tests
---

