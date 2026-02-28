# Client Onboarding V2 Rebuild Plan

> This document captures everything we've discussed. Use it to pick up where we left off in any new session.

---

## Current Status

| Field | Value |
|-------|-------|
| **Phase** | WP2 - Batched Onboarding — **COMPLETE** |
| **Slice** | WP2: Added onboarding_batch column, batch assignment on upload, ?batch=N filter on 7 endpoints, batches summary endpoint, full frontend batch threading |
| **Last Session** | 2026-02-28 |
| **Next Action** | Phase 13 (Polish), 15 (GEO) — user to decide |
| **Auth Decision** | Neon Auth (free tier, 60K MAU, Better Auth SDK) — see Phase 12 |
| **Backup Decision** | Neon free tier (PITR) + Railway pg_dump template → Cloudflare R2 — see Phase 10 |
| **Database** | Neon PostgreSQL (project: `spring-fog-49733273`, region: `aws-us-east-1`) |
| **Backups** | Cloudflare R2 bucket `client-fullfilment-backups` — every 6 hours via Railway template |

### Session Log

| Date | Completed | Next Up |
|------|-----------|---------|
| 2026-02-02 | Planning complete (FEATURE_SPEC, WIREFRAMES, V2_REBUILD_PLAN, decisions doc) | Phase 0 setup |
| 2026-02-02 | Phase 0 complete (branch setup, backend cleanup, CircuitBreaker refactor, uv migration, Docker, Next.js 14, Tailwind, CI/CD, verification) | Phase 1 |
| 2026-02-03 | Phase 1 complete (Project model updates, Alembic migration, Pydantic schemas, ProjectService, API endpoints, API tests, TanStack Query setup, API client/hooks, Tailwind warm palette, UI components, Header, ProjectCard, Dashboard, ProjectForm, Create Project page, Project Detail page, delete with confirmation, frontend component tests) | Phase 2 |
| 2026-02-03 | Phase 1 polish: Tropical oasis color palette (palm greens, sand, lagoon, coral), sharp corners (rounded-sm), improved card contrast (border-cream-500), design system documented in CLAUDE.md | Phase 2 |
| 2026-02-03 | Phase 2 complete (ProjectFile model, S3 integration with LocalStack, text extraction utils, FileService, file upload API, brand config generation service with research/synthesis phases, brand config API endpoints, multi-step project creation wizard, FileUpload component, GenerationProgress component, SectionNav, 10 brand section display components, inline section editing, regenerate functionality, comprehensive unit/integration/component tests) | Phase 3 |
| 2026-02-04 | Brand config improvements (fixed VoiceCharacteristics crash for we_are_not data format, fixed VoiceDimensions slider positioning, debugged regeneration endpoint, updated Perplexity research prompt for e-commerce focus, enhanced 9 section prompts for richer content, created 4 reusable editor components: TagInput/EditableTable/BulletListEditor/SliderInput, created 10 section-specific editors, added keyboard shortcuts Cmd+S/Escape, added validation and error display, comprehensive unit tests) | Phase 3 |
| 2026-02-04 | Phase 2 polish: Fixed JSON control char parsing for AI prompts, fixed Voice Characteristics field name (characteristic→trait_name), removed Examples Bank section (will add real examples later), renamed button to "Brand Details" | Phase 3 |
| 2026-02-04 | Phase 3 complete (URL upload with paste/CSV, crawling pipeline with Crawl4AI, content extraction with BeautifulSoup, label taxonomy generation with Claude, label assignment service, crawl progress page with polling, retry failed pages, label editing dropdown, project detail onboarding status, comprehensive API and component tests - 47 stories total) | Phase 4 |
| 2026-02-04 | Phase 3 polish: Fixed AsyncSession concurrency bug, improved product count extraction (exclude carousels), added crawl progress spinner UI, improved label prompts (cannabis-storage now works), added regenerate labels button, added recrawl-all endpoint. Deferred label improvements to Phase 3b. | Phase 4 |
| 2026-02-05 | Phase 4 complete (PageKeywords model updates, Alembic migration for approval/scoring fields, PrimaryKeywordService with generate_candidates/enrich_with_volume/filter_to_specific/calculate_score/select_primary_and_alternatives/process_page/generate_for_project methods, 7 API endpoints for keyword generation/status/approval/priority, frontend API client and TypeScript types, useKeywordGeneration/usePagesWithKeywords/useKeywordMutations hooks, keywords page with generation progress UI, KeywordPageRow/AlternativeKeywordDropdown/PriorityToggle/ApproveButton components, inline keyword editing, score tooltips, bulk approve, comprehensive unit/integration/component tests - 51 stories total) | Phase 5 |
| 2026-02-06 | Phase 4 polish: Fixed DataForSEO competition parsing (use competition_index not competition string), fixed keyword scoring normalization (0-100 to 0-1), fixed AlternativeKeywordDropdown backwards compatibility for string[] format, fixed Crawl4AI markdown extraction for nested dict response, improved keyword generation polling (poll during pending state), added unapprove functionality for keywords | Phase 5 |
| 2026-02-06 | Phase 5 planning complete (OpenSpec: proposal, design, 6 specs, tasks, prd.json). Ralph executing: S5-001 PageContent model, S5-002 PromptLog model, S5-003 model relationships, S5-004 Alembic migration, S5-005 POPMockClient, S5-006 POP content brief service, S5-007 prompt builder, S5-008 content writing service. Installed Playwright MCP + Chrome DevTools MCP + enabled agent teams. | Continue S5-009+ (quality checks, API, schemas, frontend, prompt inspector) |
| 2026-02-06 | Phase 5 complete (S5-001 through S5-018): PageContent + PromptLog models, Alembic migration, POPMockClient, POP content brief service, prompt builder, content writing service (Claude Sonnet), quality checks (5 AI trope rules), content generation pipeline orchestrator, Pydantic v2 schemas, 4 API endpoints (trigger/status/content/prompts), frontend API client + TanStack Query hooks, ContentGenerationProgress page, PromptInspector side panel, onboarding navigation, 81 backend tests, end-to-end verification in mock mode (9 pages, 0 failures). | Phase 5 staging deployment + hardening |
| 2026-02-06 | Phase 5 staging: Crawl4AI content filtering (PruningContentFilter for main body extraction), fixed Crawl4AI Railway service (Docker image reconnect), switched POP to real API (POP_USE_MOCK=false), increased Claude max_tokens to 8192 and timeout to 180s for POP word count targets, committed page content view route, Prompt Inspector run grouping with visual separation, POP prepareId debug logging. Full 3-step POP flow verified with real data (LSI terms, competitors, heading structure, word count targets). | Copywriting skill bible + lean content |
| 2026-02-07 | Copywriting skill bible integration: enriched system prompt with writing rules + AI trope avoidance + formatting standards. Lean content strategy: dropped word count targets entirely (length driven by structure not SERP competitors), use POP min heading counts capped at 8 H2/12 H3, use min term frequencies for subheading/paragraph targets (floor of 1), 120-word max per paragraph with no minimum. Pipeline reset fix: page statuses reset to pending on regeneration so frontend indicators clear immediately. Concurrency already supported via CONTENT_GENERATION_CONCURRENCY env var (default 1, set to 3+ for parallel). | Phase 6: Content Review + Editing |
| 2026-02-07 | Phase 6 complete (S6-001 through S6-026): PageContent approval fields + migration, content review/editing schemas, 6 backend endpoints (GET/PUT content, approve, bulk-approve, recheck, status with approval data), Lexical rich text editor with HTML source toggle, keyword variation generator, 4-layer highlight plugin (keyword/variation/LSI/trope) with toggle controls, content editor page (4 fields + sidebar with QA/stats/LSI/outline), auto-save on blur with dirty tracking, bottom action bar (save/recheck/approve), content list review table with QA + approval columns + bulk approve, 24 backend tests + 49 frontend tests, manual verification of all 10 AC items. | Phase 6 polish |
| 2026-02-08 | Phase 6 polish: Competitor name filtering (master list in vocabulary.competitors, auto-seeded from brand config + POP URLs, prompt exclusion, LSI filtering, QA check 9), toolbar block type dropdown fix, approve button status gate removed (approve whenever ready), approve navigates back to content list, review/approved tabs on content list page. | Phase 7: Export |
| 2026-02-08 | Phase 7 complete (S7-001 through S7-010): ExportService with URL handle extraction + filename sanitization, Matrixify CSV generation with UTF-8 BOM, export API endpoint with page_ids filter + 400/404 error handling, frontend export API client with blob download, export page with onboarding stepper + page selection list + select all/deselect all + export summary + download button, Back/Finish Onboarding navigation, 23 tests. Phase 7 polish: Added 7 Matrixify columns (Command, Sort Order, Published, Must Match, Rule: Product Column, Rule: Relation, Rule: Condition), shopify_placeholder_tag field in vocabulary section (backend schema + frontend editor/display), fixed export to read tag from BrandConfig table, updated filename to "Project Name - Onboarding - Matrixify Export via SEOasis.csv", exposed Content-Disposition header via CORS. | Phase 8: Keyword Cluster Creation |
| 2026-02-08 | Phase 8 complete (S8-001 through S8-022): KeywordCluster + ClusterPage models with Alembic migration, CrawledPage source column, Pydantic v2 schemas, ClusterKeywordService (3-stage pipeline: Claude candidate generation with 11 expansion strategies, DataForSEO volume enrichment, Claude filtering/role assignment with composite scoring), bulk approve bridging to CrawledPage + PageKeywords, 6 API endpoints (create/list/detail/update-page/approve/delete), frontend API client + TanStack Query hooks with optimistic updates, seed keyword input page with progress indicator, cluster suggestions page with inline editing + approve/reject + parent reassignment, project detail cluster list with status badges, 52 backend unit tests + 20 integration tests + 71 frontend component tests. | Phase 9: Internal Linking |
| 2026-02-09 | Railway staging fix + production CSS hardening: diagnosed Next.js 14.2.x CSS ordering bug (production chunks load in different order than dev, causing `disabled:opacity-50` cascade issues), added CSS cascade layers (`@layer base, components, utilities`) to lock ordering, created `ButtonLink` component to eliminate invalid `<button>` inside `<a>` HTML nesting, migrated project dashboard buttons, fixed lint error blocking production builds, deployed to Railway via `railway up` (git-triggered deploys were building from stale commit). | Phase 9: Internal Linking |
| 2026-02-10 | Phase 9 complete (S9-001 through S9-032): InternalLink + LinkPlanSnapshot models with Alembic migrations (0024+0025), Pydantic v2 schemas, SiloLinkPlanner (cluster graph with parent/child/sibling edges, onboarding graph with label overlap), budget calculation (clamp 3-5 based on word count), target selection (mandatory parent-first for clusters, priority bonus for onboarding), AnchorTextSelector (POP variations + natural phrase generation via Haiku, diversity-weighted scoring), LinkInjector (rule-based BeautifulSoup scanning + LLM fallback paragraph rewriting, density limits), strip_internal_links for re-planning, LinkValidator (8 rules: budget, silo integrity, self-links, duplicates, density, anchor diversity, first-link, direction), full pipeline orchestrator with progress tracking, re-plan with snapshot/rollback, 8 API endpoints (plan trigger, status polling, link map, page links, suggestions, add/remove/edit), frontend API client + TanStack Query hooks, link planning trigger pages (onboarding + cluster), cluster link map with tree visualization + stats + sortable table, onboarding link map with label grouping + filters, page link detail with add/edit/remove modals + anchor suggestions, project detail link status badges, 28 graph/budget/target unit tests, 21 anchor text tests, 24 injection tests, 36 validation tests, 5 integration pipeline tests, 21 API tests, 86 frontend component tests. | Phase 10: Database Backup & Recovery |
| 2026-02-14 | Phase 9 wrapped up, OpenSpec changes archived (keyword-cluster-creation + phase-9-internal-linking). Phase 10 added: Database Backup & Recovery (Neon free tier + Railway pg_dump → Cloudflare R2). Research complete: evaluated 5 backup strategies (Railway template + R2, Railway template + B2, SimpleBackups SaaS, Neon/Supabase migration, custom Docker cron). Decision: Neon free tier for PITR + R2 for off-platform redundancy. | Phase 10a: Neon migration |
| 2026-02-14 | Phase 10 complete. 10a: Migrated DB from Railway Postgres to Neon (pg_dump → pg_restore → Alembic upgrade, 24 tables, 3 projects). Fixed SSL for asyncpg (use `ssl` connect_arg, not `sslmode` URL param). Updated staging + production DATABASE_URL. 10b: Created Cloudflare R2 bucket with 30-day lifecycle, deployed Railway postgres-s3-backups template, verified first backup (15.98 KB). Created INFRASTRUCTURE.md and BACKUP_RESTORE_RUNBOOK.md. | Phase 11: Blog Planning & Writing |
| 2026-02-14 | Phase 11 complete (S11-001 through S11-021): BlogCampaign + BlogPost models with Alembic migration, blog topic discovery service (4-stage pipeline from POP briefs), blog campaign CRUD API (6 endpoints), blog content prompt builder, blog content generation pipeline orchestrator, blog content API (7 endpoints), blog link planning (per-post graph building, target selection, injection), blog HTML export service + 3 API endpoints, frontend TypeScript types + 18 API functions, TanStack Query hooks (17 hooks), blog section on project detail, campaign creation page, keyword approval page, content generation/review page, content editor (3-field + QA sidebar), link planning trigger + link map visualization, HTML export page with Copy/Download, 81 backend tests + 63 frontend component tests. | Phase 11 polish |
| 2026-02-15 | Phase 11 polish: Fixed ContentBrief SimpleNamespace bug (generation failures), normalized POP API response keys (LSI terms now display in frontend), rewrote blog keyword discovery prompt (real search queries instead of blog titles), integrated link planning into content pipeline (Brief → Write → Links → Check → Done with granular ContentStatus), brand-aware blog writing (company-specific system prompt + Brand Positioning section), removed FlaggedPassagesCard from editor sidebar, added Lexical table support + regenerate button. | Phase 11 QA hardening |
| 2026-02-16 | Phase 11 QA hardening: Diagnosed POP step 2 batch failure (cached partial briefs with 0 competitors), added diagnostic endpoints (/health/integrations, /health/pop-test, /health/project-debug), auto link planning after onboarding content generation (Phase 3 pipeline), auto link planning after blog content generation, robust 3-tier JSON parsing for content generation (direct parse → control char repair → key-boundary fallback), fixed fallback parser truncation (HTML double quotes in attributes), optimistic updates for blog topic approval checkbox, added "No class attributes" to content prompts. | Phase 14a: Reddit Data Foundation |
| 2026-02-16 | Phase 14a complete (S14A-001 through S14A-021): 5 Reddit models (RedditAccount, RedditProjectConfig, RedditPost, RedditComment, CrowdReplyTask) with enums + Alembic migration, Pydantic v2 schemas (11 classes), Reddit/CrowdReply config vars, Reddit API router (account CRUD with niche/status/warmup filters, project config upsert), router registration, 31 backend tests, frontend API client (5 interfaces + 6 functions), TanStack Query hooks (6 hooks with optimistic delete), Header nav links with active state, Reddit section layout, Reddit accounts page (table + filters + add modal + two-step delete), project Reddit config page (tag inputs + toggle + discovery settings), Reddit Marketing card on project detail, 51 frontend component tests. | Phase 14b: Post Discovery Pipeline |
| 2026-02-17 | Phase 14b complete: SerpAPI integration client (query construction, time range mapping, URL filtering, subreddit extraction, rate limiting, circuit breaker), keyword-based intent classification (research/pain_point/question/competitor/general/promotional with exclusion rules), Claude Sonnet relevance scoring with batch processing, discovery pipeline orchestrator with in-memory progress tracking, Pydantic v2 schemas (6 new: DiscoveryTriggerRequest/Response, DiscoveryStatusResponse, PostUpdateRequest, BulkPostActionRequest, RedditPostResponse), 5 API endpoints (POST trigger 202, GET status polling, GET posts with filters, PATCH post status, POST bulk-action), frontend API client (6 new types + 5 functions), TanStack Query hooks (5 new: useTriggerDiscovery, useDiscoveryStatus with 2s polling, useRedditPosts, useUpdatePostStatus with optimistic update, useBulkUpdatePosts), discovery UI on project Reddit config page (trigger button, progress indicator, posts table with intent badges + score badges + approve/reject actions), 64 backend tests + 27 frontend component tests. | Phase 14c: Crowd Reply Engine |
| 2026-02-17 | Phase 14b polish: Auto-refresh posts after discovery completes (useRef transition detection), moved discovery section above settings, broad reddit-wide search in addition to subreddit-scoped searches, filter tabs persist when current filter yields 0 results, differentiated empty states ("no posts match filter" vs "no posts yet"), improved approve/reject button UX (active state highlighting vs gray clickable), auto-save settings before triggering discovery. | Phase 14c: Comment Generation |
| 2026-02-17 | Phase 14c complete: Comment generation service (reddit_comment_generation.py) with 10 promotional + 11 organic approach types, prompt builder using BrandConfig v2_schema (voice/vocabulary/brand_foundation), generate_comment (Claude Sonnet temp 0.7, max_tokens 500, draft status, generation_metadata with generated_at), generate_batch (background task with in-memory progress tracking), 4 Pydantic schemas (GenerateCommentRequest, BatchGenerateRequest, GenerationStatusResponse, RedditCommentUpdateRequest), 6 API endpoints (POST single generate 201, POST batch generate 202 with 409 conflict, GET generation status, GET comments with filters, PATCH comment body for drafts), frontend API client (5 functions + 6 types), 5 TanStack Query hooks (useComments, useGenerationStatus with 2s polling, useGenerateComment, useGenerateBatch, useUpdateComment), UI: per-post Generate/Regenerate buttons, batch Generate Comments button with progress, comments section with approach type badges + promotional/organic indicators + status badges, inline draft editing with Reset to original, empty state. Code review found and fixed 3 issues (missing PATCH endpoint, missing generated_at in metadata, missing selectinload for post relationship). Built with team of 4 agents (backend-dev, frontend-dev, code-reviewer, team-lead fixes). | Phase 14c UX polish |
| 2026-02-17 | Phase 14c UX polish: Restructured comment generation UX (checkboxes in posts table for batch selection, Generate Comments button in filter toolbar with selected count, removed separate Generated Comments section, comments shown inline below posts table), delete comment feature (backend DELETE endpoint with draft-only guard, frontend API + useDeleteComment hook with optimistic cache removal, two-step confirm/cancel UI), fixed comment generation prompt builder (v2_schema key mapping was wrong — voice_dimensions not voice_characteristics, vocabulary.power_words not preferred_terms, brand_foundation.company_overview.company_name not brand_name — all falling through to "the product"), rewrote prompt with sandwich technique, anti-promotional rules, example phrasings with actual brand name, rich brand context from v2_schema (products, USP, differentiators, voice summary, formality, vocabulary preferences). | Phase 14d: Comment Queue + Approval |
| 2026-02-18 | Phase 14f Navigation Restructure: dual AI SEO + Reddit dashboards (Header rename, Reddit sub-nav with Projects/Accounts/Comments tabs, Reddit project cards grid, Reddit project detail page `/reddit/[id]`), `reddit_only` boolean flag on Project model (migration 0028, backend filtering in `list_projects`, frontend passes flag in Reddit wizard flow), bidirectional setup buttons ("Set up Reddit" on SEO detail, "Set up AI SEO" on Reddit detail), wizard `?flow=reddit` support (title/back/redirect changes), Reddit project detail enhancements (two-step delete, Brand Details button, project name header). Phase 14d committed (cross-project comment queue at `/reddit/comments`, 1008 lines). | Phase 14e: CrowdReply Integration |
| 2026-02-18 | Phase 14e complete: CrowdReply integration with 3-layer mock strategy (mock client, dry-run, webhook simulator). Backend: async CrowdReply client (real + mock + dry-run modes with circuit breaker), reddit posting service with background submission and webhook handling, 5 new API endpoints (submit 202, status poll, webhook receiver, balance, webhook simulator), 6 new schemas, 4 config fields, lifespan registration. Frontend: balance indicator with low-balance warning, submit button with confirmation dialog ($10/comment estimate), 7-status StatusBadge (submitting with pulsing dot, posted with external link, failed, mod_removed), Posted tab, auto-polling during submissions (5s refetchInterval), transition toast notifications, unapprove/move-to-draft for approved+rejected comments. Tested end-to-end with mock client: submit 5 → simulate 3 posted + 1 cancelled + 1 mod-removed. | Phase 14g: Reddit Brand Config |
| 2026-02-19 | Phase 14g complete: Subreddit research via Perplexity (auto-populate target_subreddits during brand config generation, ported from old Reddit Scraper App). Phase 14h: Brand config hardening — parallel-batched generation via asyncio.gather (7 sequential batches, 2 with concurrent sections, ~5 min total vs ~8+ sequential), per-section retry logic with MAX_SECTION_RETRIES, SECTION_CONFIG for per-section temperature/max_tokens/timeout tuning, SECTION_CONTEXT_DEPS to limit prompt bloat, _extract_json_from_response helper, trust_elements prompt rewrite (proactive inference vs permissive nulls), customer_quotes policy (real quotes only, no AI fabrication). Phase 14i: Post scoring overhaul — posts < 5/10 discarded entirely (not stored), 5-7 marked "low_relevance", 8-10 marked "relevant", removed "irrelevant" status, reject button → "skipped", cleaner dashboard. Fixed duplicate CrowdReplyTask bug in webhook handler (MultipleResultsFound → scalars().first()). Full E2E Reddit flow verified: config → discover 190 posts → approve top 5 → generate 5 comments → bulk approve → submit to CrowdReply → webhook simulation (3 posted, 1 cancelled, 1 mod_removed). Phase 14 effectively complete (14j seeded conversations is stretch). | Phase 12 (Auth), 13 (Polish), 15 (GEO), or 16 (Migration) |
| 2026-02-19 | Phase 12 complete (S12-001 through S12-017): Neon Auth SDK installed (`@neondatabase/auth`), server auth instance (`lib/auth/server.ts` via `createNeonAuth`), client auth instance (`lib/auth/client.ts` via `createAuthClient`), catch-all auth API route (`/api/auth/[...path]`), Next.js middleware for route protection (redirect unauthenticated → `/auth/sign-in`, redirect authenticated away from sign-in), route group layout restructure (`(authenticated)/` with Header vs `auth/` without), Google OAuth sign-in page, Header updated with real session data + sign-out + user avatar, AuthTokenSync component (syncs session token to module-level store), API client Authorization header injection (all `apiClient.*` + raw `fetch()` calls), `AUTH_REQUIRED` backend setting, `get_current_user` FastAPI dependency (validates Bearer token against `neon_auth.session`/`neon_auth."user"`, dev bypass when `AUTH_REQUIRED=false`), router-level auth on `api_v1_router`, CrowdReply webhook moved outside auth to `/webhooks/crowdreply`, auto-reset for stale "submitting" comments (prevents stuck state after backend restart), V2_REBUILD_PLAN.md updated. **Deferred to later:** Google Cloud OAuth credentials (currently using Neon shared dev creds), Railway env vars for production, RLS/per-user data isolation, `created_by` column on projects. | Phase 13 (Polish), 15 (GEO), or 16 (Migration) |
| 2026-02-19 | Phase 16 complete: V1 data migration — `execution/migrate_v1_to_v2.py` (sync psycopg2, deterministic uuid5 IDs, ON CONFLICT DO NOTHING idempotency, per-project transactions, dry-run default). Migrated 2 projects from `.tmp/v1-export/` JSON files to Neon: Planetary Design (36 pages, 36 keywords, 335 PAA, 32 content) + Bronson (90 pages, 90 keywords, 635 PAA, 37 content). Brand configs migrated with v2_schema section renames (foundation→brand_foundation, personas→target_audience, etc). Verification passed: no duplicate URLs, brand_foundation key present, all row counts match. Idempotent re-run confirmed (0 inserts, all skipped). | Phase 13 (Polish) or 15 (GEO) |
| 2026-02-28 | WP2 Batched Onboarding complete: `onboarding_batch` column on CrawledPage (migration 0031, nullable Integer, indexed, backfilled to 1), auto-assign next batch on URL upload, `?batch=N` filter on 7 endpoints (crawl-status, pages-with-keywords, generate-primary-keywords, approve-all-keywords, content-generation-status, generate-content, bulk-approve-content), new `GET /onboarding-batches` summary endpoint, cross-batch keyword uniqueness (seeds used keywords from all batches). Frontend: batch param threading through api.ts (7 functions + getOnboardingBatches), useOnboardingBatches hook, StepIndicator batch prop, 4 hook updates (useKeywordGeneration, usePagesWithKeywords, useKeywordMutations, useContentGeneration), all 5 onboarding pages read/pass batch via URL search params, project detail batch management UI (batch pills, "Continue Onboarding" to latest incomplete batch, "Add More Pages" button). Fixed pre-existing test failures (3 project detail test files + 2 keywords test files). | Phase 13 (Polish) or 15 (GEO) |

---

## Project Overview

**What we're building:** A client onboarding/content fulfillment tool that crawls client URLs, does keyword research, generates optimized content using POP API for guidance, and manages brand voice.

**Current state:** Brute-forced an entire app using Ralph loop in ~1 day. It's broken in unknown ways. Decided to rebuild properly with a stepwise approach.

**Decision:** Scorched-earth rebuild on a new branch, salvaging only the solid foundation pieces.

---

## Tech Stack (Finalized)

### Backend (Python/FastAPI)
| Tool | Purpose | Notes |
|------|---------|-------|
| **uv** | Package manager | Fast, modern, replaces pip |
| **FastAPI** | API framework | Already using |
| **SQLAlchemy 2.0** | ORM (async) | Already using |
| **Alembic** | Database migrations | Already using |
| **Ruff** | Linting + formatting | Replaces black, isort, flake8 |
| **mypy** | Type checking | |
| **pytest + pytest-asyncio** | Testing | |
| **factory_boy** | Test data factories | |

### Frontend (React/Next.js)
| Tool | Purpose |
|------|---------|
| **Next.js 14** | App Router |
| **TanStack Query v5** | Server state (data fetching) |
| **Zustand** | Client state (if needed) |
| **Vitest** | Unit/component tests |
| **Playwright** | E2E tests |

### DevOps
| Tool | Purpose |
|------|---------|
| **GitHub Actions** | CI/CD pipeline |
| **Pre-commit hooks** | Ruff + mypy before every commit |
| **Railway** | Staging + production app hosting (backend, frontend, Redis, Crawl4AI) |
| **Neon** | PostgreSQL database (free tier, `aws-us-east-1`) |
| **Cloudflare R2** | Off-platform database backups (every 6 hours, 30-day retention) |
| **Docker** | Optimized builds |

**All tools predate Claude Opus 4.5's May 2025 training cutoff** — safe to use.

---

## What's Salvageable from Current Codebase

| Area | Verdict | Action |
|------|---------|--------|
| **Database Models** | ✅ Keep | Copy directly |
| **Pydantic Schemas** | ✅ Keep | Copy directly |
| **Core Config** | ✅ Keep | Copy directly |
| **Database Layer** | ✅ Keep | Copy directly |
| **Logging** | ✅ Keep | Copy directly |
| **Integration Clients** | 🔄 Refactor | Extract CircuitBreaker to shared module, then copy |
| **Services** | ❌ Rebuild | Too tangled |
| **API Routes** | ❌ Rebuild | Too tangled |
| **Frontend Components** | 🔄 Review | Audit before copying |

---

## MVP Features (Must Work Perfectly)

> **Full spec:** See `FEATURE_SPEC.md` for complete details

### App Structure
1. **Main Dashboard** — Grid of client project cards with metrics
2. **Create Project** — URL, name, upload brand docs, generate brand config
3. **Project View** — Access to brand config and onboarding workflows

### Workflow 1: Collection Page Copy (Onboarding)
1. Upload URLs to crawl
2. Crawl pages (extract content, structure, metadata)
3. Keyword research (POP-informed)
4. Human approval (view/edit/approve keywords per page)
5. Content generation (research → write → check)
6. Content review & editing (HTML toggle, keyword highlighting)
7. Export to Matrixify (Shopify upload format)

### Workflow 2: Keyword Cluster Creation (New Content)
1. Enter seed keyword
2. POP returns cluster/secondary keyword suggestions
3. Human approval (same interface as onboarding)
4. Content generation (SAME pipeline as onboarding)
5. Content review & editing (SAME interface)
6. Export to Matrixify (SAME export)

### Content Fields (All Pages)
- Page title
- Meta description
- Top description
- Bottom description

### Later (Not MVP)
- Authentication — **Moved to Phase 12** (Neon Auth, free tier — switched from WorkOS 2026-02-14)
- Reddit Marketing Integration — **Phase 14** (after auth + polish, see `REDDIT_INTEGRATION_PLAN.md`)
- SEMrush integration (auto-import keywords, tag by cluster)
- Schema markup generation
- Template code updates

---

## Rebuild Phases

### Phase 0: Foundation (Do Once) ✅
- [x] Create `v2-rebuild` branch
- [x] Set up Railway staging environment
- [x] Set up CI/CD pipeline (GitHub Actions)
- [x] Configure Ruff + mypy + pre-commit hooks
- [x] Set up uv and project structure
- [x] Copy over: models, schemas, config, database layer, logging
- [x] Extract CircuitBreaker to `core/circuit_breaker.py`
- [x] Copy integration clients with refactor
- [x] Verify everything runs and tests pass

### Phase 1: Project Foundation ✅
- [x] Dashboard (list projects)
- [x] Create project (basic - name, URL only)
- [x] Project detail view (Onboarding + New Content sections)
- [x] **Verify:** Can create and view projects

### Phase 2: Brand Configuration ✅
- [x] Upload docs in project creation
- [x] Brand config generation (using skill/bible)
- [x] View/edit brand config
- [x] **Verify:** Can generate and view brand config

### Phase 3: URL Upload + Crawling ✅
- [x] Upload URLs interface
- [x] Crawling pipeline
- [x] View crawl results
- [x] **Verify:** Can upload URLs and see crawled data

### Phase 3b: Label Taxonomy Improvements (DEFERRED)
> **Note:** Deferred until after Phase 4. Labeling may work better with keyword data available.

- [ ] Improve taxonomy generation algorithm (labels still too generic)
- [ ] Fix "Edit Labels" button on crawl page (currently broken)
- [ ] Consider re-running labels after primary keywords are set
- [ ] Test with diverse site types (not just e-commerce)
- [ ] **Verify:** Labels are specific, accurate, and editable

### Phase 4: Primary Keyword + Approval (SHARED) ✅
- [x] Generate primary keyword candidates
- [x] Primary keyword approval interface (reusable component)
- [x] Edit primary keyword
- [x] **Verify:** Can see primary keyword, edit, approve
- [x] **Note:** No secondary keywords — POP provides LSI terms in Phase 5

### Phase 5: Content Generation (SHARED) ✅
- [x] POP Content Brief service (3-step: get-terms → create-report → recommendations)
- [x] Content writing service (Claude Sonnet) with copywriting skill bible
- [x] Quality checks (5 AI trope rules + Tier 1/2 banned words)
- [x] Lean content strategy (no word count targets, POP min headings capped at 8/12, 120-word max paragraphs)
- [x] Pipeline reset on regeneration (frontend indicators clear immediately)
- [x] Prompt Inspector with run grouping
- [x] Crawl4AI content filtering (PruningContentFilter)
- [x] Railway staging deployment (BE, FE, Postgres, Redis, Crawl4AI)
- [x] **Verify:** End-to-end with real POP API data, content generates with proper structure
- [x] **Architecture:** Build as standalone shared services
- [x] **Deferred:** POP scoring API (post-generation score check) — saved for Phase 6
- [x] **Deferred:** Internal links — saved for linking phase

### Phase 6: Content Review + Editing (SHARED) ✅
- [x] Content detail view
- [x] HTML/rendered toggle
- [x] Keyword highlighting
- [x] Inline editing
- [x] **Verify:** Can review, edit, re-check content

### Phase 7: Export (SHARED) ✅
- [x] Matrixify export format
- [x] Download functionality
- [x] **Verify:** Export works in Matrixify

### Phase 8: Keyword Cluster Creation
- [x] Seed keyword input UI
- [x] POP API for cluster suggestions
- [x] Wire into shared components
- [x] **Verify:** Full cluster flow works (create → generate → export)

### Phase 9: Internal Linking ✅
- [x] `InternalLink` model + edge table migration (source_page, target_page, cluster, anchor_text, position, status)
- [x] `LinkPlanSnapshot` model for auditing/rollback
- [x] SiloLinkPlanner algorithm (budget calculation, target selection, anchor text selection)
- [x] AnchorTextSelector with diversity tracking (POP keyword variations as source)
- [x] Link injection — hybrid approach:
  - [x] Generation-time: mandatory parent link in content generation prompt
  - [x] Post-processing: BeautifulSoup keyword scanning for discretionary links
  - [x] LLM fallback for links that can't be placed rule-based (~30%)
- [x] Link validation layer (first-link rule, silo integrity, density, anchor diversity)
- [x] API endpoints (link plan per page, link map per silo, manual link adjustment)
- [x] Link map UI (per-silo visualization, per-page link list, manual add/remove)
- [x] Integration with content pipeline (run link planning AFTER all silo content is generated)
- [x] **Hard rules enforced:**
  - First link on every sub-page → parent/hub collection
  - No cross-silo links
  - Every page in a silo
  - Anchor text = primary keyword or POP variation, diversified (50-60% partial, ~10% exact, ~30% natural)
  - Links flow DOWN funnel only (collection→collection OK, blog→anything in silo OK, collection→blog NEVER)
  - Uniform 3-5 link budget per page (eligible targets vary by page type)
  - Parent collection outbound links go to sub-collections only
  - Blog → blog sibling links allowed (1-2)
  - Sub-collection → sub-collection sibling links allowed
- [x] **Verify:** Full linking flow works (generate content → plan links → inject → validate → view link map)
- [x] **Research complete:** See `.tmp/linking-research-consensus.md` and supporting reports

### Phase 10: Database Backup & Recovery

> **Strategy:** Two-layer approach. Migrate PostgreSQL to Neon (free tier) for built-in PITR, plus off-platform pg_dump backups to Cloudflare R2 via Railway template for redundancy. Total cost: ~$0/mo.

#### 10a: Migrate Database to Neon (Free Tier) ✅
- [x] Create Neon project in `us-east-1` (match Railway region) — `spring-fog-49733273`
- [x] Export Railway database: `pg_dump -Fc -v --no-tablespaces -f backup.dump`
- [x] Restore to Neon: `pg_restore -v -d "$NEON_DATABASE_URL" backup.dump`
- [x] Run `alembic upgrade head` against Neon to verify schema (11 migrations applied, 24 tables)
- [x] Update `DATABASE_URL` in Railway backend service to Neon connection string (staging + production)
- [x] Configure SQLAlchemy for Neon (direct connection, `pool_pre_ping=True`, SSL via `connect_args`)
- [x] ~~Disable Neon scale-to-zero~~ — Free tier limitation, can't disable (5 min timeout, ~1-3s cold start acceptable)
- [x] Test full application flow — projects load on staging
- [ ] Keep Railway Postgres running 48 hours as fallback, then deprovision
- [x] **Verify:** App works end-to-end on Neon, PITR available in Neon dashboard

#### 10b: Off-Platform Backups (Railway Template + Cloudflare R2) ✅
- [x] Create Cloudflare account + R2 bucket (`client-fullfilment-backups`)
- [x] Generate R2 API token (read/write permissions for bucket)
- [x] Set R2 lifecycle rule: auto-delete objects after 30 days
- [x] Deploy Railway `postgres-s3-backups` template (separate Railway project)
- [x] Configure template env vars: `BACKUP_DATABASE_URL`, `AWS_S3_BUCKET`, `AWS_S3_ENDPOINT`, `BACKUP_CRON_SCHEDULE=0 */6 * * *`
- [x] Set `SINGLE_SHOT_MODE=true`, verified first backup in R2 (15.98 KB), then switch to `false` for cron
- [x] Document restore procedure in a runbook — see `BACKUP_RESTORE_RUNBOOK.md`
- [x] **Verify:** First backup confirmed in R2 bucket

### Phase 11: Blog Planning & Writing ✅
- [x] BlogCampaign and BlogPost models + migration
- [x] Blog topic discovery service (POP API)
- [x] Blog keyword approval (reuse shared UI)
- [x] Blog content generation (reuse pipeline, blog template)
- [x] Lexical rich editor integration
- [x] Live POP scoring sidebar
- [x] Blog internal linking (reuse Phase 9 infrastructure, siloed to cluster + sibling blogs)
- [x] Blog export (HTML + copy to clipboard)
- [x] **Verify:** Full blog flow works (campaign → keywords → generate → edit → export)

### Phase 12: Authentication (Neon Auth)

> **Decision (2026-02-14):** Switched from WorkOS AuthKit to Neon Auth. Since we're already on Neon for the database (Phase 10), Neon Auth keeps auth + data in one provider. Auth data lives in the same DB (neon_auth schema), enabling Row Level Security for per-user project isolation. Built on Better Auth, free for 60K MAU. Currently beta — acceptable risk for an internal tool with 1-5 users.

- [x] Enable Neon Auth in Neon dashboard (Google OAuth)
- [x] Install Neon Auth SDK (`@neondatabase/auth`)
- [x] Create server auth instance (`lib/auth/server.ts` — `createNeonAuth()`)
- [x] Create client auth instance (`lib/auth/client.ts` — `createAuthClient()`)
- [x] Add auth API route (`/api/auth/[...path]/route.ts` — GET + POST handler)
- [x] Add auth middleware in `middleware.ts` (protect all routes, redirect unauthenticated, allow auth pages + static)
- [x] Create Google OAuth sign-in page (`/auth/sign-in` — tropical oasis styled)
- [x] Create auth layout (centered, no Header) + authenticated layout (with Header)
- [x] Add sign-in/sign-out + user display to Header (session data + avatar + dropdown)
- [x] Create AuthTokenSync component (syncs session token to module-level store)
- [x] Update API client with Authorization header injection (all apiClient + raw fetch calls)
- [x] Add `AUTH_REQUIRED` backend setting with dev bypass
- [x] Create `get_current_user` FastAPI dependency (validates Bearer token against `neon_auth.session`/`neon_auth."user"`)
- [x] Apply auth dependency to `api_v1_router` (all v1 endpoints protected)
- [x] Move CrowdReply webhook outside auth to `/webhooks/crowdreply`
- [x] Health check remains unauthenticated
- [x] Add auto-reset for stale "submitting" comments (prevents stuck state after backend restart)
- [x] **Verify:** Full auth flow works (sign in with Google → use app → sign out → redirected to sign-in)
- [ ] **Deferred:** Set up own Google Cloud OAuth credentials (currently using Neon shared dev creds)
- [ ] **Deferred:** Add `NEON_AUTH_BASE_URL` + `NEON_AUTH_COOKIE_SECRET` to Railway frontend service
- [ ] **Deferred:** Set `AUTH_REQUIRED=true` on Railway backend after frontend confirmed
- [ ] **Deferred:** Add `created_by` column to projects + RLS for per-user data isolation

### Phase 13: Polish & UX Foundations

#### 13a: Quick Wins (< 30 min each, no new deps)
- [ ] Relative timestamps everywhere (`date-fns` `formatDistanceToNow` — already installed)
- [ ] Disable submit buttons during mutations (`isPending` from TanStack Query)
- [ ] Pluralization helper (simple `pluralize(count, word)` util)
- [ ] Inline form validation on blur (`mode: "onBlur"` in react-hook-form — already installed)
- [ ] Active nav states (highlight current page in sidebar/header via `usePathname`)

#### 13b: Small Additions (30 min – 1 hr each, minimal deps)
- [ ] Toast notifications — install **sonner**, add `<Toaster />` to layout, replace alerts/console
- [ ] Debounced search hook — install **use-debounce**, wire into list pages
- [ ] Retry error pattern — reusable `<ErrorWithRetry>` component using TanStack Query `refetch()`
- [ ] Empty states — friendly message + CTA on every list page (projects, pages, keywords, content, clusters)
- [ ] Text truncation + tooltips — Tailwind `truncate` + **Radix Tooltip** for overflow text
- [ ] Confirmation dialogs — reusable `<ConfirmDialog>` via **Radix AlertDialog** (replace window.confirm)
- [ ] Breadcrumbs component (reads Next.js route segments, no library needed)

#### 11c: Medium Effort (1–2 hrs each)
- [ ] 404 and 500 error pages (`app/not-found.tsx`, `app/error.tsx` — Next.js built-in)
- [ ] Unsaved changes warning (`beforeunload` + route change interception hook)
- [ ] Offline awareness banner (`navigator.onLine` + event listeners, TanStack Query pauses automatically)
- [ ] Skeleton loaders — reusable `<Skeleton>` components with Tailwind `animate-pulse`
- [ ] Hover/active states audit — pass through all interactive elements (`hover:`, `active:`, `transition-colors`)
- [ ] Focus management — Radix primitives for modals/dialogs, `useRef` + `focus()` for custom flows
- [ ] Dashboard metrics (clusters pending, content pending, blogs pending)

#### 11d: Larger Investments (2–4 hrs each)
- [ ] Accessibility audit — install **Radix UI Primitives** for accessible Dialog/Dropdown/Tabs, run Lighthouse + axe DevTools
- [ ] Search on list pages — client-side filter + `?search=` query param on FastAPI endpoints with `ilike`
- [ ] TanStack Table — headless table for sortable/filterable/paginated lists (keywords, content, clusters)
- [ ] Deep linking — persist filters/tabs/sort in URL query params via `useSearchParams`

#### New deps for Phase 12 (Auth)
| Package | Size | Purpose |
|---------|------|---------|
| `@neondatabase/auth` | ~15kb | Neon Auth SDK (wraps Better Auth for Neon) |
| `@better-auth/nextjs` | ~5kb | Next.js integration |

### Phase 14: Reddit Marketing Integration

> **Decision (2026-02-16):** Integrating the standalone Reddit Scraper App into the V2 platform. Top-level Reddit section with project association. No persona system initially (BrandConfig + custom instructions for voice). CrowdReply for posting + foundation for own accounts. See `REDDIT_INTEGRATION_PLAN.md` for full detailed plan.

- [x] **14a:** Reddit Data Foundation (5 DB tables, account pool CRUD, project config CRUD)
- [x] **14b:** Post Discovery Pipeline (SERP API + Claude filtering)
- [x] **14c:** Comment Generation (AI comments with brand context, "sandwich" technique)
- [x] **14d:** Comment Queue + Approval (cross-project comment review at `/reddit/comments`)
- [x] **14e:** CrowdReply Integration (auto-submit + webhook status tracking)
- [x] **14f:** Navigation Restructure (dual AI SEO + Reddit dashboards, `reddit_only` flag, bidirectional setup buttons)
- [x] **14g:** Subreddit Research (auto-populate target subreddits via Perplexity during brand config generation)
- [x] **14h:** Brand Config Hardening (parallel batches, retries, per-section tuning, trust_elements prompt, customer_quotes policy)
- [x] **14i:** Post Scoring Overhaul (discard < 5/10, low_relevance 5-7, relevant 8+, remove irrelevant status)
- [ ] **14j:** Seeded Conversations (stretch — orchestrated question + answer posts)
- [x] **Verify:** Full E2E flow — configure → discover 190 posts → approve → generate comments → submit to CrowdReply → webhook simulation (3 posted, 1 cancelled, 1 mod_removed)

### Phase 17: Rename to Grove

> **Decision (2026-02-19):** Brand naming exercise with 5 expert agents (luxury, tech/SaaS, verbal identity, startup/DTC, cultural semiotics). Consensus name: **Grove**. Runners-up: Canopy (strongest runner-up, 4/5 lists), Frond (phonetics killed it), Palmetto (syllable count killed it). The name is deliberately understated — the tropical identity lives in the design system (palm greens, sand, lagoon, coral), not the name. "The Grove" as casual internal shorthand encouraged.

- [ ] Audit all references to old name across codebase (frontend, backend, config, exports, UI copy)
- [ ] Update page titles, meta tags, and header branding
- [ ] Update export filenames (Matrixify CSV, blog HTML)
- [ ] Update auth pages (sign-in page copy)
- [ ] Update package.json / project metadata
- [ ] Update environment references and documentation
- [ ] **Verify:** All user-facing references say "Grove", no orphaned old name references

### Phase 15: Explore GEO Add-On Opportunities

> **Decision (2026-02-16):** Research complete. GEO (Generative Engine Optimization) represents a major differentiation opportunity. SEOasis controls the full pipeline from keyword research → content generation → quality review → export, positioning it to become a unified SEO + GEO platform. POP already returns entity data that's stored but unused — quick win. See `GEO_ADDON_OPPORTUNITIES.md` for full 926-line research document with 28 prioritized recommendations across 4 tiers.

- [ ] **15a:** Quick Wins — wire POP entities into content prompts, add answer capsule formatting, statistics injection, quotation attribution
- [ ] **15b:** Content Pipeline GEO — passage-level optimization (134-167 word chunks), query fan-out coverage analysis, schema markup generation (FAQ, HowTo, Article)
- [ ] **15c:** Embedding Infrastructure — pgvector on Neon, passage embeddings, semantic similarity search, query-passage relevance scoring
- [ ] **15d:** Advanced GEO Features — AI citation tracker (monitor Google AI Overviews, Perplexity, ChatGPT), GEO scoring dashboard, llms.txt generation
- [ ] **15e:** Strategic — Knowledge Panel optimization, entity graph building, multi-platform AI visibility monitoring
- [ ] **Verify:** GEO-optimized content scores higher on AI citation metrics than baseline content

### Phase 16: V1 Data Migration

> **Decision (2026-02-16):** One-time migration of ~2 client projects from V1 (Railway Postgres + JSON files on disk) into V2 (Neon Postgres). V1 stored pipeline data as accumulative JSON files per project (each phase extends the previous). V2 stores everything relationally. Migration script in `execution/migrate_v1_to_v2.py` with dry-run mode, idempotent inserts, and Neon PITR snapshot for rollback. See field mappings below.

**V1 source data (per project in `.tmp/old-app/`):**
- `projects` table (Railway Postgres) — project metadata + phase statuses
- `crawl_results.json` → `categorized_pages.json` → `labeled_pages.json` — accumulative page data
- `keyword_enriched.json` — primary/secondary keywords with volumes
- `keyword_with_paa.json` — People Also Ask questions per page
- `brand_config.json` — brand voice, style guide, priority pages
- `validated_content.json` / `collection_content.json` — final generated content with QA results
- `.tmp/uploads/` — brand documents (DOCX files)

**V2 target tables:** `projects`, `crawled_pages`, `page_keywords`, `page_paa`, `brand_configs`, `page_contents`, `project_files`

**Tables that do NOT need migration (new in V2):** `keyword_clusters`, `cluster_pages`, `internal_links`, `link_plan_snapshots`, `blog_campaigns`, `blog_posts`, `content_briefs`, `content_scores`, `prompt_logs`, `crawl_schedules`, `crawl_history`

#### Field Mappings

**projects (v1) → projects (v2)**
| V1 | V2 | Transform |
|---|---|---|
| `id` (UUID) | `id` | Preserve original UUIDs |
| `name` | `name` | Direct |
| `website_url` | `site_url` | Direct |
| `phase1_status` thru `phase5c_status` | `phase_status` (JSONB) | Combine: `{"crawl": "complete", "categorize": "complete", ...}` |
| `brand_wizard_step` + `brand_wizard_data` | `brand_wizard_state` (JSONB) | Merge: `{"step": N, "data": {...}}` |
| `created_at`, `updated_at` | `created_at`, `updated_at` | Direct |
| — | `status` | Set `"active"` |
| — | `client_id` | `null` |

**labeled_pages.json → crawled_pages** (use labeled_pages as it's the most complete accumulation)
| V1 | V2 | Transform |
|---|---|---|
| `url` | `normalized_url` + `raw_url` | Normalize: strip trailing slash, lowercase domain |
| `title` | `title` | Direct |
| `meta_description` | `meta_description` | Direct |
| `category` | `category` | Direct |
| `labels` | `labels` (JSONB) | Direct (already array) |
| `body_text` (from `_original_data`) | `body_content` | Direct |
| `word_count` | `word_count` | Direct |
| `h1`, `h2_list` | `headings` (JSONB) | Reshape: `{"h1": [h1], "h2": h2_list, "h3": []}` |
| `crawled_at` (from `_original_data`) | `last_crawled_at` | Direct |
| — | `source` | `"onboarding"` |
| — | `status` | `"completed"` |

**keyword_enriched.json → page_keywords** (join by URL to crawled_page)
| V1 | V2 | Transform |
|---|---|---|
| `keywords.primary.keyword` | `primary_keyword` | Direct |
| `keywords.primary.volume` | `search_volume` | Direct |
| `keywords.primary.reasoning` | `ai_reasoning` | Direct |
| `keywords.secondary` array | `secondary_keywords` (JSONB) | Direct |
| `approval_status` | `is_approved` | `"approved"` → `true` |
| — | `alternative_keywords` | `[]` |
| — | `crawled_page_id` | FK lookup by normalized URL |

**keyword_with_paa.json → page_paa** (join by URL to crawled_page)
| V1 | V2 | Transform |
|---|---|---|
| `paa_data[].question` | `question` | Direct |
| `paa_data[].answer` | `answer_snippet` | Direct |
| `paa_data[].source` | `source_url` | Direct |
| array index | `position` | Index in array |
| — | `crawled_page_id` | FK lookup by normalized URL |

**brand_config.json → brand_configs**
| V1 | V2 | Transform |
|---|---|---|
| entire JSON | `v2_schema` (JSONB) | Nest full config as-is |
| `source_url` | `domain` | Extract domain from URL |
| project `name` | `brand_name` | From parent project |

**validated_content.json → page_contents** (join by URL to crawled_page)
| V1 | V2 | Transform |
|---|---|---|
| `content.title_tag` | `page_title` | Direct |
| `content.meta_description` | `meta_description` | Direct |
| `content.top_description` | `top_description` | Direct |
| `content.bottom_description` | `bottom_description` | Direct |
| `content.word_count` | `word_count` | Direct |
| `passed` | `is_approved` | Direct |
| `qa_results` | `qa_results` (JSONB) | Direct |
| — | `status` | `"complete"` |
| — | `crawled_page_id` | FK lookup by normalized URL |

**Brand docs (.tmp/uploads/) → S3 + project_files**
| Source | V2 | Transform |
|---|---|---|
| local file | S3 bucket | Upload to `projects/{project_id}/files/{file_id}/{filename}` |
| `{uuid}_{filename}.docx` | `filename` | Strip UUID prefix |
| file extension | `content_type` | `.docx` → `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| file contents | `extracted_text` | Re-extract via `app.utils.text_extraction` |

#### Subtasks

- [x] **16a:** Build migration script (`execution/migrate_v1_to_v2.py`) — sync psycopg2, deterministic uuid5 IDs, ON CONFLICT DO NOTHING idempotency, per-project transactions, dry-run default, V1 DB optional (derives from JSON). Brand config section renames (foundation→brand_foundation, personas→target_audience, writing_rules→writing_style, proof_elements→trust_elements, ai_prompts→ai_prompt_snippet).
- [x] **16b:** Dry-run + live run against Neon — 2 projects migrated (Planetary Design: 36 pages/36 kw/335 PAA/32 content, Bronson: 90 pages/90 kw/635 PAA/37 content). Verification: no duplicate URLs, brand_foundation key present, row counts match. Idempotent re-run confirmed.
- [ ] **16c:** UI verification — Open V2 app, check both projects appear on dashboard, browse pages/keywords/content
- [ ] **16d:** Cleanup — archive v1 data files, update V2_REBUILD_PLAN.md
- [ ] **Verify:** All v1 client projects visible in v2 UI with crawled pages, keywords, brand config, and generated content intact

#### Risk Mitigations
- **Dry-run mode** — logs all transforms without writing, review before committing
- **Neon PITR snapshot** before production run — instant rollback
- **Additive only** — never deletes existing v2 data, only inserts
- **Idempotent** — `ON CONFLICT DO NOTHING` on unique constraints, safe to re-run
- **URL normalization** — consistent normalization (lowercase domain, strip trailing slash) since URL is the join key across all JSON files

#### Open Questions (resolve at execution time)
1. V1 Railway DB credentials — still accessible, or rely solely on JSON files? (JSON files are sufficient; DB only has project metadata + phase statuses)
2. V1 `content.h1` field — v2 `page_contents` has no H1 column. Options: store in `page_title`, add to `headings` JSONB on crawled_page, or discard (H1 typically matches primary keyword)
3. V1 `research_briefs.json` — no direct v2 table (v2 content briefs come from POP, different format). Options: skip, or store in `content_briefs.raw_response` JSONB for reference

#### New deps for Phase 16
None — uses existing SQLAlchemy models, Alembic, asyncpg, boto3 (S3).

#### New deps for Phase 13
| Package | Size | Purpose |
|---------|------|---------|
| `sonner` | ~5kb | Toast notifications |
| `use-debounce` | ~2kb | Debounced search/input |
| `@radix-ui/react-tooltip` | ~8kb | Accessible tooltips |
| `@radix-ui/react-alert-dialog` | ~8kb | Confirmation dialogs |
| `@radix-ui/react-dialog` | ~8kb | Accessible modals (if not already using) |
| `@tanstack/react-table` | ~14kb | Headless table (sorting, filtering, pagination) |

---

## Development Workflow

### For Each Feature (Vertical Slice)

```
1. YOU define what it does (clear spec)
2. YOU sketch the approach (which files, patterns)
3. AI implements with your guidance
4. YOU review the code (actually read it)
5. AI writes tests
6. YOU run tests and verify behavior
7. Commit only when YOU understand it
8. Deploy to staging, verify it works
9. Move to next feature
```

### Branch Strategy

- `main` → Production (protected)
- `staging` → Staging environment
- `feature/*` → Feature branches, merge to staging first

### Commit Flow

```
feature/add-crawling → staging (test) → main (production)
```

---

## Infrastructure Setup

### Database: Neon PostgreSQL
- **Project:** `spring-fog-49733273` (org: `org-cold-waterfall-84590723`)
- **Region:** `aws-us-east-1`
- **Plan:** Free tier (0.5 GB storage, 100 compute hours/mo, 6-hour PITR)
- **Scale-to-zero:** 5 minutes (free tier limit, ~1-3s cold start on first request)
- **SSL:** Required. App uses `connect_args={"ssl": "require"}` for all non-development environments
- **Dashboard:** https://console.neon.tech

### Backups: Cloudflare R2
- **Bucket:** `client-fullfilment-backups`
- **Account:** `fa80d2f9a9e3a5f7971ca70c11cd0458`
- **Schedule:** Every 6 hours via Railway `postgres-s3-backups` template (separate Railway project)
- **Retention:** 30-day lifecycle rule (auto-delete after 30 days)
- **Restore procedure:** See `BACKUP_RESTORE_RUNBOOK.md`

### App Hosting: Railway
- **Staging:** Deploys from `staging` branch
- **Production:** Deploys from `main` branch
- **Services:** Backend (FastAPI), Frontend (Next.js), Redis, Crawl4AI
- **DATABASE_URL:** Points to Neon (not Railway Postgres)

### Optimization
- Slim Docker base image (`python:3.11-slim`)
- Dependencies cached (install before code copy)
- Fast health checks (no DB calls)
- Watch patterns to avoid unnecessary rebuilds

---

## Testing Strategy

### Test Pyramid
- **Unit tests** — Fast, no DB, test individual functions
- **Integration tests** — Real DB, test services and data flow
- **E2E tests** — Full user journeys through the app

### When to Write Tests
- Write tests **alongside** implementation, not after
- Each feature must have tests before marking complete
- CI blocks merges if tests fail

---

## Questions Status

### Resolved
| Question | Answer |
|----------|--------|
| Dashboard metrics | Clusters built/pending, content generations pending |
| Keyword sources | **POP only** — no DataForSEO. See `backend/PLAN-remove-secondary-keywords-and-paa.md` |
| Content structure | Page title, meta description, top description, bottom description |
| Secondary keywords | **Removed** — POP's LSI terms replace them |
| PAA questions | **Removed** — POP's related_questions replace them |

### Still Open
1. **Crawl data** — What specific data do we need from crawled pages? Current list sufficient?
2. **Matrixify format** — Need example Matrixify file for export format

---

## Architecture Decisions (2026-02-02)

Decisions made during planning session:

| Topic | Decision | Rationale |
|-------|----------|-----------|
| **Background Jobs** | FastAPI BackgroundTasks + polling | Simpler than Celery for MVP, can add later |
| **File Storage** | S3 + extract text to DB | Keep originals, extracted text for AI |
| **Label Generation** | Project-wide taxonomy first, then apply | Ensures consistency for internal linking |
| **Link Map Storage** | Separate `InternalLink` table | Easier to query and update |
| **Content Versioning** | Skip for MVP | Too complex, add later if needed |
| **POP Score Threshold** | Aim for 100, research meaning | Higher = better, need to understand metric |
| **Retry Logic** | 2-3 retries before human review | Balance automation vs. human oversight |
| **Real-time Updates** | Polling (2-3s) for MVP | Simpler than WebSockets, good enough UX |
| **Auth** | Neon Auth (Phase 12) | Switched from WorkOS to Neon Auth (2026-02-14). Since DB is on Neon (Phase 10), auth in same provider simplifies stack. Built on Better Auth, free 60K MAU, RLS for per-user project isolation, auth data in same DB. Beta — acceptable for internal tool. |
| **Delete Confirmation** | Two-step for items, type-to-confirm for projects | Prevent accidents |
| **Keyword Change** | Rerun downstream for that page only | Don't redo everything |
| **Pause/Resume** | Table if complex | Nice-to-have, not critical |

---

## Files to Reference

- `/Users/mike/Downloads/PageOptimizer_Pro_API_Documentation.md` — POP API docs
- `backend/app/integrations/dataforseo.py` — Example integration client
- `backend/app/models/` — Database models (salvageable)
- `backend/app/schemas/` — Pydantic schemas (salvageable)
- `backend/app/core/config.py` — Configuration pattern (salvageable)

---

## Next Steps

1. **You:** Brain dump feature list
2. **Me:** Structure into proper spec with clear slices
3. **Together:** Define slice order
4. **Execute:** Phase 0 foundation setup
5. **Build:** First vertical slice

---

*Last updated: This session*
