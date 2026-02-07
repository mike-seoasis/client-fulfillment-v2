## 1. Database & Models

- [ ] 1.1 Create PageContent model (id, crawled_page_id FK unique, page_title, meta_description, top_description, bottom_description, word_count, status enum, qa_results JSONB, generation_started_at, generation_completed_at, created_at, updated_at)
- [ ] 1.2 Create PromptLog model (id, page_content_id FK, step, role, prompt_text, response_text, model, input_tokens, output_tokens, duration_ms, created_at)
- [ ] 1.3 Update ContentBrief model if needed (verify lsi_terms, related_searches, raw_response, pop_task_id fields match design)
- [ ] 1.4 Add relationships: CrawledPage.page_content (one-to-one), PageContent.prompt_logs (one-to-many), CrawledPage.content_brief (one-to-one)
- [ ] 1.5 Create Alembic migration for content_briefs, page_content, and prompt_logs tables
- [ ] 1.6 Run migration and verify tables exist

## 2. POP Content Brief Service

- [ ] 2.1 Create POPMockClient that returns realistic fixture LSI terms (15-25 terms with weights/counts), seeded by keyword hash for deterministic output
- [ ] 2.2 Create pop_content_brief service with fetch_content_brief() that calls POP get-terms, polls for result, and parses lsaPhrases/variations/prepareId into ContentBrief record
- [ ] 2.3 Add caching logic: check for existing ContentBrief before making API call, support force_refresh=True to bypass cache
- [ ] 2.4 Wire POP_USE_MOCK env var to toggle between real POPClient and POPMockClient
- [ ] 2.5 Write tests for POP content brief service (mock mode, caching, error handling)

## 3. Content Writing Service

- [ ] 3.1 Create prompt builder that constructs structured prompts from ContentBrief + brand config + CrawledPage context (system prompt from ai_prompt_snippet, user prompt with Task/Page Context/SEO Targets/Brand Voice/Output Format sections)
- [ ] 3.2 Create content writing service with generate_content() that calls Claude Sonnet, parses JSON response into PageContent fields, handles retries for invalid JSON
- [ ] 3.3 Add PromptLog creation: log system prompt, user prompt, response text, token usage, and duration for every Claude call
- [ ] 3.4 Add fallback prompt construction when ContentBrief is missing (use default 300-400 word target, omit LSI terms)
- [ ] 3.5 Write tests for prompt construction (with brief, without brief, brand config injection) and content parsing

## 4. Content Quality Checks Service

- [ ] 4.1 Create AI trope detector with checks: banned words (from brand config), em dashes, AI opener patterns ("In today's...", "Whether you're...", "Look no further", etc.), excessive triplet lists (>2), excessive rhetorical questions (>1 outside FAQ)
- [ ] 4.2 Return structured qa_results: {passed: bool, issues: [{type, field, description, context}], checked_at: timestamp}
- [ ] 4.3 Write tests for each trope detection rule with positive and negative cases

## 5. Content Generation Pipeline & API

- [ ] 5.1 Create content generation pipeline orchestrator: for each approved page, run brief → write → check with status updates at each step
- [ ] 5.2 Add asyncio.Semaphore-based concurrency control (CONTENT_GENERATION_CONCURRENCY env var, default 1)
- [ ] 5.3 Create POST /projects/{id}/generate-content endpoint (returns 202, starts background task, validates approved keywords exist, prevents duplicate runs)
- [ ] 5.4 Create GET /projects/{id}/content-generation-status endpoint (returns overall status, per-page status array with page_id, url, keyword, status, error)
- [ ] 5.5 Create GET /projects/{id}/pages/{page_id}/content endpoint (returns PageContent + ContentBrief summary + qa_results)
- [ ] 5.6 Create GET /projects/{id}/pages/{page_id}/prompts endpoint (returns PromptLog array for prompt inspector)
- [ ] 5.7 Create Pydantic schemas for all new endpoints (request/response models)
- [ ] 5.8 Write tests for API endpoints (trigger generation, poll status, retrieve content, retrieve prompts)

## 6. Frontend - Content Generation Page

- [ ] 6.1 Create API client functions and TanStack Query hooks for content generation endpoints (generate, poll status, get content, get prompts)
- [ ] 6.2 Create ContentGenerationProgress page at /projects/[id]/onboarding/content/ with "Generate Content" button and approved page summary
- [ ] 6.3 Build per-page status table with pipeline indicator (Brief → Write → Check → Done) and 3-second polling during generation
- [ ] 6.4 Add completion state: stop polling, show summary (X complete, Y failed), link to view content per page
- [ ] 6.5 Add error handling: failed pages show error description, individual retry option

## 7. Frontend - Prompt Inspector

- [ ] 7.1 Create PromptInspector side panel component with collapsible sections per prompt entry (system prompt, user prompt, response, token usage, duration)
- [ ] 7.2 Add copy-to-clipboard for full prompt text with success toast notification
- [ ] 7.3 Wire prompt inspector to page selection: clicking a page's inspect button opens the panel with that page's prompts
- [ ] 7.4 Add real-time prompt updates during generation (polling includes new PromptLog entries)

## 8. Navigation & Integration

- [ ] 8.1 Add content generation page as step 4 in onboarding flow (Upload → Crawl → Keywords → Content)
- [ ] 8.2 Update onboarding progress indicator/stepper to include step 4
- [ ] 8.3 Add navigation from keyword approval page to content generation page

## 9. Verification

- [ ] 9.1 End-to-end test: trigger generation in mock mode, verify all pages get content, prompts are logged, quality checks run
- [ ] 9.2 Manual verification: run pipeline with mock POP, verify prompt inspector shows correct prompts, quality check results display properly
- [ ] 9.3 Update V2_REBUILD_PLAN.md with Phase 5 completion status
