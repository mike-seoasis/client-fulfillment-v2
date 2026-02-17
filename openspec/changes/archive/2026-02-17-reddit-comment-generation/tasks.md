## 1. Backend: Prompt Builder & Approach Types

- [x] 1.1 Create `backend/app/services/reddit_comment_generation.py` with PROMOTIONAL_APPROACHES dict (10 types) and ORGANIC_APPROACHES dict (11 types)
- [x] 1.2 Implement `build_comment_prompt()` function that extracts voice, vocabulary, and brand_foundation from BrandConfig.v2_schema with sensible defaults
- [x] 1.3 Add comment_instructions integration from RedditProjectConfig into the prompt voice section
- [x] 1.4 Add post context section (subreddit, title, snippet truncated to 500 chars) with top-level reply instruction
- [x] 1.5 Add promotional brand section (brand name, description, key differentiators) vs organic "do NOT mention brands" section
- [x] 1.6 Add formatting rules (50-150 words, no markdown, subreddit culture matching)

## 2. Backend: Generation Service

- [x] 2.1 Implement `generate_comment()` — load BrandConfig + RedditProjectConfig, select random approach, build prompt, call Claude Sonnet (temp 0.7, max_tokens 500), store as DRAFT RedditComment with generation_metadata
- [x] 2.2 Add quote wrapping cleanup (strip leading/trailing double quotes from Claude response)
- [x] 2.3 Implement generation progress tracking (in-memory dict keyed by project_id, matching discovery pattern)
- [x] 2.4 Implement `generate_batch()` — iterate relevant posts, generate sequentially, track progress, handle per-post failures gracefully

## 3. Backend: API Endpoints

- [x] 3.1 Add Pydantic schemas: GenerateCommentRequest, BatchGenerateRequest, GenerationStatusResponse, RedditCommentUpdateRequest in `schemas/reddit.py`
- [x] 3.2 Add POST `/{project_id}/reddit/posts/{post_id}/generate` endpoint (synchronous single generation, returns 201)
- [x] 3.3 Add POST `/{project_id}/reddit/generate-batch` endpoint (background task, returns 202, 409 if already running)
- [x] 3.4 Add GET `/{project_id}/reddit/generate/status` endpoint (poll generation progress)
- [x] 3.5 Add GET `/{project_id}/reddit/comments` endpoint (list comments with optional status and post_id filters, ordered by created_at desc)
- [x] 3.6 Add PATCH `/{project_id}/reddit/comments/{comment_id}` endpoint (update draft comment body)

## 4. Frontend: API & Hooks

- [x] 4.1 Add API functions in `lib/api.ts`: generateComment, generateBatch, fetchGenerationStatus, fetchComments, updateComment
- [x] 4.2 Add TanStack Query hooks in `hooks/useReddit.ts`: useComments, useGenerationStatus (2s polling when active), useGenerateComment mutation, useGenerateBatch mutation, useUpdateComment mutation

## 5. Frontend: UI Components

- [x] 5.1 Add per-post "Generate" button in posts table rows (for relevant posts), shows "Regenerate" if draft exists, loading spinner during generation
- [x] 5.2 Add "Generate Comments" batch button in comments section header with progress display during generation
- [x] 5.3 Add comments section below posts table: comment cards with body, approach type badge, promotional/organic indicator, post title, status badge, timestamp
- [x] 5.4 Add inline comment body editing for draft comments with Reset link to restore original_body
- [x] 5.5 Add empty state for no comments ("No comments generated yet")

## 6. Verification

- [x] 6.1 Code review: 3 HIGH issues found and fixed (missing PATCH endpoint, missing generated_at, missing selectinload)
- [x] 6.2 Backend syntax validation: all files pass
- [x] 6.3 Frontend TypeScript compilation: no new errors in modified files
- [x] 6.4 Update V2_REBUILD_PLAN.md session log
