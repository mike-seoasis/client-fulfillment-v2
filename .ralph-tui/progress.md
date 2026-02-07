# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **Approval fields pattern:** `is_approved` uses `Boolean, nullable=False, default=False, server_default=text("false"), index=True`. `approved_at` uses `DateTime(timezone=True), nullable=True`. See `PageKeywords` and `PageContent` models for reference. Import `Boolean` from sqlalchemy.
- **Approval migration pattern:** Reference `0020_add_page_keywords_approval_fields.py` and `0022_add_page_contents_approval_fields.py` for adding approval columns to existing tables. Pattern: `add_column` for each field + `create_index` on `is_approved`. Downgrade drops index first, then columns.
- **Quality check type names:** Backend uses `banned_word`, `em_dash`, `ai_pattern`, `triplet_excess`, `rhetorical_excess`, `tier1_ai_word`, `tier2_ai_excess`, `negation_contrast`. Frontend labels map these for display (e.g., `ai_pattern` → "AI Openers").
- **Auto-save on blur pattern:** Use `useRef` to track last-saved values, compare on blur to detect dirty fields, send only changed fields via partial update. Use discriminated union for save status state: `{ state: 'idle' | 'saving' | 'saved' | 'failed'; at?: number; error?: string }`. For Lexical editor blur, wrap in container div with `onBlur` that checks `e.currentTarget.contains(e.relatedTarget)` to avoid firing on internal focus moves.

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

## 2026-02-07 - S6-018
- Replaced read-only content preview page with full content editor layout
- Two-column layout: left ~65% editor with 4 fields, right ~35% sidebar with QA/stats/LSI/outline
- Header: back link, page URL (from status endpoint), primary keyword badge, highlight toggle controls
- Field 1 — Page Title: text input with live character counter (N / 70, palm-600 under, coral-600 over)
- Field 2 — Meta Description: textarea with live character counter (N / 160)
- Field 3 — Top Description: textarea with live word counter
- Field 4 — Bottom Description: ContentEditorWithSource (Lexical + HTML tabs) with word + heading count footer
- Sidebar cards: Quality Status (pass/fail per check type), Flagged Passages, Content Stats, LSI Terms (found/missing), Heading Outline
- Bottom action bar: save status indicator, Re-run Checks (saves first then rechecks), Save Draft, Approve/Unapprove
- Updated ContentEditorWithSource and LexicalEditor to accept and pass through highlight props (primaryKeyword, variations, lsiTerms, tropeRanges)
- HighlightPlugin now renders inside LexicalEditor when highlight props are provided
- Files changed: `frontend/src/app/projects/[id]/onboarding/content/[pageId]/page.tsx` (replaced), `frontend/src/components/content-editor/ContentEditorWithSource.tsx` (modified), `frontend/src/components/content-editor/LexicalEditor.tsx` (modified)
- **Learnings:**
  - Page URL is not in PageContentResponse — must be fetched from ContentGenerationStatus (status endpoint) which includes `pages[]` with page_id, url, keyword per page
  - LSI terms from brief come as `unknown[]` — need to handle both string and `{term: string}` / `{text: string}` object shapes
  - QA results structure: `{passed: bool, issues: [{type, field, description, context}], checked_at: string}` — check types are lowercase snake_case (banned_word, em_dash, ai_opener, etc.)
  - Highlight toggle visibility classes (hide-hl-keyword etc.) need to be applied on the editor's outer container, not directly on the Lexical root
  - HighlightPlugin is a Lexical plugin that must render inside LexicalComposer — passed through ContentEditorWithSource → LexicalEditor as optional props
  - Pre-existing TS error in GenerationProgress.test.tsx unchanged; eslint passes clean
---

## 2026-02-07 - S6-019
- Enhanced stats sidebar with complete quality panel and content stats
- Fixed quality check types to match backend: `ai_pattern`, `triplet_excess`, `rhetorical_excess`, `tier2_ai_excess` (was using incorrect names: ai_opener, triplet_list, rhetorical_question, tier2_ai_word)
- ContentStatsCard now includes: heading targets from brief (e.g., "Target: 3–8 H2, 4–12 H3"), keyword variation count with listed words, paragraph count
- FlaggedPassagesCard now has "Jump to" button per violation
- Jump-to implementation: searches editor DOM for `.hl-trope` spans matching violation context, scrolls to view with smooth behavior, applies `violation-pulse` CSS animation (1.5s coral background pulse)
- Added `violation-pulse` keyframe animation and `sidebar-scroll` custom scrollbar styles to `globals.css`
- Files changed: `frontend/src/app/projects/[id]/onboarding/content/[pageId]/page.tsx` (modified), `frontend/src/app/globals.css` (modified)
- **Learnings:**
  - Backend quality check types differ from wireframe labels: `ai_pattern` (not ai_opener), `triplet_excess` (not triplet_list), `rhetorical_excess` (not rhetorical_question), `tier2_ai_excess` (not tier2_ai_word)
  - `heading_targets` from brief is `{level, text, min_count, max_count, priority}[]` — use min_count/max_count for target range display
  - TypeScript target doesn't support `for...of` on `Set` or `NodeListOf` without `--downlevelIteration` — use `Array.from()` to convert first
  - Jump-to uses DOM traversal (querySelectorAll + TreeWalker fallback) rather than Lexical API — simpler for read-only element lookup
  - Pre-existing TS error in GenerationProgress.test.tsx unchanged; pre-existing ESLint CSS parsing error on globals.css (Tailwind directives) unchanged; eslint passes clean on TS files
---

## 2026-02-07 - S6-020
- Enhanced existing `LsiTermsCard` component in content editor sidebar to meet full acceptance criteria
- Added "N of M terms used" summary text below header
- Added `lsi-found` CSS class and `cursor-pointer` to found term rows (matching wireframe spec)
- Fixed occurrence count symbol from `x` to `×` (multiplication sign per wireframe)
- Added `onClick` handler on found terms that scrolls editor to first occurrence
- Created `handleJumpToTerm` callback using same DOM traversal pattern as `handleJumpTo` (searches `.hl-lsi` spans first, TreeWalker fallback, smooth scroll + violation-pulse animation)
- Passed `onJumpToTerm` prop from page component to `LsiTermsCard`
- Files changed: `frontend/src/app/projects/[id]/onboarding/content/[pageId]/page.tsx` (modified)
- **Learnings:**
  - LsiTermsCard was mostly built during S6-018 but missing several AC items (CSS class, click handler, summary text, symbol)
  - Jump-to-term reuses the same DOM traversal + violation-pulse pattern from S6-019's `handleJumpTo` — searches `.hl-lsi` spans matching the term text, falls back to TreeWalker text search
  - Pre-existing TS error in GenerationProgress.test.tsx unchanged; eslint passes clean
---

## 2026-02-07 - S6-021
- Enhanced `HeadingOutlineCard` with click-to-scroll functionality for heading outline items
- Added `onJumpToHeading` callback prop that receives heading text and level (H2/H3)
- Added `handleJumpToHeading` in main page component: searches editor DOM for matching heading elements by tag name and text content, scrolls to view with smooth behavior and violation-pulse animation
- Added keyboard accessibility: `role="button"`, `tabIndex={0}`, Enter/Space key handlers
- Added hover styling: `cursor-pointer`, `hover:text-palm-600` transition matching wireframe `.outline-item:hover` spec
- Files changed: `frontend/src/app/projects/[id]/onboarding/content/[pageId]/page.tsx`
- **Learnings:**
  - HeadingOutlineCard was mostly built during S6-018 with parsing, display, and live updates — only missing click-to-scroll
  - Heading scroll uses direct DOM query (`container.querySelectorAll(tag)`) matching by `textContent` — simpler than TreeWalker approach since headings are top-level elements
  - Reuses the same `violation-pulse` animation pattern from S6-019/S6-020 for visual feedback on scroll target
  - Pre-existing TS error in GenerationProgress.test.tsx unchanged; eslint passes clean
---

## 2026-02-07 - S6-022
- Implemented auto-save on blur with dirty tracking and status indicator
- Added `useRef` to track last-saved values per field; on blur, compares current vs saved and sends only dirty fields via `useUpdatePageContent`
- Save status uses discriminated union: `idle` → `saving` → `saved` (with timestamp) or `failed` (with retry)
- Bottom bar indicator: pulsing lagoon dot + "Saving..." during API call, green dot + "Auto-saved just now" on success (updates to relative time), coral "Save failed — click to retry" on failure
- Manual "Save Draft" button saves all fields regardless of dirty state
- Added `onBlur` prop to `ContentEditorWithSource` — uses `e.currentTarget.contains(e.relatedTarget)` check to avoid firing on internal Lexical focus moves
- Files changed: `frontend/src/app/projects/[id]/onboarding/content/[pageId]/page.tsx` (modified), `frontend/src/components/content-editor/ContentEditorWithSource.tsx` (modified)
- **Learnings:**
  - React's `onBlur` bubbles from children — for a container with multiple focusable elements (like Lexical), need `e.currentTarget.contains(e.relatedTarget)` guard to only fire when focus leaves the container entirely
  - `useMutation` `onSuccess`/`onError` callbacks passed to `.mutate()` override the hook-level ones — used this to manage save status state without interfering with query invalidation in the hook
  - Discriminated union `{ state: 'idle' | 'saving' | 'saved' | 'failed' }` with optional fields per variant is cleaner than multiple boolean flags for status tracking
  - `useEffect` with `setInterval` for relative time label — re-runs when `saveStatus` changes (dependency), cleans up interval on unmount/change
  - Pre-existing TS error in GenerationProgress.test.tsx unchanged; eslint passes clean
---

## 2026-02-07 - S6-023
- Bottom action bar was mostly implemented in S6-018/S6-022; this story finalized remaining AC gaps
- Fixed Approve button: now disabled when `content.status !== 'complete'` (was only checking isPending)
- Fixed Approve button text: approved state now shows checkmark + "Approved" (was showing plain "Unapprove" text without checkmark)
- Approved state styling: palm-tinted background (`bg-palm-100 text-palm-700 border-palm-200`) visually distinguishes from default state
- Added spinner SVG to Re-run Checks button when pending (was text-only "Checking...")
- Files changed: `frontend/src/app/projects/[id]/onboarding/content/[pageId]/page.tsx`
- **Learnings:**
  - Most bottom bar functionality was built incrementally across S6-018 (layout + buttons), S6-022 (auto-save indicator), and finalized here
  - `content.status` field on `PageContentResponse` is the right field to check for 'complete' guard on approve
  - Pre-existing TS error in GenerationProgress.test.tsx unchanged; eslint passes clean
---

## 2026-02-07 - S6-024
- Updated content list page to show review table with QA Status, Approval Status, and Action columns after generation completes
- Added `qa_passed`, `qa_issue_count`, `is_approved` fields to `PageGenerationStatusItem` (backend schema + API endpoint + frontend type)
- Exposed `pagesApproved` from `useContentGeneration` hook
- Review table: green checkmark for QA passed, coral warning icon with issue count for QA failed, "Approved"/"Pending" badges for approval status, "Review" link to editor page
- Summary line shows "Approved: N of M" with approved count vs total completed
- "Approve All Ready" button calls `bulkApproveContent`, shows toast with count, disabled when no eligible pages (eligible = complete + QA passed + not yet approved)
- "Continue to Export" button enabled when at least 1 page approved, disabled with title text otherwise
- Generation progress table (PageRow) only shown during generation/idle; review table (ReviewTable) shown when complete/failed
- Files changed: `backend/app/schemas/content_generation.py`, `backend/app/api/v1/content_generation.py`, `frontend/src/lib/api.ts`, `frontend/src/hooks/useContentGeneration.ts`, `frontend/src/app/projects/[id]/onboarding/content/page.tsx`
- **Learnings:**
  - `PageGenerationStatusItem` didn't originally include QA or approval data — needed to extend both backend schema and API endpoint population loop to surface per-page review info
  - Backend `qa_results` is a JSONB dict with `passed` (bool) and `issues` (list) — extracting `len(issues)` gives the issue count for display
  - Review table uses CSS grid (`grid-cols-[1fr_1fr_100px_120px_80px]`) for clean column alignment
  - Bulk approve eligibility count is computed inline in JSX using an IIFE to keep the button text and disabled logic co-located
  - Pre-existing TS error in GenerationProgress.test.tsx unchanged; eslint passes clean
---

## 2026-02-07 - S6-010
- Created comprehensive backend test suite for content editing, approval, recheck, and bulk approve endpoints
- 24 new tests across 7 test classes covering all acceptance criteria:
  - `TestUpdatePageContent` (6 tests): partial single/multi-field update, word count recalculation, approval cleared on edit, 404 for missing content/page
  - `TestApproveContent` (5 tests): approve sets fields, unapprove clears fields, 400 when status not complete, 404 for missing content/page
  - `TestRecheckContent` (4 tests): runs quality checks with results, detects AI trope issues, 404 for missing content/page
  - `TestBulkApproveContent` (4 tests): approves eligible, skips already approved, returns zero when none eligible, skips non-complete status
  - `TestGetContentWithBrief` (2 tests): brief data included when ContentBrief exists, null when missing
  - `TestStatusApprovalCount` (2 tests): pages_approved reflects actual count, zero when none approved
  - `TestEditRecheckApproveFlow` (1 test): full edit → recheck → approve → verify status integration flow
- Files changed: `backend/tests/api/test_content_editing.py` (new)
- **Learnings:**
  - Helper functions (`_create_project`, `_create_page`, `_create_content`, `_create_keywords`) reduce boilerplate significantly — each test creates its own isolated data
  - `run_quality_checks` mutates `content.qa_results` as a side effect — tests can verify the JSONB result directly from the response without needing to re-query
  - Bulk approve JSONB query (`PageContent.qa_results["passed"].as_boolean().is_(True)`) works correctly in SQLite test environment since conftest adapts JSONB→JSON
  - Pre-existing test failure in `test_brand_config.py::TestStartGeneration::test_start_generation_returns_202` (`assert 9 == 10`) is unrelated
  - ruff passes clean after auto-fix of import sorting
---

## 2026-02-07 - S6-025
- Created comprehensive frontend test suite for the content editor page and all sidebar components
- 49 new tests across 11 describe blocks covering all acceptance criteria:
  - `renders all 4 fields with content` (7 tests): page title input, meta description textarea, top description textarea, bottom description via ContentEditorWithSource, 4 field labels, loading skeleton, error state
  - `character counters` (6 tests): correct initial values for title (N/70) and meta (N/160), palm color when under limit, coral color when over limit, live update on title input, live update on meta input
  - `sidebar quality checks` (6 tests): "All Checks Passed" when passed, 8 "Pass" indicators, issue count when failed, per-type issue counts, all 8 check type labels, null qa_results handling
  - `flagged passages` (2 tests): renders when issues exist, hidden when no issues
  - `LSI terms checklist` (5 tests): heading, all terms rendered, "not found" for missing terms, found terms with count, summary "N of M terms used"
  - `approval button` (6 tests): "Approve" when unapproved, "Approved" when approved, mutation call with value=true, mutation call with value=false, disabled when status != complete, palm-tinted styling when approved
  - `rendered/HTML tab switching` (1 test): both tab buttons rendered via ContentEditorWithSource mock
  - `header` (4 tests): page URL, keyword badge, back link, highlight toggle controls
  - `bottom action bar` (4 tests): Save Draft, Re-run Checks, save trigger, recheck trigger
  - `content stats` (4 tests): heading, word count, heading counts, heading targets from brief
  - `heading outline` (3 tests): Structure heading, H2/H3 from HTML, keyboard accessibility
  - `bottom description footer` (2 tests): word count display, heading counts in footer
- Files changed: `frontend/src/app/projects/[id]/onboarding/content/[pageId]/__tests__/page.test.tsx` (new)
- **Learnings:**
  - Mocking Lexical editor: mock the entire `ContentEditorWithSource` module with a simple textarea + test buttons — avoids complex Lexical DOM setup while still testing data flow
  - Mock hooks pattern: define `vi.fn()` at module scope, then `vi.mock('@/hooks/...')` returns a wrapper that calls the fn — allows per-test mock overrides via `mockReturnValue`
  - `useParams` mock must match the route parameter names exactly (`id` and `pageId` for `[id]` and `[pageId]` dynamic segments)
  - Character counter color testing: use `toHaveClass('text-palm-600')` / `toHaveClass('text-coral-600')` on the counter span to verify color state
  - `getAllByText(/\d+ words$/)` pattern avoids ambiguity when multiple elements contain "words" text
  - Pre-existing test failures in GenerationProgress.test.tsx (tuple index), KeywordPageRow.test.tsx, BrandConfigPage.test.tsx are unrelated; eslint and TS pass clean
---

## 2026-02-07 - S6-026
- Manual verification of complete Phase 6 workflow — all acceptance criteria confirmed met
- Verified all 10 AC items against implemented code:
  1. Content list page shows ReviewTable with QA Status, Approval, and Review columns after generation
  2. Editor page loads all 4 fields (page_title, meta_description, top_description, bottom_description) with sidebar (QualityStatusCard, FlaggedPassagesCard, ContentStatsCard, LsiTermsCard, HeadingOutlineCard)
  3. Page title character counter updates live via `titleLen = pageTitle?.length ?? 0` with CharCounter component
  4. Bottom description Lexical editor renders HighlightPlugin with keyword, variation, LSI, and trope layers
  5. ContentEditorWithSource tab switching serializes via `getHtml()` and remounts LexicalEditor via key prop
  6. HighlightToggleControls toggles keyword/lsi/trope layers via container CSS classes
  7. Re-run Checks saves first then calls recheck endpoint; sidebar updates via query invalidation
  8. Approve button toggles state with visual change (palm-tinted bg when approved, checkmark icon)
  9. ReviewTable in content list page shows per-page approval badges from status endpoint
  10. Bulk Approve All Ready calls bulk-approve-content endpoint, shows toast with count
- Backend: 24/24 content editing tests pass; all 6 endpoints verified (GET content, PUT content, POST approve, POST bulk-approve, POST recheck, GET status with approval data)
- Frontend: 485/494 tests pass (9 failures are pre-existing in GenerationProgress, KeywordPageRow, BrandConfigPage)
- TypeScript: only pre-existing tuple error in GenerationProgress.test.tsx
- ESLint: 0 errors, 13 warnings (all pre-existing in keywords page and brand section editors)
- mypy: 5 errors (all pre-existing in content_extraction.py, crawl4ai.py, crawling.py)
- ruff: 4 errors (all pre-existing in pop_content_brief.py)
- No files changed — this was a verification-only story
- **Learnings:**
  - All Phase 6 implementation (S6-001 through S6-025) is complete and coherent
  - End-to-end data flow verified: status endpoint → review table → editor page → save/recheck/approve → back to list
  - No new regressions introduced by Phase 6 work
---

## 2026-02-07 - S6-098
- Updated V2_REBUILD_PLAN.md: marked Phase 6 checkboxes as [x] complete, updated Current Status table (Phase=6 Complete, Next=Phase 7: Export), added session log row summarizing all Phase 6 work (S6-001 through S6-026)
- Files changed: `V2_REBUILD_PLAN.md`
- **Learnings:**
  - Phase 6 encompassed 26 stories (S6-001 through S6-026) covering backend endpoints, Lexical editor, highlight plugins, auto-save, sidebar panels, review table, and comprehensive tests
  - No code changes needed — purely a planning discipline update
---