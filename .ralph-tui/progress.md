# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Alembic Migration Patterns
- Migration files use sequential numbering: `0001_`, `0002_`, etc.
- Use `server_default=sa.text("false")` for Boolean defaults (not Python `False`)
- Use `server_default=sa.text("'[]'::jsonb")` for empty JSONB array defaults
- Use `server_default=sa.text("'{}'::jsonb")` for empty JSONB object defaults
- Always include proper downgrade() that reverses all upgrade() operations
- Drop indexes before dropping columns in downgrade
- Import `from sqlalchemy.dialects import postgresql` for JSONB types

---

## 2026-02-05 - S4-001
- **What was implemented:** Created Alembic migration to add approval and scoring fields to page_keywords table
- **Files changed:**
  - `backend/alembic/versions/0020_add_page_keywords_approval_fields.py` (new file)
- **Fields added:**
  - `is_approved` - Boolean with server_default=false
  - `is_priority` - Boolean with server_default=false
  - `alternative_keywords` - JSONB with server_default='[]'::jsonb
  - `composite_score` - Float (nullable)
  - `relevance_score` - Float (nullable)
  - `ai_reasoning` - Text (nullable)
- **Indexes added:**
  - `ix_page_keywords_is_approved` - for filtering approved keywords
  - `ix_page_keywords_is_priority` - for filtering priority keywords
- **Learnings:**
  - Pattern documented above for Alembic migrations
---

## 2026-02-05 - S4-002
- **What was implemented:** Added bidirectional relationship between CrawledPage and PageKeywords models
- **Files changed:**
  - `backend/app/models/crawled_page.py` - Added `keywords` relationship with one-to-one config
  - `backend/app/models/page_keywords.py` - Added ForeignKey constraint and `page` relationship
- **Changes:**
  - Added `ForeignKey("crawled_pages.id", ondelete="CASCADE")` to `crawled_page_id` column
  - Added `page` relationship in PageKeywords with `back_populates="keywords"`
  - Added `keywords` relationship in CrawledPage with `uselist=False` for one-to-one, `cascade="all, delete-orphan"`
- **Learnings:**
  - One-to-one relationships in SQLAlchemy use `uselist=False` on the parent side
  - Follow TYPE_CHECKING pattern with forward references to avoid circular imports
  - ForeignKey with `ondelete="CASCADE"` ensures database-level cascade
  - `cascade="all, delete-orphan"` on relationship ensures ORM-level cascade
---

## 2026-02-05 - S4-003
- **What was implemented:** Updated PageKeywords model with new fields for approval and scoring
- **Files changed:**
  - `backend/app/models/page_keywords.py` - Added 6 new fields matching migration 0020
- **Fields added:**
  - `is_approved: Mapped[bool]` - Boolean with default=False, indexed
  - `is_priority: Mapped[bool]` - Boolean with default=False, indexed
  - `alternative_keywords: Mapped[list[Any]]` - JSONB with default=[]
  - `composite_score: Mapped[float | None]` - Float, nullable
  - `relevance_score: Mapped[float | None]` - Float, nullable
  - `ai_reasoning: Mapped[str | None]` - Text, nullable
- **Learnings:**
  - Import `Boolean` and `Float` from sqlalchemy for explicit type declarations
  - Boolean fields with `server_default=text("false")` match Alembic pattern
  - JSONB fields need both `default=list` (Python) and `server_default=text("'[]'::jsonb")` (DB)
  - Add `index=True` on columns that have corresponding indexes in migration
---

## 2026-02-05 - S4-004
- **What was implemented:** Ran Alembic migration and verified schema changes
- **Files changed:**
  - None (database schema update only)
- **Verification results:**
  - Migration 0019 -> 0020 ran successfully
  - All 6 new columns exist: is_approved, is_priority, alternative_keywords, composite_score, relevance_score, ai_reasoning
  - Indexes created: ix_page_keywords_is_approved, ix_page_keywords_is_priority
  - Default values verified: is_approved=False, is_priority=False, alternative_keywords=[]
- **Learnings:**
  - Can run alembic migrations from host machine using `source .venv/bin/activate && alembic upgrade head`
  - Database accessible at localhost:5432 when docker compose db service is running
  - Use `sqlalchemy.inspect()` to verify table columns and indexes programmatically
---

## 2026-02-05 - S4-005
- **What was implemented:** Created Pydantic schemas for keyword generation API
- **Files changed:**
  - `backend/app/schemas/keyword_research.py` - Added 6 new schemas
- **Schemas added:**
  - `KeywordCandidate` - keyword with volume metrics and AI scoring (keyword, volume, cpc, competition, relevance_score, composite_score)
  - `PrimaryKeywordGenerationStatus` - tracks generation progress (status, total, completed, failed, current_page)
  - `PageKeywordsData` - keyword data matching PageKeywords model fields, with `from_attributes=True` for ORM support
  - `PageWithKeywords` - combines CrawledPage summary data with PageKeywords data for approval interface
  - `UpdatePrimaryKeywordRequest` - request to update primary keyword with validation
  - `BulkApproveResponse` - response for bulk approval operations (approved_count)
- **Learnings:**
  - Use `ConfigDict(from_attributes=True)` for schemas that need to be created from SQLAlchemy models
  - Nested schemas work well for combining related data (PageWithKeywords contains PageKeywordsData)
  - Follow existing pattern in keyword_research.py for Field descriptions and validators
---

## 2026-02-05 - S4-006
- **What was implemented:** Created PrimaryKeywordService class for orchestrating keyword generation
- **Files changed:**
  - `backend/app/services/primary_keyword.py` - New service class
  - `backend/app/services/__init__.py` - Added exports for PrimaryKeywordService and KeywordGenerationStats
- **Class features:**
  - Accepts ClaudeClient and DataForSEOClient in __init__
  - `_used_primary_keywords: set[str]` - Tracks keywords already assigned to prevent duplicates
  - `_stats: KeywordGenerationStats` - Dataclass tracking generation metrics (pages processed, tokens, costs, errors)
  - Helper methods: `add_used_keyword()`, `is_keyword_used()`, `reset_stats()`, `get_stats_summary()`
- **Learnings:**
  - Follow LabelTaxonomyService pattern for service class structure
  - Use dataclass for stats to make it easy to track multiple metrics
  - Normalize keywords (lowercase, strip) when checking for duplicates
  - Export both the service class and any related dataclasses from __init__.py
---

## 2026-02-05 - S4-007
- **What was implemented:** Implemented `generate_candidates` async method for generating keyword candidates from page content
- **Files changed:**
  - `backend/app/services/primary_keyword.py` - Added `generate_candidates` method
- **Method features:**
  - Takes CrawledPage data as input: url, title, h1, headings, content_excerpt, product_count, category
  - Builds category-specific prompts with guidelines for product, collection, blog, homepage, other page types
  - Collection pages get e-commerce-focused guidelines with product count context
  - Calls Claude API via `self._claude.complete()` with temperature=0.3 for keyword diversity
  - Parses JSON array response, handles markdown code blocks
  - Returns 20-25 keyword strings (lowercase, stripped)
  - Handles API failures with fallback to title/H1
  - Updates stats: claude_calls, total_input_tokens, total_output_tokens, keywords_generated, errors
- **Learnings:**
  - Reference Old KW research logic/keyword_research.py for prompt structure (generate_keywords_with_llm)
  - Use temperature=0.3 for slight variation in keyword generation (vs 0.0 for deterministic)
  - Category-specific guidelines improve keyword relevance (product=buyer intent, collection=category terms, blog=informational)
  - Always handle markdown code blocks in LLM JSON responses (```json...```)
  - Normalize keywords immediately (lowercase, strip) for consistency
  - Fallback strategy: title first, then H1 if different from title
---

## 2026-02-05 - S4-008
- **What was implemented:** Implemented `enrich_with_volume` async method for getting search volume data from DataForSEO
- **Files changed:**
  - `backend/app/services/primary_keyword.py` - Added `enrich_with_volume` method, added `KeywordVolumeData` import
- **Method features:**
  - Takes list of keyword strings as input
  - Checks DataForSEO availability before making API call
  - Calls `DataForSEOClient.get_keyword_volume_batch()` for batch volume lookup
  - Returns dict mapping keyword (lowercase, normalized) -> KeywordVolumeData
  - Handles failures gracefully: returns empty dict on API errors, empty keywords, or unavailable client
  - Logs API cost for tracking via both per-call log and stats accumulation
  - Updates stats: `dataforseo_calls`, `dataforseo_cost`, `keywords_enriched`, `errors`
- **Learnings:**
  - `KeywordVolumeData` dataclass from dataforseo.py contains: keyword, search_volume, cpc, competition, competition_level, monthly_searches, error
  - `get_keyword_volume_batch()` handles batching automatically (up to 1000 keywords per request)
  - Always normalize keywords (lowercase, strip) when building lookup maps for consistent matching
  - Log both individual API costs and cumulative totals in stats for tracking
---

## 2026-02-05 - S4-009
- **What was implemented:** Implemented `filter_to_specific` async method to filter generic keywords to page-specific ones
- **Files changed:**
  - `backend/app/services/primary_keyword.py` - Added `filter_to_specific` method
- **Method features:**
  - Takes keywords with volume data (dict[str, KeywordVolumeData]) and page context (url, title, h1, content_excerpt, category)
  - Builds prompt with specificity criteria and examples from the old keyword_research.py reference
  - Calls Claude API with temperature=0.0 for deterministic filtering
  - Returns list of dicts with keyword, volume, cpc, competition, and relevance_score (0.0-1.0)
  - Handles API failures by returning all keywords with default relevance score of 0.5
  - Validates relevance scores are in range, handles both dict and string LLM response formats
  - Updates stats: claude_calls, total_input_tokens, total_output_tokens, errors
- **Learnings:**
  - Use temperature=0.0 for filtering tasks (deterministic) vs 0.3 for generation (variety)
  - Request LLM to return relevance_score with each keyword for downstream ranking
  - Handle both `[{"keyword": "...", "relevance_score": 0.9}]` and `["keyword1", "keyword2"]` formats from LLM for robustness
  - Limit prompt to top 50 keywords to avoid token limits
  - Graceful fallback on failure is essential - return all keywords with default 0.5 relevance rather than empty list
---

## 2026-02-05 - S4-010
- **What was implemented:** Implemented `calculate_score` method to calculate composite keyword scores
- **Files changed:**
  - `backend/app/services/primary_keyword.py` - Added `calculate_score` method and `import math`
- **Method features:**
  - Takes volume (int/float/None), competition (float/None), and relevance (float) as inputs
  - Calculates volume_score: `min(50, max(0, log10(volume) * 10))` - logarithmic scale capped at 50
  - Calculates competition_score: `(1 - competition) * 100` - lower competition = higher score
  - Calculates relevance_score: `relevance * 100`
  - Returns composite: `(volume_score * 0.50) + (relevance_score * 0.35) + (competition_score * 0.15)`
  - Returns dict with all individual scores and composite score, rounded to 2 decimal places
- **Edge case handling:**
  - Zero/null/negative volume: volume_score = 0
  - Null competition: defaults to 50 (mid-range)
  - High volume (>100,000): capped at 50 by the min() function
- **Learnings:**
  - Use `math.log10()` for logarithmic volume scoring - makes the scale more meaningful (1000 searches = 30, 10000 = 40, 100000 = 50)
  - Return dict with all component scores for transparency and debugging
  - Round scores to 2 decimal places for cleaner output
---

## 2026-02-05 - S4-011
- **What was implemented:** Implemented `select_primary_and_alternatives` method to select best keyword and alternatives
- **Files changed:**
  - `backend/app/services/primary_keyword.py` - Added `select_primary_and_alternatives` method
- **Method features:**
  - Takes scored_keywords list and optional used_primaries set
  - Sorts keywords by composite_score descending
  - Skips keywords already in used_primaries set
  - Selects highest unused keyword as primary
  - Stores next 4 highest-scoring unused keywords as alternatives
  - Adds selected primary to used_primaries via `add_used_keyword()` method
  - Returns dict with 'primary', 'alternatives', and 'all_keywords' keys
- **Edge case handling:**
  - Empty scored_keywords list: returns None primary, empty alternatives
  - All keywords already used: returns None primary with warning log
  - Missing keyword field or empty string: skips the keyword
  - None composite_score: treated as 0 for sorting
- **Learnings:**
  - Use existing `add_used_keyword()` method rather than directly modifying the set
  - If `used_primaries` param is None, fall back to instance's `_used_primary_keywords` set
  - Normalize keywords to lowercase for consistent duplicate checking
  - Return `all_keywords` (full sorted list) in result for debugging/transparency
---

## 2026-02-05 - S4-012
- **What was implemented:** Implemented `process_page` method to orchestrate the full keyword pipeline for a single page
- **Files changed:**
  - `backend/app/services/primary_keyword.py` - Added `process_page` async method, added AsyncSession and TYPE_CHECKING imports
- **Method features:**
  - Takes CrawledPage and AsyncSession as inputs
  - Orchestrates all 5 pipeline methods in sequence: generate_candidates → enrich_with_volume → filter_to_specific → calculate_score → select_primary_and_alternatives
  - Creates new PageKeywords record or updates existing one (via page.keywords relationship)
  - Returns dict with success status, page_id, primary_keyword, composite_score, alternatives
  - Commits on success, rolls back on failure
- **Error handling:**
  - Catches all exceptions, logs with context, and rolls back transaction
  - Updates stats: pages_processed, pages_succeeded, pages_failed, errors list
  - Handles missing volume data by creating placeholder KeywordVolumeData objects
  - Handles empty candidates or filtered results by raising with meaningful message
- **Learnings:**
  - Access page.keywords relationship for existing one-to-one related record (returns None if doesn't exist)
  - Import PageKeywords inside method to avoid circular import
  - Use placeholder KeywordVolumeData when DataForSEO unavailable to allow pipeline to continue
  - Always rollback db session on error to avoid partial state
---

## 2026-02-05 - S4-013
- **What was implemented:** Implemented `generate_for_project` method to process all pages in a project for keyword generation
- **Files changed:**
  - `backend/app/services/primary_keyword.py` - Added `generate_for_project` async method
- **Method features:**
  - Takes project_id and AsyncSession as inputs
  - Loads all CrawledPages with status=completed, ordered by normalized_url
  - Resets stats and used_primaries set for fresh generation
  - Loops through pages calling `process_page()` for each
  - Updates `project.phase_status["onboarding"]["keywords"]` with progress after each page
  - Tracks current_page being processed for frontend display
  - Returns final status with total, completed, failed counts and full stats summary
- **Progress tracking structure in phase_status:**
  ```json
  {
    "onboarding": {
      "keywords": {
        "status": "generating|completed|partial|failed",
        "total": 10,
        "completed": 5,
        "failed": 0,
        "current_page": "https://example.com/page"
      }
    }
  }
  ```
- **Error handling:**
  - Handles project not found case
  - Handles zero completed pages (returns success with empty results)
  - Catches unexpected exceptions and attempts to update phase_status with failure info
  - Uses `flag_modified(project, "phase_status")` for JSONB updates
- **Learnings:**
  - Use `flag_modified()` from sqlalchemy.orm.attributes for JSONB field mutations
  - Import models inside method to avoid circular imports (CrawledPage, CrawlStatus, Project)
  - Reset service state (stats + used_primaries) at start of project-level operation
  - Commit after each page to enable real-time progress tracking via frontend polling
  - Final status can be "completed" (no failures), "partial" (some failures), or "failed" (all failures)
---

## 2026-02-05 - S4-014
- **What was implemented:** Unit tests for the scoring formula in PrimaryKeywordService
- **Files changed:**
  - `backend/tests/services/test_primary_keyword_service.py` (new file, 27 tests)
- **Test coverage:**
  - High volume, low competition scenarios (3 tests)
  - Low volume, high relevance scenarios (2 tests)
  - Zero volume handling (2 tests)
  - Null value handling (3 tests)
  - Formula weight verification - 50/35/15 (4 tests)
  - Edge cases: float volume, boundary values, rounding (5 tests)
  - KeywordGenerationStats dataclass (2 tests)
  - Service initialization and state management (6 tests)
- **Learnings:**
  - Test files go in `backend/tests/services/` directory (not `unit/`)
  - Mock clients only need `available` attribute for service initialization
  - Follow pattern from `test_label_taxonomy.py` for test class organization
  - Run `ruff check --fix` to auto-fix import sorting issues
---

## 2026-02-05 - S4-015
- **What was implemented:** Unit tests for duplicate prevention in PrimaryKeywordService
- **Files changed:**
  - `backend/tests/services/test_primary_keyword_service.py` - Added 13 new tests (40 total)
- **Test coverage:**
  - Used keyword is skipped (3 tests) - single skip, multiple skips, case-insensitive
  - Next best selection (2 tests) - maintains sort order, alternatives exclude used keywords
  - All keywords used behavior (3 tests) - returns None, selects last available, empty list
  - Used primaries set updates (5 tests) - primary added, alternatives not added, accumulates, no modification when none selected, custom set respected
- **Acceptance criteria verified:**
  - [x] Test that used keyword is skipped
  - [x] Test that next best is selected when first is used
  - [x] Test behavior when all top keywords are used
  - [x] Test used_primaries set is updated correctly
- **Learnings:**
  - `select_primary_and_alternatives` method checks used_primaries set to skip duplicates
  - Keywords are normalized (lowercase, stripped) for consistent duplicate checking
  - Only the selected primary is added to used_primaries, not alternatives
  - Method accepts optional custom used_primaries set parameter but still adds to instance set
---

## 2026-02-05 - S4-016
- **What was implemented:** Integration tests for the primary keyword generation pipeline
- **Files changed:**
  - `backend/tests/integrations/test_primary_keyword_generation.py` (new file, 29 tests)
- **Test coverage:**
  - Full pipeline with mocked Claude and DataForSEO (4 tests + 2 skipped)
  - Fallback when Claude fails (3 tests)
  - Fallback when DataForSEO fails (4 tests)
  - PageKeywords record creation (6 tests)
  - Alternatives storage (5 tests)
  - Project-level generation (2 tests + 3 skipped)
- **Acceptance criteria verified:**
  - [x] Test full pipeline with mocked Claude and DataForSEO
  - [x] Test fallback when Claude fails
  - [x] Test fallback when DataForSEO fails
  - [x] Test PageKeywords record is created correctly
  - [x] Test alternatives are stored correctly
- **Learnings:**
  - SQLite async tests with aiosqlite don't support lazy loading - must use `selectinload` for relationships
  - Use helper functions `get_page_with_keywords()` and `get_page_keywords()` to avoid lazy load issues
  - `db_session.expire_all()` can force fresh loads but must save IDs first since expired objects can't be accessed
  - Tests that call `generate_for_project` need PostgreSQL because the method fetches pages without eager loading
  - Mock clients for Claude and DataForSEO need `available` property and appropriate async methods
---

## 2026-02-05 - S4-017
- **What was implemented:** POST `/api/v1/projects/{project_id}/generate-primary-keywords` endpoint
- **Files changed:**
  - `backend/app/api/v1/projects.py` - Added endpoint and background task function
- **Endpoint features:**
  - Returns 202 Accepted with task_id
  - Validates project exists (404 if not)
  - Validates completed pages exist (400 if no pages with status=completed)
  - Updates `phase_status.onboarding.status` to `"generating_keywords"`
  - Initializes `phase_status.onboarding.keywords` with progress tracking structure
  - Starts `_generate_keywords_background` task to run `PrimaryKeywordService.generate_for_project`
- **Learnings:**
  - Follow the crawl endpoint pattern for background tasks: use `db_manager.session_factory()` context manager
  - Create fresh client instances in background tasks (ClaudeClient, DataForSEOClient)
  - Return task_id in response for frontend polling
  - Pre-initialize phase_status progress structure before starting background task for immediate progress visibility
---

## 2026-02-05 - S4-018
- **What was implemented:** GET `/api/v1/projects/{project_id}/primary-keywords-status` endpoint
- **Files changed:**
  - `backend/app/api/v1/projects.py` - Added status endpoint, imported PrimaryKeywordGenerationStatus schema
  - `backend/app/schemas/keyword_research.py` - Added `error` field to PrimaryKeywordGenerationStatus schema
  - `backend/tests/api/test_projects.py` - Added TestPrimaryKeywordsStatus class with 6 tests
- **Endpoint features:**
  - Returns 200 with PrimaryKeywordGenerationStatus schema
  - Returns status (pending/generating/completed/failed)
  - Returns progress counts (total, completed, failed)
  - Returns current_page being processed (URL or None)
  - Returns error message if generation failed
  - Reads from `project.phase_status["onboarding"]["keywords"]`
  - Raises 404 if project not found
- **Test coverage:**
  - test_get_status_project_not_found - 404 for non-existent project
  - test_get_status_no_keywords_yet - Returns pending status with zero counts
  - test_get_status_with_progress - Returns accurate progress during generation
  - test_get_status_completed - Returns completed status with final counts
  - test_get_status_failed - Returns failed status
  - test_get_status_failed_with_error_message - Returns error message when failed
- **Learnings:**
  - Follow crawl-status endpoint pattern for status polling endpoints
  - Use `.get()` with defaults when reading optional JSONB nested fields
  - Extend existing schemas (PrimaryKeywordGenerationStatus) when needed to add error field
  - Project model uses `site_url` not `website_url`
---

## 2026-02-05 - S4-019
- **What was implemented:** GET `/api/v1/projects/{project_id}/pages-with-keywords` endpoint
- **Files changed:**
  - `backend/app/api/v1/projects.py` - Added endpoint with joinedload query
  - `backend/tests/api/test_projects.py` - Added TestPagesWithKeywords class with 6 tests
- **Endpoint features:**
  - Returns list of CrawledPages with their PageKeywords data
  - Uses `joinedload(CrawledPage.keywords)` for efficient single-query loading
  - Filters to only status=completed pages
  - Orders by normalized_url for consistent display
  - Maps to PageWithKeywords/PageKeywordsData schemas
  - Returns null keywords for pages without keyword data
- **Test coverage:**
  - test_pages_with_keywords_project_not_found - 404 for non-existent project
  - test_pages_with_keywords_empty_project - Returns empty list
  - test_pages_with_keywords_only_completed_pages - Filters non-completed pages
  - test_pages_with_keywords_ordered_by_url - Verifies URL ordering
  - test_pages_with_keywords_includes_keyword_data - Full keyword data validation
  - test_pages_with_keywords_null_keywords - Handles pages without keywords
- **Learnings:**
  - Use `joinedload` from `sqlalchemy.orm` for efficient eager loading of relationships
  - Call `.unique().all()` after `scalars()` when using joinedload to deduplicate results
  - Manually map ORM objects to Pydantic schemas when nested relationships need transformation
  - PageKeywordsData schema has `from_attributes=True` but manual mapping gives more control
---

## 2026-02-05 - S4-020
- **What was implemented:** PUT `/api/v1/projects/{project_id}/pages/{page_id}/primary-keyword` endpoint
- **Files changed:**
  - `backend/app/api/v1/projects.py` - Added endpoint, imported PageKeywords model and UpdatePrimaryKeywordRequest schema
  - `backend/tests/api/test_projects.py` - Added TestUpdatePrimaryKeyword class with 8 tests
- **Endpoint features:**
  - Accepts keyword in request body via UpdatePrimaryKeywordRequest schema
  - Updates primary_keyword field on PageKeywords record
  - Clears volume data (search_volume, composite_score, relevance_score) if custom keyword not in alternatives
  - Preserves volume data from alternatives if keyword matches (case-insensitive)
  - Returns full PageKeywordsData response with all fields
  - Validates page exists and has keywords generated (404 otherwise)
- **Test coverage:**
  - test_update_primary_keyword_project_not_found - 404 for non-existent project
  - test_update_primary_keyword_page_not_found - 404 for non-existent page
  - test_update_primary_keyword_no_keywords_generated - 404 when keywords not generated
  - test_update_primary_keyword_success - Basic keyword update
  - test_update_primary_keyword_from_alternatives - Preserves volume data from alternatives
  - test_update_primary_keyword_clears_volume_for_custom - Clears volume for custom keywords
  - test_update_primary_keyword_validation_empty - Validates empty keyword (422)
  - test_update_primary_keyword_returns_full_data - Full response data validation
- **Learnings:**
  - Use `joinedload` to eager-load the keywords relationship when fetching page by ID
  - Use `scalar_one_or_none()` when expecting single result with potential null
  - Alternative keywords can be stored as dict format (KeywordCandidate) - handle both dict and string formats
  - Case-insensitive keyword matching: normalize to lowercase for comparison
  - Keep primary_keyword in original casing from user input, normalize only for comparison
---

## 2026-02-05 - S4-021
- **What was implemented:** POST `/api/v1/projects/{project_id}/pages/{page_id}/approve-keyword` endpoint
- **Files changed:**
  - `backend/app/api/v1/projects.py` - Added approve-keyword endpoint
  - `backend/tests/api/test_projects.py` - Added TestApproveKeyword class with 6 tests
- **Endpoint features:**
  - Sets `is_approved=true` on PageKeywords record
  - Returns updated PageKeywordsData with all fields
  - Idempotent - calling multiple times is safe (always sets is_approved=true)
  - Validates project exists (404 if not)
  - Validates page exists in project (404 if not)
  - Validates keywords generated for page (404 if not)
- **Test coverage:**
  - test_approve_keyword_project_not_found - 404 for non-existent project
  - test_approve_keyword_page_not_found - 404 for non-existent page
  - test_approve_keyword_no_keywords_generated - 404 when keywords not generated
  - test_approve_keyword_success - Sets is_approved=true
  - test_approve_keyword_idempotent - Calling twice returns same result
  - test_approve_keyword_returns_full_data - Full response data validation
- **Learnings:**
  - Follow S4-020 pattern for page+keywords endpoint structure
  - POST without request body is valid for idempotent state-change operations
  - Reuse existing patterns: `joinedload`, `scalar_one_or_none()`, PageKeywordsData response mapping
---

## 2026-02-05 - S4-022
- **What was implemented:** POST `/api/v1/projects/{project_id}/approve-all-keywords` endpoint
- **Files changed:**
  - `backend/app/api/v1/projects.py` - Added approve-all-keywords endpoint, imported BulkApproveResponse schema
  - `backend/tests/api/test_projects.py` - Added TestApproveAllKeywords class with 6 tests
- **Endpoint features:**
  - Sets `is_approved=true` for all PageKeywords in project
  - Only approves keywords for pages with status=completed
  - Returns BulkApproveResponse with approved_count
  - Returns count of *newly* approved (already approved don't add to count)
  - Idempotent - calling multiple times is safe
  - Validates project exists (404 if not)
- **Test coverage:**
  - test_approve_all_keywords_project_not_found - 404 for non-existent project
  - test_approve_all_keywords_no_pages - Returns 0 when no pages
  - test_approve_all_keywords_pages_without_keywords - Returns 0 when pages have no keywords
  - test_approve_all_keywords_success - Approves multiple keywords, counts correctly
  - test_approve_all_keywords_idempotent - Second call returns 0
  - test_approve_all_keywords_only_completed_pages - Only approves for completed pages
- **Learnings:**
  - Use `select().join()` to query PageKeywords through CrawledPage for project filtering
  - Track count of *newly* approved vs already approved for accurate response
  - Filter by page status=completed to match single-page approve behavior
---

## 2026-02-05 - S4-023
- **What was implemented:** PUT `/api/v1/projects/{project_id}/pages/{page_id}/priority` endpoint
- **Files changed:**
  - `backend/app/api/v1/projects.py` - Added toggle_priority endpoint
  - `backend/tests/api/test_projects.py` - Added TestTogglePriority class with 8 tests
- **Endpoint features:**
  - Toggles is_priority value (true->false, false->true) by default
  - Accepts optional `value` query parameter to set explicit value
  - Returns updated PageKeywordsData with all fields
  - Validates project exists (404 if not)
  - Validates page exists in project (404 if not)
  - Validates keywords generated for page (404 if not)
- **Test coverage:**
  - test_toggle_priority_project_not_found - 404 for non-existent project
  - test_toggle_priority_page_not_found - 404 for non-existent page
  - test_toggle_priority_no_keywords_generated - 404 when keywords not generated
  - test_toggle_priority_false_to_true - Toggles false to true
  - test_toggle_priority_true_to_false - Toggles true to false
  - test_toggle_priority_explicit_value_true - Sets explicit true value
  - test_toggle_priority_explicit_value_false - Sets explicit false value
  - test_toggle_priority_returns_full_data - Full response data validation
- **Learnings:**
  - Boolean toggle pattern: use `not current_value` for toggle behavior
  - Optional query parameters with `| None` type allow explicit value setting
  - Follow existing patterns from S4-020/S4-021 for page+keywords endpoint structure
---

