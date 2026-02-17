## Why

The Reddit marketing pipeline is a major revenue-driving workflow — Arly discovers relevant Reddit posts, generates brand-aware comments, reviews/approves them, and submits via CrowdReply for posting. This currently lives in a standalone Flask app that's disconnected from the main platform. Integrating it into V2 means one unified tool, shared brand context (BrandConfig), and cross-project visibility. Slice 14a establishes the data foundation: all database tables, schemas, CRUD APIs, and config UI that every subsequent Reddit slice (discovery, generation, queue, posting, dashboard) builds on.

## What Changes

- Add 5 new database tables: `reddit_accounts`, `reddit_project_configs`, `reddit_posts`, `reddit_comments`, `crowdreply_tasks`
- Add Alembic migration `0027` creating all Reddit tables
- Add Pydantic v2 request/response schemas for all Reddit entities
- Add `RedditProjectConfig` 1:1 relationship on the existing `Project` model
- Add Reddit account pool CRUD API endpoints (list, create, update, delete)
- Add project Reddit config API endpoints (get, upsert)
- Add SERP API and CrowdReply environment variables to backend settings
- Add frontend account management page at `/reddit/accounts`
- Add frontend project Reddit config page at `/projects/[id]/reddit`
- Add Reddit API client functions and TanStack Query hooks
- Add "Reddit" nav link to Header component
- Add Reddit section layout for `/reddit/*` pages

## Capabilities

### New Capabilities
- `reddit-accounts`: Account pool management — CRUD for shared Reddit accounts with warmup stages, niche tags, cooldown tracking, and status lifecycle
- `reddit-project-config`: Per-project Reddit settings — search keywords, target/banned subreddits, competitors, comment voice instructions, niche tags, discovery settings
- `reddit-data-models`: Core data models for posts, comments, and CrowdReply task tracking — the schema foundation that discovery (14b), generation (14c), queue (14d), and posting (14e) all depend on
- `reddit-navigation`: Top-level Reddit section in app navigation with layout wrapper for Reddit pages

### Modified Capabilities
- `project-detail-view`: Add Reddit marketing section card showing config status and quick stats, with link to project Reddit settings
- `project-management`: Add `reddit_config` 1:1 relationship on Project model (cascade delete)

## Impact

**Backend:**
- New files: 5 model files, 1 schema file, 1 API router, migration `0027`
- Modified: `models/project.py` (relationship), `core/config.py` (env vars), `models/__init__.py` (imports), app router registration
- New env vars: `SERPAPI_KEY`, `CROWDREPLY_API_KEY`, `CROWDREPLY_PROJECT_ID`, `CROWDREPLY_WEBHOOK_SECRET`, `CROWDREPLY_BASE_URL`

**Frontend:**
- New files: `/reddit/layout.tsx`, `/reddit/accounts/page.tsx`, `/projects/[id]/reddit/page.tsx`, `lib/api/reddit.ts` or additions to `lib/api.ts`, `hooks/useReddit.ts`, `components/reddit/AccountTable.tsx`
- Modified: `components/Header.tsx` (nav link), `app/projects/[id]/page.tsx` (Reddit card)

**Database:**
- 5 new tables with indexes, unique constraints, and foreign keys
- No changes to existing table schemas

**Dependencies:**
- No new npm or Python packages required
