## Why

The Reddit data foundation (Phase 14a) established the models, schemas, and CRUD API for accounts and project config. Now we need the first active pipeline: discovering relevant Reddit posts for a project's configured keywords. This is the feed that drives all downstream Reddit marketing (comment generation, approval queue, CrowdReply submission).

## What Changes

- Add SerpAPI async integration client (`backend/app/integrations/serpapi.py`) — Google search with `site:reddit.com` queries, 1-second rate limiting, circuit breaker pattern
- Add Reddit discovery service (`backend/app/services/reddit_discovery.py`) — full pipeline: SERP search → deduplicate → filter banned/marketing subreddits → keyword-based intent classification → Claude Sonnet relevance scoring → store results
- Add intent classification with keyword lists ported from Flask app (research, pain point, competitor mention, question patterns, promotional exclusion, marketing subreddit exclusion)
- Add Claude Sonnet relevance scoring (0-10 score with reasoning, using brand config context) — **never Haiku, always Sonnet**
- Add discovery API endpoints on project router (trigger discovery, poll status, list/filter posts, update post filter status)
- Add discovery status tracking (in-memory or DB-based progress for polling)
- Add frontend discovery trigger with progress indicator on project Reddit page
- Add discovered posts review table with intent badges, relevance scores, filter status controls, and subreddit/intent filters
- Add Pydantic schemas for discovery status, post list responses, and post update requests

## Capabilities

### New Capabilities
- `serpapi-integration`: SerpAPI async client for Reddit post discovery via Google search
- `reddit-discovery-pipeline`: Full discovery orchestrator — SERP search, deduplication, intent classification, Claude scoring, storage
- `reddit-post-management`: API endpoints for triggering discovery, polling status, listing/filtering posts, approving/rejecting posts
- `reddit-discovery-ui`: Frontend discovery trigger, progress indicator, and post review table with filters and actions

### Modified Capabilities
- `reddit-project-config`: Project Reddit config page gains discovery trigger button and posts table below the config form

## Impact

- **New files:** `backend/app/integrations/serpapi.py`, `backend/app/services/reddit_discovery.py`, new schemas in `backend/app/schemas/reddit.py`
- **Modified files:** `backend/app/api/v1/reddit.py` (add discovery + post endpoints), `frontend/src/lib/api.ts` (add discovery API functions), `frontend/src/hooks/useReddit.ts` (add discovery hooks), `frontend/src/app/projects/[id]/reddit/page.tsx` (add trigger + posts table)
- **New dependency:** None — SerpAPI is a REST API called via `httpx` (already installed)
- **Config:** Uses `SERPAPI_KEY` already added in Phase 14a settings
- **Existing model:** `RedditPost` with `PostFilterStatus` and `PostIntent` enums already created in Phase 14a — no migration needed
