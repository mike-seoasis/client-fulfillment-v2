## Context

Phase 4 is complete: users can upload URLs, crawl pages, generate primary keywords, and approve them. Phase 5 takes those approved keywords and generates optimized collection page copy.

**Current state:**
- POP API client exists (`integrations/pop.py`) with `create_report_task()` (calls get-terms endpoint), `get_task_result()`, and `poll_for_result()`. No create-report step implemented yet.
- Claude client exists (`integrations/claude.py`) with generic `complete()` method. Currently used only for page categorization.
- Database models exist for ContentBrief, ContentScore, GeneratedContent but **tables have not been created** (no Alembic migration yet).
- Pydantic schemas exist for content generation, briefs, and scores but need adjustments to match the actual content fields we need (page_title, meta_description, top_description, bottom_description).
- Brand config is stored as JSONB on the Project model, including an `ai_prompt_snippet` section specifically designed for injecting into content generation prompts.
- CrawledPage has: title, meta_description, body_content (markdown), headings (JSONB), product_count, labels.

**Constraints:**
- 50 free POP API calls for testing. Must mock POP during development.
- Production must parallelize across pages for speed.
- Content generation is a background task (can take minutes for many pages).

## Goals / Non-Goals

**Goals:**
- Generate 4 content fields per page: page_title, meta_description, top_description, bottom_description
- Use POP content brief data (LSI terms, word count targets, heading targets) to guide content writing
- Use brand config (voice, tone, vocabulary, banned words) to match brand personality
- Run quality checks: AI trope detection (deterministic, no API cost) and POP scoring (optional, costs credits)
- Provide a progress UI with per-page pipeline status
- Store and display prompts sent to Claude (prompt inspector for QA)
- Support configurable concurrency for production parallelism

**Non-Goals:**
- Internal link mapping (Phase 5 in rebuild plan refers to content generation, internal linking is a separate concern)
- Content review/editing UI with HTML toggle and keyword highlighting (that's Phase 6)
- POP scoring iteration loop (regenerate until score >=70) — defer to Phase 6 where user can manually trigger re-checks
- Export to Matrixify (Phase 7)

## Decisions

### 1. Content storage: Single row per page vs multiple rows

**Decision:** Replace the existing `GeneratedContent` model (one row per content_type) with a new `PageContent` model that stores all 4 fields in a single row.

**Rationale:** All 4 content fields are generated together in one Claude call. Tracking status, prompts, and QA results makes more sense at the page level. The existing `GeneratedContent` model was scaffolded before the content structure was finalized and doesn't match our actual needs.

**Schema:**
```
PageContent:
  id: UUID
  crawled_page_id: FK → crawled_pages (unique, one-to-one)
  page_title: text
  meta_description: text
  top_description: text (plain text, short intro)
  bottom_description: text (HTML, longer copy with FAQ)
  word_count: int
  status: enum (pending, generating_brief, writing, checking, complete, failed)
  generation_started_at: datetime
  generation_completed_at: datetime
  created_at, updated_at: datetime
```

**Alternative considered:** Use GeneratedContent with 4 rows per page. Rejected because it complicates status tracking and prompt association — we'd need a parent "generation run" concept anyway.

### 2. POP API flow: Get Terms only (skip Create Report for now)

**Decision:** For the initial implementation, only call POP's get-terms endpoint. Skip the create-report step.

**Rationale:**
- Get-terms returns the LSI terms (lsaPhrases) which are the most valuable data for content writing — these are the terms competitors use that we need to include.
- Create-report costs an additional API credit per page and returns a full scoring report that's more useful AFTER content is written (Phase 6 re-check flow).
- With only 50 free API credits, using 1 credit per page (get-terms) vs 2 credits (get-terms + create-report) doubles our testing budget.
- We can add create-report later when we implement the POP scoring re-check loop.

**What get-terms returns:**
- `lsaPhrases`: Array of {phrase, weight, averageCount, targetCount} — the LSI terms
- `variations`: Array of keyword variations
- `prepareId`: ID for future create-report call (we'll store it for later use)

**Alternative considered:** Full 2-step flow (get-terms → create-report). Deferred because it doubles API cost during development and the scoring data is more useful during the review phase.

### 3. Prompt construction: Structured prompt with sections

**Decision:** Build content writing prompts with clearly labeled sections that the prompt inspector can display.

**Prompt structure:**
```
[SYSTEM] Brand voice instructions (from ai_prompt_snippet)
[USER]
  ## Task
  Generate collection page content for: {keyword}

  ## Page Context
  URL: {url}
  Current title: {current_title}
  Current description: {current_meta}
  Product count: {product_count}
  Page labels: {labels}

  ## SEO Targets (from POP Brief)
  LSI terms to include naturally: {lsi_terms with weights}
  Keyword variations: {variations}
  Target word count: {word_count_target}

  ## Brand Voice
  {ai_prompt_snippet content}
  Banned words: {banned_words from vocabulary}

  ## Output Format
  Return JSON with: page_title, meta_description, top_description, bottom_description
```

**Rationale:** Structured prompts are easier to debug in the inspector, and separating concerns (SEO targets vs brand voice vs output format) makes it clear where to adjust when content quality isn't right.

### 4. Quality checks: AI trope detection only (no POP scoring in Phase 5)

**Decision:** Phase 5 implements only the deterministic AI trope check. POP scoring is deferred to Phase 6 (content review).

**AI trope checks (no API cost):**
- Banned words from brand config vocabulary
- Em dashes (brand standard: never use)
- Common AI patterns: "In today's...", "Whether you're...", "Look no further", triplet lists ("X, Y, and Z" patterns in excess)
- Rhetorical questions in excess

**Rationale:** AI trope detection is free (pure string analysis), fast, and catches the most obvious quality issues. POP scoring requires API credits and is more useful during the iterative review phase where the user can edit and re-check.

### 5. Concurrency: asyncio.Semaphore with configurable limit

**Decision:** Use `asyncio.Semaphore` to control parallel page processing, configurable via environment variable.

```python
CONTENT_GENERATION_CONCURRENCY=1  # Dev: sequential (conserve credits)
CONTENT_GENERATION_CONCURRENCY=5  # Production: parallel
```

**Pipeline per page (sequential within a page):**
1. Fetch POP brief (get-terms) → store ContentBrief
2. Build prompt → store in PromptLog
3. Call Claude → parse response → store PageContent
4. Run AI trope check → store results in PageContent.qa_results
5. Update status to complete

**Across pages:** Semaphore controls how many pages run their pipeline concurrently.

**Rationale:** Simple, no external dependencies (no Celery/Redis). The existing pattern from Phase 4 (BackgroundTasks + polling) works well. Semaphore gives us the production parallelism we need.

### 6. Prompt storage: PromptLog table

**Decision:** Create a lightweight `PromptLog` table to persist prompts.

```
PromptLog:
  id: UUID
  page_content_id: FK → page_content
  step: string (e.g., "content_writing", "quality_check")
  role: string ("system" | "user")
  prompt_text: text
  response_text: text (nullable, filled after completion)
  model: string
  input_tokens: int
  output_tokens: int
  duration_ms: float
  created_at: datetime
```

**Rationale:** Storing prompts in the database means they survive page refreshes, can be queried later, and the prompt inspector can load them at any time. The alternative (in-memory only) would lose prompts on page reload.

### 7. Frontend: Extend onboarding flow, not new standalone page

**Decision:** Add content generation as step 4 of the onboarding flow (`/projects/[id]/onboarding/content/`), consistent with the existing Upload → Crawl → Keywords progression.

**Components:**
- `ContentGenerationProgress` — Main page showing all pages with their pipeline status
- `PromptInspector` — Collapsible side panel showing prompts for a selected page, with copy-to-clipboard and expand/collapse for each prompt section

**Polling:** Same pattern as crawl progress and keyword generation — TanStack Query with 3s refetch interval while status is "generating".

### 8. Mock POP responses for development

**Decision:** Create a `POPMockClient` that returns realistic fixture data, toggled via environment variable.

```
POP_USE_MOCK=true  # Dev: use mock responses
POP_USE_MOCK=false  # Production: real API calls
```

The mock returns pre-built LSI terms, variations, and prepareId based on the keyword, so the full pipeline can be tested end-to-end without spending API credits.

**Rationale:** With only 50 free credits, we need to develop and test the entire pipeline without hitting the API. Mock data lets us verify prompt construction, content parsing, quality checks, and UI without any POP calls.

## Risks / Trade-offs

**[Risk] POP get-terms response format may differ from documentation** → Mitigation: Log raw responses, store in ContentBrief.raw_response. Parse defensively with fallbacks. Test with 1-2 real API calls early to validate parsing.

**[Risk] Claude content quality may be poor initially** → Mitigation: Prompt inspector lets user see exactly what's being sent and iterate on prompt design. Prompts are stored so we can compare versions.

**[Risk] 50 POP credits may not be enough for integration testing** → Mitigation: Mock client for all dev/unit/integration tests. Only use real API for final manual verification. Cache successful POP responses to replay later.

**[Trade-off] Skipping POP create-report means no page scoring in Phase 5** → Acceptable: Scoring is more useful during review (Phase 6). Get-terms gives us the most valuable data (LSI terms) for content writing.

**[Trade-off] Single Claude call for all 4 content fields** → Could split into separate calls for finer control, but a single call is faster, cheaper, and simpler. Can split later if quality suffers.

**[Trade-off] PromptLog table adds database writes per generation** → Lightweight rows (just text), and it's critical for prompt QA during this phase. Can be cleaned up or made optional later.

## Migration Plan

1. Create Alembic migration for: `content_briefs`, `page_content` (new, replacing generated_content), `prompt_logs` tables
2. Do NOT create `content_scores` table yet (deferred to Phase 6)
3. Do NOT drop `generated_content` table if it exists — leave it for now
4. All new code is additive (new services, new endpoints, new pages) — no breaking changes to existing functionality

## Resolved Questions

1. **Claude model:** Use **claude-sonnet-4-5** for all content generation. Quality matters more than speed/cost for this use case.
2. **Content word count targets:** Default fallback is **300-400 words** for bottom_description, but always prefer POP brief word count targets when available. Only use the fallback if POP data is missing or mock mode.
3. **Top description format:** Plain text, just 1-2 sentences describing the collection page. No HTML. Bottom description is the longer HTML copy with headings, FAQ, etc.
