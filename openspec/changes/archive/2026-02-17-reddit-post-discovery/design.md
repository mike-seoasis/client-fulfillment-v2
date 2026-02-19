## Context

Phase 14a established the Reddit data foundation: 5 database models (RedditAccount, RedditProjectConfig, RedditPost, RedditComment, CrowdReplyTask), Pydantic schemas, account pool CRUD, and project config management. The RedditPost model already has `PostFilterStatus` (pending/relevant/irrelevant) and `PostIntent` (research/pain_point/competitor/question/general) enums, plus JSONB fields for `intent_categories`, `matched_keywords`, and `ai_evaluation`.

Now we need the first active pipeline: searching Google for Reddit posts matching a project's keywords, filtering/scoring them with intent classification + Claude Sonnet, and storing them for human review.

The existing content generation pipeline (Phase 5) provides the pattern: trigger endpoint → BackgroundTask → poll status → review results. We follow that pattern exactly.

## Goals / Non-Goals

**Goals:**
- Discover Reddit posts via SerpAPI (Google search with `site:reddit.com` queries)
- Classify post intent using keyword lists (fast, no API calls)
- Score post relevance using Claude Sonnet with brand context
- Store discovered posts with deduplication (upsert by project_id + url)
- Let users trigger discovery, monitor progress, and review/filter results
- Follow existing integration and pipeline patterns exactly

**Non-Goals:**
- Real-time Reddit API scraping (we use Google's index via SerpAPI)
- Automated scheduling/cron for discovery (manual trigger only for now)
- Comment generation (Phase 14c)
- Full post body fetching (we work with SERP snippets; full scraping is a later enhancement)
- Reddit OAuth or direct API integration

## Decisions

### 1. SerpAPI Client follows integration pattern
**Decision:** Create `backend/app/integrations/serpapi.py` following `claude.py` pattern — httpx.AsyncClient, CircuitBreaker, structured logging, retry with backoff.

**Rationale:** Consistency. Every external API client uses the same pattern. SerpAPI is a simple REST GET with JSON response.

**Key details:**
- Query format: `site:reddit.com "{keyword}"` (exact match in quotes)
- If target subreddits configured: `site:reddit.com/r/{subreddit} "{keyword}"` for each subreddit
- Time range: `tbs` param maps `24h→qdr:d`, `7d→qdr:w`, `30d→qdr:m`
- Rate limit: 1-second delay between requests (same as Flask app)
- Filter results: only URLs containing `/comments/` (actual posts, not subreddit pages)
- Extract subreddit from URL path: `/r/{subreddit}/comments/...`
- Return `SerpResult` dataclass with url, title, snippet, subreddit, discovered_at

### 2. Two-stage filtering: fast keywords then Claude Sonnet
**Decision:** Intent classification runs first (keyword matching, no API calls), then Claude Sonnet scores relevance. Posts below score threshold (< 4) auto-marked irrelevant.

**Rationale:** Keyword-based intent classification is free and instant — it categorizes intent (research, pain_point, competitor, question). Claude scoring is the expensive step — it evaluates brand relevance using brand config context. Running keywords first lets us skip obviously promotional/marketing posts before sending to Claude.

**Alternative considered:** Claude-only scoring. Rejected because it would waste API calls on spam posts that keyword filtering catches instantly.

**Key details:**
- Port keyword lists exactly from Flask app (RESEARCH_INTENT_KEYWORDS, PAIN_POINT_KEYWORDS, QUESTION_PATTERNS, PROMOTIONAL_KEYWORDS, MARKETING_SUBREDDITS)
- Promotional posts and marketing subreddit posts are auto-rejected (never sent to Claude)
- Claude prompt includes brand name, description, competitors from BrandConfig
- Claude returns JSON: `{"score": 0-10, "reasoning": "...", "intent": "research|pain_point|competitor|question|general"}`
- Claude's intent enriches (not replaces) the keyword-based intent
- **Always use Claude Sonnet, never Haiku**

### 3. In-memory status tracking with DB fallback
**Decision:** Use `_active_discoveries: dict[str, DiscoveryProgress]` in-memory dict for real-time progress, same pattern as `_active_generations` set in content_generation.py but with richer progress data.

**Rationale:** Discovery is fast (30-60 seconds for a typical project). In-memory tracking is simpler than a dedicated status table. If the server restarts mid-discovery, the status simply resets — user can re-trigger.

**Progress fields:** `total_keywords`, `keywords_searched`, `total_posts_found`, `posts_scored`, `posts_stored`, `status` (searching/scoring/storing/complete/failed), `error`.

### 4. Discovery endpoints on the existing project router
**Decision:** Add discovery endpoints to the existing `reddit_project_router` in `backend/app/api/v1/reddit.py`, scoped under `/projects/{project_id}/reddit/`.

**Endpoints:**
- `POST /projects/{project_id}/reddit/discover` → 202 Accepted, triggers BackgroundTask
- `GET /projects/{project_id}/reddit/discover/status` → Poll progress
- `GET /projects/{project_id}/reddit/posts` → List posts with query filters (filter_status, intent, subreddit)
- `PATCH /projects/{project_id}/reddit/posts/{post_id}` → Update filter_status (approve/reject)
- `POST /projects/{project_id}/reddit/posts/bulk-action` → Bulk approve/reject

**Rationale:** Keeps all project-scoped Reddit endpoints together. Follows the same trigger/poll/review pattern as content generation.

### 5. Upsert by (project_id, url) for deduplication
**Decision:** Use the existing UniqueConstraint on `(project_id, url)` on RedditPost model. On re-discovery, update existing posts (new score, refreshed snippet) rather than creating duplicates.

**Rationale:** A post discovered twice should update its metadata, not create a duplicate entry. The UniqueConstraint enforces this at the DB level. Use `ON CONFLICT DO UPDATE` for the upsert.

### 6. Frontend: extend project Reddit config page
**Decision:** Add discovery trigger and posts table to the existing `/projects/[id]/reddit/page.tsx` rather than creating a new route.

**Rationale:** Discovery is directly tied to the project's Reddit config (keywords drive what gets discovered). Having trigger + results on the same page creates a tight feedback loop: configure keywords → discover → review posts.

**UI additions:**
- "Discover Posts" button below the config form (or in a new section)
- Progress indicator during discovery (polling useQuery)
- Posts table with columns: Subreddit, Title (linked to Reddit), Intent badge, Score, Status, Discovered date
- Filter tabs: All | Relevant | Irrelevant | Pending
- Inline approve/reject buttons per row
- Bulk select + bulk action

## Risks / Trade-offs

- **SerpAPI rate limits** → 1-second delay between requests. For a project with 10 keywords × no subreddit filter, that's ~10 seconds of search time. Acceptable.
- **SerpAPI cost** → ~$50/mo for 5,000 searches. Each discovery run uses 1 search per keyword (or keyword × subreddit). Projects with 5-10 keywords = 5-10 searches per run. Well within budget.
- **Claude Sonnet cost for scoring** → Each post scored individually. A discovery returning 50 posts = 50 Claude calls. At ~$0.003/call (short prompt) = $0.15/run. Acceptable.
- **In-memory status lost on restart** → If server restarts during discovery, progress is lost. Mitigation: discovery is fast (< 60s), user can re-trigger. Posts already stored in DB are not lost.
- **SERP snippets may be stale** → Google's index lags Reddit by hours/days. Mitigation: time_range filter helps, and freshness is less critical for marketing posts (most relevant threads stay relevant for days/weeks).
