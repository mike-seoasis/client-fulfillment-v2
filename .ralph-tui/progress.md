# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **Approval fields pattern:** `is_approved` uses `Boolean, nullable=False, default=False, server_default=text("false"), index=True`. `approved_at` uses `DateTime(timezone=True), nullable=True`. See `PageKeywords` and `PageContent` models for reference. Import `Boolean` from sqlalchemy.
- **Approval migration pattern:** Reference `0020_add_page_keywords_approval_fields.py` and `0022_add_page_contents_approval_fields.py` for adding approval columns to existing tables. Pattern: `add_column` for each field + `create_index` on `is_approved`. Downgrade drops index first, then columns.

---

## 2026-02-07 - S6-001
- Added `is_approved` (Boolean, default=False, indexed) and `approved_at` (DateTime, nullable) fields to PageContent model
- Files changed: `backend/app/models/page_content.py`
- **Learnings:**
  - Pattern matches PageKeywords.is_approved exactly (lines 88-94 of page_keywords.py)
  - `Boolean` import was not previously in page_content.py — needed to add it to the sqlalchemy import line
  - mypy and ruff both pass clean
---

## 2026-02-07 - S6-002
- Created Alembic migration `0022_add_page_contents_approval_fields.py` adding `is_approved` and `approved_at` to `page_contents` table
- Files changed: `backend/alembic/versions/0022_add_page_contents_approval_fields.py` (new)
- **Learnings:**
  - Followed exact pattern from `0020_add_page_keywords_approval_fields.py` — `is_approved` with `server_default=sa.text("false")`, NOT NULL; `approved_at` as nullable `DateTime(timezone=True)`; index on `is_approved`
  - Downgrade drops index before columns (order matters)
  - Space in project path (`Projects (1)`) causes Alembic's `version_locations` config to split on space; workaround is to set `script_location` to absolute path and clear `version_locations`
  - Migration tested: upgrade, downgrade, re-upgrade all succeed
  - ruff and mypy pass clean
---

## 2026-02-07 - S6-003
- Added content review/editing schemas to `backend/app/schemas/content_generation.py`
- New schemas: `ContentUpdateRequest` (partial update with optional page_title, meta_description, top_description, bottom_description), `ContentBriefData` (keyword, lsi_terms, heading_targets, keyword_targets), `BulkApproveResponse` (approved_count)
- Updated `PageContentResponse` with `is_approved` (bool), `approved_at` (datetime|None), and `brief` (ContentBriefData|None)
- Updated `ContentGenerationStatus` with `pages_approved` (int, default 0)
- Files changed: `backend/app/schemas/content_generation.py`
- **Learnings:**
  - All schemas follow Pydantic v2 conventions (BaseModel, Field, ConfigDict)
  - ContentBriefData uses `list[Any]` for JSONB fields (lsi_terms, heading_targets, keyword_targets) to match the model's flexible JSON structure
  - Pre-existing mypy errors in brand_config.py and config.py are unrelated to this change
  - ruff passes clean
---

## 2026-02-07 - S6-011
- Installed Lexical packages: lexical, @lexical/react, @lexical/html, @lexical/rich-text, @lexical/list (all ^0.40.0)
- Updated frontend TypeScript types in `frontend/src/lib/api.ts` to match backend Pydantic schemas:
  - Added `pages_approved` (number) to `ContentGenerationStatus`
  - Added `is_approved` (boolean) and `approved_at` (string|null) to `PageContentResponse`
  - Added `brief` (ContentBriefData|null) to `PageContentResponse`
  - Added `ContentBriefData` type (keyword, lsi_terms, heading_targets, keyword_targets)
  - Added `ContentUpdateRequest` type (optional page_title, meta_description, top_description, bottom_description)
  - Added `ContentBulkApproveResponse` type (approved_count)
- Files changed: `frontend/package.json`, `frontend/package-lock.json`, `frontend/src/lib/api.ts`
- **Learnings:**
  - Lexical packages all install at same version (0.40.0) — they're a monorepo
  - Backend uses `list[Any]` for JSONB brief fields; mapped to `unknown[]` on frontend for type safety
  - Pre-existing TS error in GenerationProgress.test.tsx (tuple index out of bounds) is unrelated
  - Named content bulk approve `ContentBulkApproveResponse` to avoid collision with existing keyword `BulkApproveResponse`
---

## 2026-02-07 - S6-004
- Added PUT /api/v1/projects/{project_id}/pages/{page_id}/content endpoint for partial content updates
- Accepts ContentUpdateRequest body; updates only provided fields (exclude_unset=True partial update)
- Recalculates word_count by stripping HTML tags from all 4 content fields (matches `_apply_parsed_content` pattern in content_writing.py)
- Clears approval on edit: sets is_approved=False, approved_at=None
- Returns updated PageContentResponse with brief_summary (same construction as GET endpoint)
- Returns 404 if page or PageContent not found
- Files changed: `backend/app/api/v1/content_generation.py`
- **Learnings:**
  - Word count pattern: `re.sub(r"<[^>]+>", " ", value)` then `len(text_only.split())` — used in content_writing.py line 824
  - Partial update via Pydantic: `body.model_dump(exclude_unset=True)` gives only the fields the client sent, so omitted fields stay unchanged
  - Brief summary construction is duplicated between GET and PUT — could be extracted to a helper in future
  - Pre-existing mypy errors in content_extraction.py, crawl4ai.py, crawling.py are unrelated; all router endpoints get "untyped decorator" warnings
  - ruff passes clean
---

## 2026-02-07 - S6-005
- Added POST /api/v1/projects/{project_id}/pages/{page_id}/approve-content endpoint
- When value=true (default): sets is_approved=True, approved_at=now(UTC)
- When value=false: sets is_approved=False, approved_at=None
- Returns 400 if content status is not 'complete'
- Returns 404 if page or PageContent not found
- Returns updated PageContentResponse with brief_summary
- Files changed: `backend/app/api/v1/content_generation.py`
- **Learnings:**
  - Ruff enforces `datetime.UTC` alias over `timezone.utc` (rule UP017)
  - Followed exact same pattern as approve-keyword in projects.py but adapted for content (added status check for 'complete', set approved_at timestamp)
  - Brief summary construction is duplicated across GET, PUT, and POST approve endpoints — candidate for helper extraction
  - Pre-existing mypy errors unchanged; ruff passes clean
---

## 2026-02-07 - S6-006
- Added POST /api/v1/projects/{project_id}/pages/{page_id}/recheck-content endpoint
- Loads BrandConfig.v2_schema for the project, calls run_quality_checks() with current content fields
- Stores updated qa_results in PageContent, returns full PageContentResponse
- Returns 404 if page or PageContent not found
- Files changed: `backend/app/api/v1/content_generation.py`
- **Learnings:**
  - run_quality_checks() mutates content.qa_results directly (side effect), so just need db.commit() after calling it
  - BrandConfig loading pattern: `select(BrandConfig).where(BrandConfig.project_id == project_id)` then `.v2_schema` — same as `_load_brand_config` in content_generation service
  - Pre-existing mypy errors unchanged; ruff passes clean
---

## 2026-02-07 - S6-007
- Added POST /api/v1/projects/{project_id}/bulk-approve-content endpoint
- Finds all PageContent records for project where status='complete', qa_results.passed=true, and is_approved=False
- Sets each to is_approved=True with approved_at=now(UTC)
- Returns BulkApproveResponse with approved_count (returns 0 if no eligible pages)
- Files changed: `backend/app/api/v1/content_generation.py`
- **Learnings:**
  - JSONB boolean query pattern: `PageContent.qa_results["passed"].as_boolean().is_(True)` — SQLAlchemy's JSONB subscript + as_boolean() cast for querying nested JSON boolean values
  - Join through CrawledPage to filter by project_id: `select(PageContent).join(CrawledPage, PageContent.crawled_page_id == CrawledPage.id).where(CrawledPage.project_id == project_id)`
  - Bulk update pattern: fetch all eligible records, loop to set fields, single commit — simpler than a bulk UPDATE statement and consistent with ORM usage elsewhere
  - Pre-existing mypy errors unchanged; ruff passes clean
---

## 2026-02-07 - S6-008
- Updated GET /api/v1/projects/{project_id}/pages/{page_id}/content to include `brief` field
- Brief data populated from ContentBrief model via `selectinload(CrawledPage.content_brief)` (already loaded)
- Returns ContentBriefData with keyword, lsi_terms (full array), heading_targets (full array), keyword_targets (full array)
- Returns null if no ContentBrief exists for the page
- Existing response fields (brief_summary, qa_results, etc.) unchanged
- Files changed: `backend/app/api/v1/content_generation.py`
- **Learnings:**
  - ContentBriefData schema was already defined in S6-003 and the `brief` field already existed on PageContentResponse — just needed to populate it in the GET endpoint
  - The `selectinload(CrawledPage.content_brief)` was already present in the GET query from previous work, so no query changes needed
  - Pre-existing mypy errors unchanged; ruff passes clean
---

## 2026-02-07 - S6-009
- Updated GET /api/v1/projects/{project_id}/content-generation-status to include `pages_approved` count
- Added `pages_approved` counter in the page iteration loop, increments when `page.page_content.is_approved` is True
- Passed `pages_approved` to the `ContentGenerationStatus` response (schema field already existed from S6-003)
- Existing response fields (overall_status, pages_total, pages_completed, pages_failed, pages) unchanged
- Files changed: `backend/app/api/v1/content_generation.py`
- **Learnings:**
  - The `pages_approved` count is independent of status — a page could theoretically be approved regardless of status, so the approval check is outside the status if/elif block
  - Schema field `pages_approved` was already added in S6-003 with `default=0`, so no schema changes needed
  - Pre-existing mypy errors unchanged; ruff passes clean
---

## 2026-02-07 - S6-012
- Added 4 API functions to `frontend/src/lib/api.ts`: `updatePageContent`, `approvePageContent`, `recheckPageContent`, `bulkApproveContent`
- Added 4 mutation hooks to `frontend/src/hooks/useContentGeneration.ts`: `useUpdatePageContent`, `useApprovePageContent`, `useRecheckPageContent`, `useBulkApproveContent`
- Files changed: `frontend/src/lib/api.ts`, `frontend/src/hooks/useContentGeneration.ts`
- **Learnings:**
  - Content approval pattern mirrors keyword approval: `?value=false` query param to unapprove, same as `approveKeyword` in api.ts
  - `useApprovePageContent` invalidates both `pageContent` and `status` queries (approval count changes the status response); `useBulkApproveContent` only invalidates `status` (no single-page context)
  - `useUpdatePageContent` and `useRecheckPageContent` only invalidate the specific page's content query
  - `useBulkApproveContent` takes a plain `string` (projectId) like `useApproveAllKeywords`, not an object
  - Pre-existing TS error in GenerationProgress.test.tsx (tuple index out of bounds) is unrelated; eslint passes clean
---

## 2026-02-07 - S6-014
- Created `ContentEditorWithSource` tab toggle component for switching between Lexical rendered view and raw HTML textarea
- Modified `LexicalEditor` to use `forwardRef` + `useImperativeHandle` exposing `getHtml()` method via `LexicalEditorHandle` interface
- Added internal `EditorRefPlugin` to capture Lexical editor instance inside LexicalComposer children
- Tab switching: Rendered→HTML serializes Lexical state via `getHtml()`; HTML→Rendered remounts LexicalEditor with incremented `key` so `HtmlLoaderPlugin` re-parses the textarea content
- Tab styling matches wireframe: active tab has `text-palm-500 border-b-2 border-palm-500 font-semibold`, inactive has `text-warm-500 border-transparent`
- HTML source textarea uses dark theme: `bg-warm-900 text-sand-200 font-mono` matching wireframe spec
- Files changed: `frontend/src/components/content-editor/LexicalEditor.tsx` (modified), `frontend/src/components/content-editor/ContentEditorWithSource.tsx` (new)
- **Learnings:**
  - Lexical editor state is encapsulated inside `LexicalComposer` — to read it externally, use an internal plugin (`EditorRefPlugin`) that captures the editor instance via `useLexicalComposerContext`, then expose methods through `useImperativeHandle`
  - `editor.read()` is synchronous — `$generateHtmlFromNodes` assigns to a local variable inside the callback and it's available immediately after the `read()` call returns
  - Remounting LexicalEditor via React `key` prop is the cleanest way to reload new HTML content, since `HtmlLoaderPlugin` only loads on mount/`initialHtml` change
  - `MutableRefObject` type import needed from React for the `EditorRefPlugin` prop typing
  - Pre-existing TS error in GenerationProgress.test.tsx unchanged; eslint passes clean
---

## 2026-02-07 - S6-015
- Created `frontend/src/lib/keyword-variations.ts` — keyword variation generator utility for highlighting
- `generateVariations(keyword)` splits primary keyword into words, generates suffix variations (+s, +es, +ing, +er, +ers) and removal variations (-s, -es, -ing, -er) for each word
- Consonant doubling for CVC words (run → running, runner)
- Silent-e handling (bake → baking, baker)
- Returns Set<string> of all lowercase variations, excluding exact primary keyword and sub-phrases
- Handles edge cases: empty input, single-word keywords, hyphenated words
- Files changed: `frontend/src/lib/keyword-variations.ts` (new)
- **Learnings:**
  - No NLP needed — simple suffix rules cover 90%+ of SEO keyword variations per design decision #3
  - Hyphens treated as word separators (split on `/[\s-]+/`) so "long-tail" generates variations for "long" and "tail" individually
  - Sub-phrase exclusion uses nested loops for all contiguous multi-word subsets of the original keyword
  - Pre-existing TS error in GenerationProgress.test.tsx unchanged; eslint passes clean
---

## 2026-02-07 - S6-013
- Created `frontend/src/components/content-editor/LexicalEditor.tsx` — Lexical editor wrapper component
- LexicalComposer with RichTextPlugin, HistoryPlugin, ListPlugin, OnChangePlugin
- Accepts `initialHtml` prop, converts to Lexical state on mount via `$generateNodesFromDOM` (DOMParser)
- `onChange` callback serializes Lexical state back to HTML via `$generateHtmlFromNodes`
- Supports: headings (H2, H3), paragraphs, bold, italic, ordered/unordered lists
- Editor theme uses project's warm typography styles (warm-gray text, relaxed leading)
- No toolbar — editing via keyboard shortcuts and existing HTML structure
- Files changed: `frontend/src/components/content-editor/LexicalEditor.tsx` (new)
- **Learnings:**
  - Lexical 0.40.0 requires registering node types explicitly: HeadingNode, QuoteNode, ListNode, ListItemNode
  - `$generateNodesFromDOM` needs a browser DOMParser document — use `new DOMParser().parseFromString(html, 'text/html')`
  - `$generateHtmlFromNodes(editor, null)` serializes full content (pass null for selection to get everything)
  - RichTextPlugin requires ErrorBoundary prop (LexicalErrorBoundary from @lexical/react)
  - OnChangePlugin `ignoreSelectionChange` prevents firing onChange on every cursor move
  - HtmlLoaderPlugin pattern: internal plugin component using `useLexicalComposerContext` to access editor in LexicalComposer children
  - Pre-existing TS error in GenerationProgress.test.tsx unchanged; eslint passes clean
---

## 2026-02-07 - S6-016
- Created `frontend/src/components/content-editor/HighlightPlugin.tsx` — Lexical highlight plugin with four layers
- Custom `HighlightNode` extends `ElementNode` to render inline `<span>` elements with CSS classes for each highlight layer
- Layer 1 (`hl-keyword`): exact primary keyword matches get gold half-underline via linear-gradient
- Layer 2 (`hl-keyword-var`): keyword variation matches get lighter gold with dashed bottom border
- Layer 3 (`hl-lsi`): LSI term matches get lagoon/teal background tint and solid bottom border
- Layer 4 (`hl-trope`): AI trope violations get coral wavy underline (no word boundaries, exact substring match)
- Plugin accepts `primaryKeyword`, `variations` (Set), `lsiTerms` (string[]), `tropeRanges` ({text}[])
- Highlight recomputes with 200ms debounce after content changes; skips self-triggered updates via `tag: 'highlight-plugin'`
- Priority system: keyword > keyword-var > LSI > trope; overlapping lower-priority matches are discarded
- CSS styles injected dynamically into editor container; cleanup on unmount
- Registered `HighlightNode` in LexicalEditor's nodes array
- Files changed: `frontend/src/components/content-editor/HighlightPlugin.tsx` (new), `frontend/src/components/content-editor/LexicalEditor.tsx` (modified)
- **Learnings:**
  - `@lexical/mark` MarkNode does NOT store IDs as DOM attributes — `createDOM` returns a bare `<mark>` element with only theme CSS classes, no data attributes for IDs. Custom ElementNode is needed for class-based styling.
  - Custom inline ElementNode pattern: `isInline()` must return `true`, `canBeEmpty()` returns `false`, `canInsertTextBefore/After()` return `false` — prevents Lexical from merging/editing into the highlight wrapper
  - `editor.update()` with `{ tag: 'highlight-plugin' }` prevents infinite loops — the `registerUpdateListener` callback checks `tags.has('highlight-plugin')` to skip self-triggered updates
  - `excludeFromCopy()` returns `true` on HighlightNode so highlights don't contaminate clipboard
  - Trope regex uses no word boundaries (exact substring match) unlike keyword/LSI regexes which use `\b` word boundaries
  - `Spread` type utility imported from `lexical` for serialized node type definitions
  - Pre-existing TS error in GenerationProgress.test.tsx unchanged; eslint passes clean
---

## 2026-02-07 - S6-017
- Created `frontend/src/components/content-editor/HighlightToggleControls.tsx` — three toggle buttons for highlight layers
- `HighlightVisibility` interface tracks keyword/lsi/trope boolean states
- `highlightVisibilityClasses()` utility converts visibility state to container CSS classes (`hide-hl-keyword`, `hide-hl-lsi`, `hide-hl-trope`)
- Button styling matches wireframe: colored backgrounds, colored dot indicators, opacity toggle (1.0 active / 0.4 inactive)
- Keywords + Vars button controls both `hl-keyword` and `hl-keyword-var` layers together
- Added CSS rules to `HighlightPlugin.tsx` `injectHighlightStyles` for container-level toggle: `.hide-hl-keyword .hl-keyword` etc. use `!important` to override inline highlight styles
- Toggle state is local `useState`, no persistence
- Files changed: `frontend/src/components/content-editor/HighlightToggleControls.tsx` (new), `frontend/src/components/content-editor/HighlightPlugin.tsx` (modified)
- **Learnings:**
  - Container-class approach for toggling highlights (`.hide-hl-keyword .hl-keyword { background: none !important }`) is cleaner than directly manipulating each span's inline styles — single class toggle on parent hides all matching children
  - `!important` is needed on the hide rules because the highlight CSS uses specific property values that would otherwise take precedence
  - Pre-existing TS error in GenerationProgress.test.tsx unchanged; eslint passes clean
---
