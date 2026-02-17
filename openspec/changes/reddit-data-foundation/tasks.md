## 1. Database Models

- [ ] 1.1 Create `backend/app/models/reddit_account.py` — RedditAccount model with WarmupStage and AccountStatus enums, following blog.py pattern (UUID PK, Mapped types, JSONB niche_tags, server_defaults)
- [ ] 1.2 Create `backend/app/models/reddit_config.py` — RedditProjectConfig model with project_id unique FK, JSONB arrays for keywords/subreddits/competitors/niche_tags, comment_instructions text, discovery_settings JSONB, is_active boolean
- [ ] 1.3 Create `backend/app/models/reddit_post.py` — RedditPost model with PostFilterStatus and PostIntent enums, UniqueConstraint on (project_id, url), JSONB for intent_categories/matched_keywords/ai_evaluation
- [ ] 1.4 Create `backend/app/models/reddit_comment.py` — RedditComment model with CommentStatus enum, FKs to reddit_posts (CASCADE), projects (CASCADE), reddit_accounts (SET NULL), body + original_body text fields, generation_metadata JSONB
- [ ] 1.5 Create `backend/app/models/crowdreply_task.py` — CrowdReplyTask model with CrowdReplyTaskType and CrowdReplyTaskStatus enums, FK to reddit_comments (SET NULL), request/response_payload JSONB, price float
- [ ] 1.6 Register all 5 models in `backend/app/models/__init__.py` — add imports and __all__ entries
- [ ] 1.7 Add `reddit_config` relationship to `backend/app/models/project.py` — 1:1 relationship with back_populates and cascade delete-orphan, add TYPE_CHECKING import for RedditProjectConfig

## 2. Alembic Migration

- [ ] 2.1 Generate migration `0027_create_reddit_tables.py` with `alembic revision --autogenerate` — verify it creates all 5 tables with correct columns, indexes, FKs, and unique constraints
- [ ] 2.2 Test migration: run `alembic upgrade head` and verify tables exist, then `alembic downgrade -1` and verify tables are dropped

## 3. Pydantic Schemas

- [ ] 3.1 Create `backend/app/schemas/reddit.py` — RedditAccountCreate, RedditAccountUpdate, RedditAccountResponse, RedditProjectConfigCreate, RedditProjectConfigResponse, RedditPostResponse, RedditCommentResponse (with nested post), CommentApproveRequest, CommentRejectRequest, BulkCommentActionRequest, CrowdReplyTaskResponse. All response schemas use ConfigDict(from_attributes=True).

## 4. Application Config

- [ ] 4.1 Add Reddit config vars to `backend/app/core/config.py` Settings class — serpapi_key (str, default ""), crowdreply_api_key (str, default ""), crowdreply_project_id (str, default ""), crowdreply_webhook_secret (str, default ""), crowdreply_base_url (str, default "https://crowdreply.io/api")

## 5. API Router

- [ ] 5.1 Create `backend/app/api/v1/reddit.py` — two APIRouter instances: global_router (prefix="/reddit") for account CRUD (GET/POST/PATCH/DELETE /accounts, GET/accounts/{id}), project_router (prefix="/projects") for config endpoints (GET/POST /projects/{project_id}/reddit/config)
- [ ] 5.2 Register both routers in `backend/app/api/v1/__init__.py`
- [ ] 5.3 Implement account list with niche/status/warmup_stage query filters using JSONB @> operator for niche
- [ ] 5.4 Implement account create with 409 on duplicate username
- [ ] 5.5 Implement account update (PATCH) and delete (DELETE) with 404 handling
- [ ] 5.6 Implement project config GET (404 if not found) and POST (upsert — create or update)

## 6. Backend Tests

- [ ] 6.1 Write model unit tests — verify enum values, default field values, and relationships for all 5 models
- [ ] 6.2 Write API integration tests — account CRUD (create, list, filter by niche, update, delete, duplicate username 409), project config (create, get, upsert, 404 on missing project)

## 7. Frontend API Client + Hooks

- [ ] 7.1 Add Reddit API functions to `frontend/src/lib/api.ts` — fetchRedditAccounts, createRedditAccount, updateRedditAccount, deleteRedditAccount, fetchRedditConfig, upsertRedditConfig
- [ ] 7.2 Create `frontend/src/hooks/useReddit.ts` — TanStack Query hooks: useRedditAccounts (with filter params), useCreateRedditAccount, useUpdateRedditAccount, useDeleteRedditAccount (with optimistic delete), useRedditConfig, useUpsertRedditConfig

## 8. Frontend Navigation

- [ ] 8.1 Update `frontend/src/components/Header.tsx` — add "Projects" and "Reddit" nav links with active state via usePathname(), use warm-gray text with palm-500 underline for active state
- [ ] 8.2 Create `frontend/src/app/reddit/layout.tsx` — simple pass-through layout that renders children

## 9. Frontend Pages

- [ ] 9.1 Create `frontend/src/app/reddit/accounts/page.tsx` — account table with Username/Status/Warmup Stage/Niche Tags/Karma/Cooldown/Last Used columns, filter dropdowns (niche, status, warmup), "Add Account" button with modal form (username, niche tags, notes), inline status editing, delete with confirmation, empty state
- [ ] 9.2 Create `frontend/src/app/projects/[id]/reddit/page.tsx` — config form with tag inputs for search_keywords/target_subreddits/banned_subreddits/competitors/niche_tags, textarea for comment_instructions, time range dropdown + max posts input for discovery_settings, active/inactive toggle, Save button, back link to project detail, loads existing config on mount

## 10. Project Detail Integration

- [ ] 10.1 Add Reddit Marketing section card to `frontend/src/app/projects/[id]/page.tsx` — below Blogs section, shows "Not configured" with CTA when no config, shows "Configured" with link when config exists, uses reddit config from a new useRedditConfig hook call

## 11. Frontend Tests

- [ ] 11.1 Write component tests for accounts page — renders table, filter controls work, add account modal, delete confirmation
- [ ] 11.2 Write component tests for project Reddit config page — form renders with all fields, loads existing config, saves successfully
- [ ] 11.3 Write component tests for Header nav — both links render, active states toggle correctly

## 12. Verification

- [ ] 12.1 Run full test suite — `pytest` (backend) and `npm test` (frontend) all pass
- [ ] 12.2 Manual verification — create account, set niche tags, configure project Reddit settings, verify project detail shows Reddit card, verify header nav works
- [ ] 12.3 `npm run build` succeeds with no errors
