# Client Onboarding V2 Rebuild Plan

> This document captures everything we've discussed. Use it to pick up where we left off in any new session.

---

## Current Status

| Field | Value |
|-------|-------|
| **Phase** | 8 - Keyword Cluster Creation (Complete) |
| **Slice** | Phase 8 complete + staging deployment fix |
| **Last Session** | 2026-02-09 |
| **Next Action** | Phase 9: Internal Linking |
| **Auth Decision** | WorkOS AuthKit (free tier, 1M MAU) — see Phase 11 |

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
| **Railway** | Staging + production environments |
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
- Authentication — **Moved to Phase 10** (WorkOS AuthKit, free tier)
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

### Phase 9: Internal Linking
- [ ] `InternalLink` model + edge table migration (source_page, target_page, cluster, anchor_text, position, status)
- [ ] `LinkPlanSnapshot` model for auditing/rollback
- [ ] SiloLinkPlanner algorithm (budget calculation, target selection, anchor text selection)
- [ ] AnchorTextSelector with diversity tracking (POP keyword variations as source)
- [ ] Link injection — hybrid approach:
  - [ ] Generation-time: mandatory parent link in content generation prompt
  - [ ] Post-processing: BeautifulSoup keyword scanning for discretionary links
  - [ ] LLM fallback for links that can't be placed rule-based (~30%)
- [ ] Link validation layer (first-link rule, silo integrity, density, anchor diversity)
- [ ] API endpoints (link plan per page, link map per silo, manual link adjustment)
- [ ] Link map UI (per-silo visualization, per-page link list, manual add/remove)
- [ ] Integration with content pipeline (run link planning AFTER all silo content is generated)
- [ ] **Hard rules enforced:**
  - First link on every sub-page → parent/hub collection
  - No cross-silo links
  - Every page in a silo
  - Anchor text = primary keyword or POP variation, diversified (50-60% partial, ~10% exact, ~30% natural)
  - Links flow DOWN funnel only (collection→collection OK, blog→anything in silo OK, collection→blog NEVER)
  - Uniform 3-5 link budget per page (eligible targets vary by page type)
  - Parent collection outbound links go to sub-collections only
  - Blog → blog sibling links allowed (1-2)
  - Sub-collection → sub-collection sibling links allowed
- [ ] **Verify:** Full linking flow works (generate content → plan links → inject → validate → view link map)
- [ ] **Research complete:** See `.tmp/linking-research-consensus.md` and supporting reports

### Phase 10: Blog Planning & Writing
- [ ] BlogCampaign and BlogPost models + migration
- [ ] Blog topic discovery service (POP API)
- [ ] Blog keyword approval (reuse shared UI)
- [ ] Blog content generation (reuse pipeline, blog template)
- [ ] Lexical rich editor integration
- [ ] Live POP scoring sidebar
- [ ] Blog internal linking (reuse Phase 9 infrastructure, siloed to cluster + sibling blogs)
- [ ] Blog export (HTML + copy to clipboard)
- [ ] **Verify:** Full blog flow works (campaign → keywords → generate → edit → export)

### Phase 11: Authentication (WorkOS AuthKit)
- [ ] Install `@workos-inc/authkit-nextjs` package
- [ ] Configure WorkOS environment variables (`WORKOS_CLIENT_ID`, `WORKOS_API_KEY`, `WORKOS_COOKIE_PASSWORD`, `NEXT_PUBLIC_WORKOS_REDIRECT_URI`)
- [ ] Create WorkOS account and configure AuthKit in dashboard (redirect URIs, sign-out redirect)
- [ ] Create `/app/auth/callback/route.ts` (OAuth callback handler via `handleAuth()`)
- [ ] Add `authkitMiddleware()` in `middleware.ts` (protect all app routes)
- [ ] Wrap root layout with `AuthKitProvider` (alongside existing `QueryProvider`)
- [ ] Add sign-in/sign-out to Header component (via `useAuth()` hook)
- [ ] Display current user name/email in Header
- [ ] Create login landing page (unauthenticated users see sign-in prompt)
- [ ] Pass `accessToken` JWT in API requests to FastAPI backend
- [ ] Add FastAPI middleware to verify WorkOS JWT on protected endpoints
- [ ] Update Railway environment variables (staging + production)
- [ ] **Verify:** Full auth flow works (sign in → use app → sign out → redirected to login)

### Phase 12: Polish & UX Foundations

#### 11a: Quick Wins (< 30 min each, no new deps)
- [ ] Relative timestamps everywhere (`date-fns` `formatDistanceToNow` — already installed)
- [ ] Disable submit buttons during mutations (`isPending` from TanStack Query)
- [ ] Pluralization helper (simple `pluralize(count, word)` util)
- [ ] Inline form validation on blur (`mode: "onBlur"` in react-hook-form — already installed)
- [ ] Active nav states (highlight current page in sidebar/header via `usePathname`)

#### 11b: Small Additions (30 min – 1 hr each, minimal deps)
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

#### New deps for Phase 11
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

## Railway Setup

### Environments
- **Staging:** Separate Railway project/environment, deploys from `staging` branch
- **Production:** Deploys from `main` branch

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
| **Auth** | WorkOS AuthKit (Phase 10) | Free tier (1M MAU), hosted login UI, no SSO needed. Evaluated Keycloak/SuperTokens/Ory/Authentik — WorkOS wins for our use case (zero infra, zero cost). See `auth-evaluation-report.md`. |
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
