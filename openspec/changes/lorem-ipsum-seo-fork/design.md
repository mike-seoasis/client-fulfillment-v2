## Context

The client-onboarding-v2 app has a full content generation pipeline: POP brief fetching → outline generation → Claude-powered content writing → quality checks → export. The pipeline is service-based (FastAPI + SQLAlchemy + Neon PostgreSQL), deployed on Railway.

We want a local-only instance of the same app that:
1. Uses the same cluster-building, POP brief, and internal linking workflows
2. Generates content where body text is lorem ipsum but all SEO signals (H1s, H2s, H3s, title tags, meta descriptions, lead sentences) contain real target keywords
3. Exports all projects into a single XLSX file matching the `sites-template.xlsx` format for the static site generator

The production instance runs against Neon PostgreSQL. The local instance runs against a local PostgreSQL via docker-compose. No shared database = zero contamination risk.

## Goals / Non-Goals

**Goals:**
- Add a "lorem ipsum" content generation mode that can be toggled per-instance via environment variable
- Build an XLSX export endpoint that maps projects → tabs, cluster pages → collection rows, blog posts → blog rows
- Provide a docker-compose profile that spins up a fully isolated local instance with its own database
- Reuse 100% of the existing pipeline (POP briefs, clusters, internal linking, blog campaigns) without forking the codebase

**Non-Goals:**
- Deploying this to Railway or any hosted environment
- Changing the production instance in any way
- Building a separate codebase or forked repo — this is a feature toggle, not a fork
- Handling domain purchases, DNS, or static site deployment
- Modifying the static site generator (that's a separate project)

## Decisions

### 1. Feature toggle via environment variable, not a code fork

**Decision:** Add `CONTENT_MODE=lorem` environment variable (default: `real`). The same codebase serves both production and SEO test instances.

**Why not fork:** A forked codebase means maintaining two copies. Every bug fix, every new feature has to be applied twice. An env var toggle means one codebase, two configurations. The content writing service already has feature flags for POP mock mode, quality pipeline, shadow mode — this follows the same pattern.

**Integration point:** `content_writing.py:_build_task_section()` (line 762) and `content_outline.py:_build_content_from_outline_prompt()`. When `CONTENT_MODE=lorem`:
- System prompt stays the same (brand voice, formatting rules)
- Task section changes: instead of "write natural, engaging copy", instruct Claude to "place target keywords in all H2s, H3s, and lead sentences, then fill all remaining body paragraph text with latin lorem ipsum placeholder text"
- Output format stays the same (page_title, meta_description, top_description, bottom_description)

Same approach for blog content via `blog_content_generation.py`.

**Alternatives considered:**
- Post-processing (generate real content, then regex-replace body with lorem): Wasteful — burns the same Claude tokens for content that gets thrown away
- Hardcoded lorem (no Claude at all): Can't intelligently place keywords within headings and lead sentences at the right density
- Per-project toggle in database: Adds schema complexity for something that's instance-wide

### 2. XLSX export as a new API endpoint + dashboard button

**Decision:** New endpoint `GET /api/v1/export/sites-xlsx` that queries all projects (or selected projects) and generates a single XLSX workbook. New button on the main dashboard.

**XLSX structure (matching sites-template.xlsx):**
- Tab 1: `INSTRUCTIONS` — static content, hardcoded in the export service
- Tab N+1: One tab per project, tab name = project domain (e.g., `crossbodywaterbottlebag.shop`)
- Columns: `page_type` | `title` | `meta_description` | `h1` | `Top description` | `Bottom Description` | `Blog Content`
- Collection pages (from `CrawledPage` + `PageContent`): page_type=`collection`, uses Top/Bottom Description columns
- Blog posts (from `BlogPost`): page_type=`blog`, uses Blog Content column

**Data mapping:**
| XLSX Column | Collection Source | Blog Source |
|-------------|------------------|-------------|
| page_type | `"collection"` | `"blog"` |
| title | `PageContent.page_title` | `BlogPost.title` |
| meta_description | `PageContent.meta_description` | `BlogPost.meta_description` |
| h1 | `PageContent.page_title` (same as title for collections) | `BlogPost.title` |
| Top description | `PageContent.top_description` | (empty) |
| Bottom Description | `PageContent.bottom_description` | (empty) |
| Blog Content | (empty) | `BlogPost.content` |

**Library:** `openpyxl` — already used in the user's static site generator project, zero-dependency Python XLSX library, well-maintained.

**Why not CSV:** The template uses multiple tabs (one per domain). CSV can't do that. The static site generator expects XLSX input.

### 3. Docker-compose profile for isolated local instance

**Decision:** Add a `docker-compose.seo-test.yml` override file that extends the existing `docker-compose.yml` with SEO-test-specific configuration.

**Usage:**
```bash
docker-compose -f docker-compose.yml -f docker-compose.seo-test.yml up -d
```

**What it sets:**
- `CONTENT_MODE=lorem` on the backend service
- `AUTH_REQUIRED=false` (no Neon Auth needed locally)
- `APP_TITLE=SEO Test Instance` (visual indicator in UI)
- Separate PostgreSQL volume name (`seo-test-pgdata`) to avoid colliding with regular local dev
- Backend port mapped to 8001 (so it can coexist with a regular local dev instance on 8000)
- Frontend port mapped to 3001

**Companion `.env.seo-test` file** with all the env vars pre-configured (database URL pointing to local PG, API keys, content mode).

### 4. Visual indicator for SEO test instance

**Decision:** When `CONTENT_MODE=lorem`, the frontend shows a small banner/badge on the sidebar: "SEO Test Mode" in coral. This prevents any confusion about which instance you're looking at.

**Implementation:** Backend already exposes a `/health` endpoint. Extend it (or add `/api/v1/config`) to return `content_mode`. Frontend reads this on mount and conditionally renders the badge.

## Risks / Trade-offs

**[API costs still apply]** → POP briefs, DataForSEO keyword research, and Claude API calls all still cost money. Mitigation: POP mock mode (`POP_USE_MOCK=true`) can be used during development. For actual test runs, budget ~$2-5 per site for POP briefs + Claude generation.

**[Lorem ipsum prompt may need iteration]** → Claude might not perfectly balance keyword placement with lorem ipsum on the first try. Mitigation: The prompt is isolated to one function (`_build_task_section`), easy to iterate. Quality pipeline can still score keyword coverage.

**[XLSX tab name length]** → Excel limits tab names to 31 characters. Some domains might exceed this (e.g., `crossbodywaterbottlebag.shop` = 28 chars, fine). Mitigation: Truncate domain to 31 chars if needed, drop `.shop` suffix.

**[Coexistence with production]** → Someone could accidentally set `CONTENT_MODE=lorem` on the production Railway deployment. Mitigation: The env var defaults to `real`. Railway env vars are set explicitly per service. Add a startup log warning when lorem mode is active.

**[POP brief caching]** → If you run a keyword through POP on the production instance and then again on the local instance, you'll pay for two reports (different databases, different cache). Mitigation: Acceptable cost. Could share a POP cache externally but not worth the complexity.
