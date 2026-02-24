## Context

Phase 14b delivers discovered Reddit posts scored for relevance and classified by intent. The `RedditComment` model and `reddit_comments` table already exist from Phase 14a with full schema (body, original_body, is_promotional, approach_type, status enum, generation_metadata JSONB, reject_reason). The `RedditCommentResponse` Pydantic schema also exists.

The original Flask app had comment generation in `execution/generate_comment_v2.py` with approach-type dictionaries and a prompt builder. This needs to be ported to the V2 architecture using `ClaudeClient`, `BrandConfig.v2_schema`, and `RedditProjectConfig`.

## Goals / Non-Goals

**Goals:**
- Generate natural-sounding Reddit comments using brand context from BrandConfig
- Support 10 promotional approaches (brand mention) and 11 organic approaches (community building)
- Single-post and batch generation with background task pattern
- Store comments as drafts with full generation metadata for the approval pipeline (14d)

**Non-Goals:**
- Comment approval/rejection workflow (Phase 14d)
- CrowdReply submission (Phase 14e)
- Account assignment or cooldown management (Phase 14e)
- Promotional/organic ratio management (future enhancement)
- Comment quality scoring or automated review

## Decisions

### 1. Claude model for comment generation

**Decision:** Use Claude Sonnet (project default via `ClaudeClient`) — NOT Haiku.

**Rationale:** User has explicitly required "Always Claude Sonnet, NEVER Haiku" across the project. Comment quality is critical for brand reputation. The REDDIT_INTEGRATION_PLAN.md mentions Haiku, but the project-wide directive overrides that.

**Alternative considered:** Haiku for speed/cost — rejected per user directive.

### 2. Approach selection strategy

**Decision:** Random selection from the appropriate approach set (promotional or organic). Default to promotional (is_promotional=true) for all generated comments.

**Rationale:** Matches the Flask app behavior. Ratio management (promotional vs organic mix) is a future enhancement. Random selection ensures variety across comments for the same project.

### 3. Generation pattern — synchronous for single, background task for batch

**Decision:**
- Single comment: synchronous POST → returns the generated comment directly
- Batch generation: background task with progress polling (matches discovery pipeline pattern)

**Rationale:** Single comment generation takes ~2-3 seconds (one Claude call) — acceptable for synchronous response. Batch generation for 10+ posts would timeout, so it needs the background task pattern already established in discovery.

### 4. Prompt builder architecture

**Decision:** Single `build_comment_prompt()` function in the service module. Extracts voice characteristics, vocabulary, and brand foundation from `BrandConfig.v2_schema`. Falls back to sensible defaults when brand config fields are missing.

**Rationale:** Keeps the prompt logic co-located with the generation service. No need for a separate module — the prompt builder is only used by comment generation.

### 5. Temperature setting

**Decision:** Use temperature 0.7 for comment generation.

**Rationale:** Comments need variation and naturalness. Temperature 0.0 (used for scoring) would produce identical comments for similar posts. 0.7 provides good creativity while staying coherent.

### 6. Re-generation behavior

**Decision:** Generating a new comment for a post that already has a draft comment creates a NEW comment row (doesn't overwrite). The UI shows the latest draft.

**Rationale:** Preserves generation history. Users can regenerate until they get a comment they like. Old drafts can be cleaned up later.

## Risks / Trade-offs

- **[Brand voice quality]** → BrandConfig may not have rich voice data for all projects. Prompt builder uses sensible defaults and the comment_instructions field from RedditProjectConfig as a fallback voice guide.
- **[Batch size]** → Large batches (50+ posts) mean 50+ sequential Claude calls. → Cap batch at relevant posts without existing draft comments. Progress polling keeps the UI responsive.
- **[Approach randomness]** → Random approach selection may produce suboptimal matches for certain post types. → Acceptable for MVP. Future enhancement could use intent-based approach matching.

## Open Questions

- None — the spec from REDDIT_INTEGRATION_PLAN.md is comprehensive and the model/schema already exist.
