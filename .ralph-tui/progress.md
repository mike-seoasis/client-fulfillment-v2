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

