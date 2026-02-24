## 1. SerpAPI Integration Client

- [ ] 1.1 Create `backend/app/integrations/serpapi.py` — SerpResult dataclass (url, title, snippet, subreddit, discovered_at), SerpAPIClient class with httpx.AsyncClient, CircuitBreaker, structured logging, SERPAPI_KEY from settings
- [ ] 1.2 Implement `search()` method — query construction (`site:reddit.com "{keyword}"`), time range mapping (24h→qdr:d, 7d→qdr:w, 30d→qdr:m), `/comments/` URL filtering, subreddit extraction from URL path
- [ ] 1.3 Implement subreddit-scoped search — when target_subreddits provided, search `site:reddit.com/r/{subreddit} "{keyword}"` for each subreddit, combine results
- [ ] 1.4 Add 1-second rate limiting between consecutive SerpAPI requests using asyncio.sleep
- [ ] 1.5 Initialize SerpAPI client in `backend/app/main.py` startup (same pattern as Claude/Perplexity clients)

## 2. Intent Classification

- [ ] 2.1 Add intent keyword lists to `backend/app/services/reddit_discovery.py` — port RESEARCH_INTENT_KEYWORDS, PAIN_POINT_KEYWORDS, QUESTION_PATTERNS, PROMOTIONAL_KEYWORDS, MARKETING_SUBREDDITS exactly from REDDIT_INTEGRATION_PLAN.md
- [ ] 2.2 Implement `classify_intent()` function — match post title+snippet against keyword lists, return list of matched intents and matched_keywords, detect promotional posts for exclusion
- [ ] 2.3 Implement `is_excluded_post()` function — return True if post matches PROMOTIONAL_KEYWORDS or subreddit is in MARKETING_SUBREDDITS

## 3. Claude Relevance Scoring

- [ ] 3.1 Implement `score_post_with_claude()` function — build prompt with brand_name, description, competitors from BrandConfig, post subreddit/title/snippet, return JSON {score, reasoning, intent}. Use Claude Sonnet (never Haiku).
- [ ] 3.2 Implement `score_posts_batch()` function — score multiple posts sequentially with error handling per post (one failure doesn't stop the batch), update progress tracker between each call
- [ ] 3.3 Implement auto-status logic — score < 4 → filter_status "irrelevant", score 4-6 → "pending", score >= 7 → "relevant"

## 4. Discovery Pipeline Orchestrator

- [ ] 4.1 Create `DiscoveryProgress` dataclass — status (idle/searching/scoring/storing/complete/failed), total_keywords, keywords_searched, total_posts_found, posts_scored, posts_stored, error
- [ ] 4.2 Create in-memory progress store — `_active_discoveries: dict[str, DiscoveryProgress]` module-level dict with get/set/clear helpers
- [ ] 4.3 Implement `discover_posts()` orchestrator — load config + brand_config, search SERP for each keyword (update progress), deduplicate by URL, filter banned/marketing subreddits, classify intent, exclude promotional, score with Claude (update progress), store results (upsert), update progress to complete
- [ ] 4.4 Implement `store_discovered_posts()` — upsert RedditPost rows using INSERT ON CONFLICT (project_id, url) DO UPDATE, preserve user-set filter_status (only update if still "pending")

## 5. Pydantic Schemas

- [ ] 5.1 Add discovery schemas to `backend/app/schemas/reddit.py` — DiscoveryStatusResponse (status, progress counts), DiscoveryTriggerResponse (message), PostListResponse (list of RedditPostResponse), PostUpdateRequest (filter_status), BulkPostActionRequest (post_ids, filter_status)

## 6. API Endpoints

- [ ] 6.1 Add `POST /projects/{project_id}/reddit/discover` endpoint — validate config exists and has keywords, check not already running (409), trigger BackgroundTask, return 202
- [ ] 6.2 Add `GET /projects/{project_id}/reddit/discover/status` endpoint — return current DiscoveryProgress from in-memory store, or idle status if none
- [ ] 6.3 Add `GET /projects/{project_id}/reddit/posts` endpoint — list posts with optional query filters (filter_status, intent via JSONB @> operator, subreddit), order by relevance_score DESC
- [ ] 6.4 Add `PATCH /projects/{project_id}/reddit/posts/{post_id}` endpoint — update filter_status, return updated post, 404 if not found
- [ ] 6.5 Add `POST /projects/{project_id}/reddit/posts/bulk-action` endpoint — bulk update filter_status for list of post_ids

## 7. Backend Tests

- [ ] 7.1 Write SerpAPI client unit tests — query construction, time range mapping, URL filtering, subreddit extraction, rate limiting
- [ ] 7.2 Write intent classification unit tests — each keyword list category, promotional exclusion, marketing subreddit exclusion, multiple intents
- [ ] 7.3 Write discovery pipeline unit tests — deduplication, banned subreddit filtering, progress tracking, upsert logic (new vs existing post, preserve user filter_status)
- [ ] 7.4 Write API integration tests — trigger discovery (202, 409 duplicate, 404 no config, 400 no keywords), poll status, list posts with filters, PATCH post status, bulk action

## 8. Frontend API Client + Hooks

- [ ] 8.1 Add discovery API functions to `frontend/src/lib/api.ts` — triggerRedditDiscovery, fetchDiscoveryStatus, fetchRedditPosts (with filter params), updateRedditPostStatus, bulkUpdateRedditPosts. Add TypeScript interfaces: DiscoveryStatus, RedditPost (frontend type).
- [ ] 8.2 Add discovery hooks to `frontend/src/hooks/useReddit.ts` — useTriggerDiscovery (mutation), useDiscoveryStatus (polling query with refetchInterval when active), useRedditPosts (query with filter params), useUpdatePostStatus (mutation with optimistic update), useBulkUpdatePosts (mutation)

## 9. Frontend Discovery UI

- [ ] 9.1 Add discovery section to `frontend/src/app/projects/[id]/reddit/page.tsx` — "Discover Posts" button below config form, disabled when no saved config/keywords, progress indicator during discovery (searching/scoring phases with counts)
- [ ] 9.2 Add posts table component — columns: Subreddit, Title (external link), Intent badges (color-coded), Score (color-coded), Status, Discovered date. Sort by score descending.
- [ ] 9.3 Add filter controls — status tabs (All/Relevant/Irrelevant/Pending), intent dropdown filter, subreddit dropdown filter
- [ ] 9.4 Add inline approve/reject buttons per row — optimistic UI update, color-coded status badges
- [ ] 9.5 Add empty state for no posts — message with "Discover Posts" CTA

## 10. Frontend Tests

- [ ] 10.1 Write discovery UI component tests — trigger button states (enabled/disabled/loading), progress indicator, completion summary
- [ ] 10.2 Write posts table component tests — renders columns, filter tabs work, intent badges display, score color coding, external links open in new tab
- [ ] 10.3 Write approve/reject component tests — inline buttons update status, bulk action

## 11. Verification

- [ ] 11.1 Run full backend test suite — `pytest` passes including new discovery tests
- [ ] 11.2 Run full frontend test suite — `npm test` passes including new discovery component tests
- [ ] 11.3 `npm run build` succeeds with no errors
- [ ] 11.4 Update V2_REBUILD_PLAN.md — mark Phase 14b complete, add session log entry
