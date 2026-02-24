## Why

Phase 14b delivers discovered Reddit posts scored for relevance. The next step is generating AI comments that operations staff can review, edit, and approve before posting. This is the core value of the Reddit marketing pipeline — turning discovered opportunities into brand-aware replies that feel natural and community-appropriate.

## What Changes

- New comment generation service with approach-type system (10 promotional + 11 organic approaches ported from `execution/generate_comment_v2.py`)
- Prompt builder that integrates BrandConfig v2_schema (voice characteristics, vocabulary, brand foundation) with Reddit project config (comment instructions, competitors)
- Single-post and batch generation endpoints with background task pattern
- Pydantic schemas for generation requests/responses
- Frontend: per-post "Generate" button in posts table, batch "Generate Comments" button, comments list with draft/status indicators
- Comment editing inline (body is editable, original_body preserved)

## Capabilities

### New Capabilities
- `comment-prompt-builder`: Prompt construction using BrandConfig voice/vocabulary/brand_foundation, approach types (promotional vs organic), subreddit culture matching, and formatting rules
- `comment-generation-service`: Single and batch comment generation via Claude, approach selection, comment storage with draft status, generation metadata tracking
- `comment-generation-api`: REST endpoints for triggering single/batch generation and listing comments with status filters
- `comment-generation-ui`: Frontend generate buttons (per-post + batch), comments display with approach badges and status indicators, inline body editing

### Modified Capabilities

## Impact

- **Backend new files:** `services/reddit_comment_generation.py` (prompt builder + generation service)
- **Backend modified:** `api/v1/reddit.py` (3 new endpoints), `schemas/reddit.py` (new request/response schemas)
- **Frontend modified:** `app/projects/[id]/reddit/page.tsx` (generate buttons, comments section), `lib/api.ts` (new API functions), `hooks/useReddit.ts` (new hooks)
- **Dependencies:** Uses existing `ClaudeClient` integration, `BrandConfig` model, `RedditComment` model (created in 14a), `RedditProjectConfig` model
- **No migrations needed:** `reddit_comments` table already exists from Phase 14a
