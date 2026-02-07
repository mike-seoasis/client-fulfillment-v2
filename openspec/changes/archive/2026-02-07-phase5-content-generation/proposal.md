## Why

After Phase 4, users can upload URLs, crawl pages, generate keywords, and approve them. But there's nothing to do with those approved keywords yet. Phase 5 builds the core content generation pipeline: fetch a POP content brief for each approved keyword, write SEO-optimized content using Claude (guided by the brief + brand voice), and run quality checks. This is the highest-value feature in the tool — it's where approved keywords become ready-to-publish collection page copy.

## What Changes

**New services (backend):**
- **POP Content Brief service** — Orchestrates the 2-step POP API flow: (1) get-terms to retrieve LSI terms + prepareId, (2) create-report to get the full content brief with word count targets, heading targets, keyword placement, competitors, related questions, and related searches. Parses POP response into ContentBrief model.
- **Content Writing service** — Generates 4 content fields per page (page title, meta description, top description, bottom description) using Claude. Constructs prompts from: POP content brief targets, brand config voice/tone/vocabulary, page context from crawl data, and LSI terms to include naturally. Stores results in GeneratedContent. Stores full prompt text for each generation step.
- **Content Quality service** — Runs AI trope detection (banned words, em dashes, triplet patterns, rhetorical questions) and optionally calls POP scoring API for content score. Flags content that fails checks.

**New API endpoints:**
- `POST /projects/{id}/generate-content` — Kick off content generation for all approved-keyword pages (background task)
- `GET /projects/{id}/content-generation-status` — Poll generation progress per page
- `GET /projects/{id}/pages/{page_id}/content` — Retrieve generated content + brief + quality results
- `PATCH /projects/{id}/pages/{page_id}/content` — Edit generated content fields
- `POST /projects/{id}/pages/{page_id}/recheck` — Re-run quality checks after editing
- `GET /projects/{id}/pages/{page_id}/prompts` — Retrieve stored prompts for the prompt inspector

**New frontend pages/components:**
- Content generation progress page (step 4 of onboarding flow) showing per-page pipeline status: Brief → Writing → Checking → Done
- Content review link per completed page
- **Prompt Inspector panel** (temporary dev/QA tool) — Side panel that displays the full prompts sent to Claude at each step, with ability to save/copy prompts for offline review. Visible during generation and on the content detail page.

**Model changes:**
- Existing ContentBrief, ContentScore, GeneratedContent models are already defined but need Alembic migration to create tables in the database
- GeneratedContent model may need adjustments: current schema stores one `content_type` per row, but we may want a single-row-per-page approach with all 4 content fields together (design decision)
- New `PromptLog` table (lightweight) to persist prompts sent to Claude for the inspector feature

## Capabilities

### New Capabilities
- `pop-content-brief`: Service that fetches POP content briefs via the 2-step API flow (get-terms → create-report), parses the response into structured data (LSI terms, word count targets, heading targets, competitors, related questions), and stores in ContentBrief model.
- `content-writing`: Service that generates page title, meta description, top description, and bottom description using Claude, guided by POP brief targets + brand config + crawl context. Stores all prompts for transparency.
- `content-quality-checks`: Service that runs AI trope detection (banned words/patterns) and POP scoring on generated content. Returns pass/fail with details.
- `content-generation-api`: API endpoints for triggering content generation (background task with polling), retrieving content, editing content, re-running quality checks, and fetching prompt logs.
- `content-generation-ui`: Frontend content generation progress page with per-page pipeline steps, and a temporary Prompt Inspector side panel for viewing/saving the prompts sent to Claude.

### Modified Capabilities
- `page-keywords`: Content generation requires approved keywords — the generation endpoint will validate that keywords are approved before proceeding.

## Impact

**Backend:**
- New services: `pop_content_brief.py`, `content_writing.py`, `content_quality.py`
- New/extended API endpoints in `projects.py` (or new router file)
- Alembic migration for content_briefs, content_scores, generated_content tables (models exist, tables don't)
- New PromptLog model + migration
- POP client (`integrations/pop.py`) may need a `create_full_report()` method that chains get-terms → create-report

**Frontend:**
- New page: `/projects/[id]/onboarding/content/` (generation progress)
- New components: ContentGenerationProgress, PromptInspector panel
- New API client functions + TanStack Query hooks for content endpoints
- Navigation updates to wire content page into onboarding flow

**Dependencies:**
- POP API key must be configured (already in .env pattern)
- Claude/Anthropic API key (already configured)
- Brand config must exist for the project (Phase 2)
- Keywords must be approved (Phase 4)

**Cost considerations:**
- Each page consumes 1 POP API credit (get-terms) + 1 POP API credit (create-report)
- Each page consumes Claude tokens for content writing
- Quality re-checks consume additional POP credits if POP scoring is used
- **CONSTRAINT: 50 free POP API calls for dev/testing.** All POP-dependent services must be designed with mock/cached responses for development. Only make real POP calls when explicitly testing the integration. Tests must use fixtures, not live API calls.

**Performance considerations:**
- During development: sequential processing is fine, conserve POP credits
- **In production: POP brief fetches and content generation must run in parallel across pages** (e.g., process 3-5 pages concurrently) to avoid slow serial execution when generating content for 10+ pages. The service layer must support configurable concurrency.
