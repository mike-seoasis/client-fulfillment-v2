# Phase 14: Reddit Marketing Integration — Detailed Plan

> This document is the complete blueprint for integrating Reddit marketing features into the client-onboarding-v2 platform. It is designed to be picked up and executed as-is after Phase 12 (Authentication) and Phase 13 (Polish & UX) are complete. Source: standalone Reddit Scraper App (Flask/PostgreSQL) + meeting with Arly (Reddit operator, 2026-02-16).

---

## Table of Contents

1. [Background & Decisions](#1-background--decisions)
2. [Architecture Overview](#2-architecture-overview)
3. [Slice 14a: Reddit Data Foundation](#3-slice-14a-reddit-data-foundation)
4. [Slice 14b: Post Discovery Pipeline](#4-slice-14b-post-discovery-pipeline)
5. [Slice 14c: Comment Generation](#5-slice-14c-comment-generation)
6. [Slice 14d: Comment Queue + Approval](#6-slice-14d-comment-queue--approval)
7. [Slice 14e: CrowdReply Integration](#7-slice-14e-crowdreply-integration)
8. [Slice 14f: Reddit Dashboard + Project Integration](#8-slice-14f-reddit-dashboard--project-integration)
9. [Slice 14g: Seeded Conversations (Stretch)](#9-slice-14g-seeded-conversations-stretch)
10. [What to Port vs. Rebuild](#10-what-to-port-vs-rebuild)
11. [Environment Variables](#11-environment-variables)
12. [File Structure Summary](#12-file-structure-summary)
13. [Verification Plan](#13-verification-plan)

---

## 1. Background & Decisions

### What We're Integrating

The Reddit Scraper App is a standalone Flask/PostgreSQL platform that:
- Discovers relevant Reddit posts via SERP API (Google search with `site:reddit.com`)
- Filters posts by intent (research questions, pain points, competitor mentions)
- Generates natural AI comments using persona profiles and brand context
- Queues comments for human review (Arly reviews/edits/approves)
- Posts approved comments via CrowdReply (third-party Reddit posting service)
- Tracks posting status via webhooks

### Key Decisions (from planning session)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Navigation** | Top-level Reddit section + project links | Reddit is a major workflow, not just a project sub-feature. `/reddit` dashboard + `/reddit/accounts` + `/reddit/comments`. Project-specific config at `/projects/[id]/reddit`. |
| **Persona System** | No personas initially | The Flask app has an elaborate persona pipeline (demographics, style metrics, quirks, linguistic signatures). Too complex for V1. Instead, use existing `BrandConfig.v2_schema` (voice characteristics, vocabulary, brand foundation) + per-project `comment_instructions` text field. |
| **Posting Method** | CrowdReply + foundation for own accounts | CrowdReply handles the actual posting for now ($5/comment). Account pool tracks our own accounts for warmup and future direct posting. |
| **Phase Priority** | Phase 14 (after auth + polish) | Depends on auth for user context. Polish phase improves base UX first. |
| **Niche Tags** | JSONB arrays (not join tables) | Simple `["skincare", "supplements"]` arrays on accounts and project configs. Queryable with PostgreSQL `@>` operator. Avoids the complexity of separate `niche_tags` + `account_niche_tags` join tables from the Flask V2 plan. |
| **Account Pool** | Shared across projects | Accounts tagged by niche, not bound to a single client. Multiple projects can use the same account pool filtered by niche overlap. |

### Arly's Workflow (from meeting transcript)

**Daily routine:**
1. Open comment queue → see pending comments across all projects
2. Quick scan: read post title + generated comment
3. Approve good ones (keyboard shortcut), edit mediocre ones, reject bad ones
4. Bulk approve obvious wins
5. Submit approved batch to CrowdReply
6. Check back later for posting confirmations

**Key insights from Arly:**
- Speed is everything — keyboard shortcuts are critical
- Usually approves 60-70% as-is, edits 20%, rejects 10%
- Wants cross-project queue (not per-project)
- Needs to see the original post context alongside the comment
- CrowdReply costs ~$5/comment, so quality matters
- After posting, wants 5-10 upvotes on each comment (CrowdReply can do this)
- Seeded conversations (plant a question, then answer it) are the next-level play
- Account warmup: new accounts need 2-4 weeks of organic activity before promotional use

---

## 2. Architecture Overview

### Pipeline Flow

```
Configure Project Reddit Settings
        ↓
SERP API Discovery (scrape_serp logic)
        ↓
Claude Intent Filtering (filter_posts logic)
        ↓
Store Relevant Posts (reddit_posts table)
        ↓
AI Comment Generation (generate_comment_v2 logic)
        ↓
Store Draft Comments (reddit_comments table)
        ↓
Human Review Queue (Arly approves/edits/rejects)
        ↓
Submit to CrowdReply API (crowdreply_tasks table)
        ↓
Webhook Status Updates (posted/mod-removed/etc.)
        ↓
Optional: Send Upvotes (5-10 per comment)
```

### Integration Points with Existing V2 App

| V2 Feature | Reddit Integration |
|------------|-------------------|
| `Project` model | Add `reddit_config` 1:1 relationship |
| `BrandConfig.v2_schema` | Source for brand voice in comment generation prompts |
| `Header.tsx` | Add "Reddit" top-level nav link |
| `Project Detail` page | Add Reddit section card with stats |
| TanStack Query patterns | Follow existing hooks/API client patterns |
| Alembic migrations | Continue numbering (next: 0027) |
| Integration client pattern | Follow `backend/app/integrations/claude.py` for SERP + CrowdReply clients |
| Service pattern | Follow `backend/app/services/` async patterns |

---

## 3. Slice 14a: Reddit Data Foundation

**Goal:** Database tables exist, accounts can be managed, project Reddit config can be set.

### Database Models (5 tables, 1 migration)

#### Table: `reddit_accounts`

Shared account pool. Accounts are tagged by niche, not bound to a single project.

```python
# backend/app/models/reddit_account.py
# Follow blog.py pattern exactly

class WarmupStage(str, Enum):
    OBSERVATION = "observation"           # Week 1-2: browse, upvote
    LIGHT_ENGAGEMENT = "light_engagement" # Week 2-3: non-promotional comments
    REGULAR_ACTIVITY = "regular_activity" # Week 3-4: mix of organic + light promo
    OPERATIONAL = "operational"           # Week 4+: full promotional use

class AccountStatus(str, Enum):
    ACTIVE = "active"
    WARMING_UP = "warming_up"
    COOLDOWN = "cooldown"     # Hit rate limit or needs rest
    SUSPENDED = "suspended"   # Reddit flagged
    BANNED = "banned"

class RedditAccount(Base):
    __tablename__ = "reddit_accounts"

    id              # UUID PK (gen_random_uuid())
    username        # String(100), unique, not null, indexed
    status          # String(50), default "active", indexed — AccountStatus enum
    warmup_stage    # String(50), default "observation" — WarmupStage enum
    niche_tags      # JSONB, default [], not null — e.g. ["skincare", "supplements"]
    karma_post      # Integer, default 0
    karma_comment   # Integer, default 0
    account_age_days # Integer, nullable
    cooldown_until  # DateTime(timezone=True), nullable — don't use until this time
    last_used_at    # DateTime(timezone=True), nullable
    notes           # Text, nullable — admin notes
    metadata        # JSONB, nullable — flexible storage (crowdreply account info, etc.)
    created_at      # DateTime(timezone=True), not null, server_default now()
    updated_at      # DateTime(timezone=True), not null, server_default now(), onupdate
```

**Design notes:**
- No `password_encrypted` or `email_encrypted` — CrowdReply handles posting, we don't need credentials
- No `persona_id` or `browser_profile_id` — no persona system in V1, no direct posting
- `niche_tags` is a JSONB array, queryable with `WHERE niche_tags @> '["skincare"]'::jsonb`
- `cooldown_until` replaces complex cooldown logic — simple timestamp check
- `metadata` JSONB for future extensibility (CrowdReply account mapping, proxy info, etc.)

#### Table: `reddit_project_configs`

Per-project Reddit settings. 1:1 with Project.

```python
# backend/app/models/reddit_config.py

class RedditProjectConfig(Base):
    __tablename__ = "reddit_project_configs"

    id              # UUID PK (gen_random_uuid())
    project_id      # UUID FK → projects.id, unique (1:1), CASCADE, indexed
    search_keywords # JSONB, default [], not null — keywords for SERP discovery
    target_subreddits # JSONB, default [], not null — subreddits to search in
    banned_subreddits # JSONB, default [], not null — subreddits to exclude
    competitors     # JSONB, default [], not null — competitor brand names for intent matching
    comment_instructions # Text, nullable — custom instructions for AI comment voice
    niche_tags      # JSONB, default [], not null — match against account pool
    discovery_settings # JSONB, nullable — {time_range: "24h"|"7d"|"30d", max_posts_per_run: 20}
    is_active       # Boolean, default true — enable/disable Reddit for this project
    created_at      # DateTime(timezone=True)
    updated_at      # DateTime(timezone=True)
```

**Relationship on Project model:**
```python
# In backend/app/models/project.py, add:
reddit_config: Mapped["RedditProjectConfig | None"] = relationship(
    "RedditProjectConfig",
    back_populates="project",
    uselist=False,
    cascade="all, delete-orphan",
)
```

#### Table: `reddit_posts`

Discovered Reddit threads from SERP API.

```python
# backend/app/models/reddit_post.py

class PostFilterStatus(str, Enum):
    PENDING = "pending"       # Just discovered, not yet filtered
    RELEVANT = "relevant"     # Passed intent/relevance filtering
    IRRELEVANT = "irrelevant" # Failed filtering
    SKIPPED = "skipped"       # Manually skipped by user

class PostIntent(str, Enum):
    RESEARCH = "research"           # Looking for recommendations
    PAIN_POINT = "pain_point"       # Expressing a problem
    COMPETITOR = "competitor"       # Mentioning a competitor
    QUESTION = "question"           # Asking a question
    GENERAL = "general"             # Generic relevant discussion

class RedditPost(Base):
    __tablename__ = "reddit_posts"

    id              # UUID PK (gen_random_uuid())
    project_id      # UUID FK → projects.id, CASCADE, indexed
    reddit_post_id  # String(50), nullable — Reddit's t3_ ID (for dedup)
    subreddit       # String(100), not null, indexed
    title           # Text, not null
    url             # String(2048), not null
    snippet         # Text, nullable — SERP snippet / post preview
    keyword         # String(500), nullable — which search keyword found this
    intent          # String(50), nullable — PostIntent enum
    intent_categories # JSONB, nullable — ["research", "pain_point"] (can have multiple)
    relevance_score # Float, nullable — 0.0-1.0 from Claude scoring
    matched_keywords # JSONB, nullable — intent keywords that matched
    ai_evaluation   # JSONB, nullable — full Claude evaluation response
    filter_status   # String(50), default "pending", indexed — PostFilterStatus enum
    serp_position   # Integer, nullable — Google SERP rank position
    discovered_at   # DateTime(timezone=True), not null — when SERP returned this
    created_at      # DateTime(timezone=True)
    updated_at      # DateTime(timezone=True)

    # Unique constraint: don't store same URL twice per project
    __table_args__ = (
        UniqueConstraint('project_id', 'url', name='uq_reddit_posts_project_url'),
    )
```

#### Table: `reddit_comments`

Generated AI comments linked to posts.

```python
# backend/app/models/reddit_comment.py

class CommentStatus(str, Enum):
    DRAFT = "draft"           # AI generated, pending review
    APPROVED = "approved"     # Human approved, ready to submit
    REJECTED = "rejected"     # Human rejected
    SUBMITTING = "submitting" # Sent to CrowdReply, awaiting confirmation
    POSTED = "posted"         # CrowdReply confirmed posted
    FAILED = "failed"         # CrowdReply posting failed
    MOD_REMOVED = "mod_removed" # Posted but removed by subreddit moderator

class RedditComment(Base):
    __tablename__ = "reddit_comments"

    id              # UUID PK (gen_random_uuid())
    post_id         # UUID FK → reddit_posts.id, CASCADE, indexed
    project_id      # UUID FK → projects.id, CASCADE, indexed
    account_id      # UUID FK → reddit_accounts.id, SET NULL, nullable, indexed
    body            # Text, not null — current comment text (may be edited)
    original_body   # Text, not null — AI-generated original (never changes)
    is_promotional  # Boolean, not null, default true
    approach_type   # String(100), nullable — "Sandwich", "Story-Based", etc.
    status          # String(50), default "draft", indexed — CommentStatus enum
    reject_reason   # Text, nullable — why it was rejected
    crowdreply_task_id # String(255), nullable — CrowdReply external task ID
    posted_url      # String(2048), nullable — actual Reddit comment URL after posting
    posted_at       # DateTime(timezone=True), nullable
    generation_metadata # JSONB, nullable — {model, tokens_used, prompt_hash, approach}
    created_at      # DateTime(timezone=True)
    updated_at      # DateTime(timezone=True)
```

#### Table: `crowdreply_tasks`

Track CrowdReply API submissions and their status.

```python
# backend/app/models/crowdreply_task.py

class CrowdReplyTaskType(str, Enum):
    COMMENT = "comment"   # RedditCommentTask
    POST = "post"         # RedditPostTask
    REPLY = "reply"       # RedditReplyTask
    UPVOTE = "upvote"     # Standalone upvote request

class CrowdReplyTaskStatus(str, Enum):
    PENDING = "pending"               # Created, not yet submitted
    SUBMITTED = "submitted"           # Sent to CrowdReply API
    ASSIGNED = "assigned"             # CrowdReply assigned a worker
    PUBLISHED = "published"           # Successfully posted
    MOD_REMOVED = "mod_removed"       # Removed by moderator
    CANCELLED = "cancelled"           # Cancelled by us or CrowdReply
    FAILED = "failed"                 # Submission failed

class CrowdReplyTask(Base):
    __tablename__ = "crowdreply_tasks"

    id              # UUID PK (gen_random_uuid())
    comment_id      # UUID FK → reddit_comments.id, SET NULL, nullable, indexed
    external_task_id # String(255), nullable, indexed — CrowdReply's _id
    task_type       # String(50), not null — CrowdReplyTaskType enum
    status          # String(50), default "pending", indexed — CrowdReplyTaskStatus enum
    target_url      # String(2048), not null — Reddit thread/post URL
    content         # Text, not null — comment/post content sent
    crowdreply_project_id # String(255), nullable — CrowdReply project ID used
    request_payload # JSONB, nullable — full request body sent to CrowdReply
    response_payload # JSONB, nullable — webhook response body
    upvotes_requested # Integer, nullable — how many upvotes ordered
    price           # Float, nullable — CrowdReply clientPrice from webhook
    submitted_at    # DateTime(timezone=True), nullable
    published_at    # DateTime(timezone=True), nullable
    created_at      # DateTime(timezone=True)
    updated_at      # DateTime(timezone=True)
```

### Alembic Migration

**File:** `backend/alembic/versions/0027_create_reddit_tables.py`

Create all 5 tables in a single migration. Use the next available migration number (check what 0026 is at implementation time). Include:
- All tables with indexes
- `UniqueConstraint` on `reddit_posts(project_id, url)`
- Foreign keys with appropriate `ondelete` behavior
- JSONB columns with server defaults where applicable

### Pydantic Schemas

**File:** `backend/app/schemas/reddit.py`

All schemas follow Pydantic v2 patterns (same as `backend/app/schemas/blog.py`):

```python
# --- Reddit Account schemas ---
class RedditAccountCreate(BaseModel):
    username: str = Field(max_length=100)
    niche_tags: list[str] = Field(default_factory=list)
    warmup_stage: str = "observation"
    notes: str | None = None

class RedditAccountUpdate(BaseModel):
    username: str | None = None
    status: str | None = None
    warmup_stage: str | None = None
    niche_tags: list[str] | None = None
    karma_post: int | None = None
    karma_comment: int | None = None
    cooldown_until: datetime | None = None
    notes: str | None = None

class RedditAccountResponse(BaseModel):
    id: str
    username: str
    status: str
    warmup_stage: str
    niche_tags: list[str]
    karma_post: int
    karma_comment: int
    account_age_days: int | None
    cooldown_until: datetime | None
    last_used_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- Reddit Project Config schemas ---
class RedditProjectConfigCreate(BaseModel):
    search_keywords: list[str] = Field(default_factory=list)
    target_subreddits: list[str] = Field(default_factory=list)
    banned_subreddits: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    comment_instructions: str | None = None
    niche_tags: list[str] = Field(default_factory=list)
    discovery_settings: dict | None = None

class RedditProjectConfigResponse(BaseModel):
    id: str
    project_id: str
    search_keywords: list[str]
    target_subreddits: list[str]
    banned_subreddits: list[str]
    competitors: list[str]
    comment_instructions: str | None
    niche_tags: list[str]
    discovery_settings: dict | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- Reddit Post schemas ---
class RedditPostResponse(BaseModel):
    id: str
    project_id: str
    subreddit: str
    title: str
    url: str
    snippet: str | None
    keyword: str | None
    intent: str | None
    intent_categories: list[str] | None
    relevance_score: float | None
    filter_status: str
    serp_position: int | None
    discovered_at: datetime
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- Reddit Comment schemas ---
class RedditCommentResponse(BaseModel):
    id: str
    post_id: str
    project_id: str
    account_id: str | None
    body: str
    original_body: str
    is_promotional: bool
    approach_type: str | None
    status: str
    reject_reason: str | None
    posted_url: str | None
    posted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # Nested for queue view
    post: RedditPostResponse | None = None
    model_config = ConfigDict(from_attributes=True)

class CommentApproveRequest(BaseModel):
    body: str | None = None  # Optional edited body

class CommentRejectRequest(BaseModel):
    reason: str | None = None

class BulkCommentActionRequest(BaseModel):
    comment_ids: list[str]

# --- CrowdReply Task schemas ---
class CrowdReplyTaskResponse(BaseModel):
    id: str
    comment_id: str | None
    external_task_id: str | None
    task_type: str
    status: str
    target_url: str
    upvotes_requested: int | None
    price: float | None
    submitted_at: datetime | None
    published_at: datetime | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

### API Endpoints (Slice 14a)

**File:** `backend/app/api/v1/reddit.py` (new router, registered in main app)

```
# Account Pool CRUD
GET    /api/v1/reddit/accounts                    → List accounts (query: niche, warmup_stage, status)
POST   /api/v1/reddit/accounts                    → Create account
PATCH  /api/v1/reddit/accounts/{account_id}       → Update account
DELETE /api/v1/reddit/accounts/{account_id}        → Delete account

# Project Reddit Config
GET    /api/v1/projects/{project_id}/reddit/config → Get config (404 if none)
POST   /api/v1/projects/{project_id}/reddit/config → Create or update config (upsert)
```

### Frontend (Slice 14a)

**New files:**
- `frontend/src/lib/api/reddit.ts` — API client functions (follow `frontend/src/lib/api/blog.ts` pattern)
- `frontend/src/hooks/useReddit.ts` — TanStack Query hooks (follow `frontend/src/hooks/useBlog.ts` pattern)
- `frontend/src/app/reddit/layout.tsx` — Reddit section layout
- `frontend/src/app/reddit/accounts/page.tsx` — Account pool management page
- `frontend/src/app/projects/[id]/reddit/page.tsx` — Project Reddit config page

**Account Pool page (`/reddit/accounts`):**
- Table with columns: Username, Status, Warmup Stage, Niche Tags (chips), Karma, Cooldown, Last Used
- Filter bar: niche dropdown, warmup stage dropdown, status dropdown
- Sort by any column
- "Add Account" button → modal with username + niche tags + notes
- Inline status/warmup editing
- Delete with confirmation

**Project Reddit Config page (`/projects/[id]/reddit`):**
- Form with:
  - Search Keywords (tag input — comma-separated, same as blog keyword input)
  - Target Subreddits (tag input — prefixed with `r/`)
  - Banned Subreddits (tag input)
  - Competitors (tag input)
  - Comment Instructions (textarea — freeform text for AI voice guidance)
  - Niche Tags (tag input — for account matching)
  - Discovery Settings (time range dropdown: 24h/7d/30d, max posts input)
- Save button
- Active/inactive toggle

---

## 4. Slice 14b: Post Discovery Pipeline

**Goal:** Discover Reddit posts for a project via SERP API + Claude filtering.

### SERP API Integration

**File:** `backend/app/integrations/serpapi.py`

Port the query logic from `execution/scrape_serp.py`. Key logic to preserve:

```python
# Query construction
search_query = f'site:reddit.com "{keyword}"'

# SERP API call
url = "https://serpapi.com/search"
params = {
    "q": search_query,
    "api_key": settings.SERPAPI_KEY,
    "engine": "google",
    "num": 20,
    "tbs": {"24h": "qdr:d", "7d": "qdr:w", "30d": "qdr:m"}[time_range],
}

# Filter results: only reddit.com URLs with /comments/ path
for result in data["organic_results"]:
    link = result.get("link", "")
    if "reddit.com" in link and "/comments/" in link:
        # Extract subreddit from URL
        parts = link.split("/")
        r_index = parts.index("r")
        subreddit = parts[r_index + 1]
```

**V2 changes from Flask version:**
- Use `httpx.AsyncClient` instead of `requests`
- Follow `backend/app/integrations/claude.py` pattern (circuit breaker, logging, error handling)
- Add rate limiting (1 second between SERP requests, same as Flask app)
- Return structured dataclass, not raw dicts

### Intent Filtering Service

**File:** `backend/app/services/reddit_discovery.py`

Port the intent classification from `execution/filter_posts.py`. Key logic to preserve:

```python
# Intent classification keyword lists (PORT THESE EXACTLY)
RESEARCH_INTENT_KEYWORDS = [
    "recommend", "recommendation", "suggestions", "suggest", "advice",
    "best", "looking for", "help me find", "what should i", "which",
    "vs", "compare", "alternative", "instead of", "similar to",
    "thoughts on", "opinions on", "reviews", "worth it", "good",
    "anyone tried", "has anyone used", "experiences with",
    "ideas", "options", "need help", "new to", "know nothing",
    "where to start", "beginner", "first time"
]

PAIN_POINT_KEYWORDS = [
    "struggling", "problem", "issue", "help", "not working", "failed",
    "disappointed", "waste", "regret", "frustrated", "confused",
    "expensive", "can't afford", "too much", "overpriced",
    "dry skin", "sensitive skin", "acne", "wrinkles", "aging",
    "irritation", "redness", "breakout", "doesn't work",
    "afraid", "worried", "concern", "losing", "getting worse",
    "don't know", "clueless", "overwhelmed", "unsure"
]

QUESTION_PATTERNS = [
    "?", "how do i", "how to", "what is", "what are", "why",
    "can i", "should i", "is it", "are there", "does anyone"
]

PROMOTIONAL_KEYWORDS = [  # EXCLUDE these posts
    "my brand", "i founded", "my company", "my business", "i'm selling",
    "our product", "check out my", "my store", "promotion", "discount code",
    "affiliate", "my website", "buy from", "i created", "launching my",
    "for sale", "selling", "buy now", "shop", "coupon", "promo code"
]

MARKETING_SUBREDDITS = [  # Skip these
    "facebookads", "ppc", "marketing", "entrepreneur", "smallbusiness",
    "ecommerce", "shopify", "business", "startup", "advertising"
]
```

**V2 changes from Flask version:**
- Replace OpenAI `gpt-4o-mini` evaluation with Claude Haiku (via existing `backend/app/integrations/claude.py`)
- Claude prompt for relevance scoring:

```
You are evaluating Reddit posts for marketing opportunities for {brand_name}.

Brand: {brand_name}
Products: {brand_description}
Competitors: {competitors}

Reddit Post:
Subreddit: r/{subreddit}
Title: {title}
Content: {snippet}

Score 0-10: Is this a natural opportunity to mention {brand_name}?
REJECT if: unrelated to brand, purely negative/ranting, promotional/spam
ACCEPT if: asking for recommendations, has a problem brand could solve, comparing products

Return JSON: {"score": N, "reasoning": "...", "intent": "research|pain_point|competitor|question|general"}
```

### Discovery Pipeline Orchestrator

```python
# backend/app/services/reddit_discovery.py

async def discover_posts(project_id: str, db: AsyncSession) -> dict:
    """Full discovery pipeline for a project."""
    # 1. Load project config
    config = await get_reddit_config(project_id, db)
    brand_config = await get_brand_config(project_id, db)

    # 2. Search SERP for each keyword × subreddit combination
    all_posts = []
    for keyword in config.search_keywords:
        posts = await serpapi_client.search(
            keyword=keyword,
            subreddits=config.target_subreddits,
            time_range=config.discovery_settings.get("time_range", "24h"),
        )
        all_posts.extend(posts)

    # 3. Deduplicate by URL
    unique_posts = deduplicate_posts(all_posts)

    # 4. Filter out banned subreddits + marketing subreddits
    filtered = [p for p in unique_posts
                if p.subreddit.lower() not in config.banned_subreddits
                and p.subreddit.lower() not in MARKETING_SUBREDDITS]

    # 5. Keyword-based intent classification (fast, no API calls)
    for post in filtered:
        post.intent = classify_intent(post, config.competitors)

    # 6. Claude relevance scoring (batch, API calls)
    scored = await score_posts_with_claude(filtered, brand_config)

    # 7. Store results (upsert by project_id + url)
    stored = await store_discovered_posts(project_id, scored, db)

    return {"total_found": len(all_posts), "unique": len(unique_posts), "stored": len(stored)}
```

### API Endpoints (Slice 14b)

```
POST   /api/v1/projects/{project_id}/reddit/discover         → Trigger discovery (202 Accepted, BackgroundTask)
GET    /api/v1/projects/{project_id}/reddit/discover/status   → Poll discovery status
GET    /api/v1/projects/{project_id}/reddit/posts             → List posts (query: filter_status, intent, subreddit)
PATCH  /api/v1/projects/{project_id}/reddit/posts/{post_id}   → Update post (change filter_status)
```

### Frontend (Slice 14b)

Add to `/projects/[id]/reddit` page:
- "Discover Posts" button (triggers discovery, shows progress indicator)
- Posts list table below config form
- Columns: Subreddit, Title (linked), Intent badges, Relevance Score, Filter Status, Discovered
- Filter tabs: All | Relevant | Irrelevant | Pending
- Click row to expand/show snippet

---

## 5. Slice 14c: Comment Generation

**Goal:** Generate AI comments for discovered posts using brand context.

### Comment Generation Service

**File:** `backend/app/services/reddit_comment_generation.py`

This is the core IP to port from `execution/generate_comment_v2.py`. The key elements:

#### Comment Approach Types (Port from GENERIC_APPROACHES)

```python
# Promotional approaches (brand mention)
PROMOTIONAL_APPROACHES = {
    'Sandwich': 'Start with helpful advice, share your personal experience including what helped you, then add more tips.',
    'Story-Based': 'Share a story about a problem you faced, what you tried, what finally worked for you.',
    'Skeptic Converted': 'Mention you were skeptical at first, explain what changed your mind, share your honest experience.',
    'Comparison': 'Compare a few options you\'ve tried, share pros/cons of each, explain your preference.',
    'Quick Tip': 'Share a quick, actionable tip that worked for you.',
    'Problem-Solution': 'Describe the problem you had, explain how you solved it.',
    'Before/After': 'Share what things were like before and how they improved after.',
    'Question-Based': 'Start with a question, then share what worked for you.',
    'List-Based': 'Share a few options/tips in a casual list format.',
    'Technical Deep-Dive': 'Explain the details of what worked and why.',
}

# Non-promotional approaches (community building, no brand mention)
ORGANIC_APPROACHES = {
    'Simple Reaction': 'Give a brief, authentic reaction to the post.',
    'Appreciation': 'Express genuine appreciation for what they shared.',
    'Follow-Up Question': 'Ask a relevant follow-up question to understand better.',
    'Agree + Add': 'Agree with them and add a related insight.',
    'Relate Personal Experience': 'Share a brief related personal experience.',
    'Helpful Tip': 'Offer a specific, actionable tip.',
    'Empathy': 'Show understanding for their situation.',
    'Validation': 'Validate their feelings or experience.',
    'Encouragement': 'Offer supportive encouragement.',
    'Agree + Nuance': 'Agree but add some nuance or caveat.',
    'Suggest Alternative Approach': 'Suggest a different approach they might try.',
}
```

#### Prompt Builder (Port from _build_prompt, adapted for BrandConfig)

```python
async def build_comment_prompt(
    post: RedditPost,
    brand_config: BrandConfig,  # V2 BrandConfig, not Flask Client
    comment_instructions: str | None,
    approach: str,
    is_promotional: bool,
) -> str:
    """Build the LLM prompt for comment generation.

    Key difference from Flask: uses BrandConfig.v2_schema instead of persona profiles.
    """
    # Extract brand voice from BrandConfig v2_schema
    v2 = brand_config.v2_schema or {}
    voice = v2.get("voice_characteristics", {})
    vocabulary = v2.get("vocabulary", {})
    brand_foundation = v2.get("brand_foundation", {})

    # Build voice description from BrandConfig (replaces persona description)
    voice_desc = f"""You are a helpful Reddit user who:
- Communicates in a {voice.get('overall_tone', 'friendly and conversational')} way
- Uses vocabulary like: {', '.join((vocabulary.get('preferred_terms', []) or [])[:5])}
- Avoids words like: {', '.join((vocabulary.get('terms_to_avoid', []) or [])[:5])}"""

    if comment_instructions:
        voice_desc += f"\n- Special instructions: {comment_instructions}"

    # Post context
    post_context = f"""
REDDIT POST TO REPLY TO:
Subreddit: r/{post.subreddit}
Post Title: "{post.title}"
Context/Preview: {(post.snippet or 'No content available')[:500]}

IMPORTANT: You are writing a TOP-LEVEL REPLY to the original post (responding to the title/question).
The "Context/Preview" above may include text from other comments - ignore those and focus on the post title."""

    # Approach instructions
    approach_instruction = PROMOTIONAL_APPROACHES.get(approach) or ORGANIC_APPROACHES.get(approach) or 'Respond naturally and helpfully.'
    template_instructions = f"\nCOMMENT APPROACH: {approach_instruction}"

    # Brand section (promotional vs organic)
    if is_promotional:
        brand_name = brand_foundation.get("brand_name", v2.get("company_name", "the product"))
        brand_desc = brand_foundation.get("brand_description", "")
        key_features = brand_foundation.get("key_differentiators", [])

        brand_section = f"""
BRAND TO MENTION (naturally, as part of your experience):
- Brand: {brand_name}
- What it does: {brand_desc}
- Key features you might mention: {', '.join(key_features[:3]) if key_features else 'general helpfulness'}

IMPORTANT: The brand mention should feel organic - like you're sharing something that genuinely helped you, not advertising."""
    else:
        brand_section = """
NOTE: This is a NON-PROMOTIONAL comment. Do NOT mention any brands or products.
Focus purely on being helpful and engaging with the community."""

    # Final prompt
    prompt = f"""{voice_desc}

{post_context}

{template_instructions}
{brand_section}

LENGTH: approximately 50-150 words

CRITICAL FORMATTING RULES:
- Write ONLY the raw comment text - no headers, labels, or formatting markers
- Do NOT use **Bold Headers:** or any markdown section headers
- Write as a natural Reddit comment - just flowing text as a real user would type
- Respond to the POST TITLE, not to other comments in the thread
- Match the subreddit's culture and tone (r/{post.subreddit})

Write your Reddit comment now:"""

    return prompt
```

#### Generation Service

```python
async def generate_comment(
    post: RedditPost,
    project_id: str,
    db: AsyncSession,
) -> RedditComment:
    """Generate a single comment for a post."""
    # Load brand config + project reddit config
    brand_config = await get_brand_config(project_id, db)
    reddit_config = await get_reddit_config(project_id, db)

    # Select approach (random from appropriate set)
    is_promotional = True  # Default; ratio logic can be added later
    approach = random.choice(list(PROMOTIONAL_APPROACHES.keys()))

    # Build prompt
    prompt = await build_comment_prompt(
        post=post,
        brand_config=brand_config,
        comment_instructions=reddit_config.comment_instructions,
        approach=approach,
        is_promotional=is_promotional,
    )

    # Generate with Claude Haiku (fast + cheap, same as Flask app)
    response = await claude_client.create_message(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    comment_text = response.content[0].text.strip()

    # Clean up quote wrapping
    if comment_text.startswith('"') and comment_text.endswith('"'):
        comment_text = comment_text[1:-1]

    # Store
    comment = RedditComment(
        post_id=post.id,
        project_id=project_id,
        body=comment_text,
        original_body=comment_text,
        is_promotional=is_promotional,
        approach_type=approach,
        status=CommentStatus.DRAFT.value,
        generation_metadata={"model": "claude-haiku-4-5-20251001", "approach": approach},
    )
    db.add(comment)
    await db.flush()
    return comment


async def generate_batch(project_id: str, post_ids: list[str], db: AsyncSession) -> list:
    """Generate comments for multiple posts."""
    results = []
    for post_id in post_ids:
        post = await db.get(RedditPost, post_id)
        if post and post.filter_status == "relevant":
            comment = await generate_comment(post, project_id, db)
            results.append(comment)
    await db.commit()
    return results
```

### API Endpoints (Slice 14c)

```
POST   /api/v1/projects/{project_id}/reddit/posts/{post_id}/generate    → Generate single comment
POST   /api/v1/projects/{project_id}/reddit/generate-batch              → Generate for all relevant posts
GET    /api/v1/projects/{project_id}/reddit/comments                    → List comments (query: status)
```

### Frontend (Slice 14c)

Add to `/projects/[id]/reddit` page:
- "Generate Comments" button (batch generation for all relevant posts without comments)
- Per-post "Generate" button in posts table
- Comments section below posts with status indicators

---

## 6. Slice 14d: Comment Queue + Approval

**Goal:** Keyboard-driven comment review interface for Arly. This is the most-used screen — design for speed.

### API Endpoints (Slice 14d)

```
GET    /api/v1/reddit/comments                                          → Cross-project comment queue (query: status, project_id, niche)
PATCH  /api/v1/projects/{project_id}/reddit/comments/{id}               → Edit comment body
POST   /api/v1/projects/{project_id}/reddit/comments/{id}/approve       → Approve (optional edited body)
POST   /api/v1/projects/{project_id}/reddit/comments/{id}/reject        → Reject with reason
POST   /api/v1/projects/{project_id}/reddit/comments/bulk-approve       → Bulk approve
POST   /api/v1/projects/{project_id}/reddit/comments/bulk-reject        → Bulk reject
```

### Frontend Page: `/reddit/comments`

**Layout:** Split view
- **Left panel (60%):** Scrollable comment list
- **Right panel (40%):** Selected comment's post context (title, subreddit, snippet, URL link to Reddit)

**Comment card content:**
- Project name badge (color-coded)
- Subreddit tag
- Comment body text (truncated to 3 lines in list, full in detail)
- Approach type badge (Sandwich, Story-Based, etc.)
- Status badge (Draft / Approved / Rejected / Posted)
- Action buttons: Approve, Edit, Reject

**Status tabs at top:**
- Draft (default) | Approved | Rejected | Posted
- Count badges on each tab

**Filter bar:**
- Project dropdown (all projects or specific)
- Niche dropdown
- Search (text search in comment body)

**Keyboard shortcuts (critical for Arly's workflow):**
- `j` / `k` — Navigate up/down through comments
- `a` — Approve selected comment
- `e` — Enter inline edit mode
- `r` — Reject selected comment (opens reason picker)
- `x` — Toggle select for bulk action
- `Cmd+A` — Select all visible
- `Cmd+Enter` — (in edit mode) Save + Approve
- `Escape` — Cancel edit / deselect

**Inline editing:**
- Pressing `e` replaces the comment body with a textarea
- Textarea is pre-filled with current body
- `Cmd+Enter` saves the edit and approves
- `Escape` cancels the edit
- Show character count and word count while editing

**Reject flow:**
- Quick-pick reasons: "Off-topic", "Too promotional", "Doesn't match voice", "Low quality", "Other"
- Optional freeform text
- Comment slides out of the list on reject

**Bulk actions:**
- Select multiple with `x` or `Cmd+A`
- "Approve Selected" / "Reject Selected" buttons appear in a floating action bar
- Optimistic UI updates (TanStack Query mutation with `onMutate` for instant feedback)

**Animations:**
- Approved/rejected comments slide out of the current tab view
- Smooth transitions between comment selection

### Component Files

- `frontend/src/components/reddit/CommentQueue.tsx` — Main queue container with split view
- `frontend/src/components/reddit/CommentCard.tsx` — Individual comment card
- `frontend/src/components/reddit/CommentEditor.tsx` — Inline edit textarea
- `frontend/src/components/reddit/PostContextPanel.tsx` — Right panel post preview
- `frontend/src/components/reddit/RejectReasonPicker.tsx` — Reject reason selector
- `frontend/src/components/reddit/BulkActionBar.tsx` — Floating bulk action toolbar

---

## 7. Slice 14e: CrowdReply Integration

**Goal:** Approved comments auto-submit to CrowdReply, posting status tracked via webhooks.

### CrowdReply API Client

**File:** `backend/app/integrations/crowdreply.py`

Follow `backend/app/integrations/claude.py` pattern (async httpx, circuit breaker, logging).

**Base URL:** `https://crowdreply.io/api`
**Auth:** `x-api-key` header

```python
class CrowdReplyClient:
    """Async client for CrowdReply Reddit posting API."""

    async def create_comment_task(
        self,
        thread_url: str,
        content: str,
        project_id: str,
        initial_upvotes: int | None = None,
        schedule_at: datetime | None = None,
    ) -> dict:
        """Submit a comment task.

        CrowdReply API: POST /api/tasks
        Body:
        {
            "taskData": {
                "taskType": "comment",
                "type": "RedditCommentTask",
                "platform": "reddit",
                "project": project_id,
                "content": content,
                "threadUrl": thread_url
            },
            "initialUpvotesOrder": {  # optional
                "delivery": 2,        # upvotes per day
                "quantity": initial_upvotes,
            },
            "scheduleAt": schedule_at  # optional, ISO string
        }
        """

    async def create_post_task(
        self,
        subreddit_url: str,
        title: str,
        content: str,
        project_id: str,
        flair: str | None = None,
        initial_upvotes: int | None = None,
    ) -> dict:
        """Create a new Reddit post via CrowdReply.

        Body.taskData: taskType="post", type="RedditPostTask"
        """

    async def create_reply_task(
        self,
        thread_url: str,
        content: str,
        project_id: str,
        should_assign_op: bool = False,
    ) -> dict:
        """Reply to a comment via CrowdReply.

        Body.taskData: taskType="reply", type="RedditReplyTask"
        """

    async def send_upvotes(
        self,
        task_id: str,
        quantity: int = 5,
        upvotes_per_day: int = 2,
    ) -> dict:
        """Send upvotes to an existing task.

        POST /api/tasks/{task_id}/upvotes
        Comment tasks: upvotesPerInterval can only be 1 or 2, intervalUnit="day"
        """

    async def send_standalone_upvotes(
        self,
        url: str,
        vote_type: str = "comment-upvotes",  # comment-upvotes|comment-downvotes|post-upvotes|post-downvotes
        quantity: int = 5,
        upvotes_per_day: int = 2,
    ) -> dict:
        """Send upvotes/downvotes to any Reddit URL.

        POST /api/upvotes
        """

    async def get_task(self, task_id: str) -> dict:
        """GET /api/tasks/{task_id}"""

    async def get_tasks(self, filters: dict | None = None) -> dict:
        """GET /api/tasks with optional filters"""

    async def cancel_task(self, task_id: str) -> dict:
        """PUT /api/tasks/{task_id}/cancel-task"""

    async def edit_task(self, task_id: str, new_content: str) -> dict:
        """POST /api/tasks/{task_id}/create-edit-request"""

    async def get_balance(self) -> dict:
        """GET /api/billing/balance"""

    async def get_projects(self) -> dict:
        """GET /api/projects"""
```

### Posting Service

**File:** `backend/app/services/reddit_posting.py`

```python
async def submit_approved_comments(
    project_id: str,
    db: AsyncSession,
    upvotes_per_comment: int = 5,  # Arly's default: 5-10 upvotes
) -> list[CrowdReplyTask]:
    """Submit all approved comments for a project to CrowdReply."""
    # 1. Load approved comments that haven't been submitted
    comments = await get_comments_by_status(project_id, CommentStatus.APPROVED, db)

    # 2. Load CrowdReply project ID from config
    config = await get_reddit_config(project_id, db)
    cr_project_id = config.metadata.get("crowdreply_project_id") or settings.CROWDREPLY_PROJECT_ID

    tasks = []
    for comment in comments:
        post = await db.get(RedditPost, comment.post_id)

        # 3. Submit to CrowdReply
        response = await crowdreply_client.create_comment_task(
            thread_url=post.url,
            content=comment.body,
            project_id=cr_project_id,
            initial_upvotes=upvotes_per_comment,
        )

        # 4. Create tracking record
        task = CrowdReplyTask(
            comment_id=comment.id,
            task_type=CrowdReplyTaskType.COMMENT.value,
            status=CrowdReplyTaskStatus.SUBMITTED.value,
            target_url=post.url,
            content=comment.body,
            crowdreply_project_id=cr_project_id,
            request_payload=response,  # Store full request for debugging
            upvotes_requested=upvotes_per_comment,
            submitted_at=datetime.now(UTC),
        )
        db.add(task)

        # 5. Update comment status
        comment.status = CommentStatus.SUBMITTING.value
        tasks.append(task)

    await db.commit()
    return tasks


async def handle_crowdreply_webhook(payload: dict, db: AsyncSession) -> None:
    """Process CrowdReply webhook notifications.

    Webhook fires when task status changes to:
    - published: Comment is live on Reddit
    - mod-removed: Moderator removed it
    - main-comment-removed-deleted: Comment was deleted
    - thread-archived-locked: Thread is locked
    - cancelled: Task was cancelled
    - user-deleted: User deleted their comment

    Sample webhook body (from CrowdReply docs):
    {
        "_id": "taskId",
        "threadUrl": "...",
        "taskType": "comment",
        "status": "published",
        "content": "...",
        "clientPrice": 5,
        "taskSubmission": [{
            "submissionUrl": "https://www.reddit.com/r/.../comment/...",
            "screenshotProofUrl": "..."
        }],
        "publishedAt": "2025-07-12T18:55:01.533Z",
        "latestCommentDetails": {
            "subreddit": "...",
            "author": "...",
            "score": 1,
            "rank": 32
        }
    }
    """
    external_task_id = payload.get("_id")
    status = payload.get("status")

    # Find our tracking record
    task = await find_task_by_external_id(external_task_id, db)
    if not task:
        logger.warning(f"Webhook for unknown CrowdReply task: {external_task_id}")
        return

    # Update task
    task.status = _map_crowdreply_status(status)
    task.response_payload = payload
    task.price = payload.get("clientPrice")

    if status == "published":
        task.published_at = datetime.now(UTC)
        submission = (payload.get("taskSubmission") or [{}])[0]
        posted_url = submission.get("submissionUrl")

        # Update the comment too
        if task.comment_id:
            comment = await db.get(RedditComment, task.comment_id)
            if comment:
                comment.status = CommentStatus.POSTED.value
                comment.posted_url = posted_url
                comment.posted_at = datetime.now(UTC)

    elif status in ("mod-removed", "main-comment-removed-deleted"):
        if task.comment_id:
            comment = await db.get(RedditComment, task.comment_id)
            if comment:
                comment.status = CommentStatus.MOD_REMOVED.value

    elif status in ("cancelled", "user-deleted"):
        if task.comment_id:
            comment = await db.get(RedditComment, task.comment_id)
            if comment:
                comment.status = CommentStatus.FAILED.value

    await db.commit()
```

### API Endpoints (Slice 14e)

```
POST   /api/v1/projects/{project_id}/reddit/comments/submit   → Submit approved comments to CrowdReply
POST   /api/v1/reddit/webhooks/crowdreply                      → Webhook receiver (no auth check for now, add HMAC later)
GET    /api/v1/reddit/balance                                   → Get CrowdReply balance
```

### Frontend (Slice 14e)

- "Submit to CrowdReply" button on the Approved tab of the comment queue
- Posting status indicators on comment cards (Submitting → Posted with Reddit URL link, or Failed/Mod Removed)
- CrowdReply balance display in Reddit dashboard header
- Upvote count setting (default 5, configurable per-submission)

---

## 8. Slice 14f: Reddit Dashboard + Project Integration

**Goal:** Cross-project Reddit dashboard, project detail integration, stats.

### API Endpoints (Slice 14f)

```
GET    /api/v1/reddit/dashboard    → Global stats
GET    /api/v1/reddit/activity     → Recent activity feed
```

**Dashboard stats response:**
```json
{
    "pending_comments": 12,
    "approved_today": 8,
    "posted_today": 5,
    "posted_this_week": 23,
    "active_accounts": 15,
    "cooldown_accounts": 3,
    "total_posts_discovered": 145,
    "crowdreply_balance": 250.00,
    "projects_with_reddit": 4
}
```

### Frontend Pages

**`/reddit` — Dashboard:**
- Stat cards row: Pending Comments, Approved Today, Posted Today, Active Accounts, CrowdReply Balance
- Recent activity feed (last 20 actions: discoveries, approvals, postings)
- Quick action buttons: "Go to Queue", "Run Discovery (all projects)"
- Per-project breakdown table

**Header update:** Add "Reddit" link to `frontend/src/components/Header.tsx` navigation, between existing nav items.

**Project Detail update:** Add Reddit section card on `/projects/[id]` page showing:
- Reddit config status (configured / not configured)
- Quick stats (posts discovered, comments pending, comments posted)
- Link to `/projects/[id]/reddit`

### Component Files

- `frontend/src/components/reddit/RedditDashboard.tsx` — Dashboard stat cards + activity feed
- `frontend/src/components/reddit/ProjectRedditCard.tsx` — Reddit card for project detail page

---

## 9. Slice 14g: Seeded Conversations (Stretch)

**Goal:** Create orchestrated "seeded" conversations where Account A posts a question and Account B answers recommending the brand.

### Service

**File:** `backend/app/services/reddit_pipeline.py`

```python
async def orchestrate_seeded_conversation(
    project_id: str,
    subreddit: str,
    topic: str,
    db: AsyncSession,
) -> dict:
    """Create a seeded conversation.

    Steps:
    1. Generate a natural question post for the subreddit topic
    2. Submit question post to CrowdReply (Account A)
    3. Wait for posting confirmation (webhook)
    4. Generate a helpful reply that naturally mentions the brand
    5. Schedule reply 2-6 hours after the original post
    6. Submit reply to CrowdReply (Account B, with shouldAssignOP=false)
    7. Schedule 5-10 upvotes on both post and reply
    """
```

### API Endpoint

```
POST   /api/v1/projects/{project_id}/reddit/seeded-conversation
```

### Frontend

- Seeded conversation builder form:
  - Subreddit selector
  - Topic/question text (AI can generate, user can edit)
  - Timing delay for reply (2h, 4h, 6h, custom)
  - Account selection (optional)
  - Preview before submitting

---

## 10. What to Port vs. Rebuild

| Flask App File | Action | Port What | V2 Changes |
|---------------|--------|-----------|------------|
| `execution/scrape_serp.py` | **Port query logic** | SERP API query construction (`site:reddit.com "{keyword}"`), time filter mapping (`qdr:d/w/m`), Reddit URL parsing (`/r/SUBREDDIT/comments/`), deduplication by URL | Use `httpx.AsyncClient` instead of `requests`. Follow V2 integration client pattern. Add circuit breaker. |
| `execution/filter_posts.py` | **Port keyword lists + classification** | All 4 keyword lists (RESEARCH_INTENT, PAIN_POINT, QUESTION_PATTERNS, PROMOTIONAL), subreddit exclusion lists, `classify_intent()` scoring logic | Replace OpenAI `gpt-4o-mini` with Claude Haiku for AI evaluation. Switch from sync to async. |
| `execution/generate_comment_v2.py` | **Port prompt structure + approaches** | All 20+ GENERIC_APPROACHES (Sandwich, Story-Based, Skeptic Converted, etc.), `_build_prompt()` structure (post context → approach → brand section → formatting rules), quote-wrapping cleanup | Replace persona description with BrandConfig v2_schema voice. Remove template_selector and post_persona_matcher dependencies. Use Claude Haiku (already used in Flask). |
| `execution/crowdreply_service.py` | **Port API calls** | HTTP request construction for create_comment_task, create_post_task, upvotes | Wrap in V2 integration pattern (async httpx, circuit breaker). Add all CrowdReply endpoints from API docs. |
| `execution/account_service.py` | **Port cooldown logic** | Cooldown timestamp checking, account availability filtering | Simplify: just check `cooldown_until > now()` and `status = 'active'`. No persona matching. |
| `crowd reply API docs.md` | **Reference only** | Complete CrowdReply API spec | Keep as reference in `.tmp/` for implementation. |
| `webapp/models.py` | **Do NOT port** | N/A | Build fresh V2 models following `blog.py` pattern (UUID PKs, Mapped types, JSONB). |
| All Flask routes, templates, JS | **Do NOT port** | N/A | Build fresh with FastAPI + Next.js. |
| Persona system (persona_routes, generate_persona, etc.) | **Do NOT port** | N/A | Skipped in V1. BrandConfig + comment_instructions replaces persona voice. |
| Template system (template_selector.py) | **Do NOT port** | N/A | Replaced by random approach selection from GENERIC_APPROACHES dict. |
| Asana integration | **Do NOT port** | N/A | Not needed in V2. |
| Google Sheets sync | **Do NOT port** | N/A | Not needed in V2. |

---

## 11. Environment Variables

Add to `.env` and Railway:

```bash
# SERP API (for Reddit post discovery)
SERPAPI_KEY=...

# CrowdReply (for Reddit comment posting)
CROWDREPLY_API_KEY=...
CROWDREPLY_PROJECT_ID=...          # Default CrowdReply project ID
CROWDREPLY_WEBHOOK_SECRET=...      # For verifying webhook signatures (optional initially)
CROWDREPLY_BASE_URL=https://crowdreply.io/api  # Can override for testing
```

Add to `backend/app/core/config.py` Settings class:

```python
SERPAPI_KEY: str = ""
CROWDREPLY_API_KEY: str = ""
CROWDREPLY_PROJECT_ID: str = ""
CROWDREPLY_WEBHOOK_SECRET: str = ""
CROWDREPLY_BASE_URL: str = "https://crowdreply.io/api"
```

---

## 12. File Structure Summary

```
backend/
├── app/
│   ├── models/
│   │   ├── reddit_account.py          # 14a - RedditAccount, WarmupStage, AccountStatus
│   │   ├── reddit_config.py           # 14a - RedditProjectConfig
│   │   ├── reddit_post.py             # 14a - RedditPost, PostFilterStatus, PostIntent
│   │   ├── reddit_comment.py          # 14a - RedditComment, CommentStatus
│   │   └── crowdreply_task.py         # 14a - CrowdReplyTask, CrowdReplyTaskType/Status
│   ├── schemas/
│   │   └── reddit.py                  # 14a - All Pydantic v2 schemas
│   ├── services/
│   │   ├── reddit_discovery.py        # 14b - SERP search + Claude filtering pipeline
│   │   ├── reddit_comment_generation.py  # 14c - Comment prompt builder + generation
│   │   ├── reddit_posting.py          # 14e - CrowdReply submission + webhook handler
│   │   ├── reddit_account_pool.py     # 14a - Account availability, cooldown management
│   │   └── reddit_pipeline.py         # 14g - Seeded conversation orchestration
│   ├── integrations/
│   │   ├── serpapi.py                 # 14b - SERP API async client
│   │   └── crowdreply.py             # 14e - CrowdReply async client
│   └── api/v1/
│       └── reddit.py                  # 14a-14f - All Reddit API endpoints (grows per slice)
├── alembic/versions/
│   └── 00XX_create_reddit_tables.py   # 14a - Single migration for all 5 tables

frontend/src/
├── app/
│   ├── reddit/
│   │   ├── layout.tsx                 # 14f - Reddit section layout
│   │   ├── page.tsx                   # 14f - Dashboard
│   │   ├── comments/page.tsx          # 14d - Cross-project comment queue
│   │   └── accounts/page.tsx          # 14a - Account pool management
│   └── projects/[id]/reddit/
│       └── page.tsx                   # 14a - Project Reddit config + posts + comments
├── lib/api/
│   └── reddit.ts                      # 14a - API client functions
├── hooks/
│   └── useReddit.ts                   # 14a - TanStack Query hooks
└── components/
    └── reddit/
        ├── CommentQueue.tsx           # 14d - Main queue with split view
        ├── CommentCard.tsx            # 14d - Individual comment card
        ├── CommentEditor.tsx          # 14d - Inline edit textarea
        ├── PostContextPanel.tsx       # 14d - Right panel post preview
        ├── RejectReasonPicker.tsx     # 14d - Reject reason selector
        ├── BulkActionBar.tsx          # 14d - Floating bulk action toolbar
        ├── AccountTable.tsx           # 14a - Account pool table
        ├── RedditDashboard.tsx        # 14f - Dashboard stat cards
        └── ProjectRedditCard.tsx      # 14f - Project detail Reddit card
```

---

## 13. Verification Plan

### After Each Slice

1. **Backend:** Run `pytest` — all new tests pass, existing tests unaffected
2. **Migration:** `alembic upgrade head` succeeds on Neon dev database
3. **API:** Manual curl/httpie testing of all new endpoints
4. **Frontend:** `npm run build` succeeds, pages render correctly
5. **Lint:** `ruff check` and `mypy` pass

### End-to-End Verification (After All Slices)

Full flow test:
1. Create a project with brand config
2. Configure Reddit settings (keywords, subreddits, niche)
3. Trigger discovery → posts appear
4. Generate comments → draft comments created
5. Open comment queue → review, edit, approve
6. Submit to CrowdReply → tasks created, status tracked
7. Simulate webhook → comment status updates to "posted"
8. Check dashboard → stats reflect activity

### CrowdReply Integration Test

Since CrowdReply is a paid service ($5/comment), use these strategies:
- Mock the CrowdReply client for unit/integration tests
- Create a `CROWDREPLY_DRY_RUN` env var that logs requests instead of sending
- Test webhook handler with sample payloads from API docs
- Do one real end-to-end test with a single comment before going live

---

*Source material: Reddit Scraper App (Flask), CrowdReply API docs, Arly meeting transcript (2026-02-16)*
*Plan created: 2026-02-16*
