## Context

Phase 5 built the content generation pipeline: POP content briefs, Claude-powered writing, and deterministic AI trope quality checks. Content is stored in `PageContent` (4 fields + word_count + status + qa_results JSONB). The current frontend has a read-only preview page at `/projects/[id]/onboarding/content/[pageId]` and a generation progress list page. ContentBrief stores LSI terms, heading targets, and keyword targets in JSONB columns linked to each CrawledPage.

Phase 6 adds editing, highlighting, and approval so the operations team can review AI output, fix issues, and approve for export.

## Goals / Non-Goals

**Goals:**
- Editable content fields with auto-save and manual save
- Lexical rich text editor for bottom_description (HTML content)
- Four-layer highlighting (exact keyword, keyword variations, LSI terms, AI trope violations)
- Live sidebar with stats, quality checks, LSI checklist, and heading outline
- Approval workflow consistent with Phase 4 keyword approval pattern
- Re-run quality checks after human edits

**Non-Goals:**
- POP scoring API integration (deferred — will add post-generation score check later)
- Content versioning / edit history (skip for MVP, can add later)
- Collaborative editing / conflict resolution (single user for MVP)
- Internal linking (separate phase)
- Regenerating a single page from this UI (user can re-trigger from content list)

## Decisions

### 1. Lexical for bottom description only

**Decision:** Use Lexical rich text editor exclusively for the `bottom_description` field. Page title, meta description, and top description use plain HTML inputs/textareas.

**Rationale:** Bottom description is the only field with structured HTML (headings, paragraphs). The other three fields are plain text or very short. Lexical's decorator node system gives us highlighting for free. Using Lexical for all fields would be over-engineering.

**Alternative considered:** TipTap (ProseMirror-based) — rejected because Lexical is already planned for Phase 9 blogs and has better React integration. contenteditable div — rejected because multi-layer highlighting and HTML serialization would be fragile without a proper editor framework.

### 2. Highlighting via Lexical decorator nodes

**Decision:** Implement highlighting using Lexical's `DecoratorNode` or `TextNode` transforms that wrap matched text spans with styled elements. The highlight computation runs client-side by scanning the editor content against the keyword, variation list, LSI terms, and qa_results issues.

**Rationale:** This keeps highlighting as a pure frontend concern — no backend processing needed. Lexical's node system supports overlapping decorations and is designed for exactly this use case. Highlights recompute on content changes so they stay accurate as the user edits.

**Layers:**
- `hl-keyword`: Exact primary keyword matches — solid gold underline (`linear-gradient` lower half)
- `hl-keyword-var`: Keyword variations (word stems/fragments) — lighter gold, dashed underline
- `hl-lsi`: LSI terms from ContentBrief.lsi_terms — lagoon background tint + bottom border
- `hl-trope`: AI trope violations from qa_results.issues — coral wavy `text-decoration: underline wavy`

Each layer toggles independently via header buttons. Keywords + variations toggle together.

### 3. Keyword variations: simple stemming, not NLP

**Decision:** Primary keyword variations are computed by splitting the primary keyword into individual words and matching each word (case-insensitive, word-boundary). For example, "best running shoes" yields variations: "best", "running", "shoes", "shoe", "runner", "runners". Add common plural/singular forms.

**Rationale:** Full NLP stemming (e.g., Porter stemmer) adds a dependency for marginal benefit. Simple word splitting + a small set of common English suffixes (s, es, ing, er, ers) covers 90%+ of real-world cases for SEO keywords. This runs entirely client-side.

**Alternative considered:** Backend stemming with NLTK/spaCy — rejected as overkill, adds dependency, and would need an API round-trip.

### 4. Approval field pattern: match Phase 4 keywords

**Decision:** Add `is_approved` (Boolean, default false, indexed) and `approved_at` (DateTime, nullable) to the PageContent model, matching the Phase 4 `PageKeywords.is_approved` pattern exactly.

**Rationale:** Consistency across the app. The operations team already understands the approve/unapprove toggle from the keywords phase. Same mental model, same UI pattern.

**Migration:** Single Alembic migration adding both columns with server defaults.

### 5. Content brief data exposed through existing GET endpoint

**Decision:** Extend the existing `GET /pages/{page_id}/content` response to include a `brief` object with `lsi_terms`, `heading_targets`, and `keyword_targets` from the ContentBrief model. This avoids adding a separate endpoint.

**Rationale:** The editor page needs content + brief data in a single load. Adding a separate brief endpoint would require an extra API call and coordinated loading states. The ContentBrief is already linked to CrawledPage via `page_id`, same FK chain as PageContent.

**Alternative considered:** Separate `GET /pages/{page_id}/brief` endpoint — rejected because it adds frontend complexity for no benefit.

### 6. Auto-save on blur, not on keystroke

**Decision:** Auto-save triggers on field blur (focus loss) when content has changed, not on every keystroke. A manual "Save Draft" button is also available.

**Rationale:** Keystroke-level saving would create excessive API calls, especially in the Lexical editor. Blur-based saving is a good compromise — saves naturally when the user moves to another field or the sidebar without requiring explicit action. Debounced keystroke saving was considered but blur is simpler and sufficient for single-user MVP.

### 7. Re-run checks is a separate endpoint, not automatic

**Decision:** Quality checks are re-run only when the user explicitly clicks "Re-run Checks", not automatically after every edit.

**Rationale:** The quality checks run synchronously and are fast (pure regex), but auto-running on every blur would create noise in the sidebar while the user is mid-edit. Explicit re-check gives the user control: edit several passages, then verify.

### 8. Frontend state: TanStack Query mutations + cache invalidation

**Decision:** Content updates, approval, and re-checks use TanStack Query mutations that invalidate the page content query cache on success. No Zustand store needed.

**Rationale:** Consistent with how Phases 4 and 5 handle mutations. TanStack Query's `onSuccess` → `queryClient.invalidateQueries` pattern handles refetching automatically.

## Risks / Trade-offs

**[Lexical bundle size]** → Lexical adds ~30-40KB gzipped to the frontend bundle. Acceptable for a tool app, and we'll reuse it in Phase 9 blogs.

**[Highlight performance on large content]** → Scanning 500+ word content for 15+ terms on every render could be slow. Mitigation: debounce highlight recomputation (200ms after last edit), and use Lexical's built-in diffing to only update changed nodes.

**[Approval cleared on edit]** → Editing approved content clears the approval flag. This prevents stale approvals but means the user must re-approve after any edit. Acceptable because the review workflow is: edit → re-check → approve.

**[No edit history]** → We're not tracking content versions. If a user makes a bad edit and saves, there's no undo beyond browser undo. Mitigation: this is MVP, content can be regenerated. Add versioning in a later phase if users report issues.

## Open Questions

None — all decisions resolved during planning discussion.
