# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **Model pattern**: Models use `UUID(as_uuid=False)` with `str` Mapped type, `server_default=text("gen_random_uuid()")`, timestamps use `DateTime(timezone=True)` with `default=lambda: datetime.now(UTC)` and `server_default=text("now()")`. Relationships use `TYPE_CHECKING` imports. Status fields use `String(20)` with str Enum classes.
- **One-to-one relationships**: Use `unique=True` on FK column + `uselist=False` on parent relationship. See PageKeywords and PageContent patterns.
- **Model registration**: Add import to `models/__init__.py` and add to `__all__` list (alphabetical order).

---

## 2026-02-06 - S5-001
- Created `PageContent` SQLAlchemy model with all 4 content fields, status tracking, QA results, and generation timestamps
- Files changed:
  - `backend/app/models/page_content.py` (new) — PageContent model with ContentStatus enum
  - `backend/app/models/crawled_page.py` — Added `page_content` one-to-one relationship and TYPE_CHECKING import
  - `backend/app/models/__init__.py` — Registered PageContent import and __all__ entry
- **Learnings:**
  - Pattern: One-to-one relationships use `unique=True` on FK + `uselist=False` on parent side
  - Pattern: ForeignKey uses `ondelete="CASCADE"` for child models tied to crawled_pages
  - All existing models follow the same UUID/timestamp/status pattern consistently
---

## 2026-02-06 - S5-002
- Created `PromptLog` SQLAlchemy model for persisting all Claude prompts/responses during content generation
- Files changed:
  - `backend/app/models/prompt_log.py` (new) — PromptLog model with all fields per acceptance criteria
  - `backend/app/models/page_content.py` — Added `prompt_logs` one-to-many relationship and TYPE_CHECKING import for PromptLog
  - `backend/app/models/__init__.py` — Registered PromptLog import and __all__ entry
- **Learnings:**
  - Ruff import sorting: `project` sorts before `prompt_log` alphabetically — need to maintain strict alphabetical order by module path
  - Many-to-one pattern: FK column without `unique=True` + `Mapped[list["Child"]]` on parent side for one-to-many
---

## 2026-02-06 - S5-003
- Verified ContentBrief model has all required fields (keyword, lsi_terms, related_searches, raw_response, pop_task_id)
- Changed CrawledPage.content_briefs (list) to CrawledPage.content_brief (one-to-one with uselist=False)
- Added unique=True to ContentBrief.page_id FK for proper one-to-one constraint
- Updated ContentBrief.page back_populates from "content_briefs" to "content_brief"
- Verified PageContent.prompt_logs one-to-many and CrawledPage.page_content one-to-one already existed from S5-001/S5-002
- Files changed:
  - `backend/app/models/crawled_page.py` — Changed content_briefs list relationship to content_brief one-to-one
  - `backend/app/models/content_brief.py` — Added unique=True to page_id FK, updated back_populates
- **Learnings:**
  - When converting list relationship to one-to-one: change Mapped type to Optional, add uselist=False, and add unique=True on FK column
  - Always grep for attribute references in app code before renaming relationship attributes
---

## 2026-02-06 - S5-004
- Created Alembic migration 0021 for Phase 5 content tables
- Migration creates `page_contents` table with unique constraint on `crawled_page_id` (one-to-one with crawled_pages)
- Migration creates `prompt_logs` table with FK to `page_contents`
- Migration upgrades `content_briefs.page_id` index from non-unique to unique (matching S5-003 model change)
- Did NOT create `content_scores` table (deferred to Phase 6)
- Did NOT drop `generated_content` table
- Files changed:
  - `backend/alembic/versions/0021_create_page_contents_and_prompt_logs.py` (new) — Migration file
- **Learnings:**
  - Migration pattern: Use `sa.UniqueConstraint("col", name="uq_table_col")` for explicit unique constraints
  - To upgrade an index from non-unique to unique: drop existing index then recreate with `unique=True`
  - content_briefs table was created in migration 0012 but the unique constraint on page_id was missing — added in this migration
  - venv binaries are at `backend/.venv/bin/` (use `.venv/bin/alembic` not bare `alembic`)
---

## 2026-02-06 - S5-005
- Created `POPMockClient` class in `backend/app/integrations/pop.py` with deterministic fixture data generation
- Mock returns 15-25 realistic LSI terms with phrase, weight (0-100), averageCount, and targetCount fields
- Mock returns keyword variations array (5-10 entries) and fake prepareId string
- Output is deterministic: same keyword always produces same fixture data via SHA-256 seed
- Mock implements same interface as real POPClient: `create_report_task()`, `poll_for_result()`, plus convenience `get_terms()` method
- Added `pop_use_mock` setting to `config.py` (env var: `POP_USE_MOCK`)
- Wired `init_pop()` and `get_pop_client()` to return `POPMockClient` when `POP_USE_MOCK=true`
- Files changed:
  - `backend/app/integrations/pop.py` — Added POPMockClient class, LSI term corpus, updated global client functions
  - `backend/app/core/config.py` — Added `pop_use_mock` bool setting
- **Learnings:**
  - Mock methods that match a real interface but don't use all params: use `# noqa: ARG002` for ruff
  - `random.Random(seed)` provides deterministic random number generation without affecting global state
  - `dict.fromkeys(list)` is a clean Python idiom for ordered deduplication
---

## 2026-02-06 - S5-006
- Created `fetch_content_brief()` async function in `backend/app/services/pop_content_brief.py`
- Service calls POP get-terms endpoint with keyword and target URL, polls for completion
- Parses lsaPhrases into lsi_terms, variations into related_searches, stores raw_response and pop_task_id
- Caching: returns existing ContentBrief if one exists for the page (unless force_refresh=True)
- Force refresh: makes new API call and upserts (updates in place) the existing ContentBrief
- On POP API error or timeout, returns failure result with error details (does NOT raise or block)
- Uses POPMockClient.get_terms() when mock client detected, real client uses create_report_task + poll_for_result
- Registered ContentBriefResult and fetch_content_brief in services/__init__.py
- Files changed:
  - `backend/app/services/pop_content_brief.py` (new) — Service with fetch_content_brief, ContentBriefResult dataclass, parse helpers, upsert helper
  - `backend/app/services/__init__.py` — Added imports and __all__ entries
- **Learnings:**
  - POPMockClient has a convenience `get_terms()` method that combines create+poll, while real POPClient needs separate create_report_task + poll_for_result calls
  - Use `isinstance(client, POPMockClient)` to branch between mock convenience method and real client two-step flow
  - ContentBrief has a `unique=True` on page_id FK, so upsert pattern queries by page_id first then updates or creates
---

## 2026-02-06 - S5-007
- Created `build_content_prompt()` function in `backend/app/services/content_writing.py`
- Returns `PromptPair` dataclass with `system_prompt` and `user_prompt`
- System prompt: injects `ai_prompt_snippet.full_prompt` from brand config v2_schema as brand guidelines
- User prompt has labeled sections: ## Task, ## Page Context (URL, current title, current meta, product count, labels), ## SEO Targets (LSI terms with weights/targetCount, variations, word count target from brief), ## Brand Voice (ai_prompt_snippet content, banned words from vocabulary), ## Output Format (JSON with page_title, meta_description, top_description, bottom_description)
- Fallback mode: when ContentBrief is None, omits LSI terms, uses default 300-400 word target for bottom_description
- Output format specifies: page_title under 60 chars with primary keyword, meta_description under 160 chars for CTR, top_description as plain text 1-2 sentences, bottom_description as HTML with headings and FAQ
- Registered `PromptPair` and `build_content_prompt` in `services/__init__.py`
- Files changed:
  - `backend/app/services/content_writing.py` (new) — Prompt builder with build_content_prompt, PromptPair dataclass, and section builder helpers
  - `backend/app/services/__init__.py` — Added imports and __all__ entries for PromptPair and build_content_prompt
- **Learnings:**
  - Brand config is stored in `BrandConfig.v2_schema` JSONB (not on Project model). Key sections: `ai_prompt_snippet.full_prompt` for system prompt injection, `vocabulary.banned_words` for banned word lists
  - ContentBrief.lsi_terms is a JSONB list of dicts with keys: phrase, weight, averageCount, targetCount
  - CrawledPage has direct access to product_count, labels, title, meta_description, normalized_url
  - Import sorting: `content_extraction` sorts before `content_writing` alphabetically — ruff enforces strict module path ordering
---

## 2026-02-06 - S5-008
- Created `generate_content()` async function in `backend/app/services/content_writing.py`
- Service calls Claude Sonnet (`claude-sonnet-4-5-20250929`) via a dedicated `ClaudeClient` instance with model override
- Parses JSON response into PageContent fields (page_title, meta_description, top_description, bottom_description, word_count)
- If Claude returns invalid JSON, retries once with stricter prompt (temperature 0.0); if still invalid, marks status='failed' with error in qa_results JSONB
- Creates PromptLog records: one for system prompt, one for user prompt, both updated with response_text, input_tokens, output_tokens, duration_ms after completion
- Updates PageContent.status progression: writing → complete (or failed)
- Sets generation_started_at when writing begins, generation_completed_at when done (success or failure)
- Added helper functions: `_parse_content_json` (handles markdown fences + regex extraction), `_apply_parsed_content` (populates fields + word count), `_update_prompt_logs`, `_mark_failed`
- Registered `ContentWritingResult` and `generate_content` in `services/__init__.py`
- Files changed:
  - `backend/app/services/content_writing.py` — Added generate_content, ContentWritingResult, retry logic, parsing helpers
  - `backend/app/services/__init__.py` — Added imports and __all__ entries for ContentWritingResult and generate_content
- **Learnings:**
  - ClaudeClient accepts `model` param in constructor to override default haiku — use `ClaudeClient(model="claude-sonnet-4-5-20250929")` for per-service model selection
  - PageContent has no dedicated `error` column — use `qa_results` JSONB field to store error details when status='failed'
  - ClaudeClient needs explicit `close()` after use when creating ad-hoc instances (not using the global singleton)
  - The `complete()` method returns `CompletionResult` with `text`, `input_tokens`, `output_tokens`, `duration_ms` — but `duration_ms` on the result is the total across retries, so we track our own wall-clock time for PromptLog
---

## 2026-02-06 - S5-009
- Created `run_quality_checks()` function in `backend/app/services/content_quality.py` with 5 deterministic AI trope checks
- Check 1 (banned_word): Word-boundary regex matching against brand config vocabulary.banned_words
- Check 2 (em_dash): Detects em dash character (—) in any content field with surrounding context
- Check 3 (ai_pattern): Detects AI opener phrases ("In today's", "Whether you're", "Look no further", "In the world of", "When it comes to")
- Check 4 (triplet_excess): Flags >2 instances of "X, Y, and Z" triplet list patterns across all fields
- Check 5 (rhetorical_excess): Flags >1 rhetorical question outside FAQ sections (FAQ heading detection strips FAQ content before checking)
- Returns structured QualityResult with passed/issues/checked_at, stored in PageContent.qa_results JSONB
- Registered QualityIssue, QualityResult, run_quality_checks in services/__init__.py
- Files changed:
  - `backend/app/services/content_quality.py` (new) — Quality checks service with run_quality_checks, QualityResult/QualityIssue dataclasses, 5 check functions
  - `backend/app/services/__init__.py` — Added imports and __all__ entries
- **Learnings:**
  - FAQ section stripping: Use `[^<]*` instead of `.*?` (even non-greedy) in HTML tag content matching to avoid crossing tag boundaries
  - SQLAlchemy models can't use `__new__` for test instantiation — instrumented attributes need proper `__init__`; test individual functions with plain dicts instead
  - Import ordering: `content_extraction` sorts before `content_quality` alphabetically (ruff enforces strict module path ordering)
---

## 2026-02-06 - S5-010
- Created `run_content_pipeline()` async function in `backend/app/services/content_generation.py`
- Pipeline orchestrates brief → write → check for each approved-keyword page
- Per-page pipeline: (1) status=generating_brief → fetch POP brief, (2) status=writing → call Claude content writing, (3) status=checking → run quality checks, (4) status=complete
- Uses `asyncio.Semaphore` for concurrency control with `CONTENT_GENERATION_CONCURRENCY` env var (default 1)
- Error isolation: each page processed in its own database session; failures don't affect other pages
- Failed pages get status='failed' with error in qa_results JSONB; error recovery uses a separate session in case the primary session is broken
- Only processes pages where `PageKeywords.is_approved=True`, skips pages with existing complete content (unless `force_refresh=True`)
- Loads page data (ids, urls, keywords) in a read-only session, then processes each page in isolated write sessions
- Returns `PipelineResult` with per-page results and aggregate counts (succeeded/failed/skipped)
- Added `content_generation_concurrency` setting to `config.py` (env var: `CONTENT_GENERATION_CONCURRENCY`)
- Registered `PipelinePageResult`, `PipelineResult`, `run_content_pipeline` in `services/__init__.py`
- Files changed:
  - `backend/app/services/content_generation.py` (new) — Pipeline orchestrator with run_content_pipeline, PipelineResult/PipelinePageResult dataclasses
  - `backend/app/core/config.py` — Added `content_generation_concurrency` int setting
  - `backend/app/services/__init__.py` — Added imports and __all__ entries
- **Learnings:**
  - When reusing variable names across different `select()` calls in the same scope, mypy infers the type from the first assignment — use distinct variable names (`stmt` vs `err_stmt`) to avoid type conflicts
  - `db_manager.session_factory()` can be used directly as an async context manager for background tasks that don't go through FastAPI's dependency injection
  - `generate_content()` already handles PageContent creation and status=WRITING internally, so the pipeline only needs to set status=GENERATING_BRIEF before the brief step and status=CHECKING/COMPLETE after writing
  - Content brief failure is non-blocking: pipeline continues with `content_brief=None` (services degrade gracefully)
---

