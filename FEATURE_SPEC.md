# Feature Specification: Client Onboarding V2

> This is the source of truth for what we're building.

---

## App Structure Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        LOGIN                                 │
│  - Google sign-in                                           │
│  - Username/password                                        │
│  (NOT MVP - can be basic auth or skipped initially)         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    MAIN DASHBOARD                            │
│                                                             │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │ Client 1│  │ Client 2│  │ Client 3│  │ Client 4│        │
│  │ metrics │  │ metrics │  │ metrics │  │ metrics │        │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │
│                                                             │
│              [ + Create New Project ]                       │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│               CLIENT PROJECT VIEW                            │
│  (After clicking into a client)                             │
│                                                             │
│  - Brand Config (view/edit)                                 │
│  - Onboarding Tasks:                                        │
│    ├── Collection Page Copy (MVP)                           │
│    ├── Schema Markup (Later)                                │
│    └── Template Code (Later)                                │
└─────────────────────────────────────────────────────────────┘
```

---

## Feature 1: Authentication (NOT MVP)

**Priority:** Low (defer until core features work)

**User can:**
- Sign in with Google OAuth
- Create account with username/password
- Log in with username/password

**For MVP:** Use basic auth or hardcoded credentials, or skip entirely (local dev mode).

---

## Feature 2: Main Dashboard

**Priority:** MVP

**User sees:**
- Grid of client project cards
- Each card shows:
  - Client/project name
  - Key metrics (TBD - pages crawled, content generated, etc.)
  - Click to enter project
- "Create New Project" button

**User can:**
- View all their client projects at a glance
- Click into any project
- Create a new project

---

## Feature 3: Create New Project (Client Onboarding Setup)

**Priority:** MVP

**Flow:**
```
Step 1: Project Details
├── Site URL (required)
├── Project name (required)
├── Upload brand docs/guidelines (optional, multiple files)
└── Additional info text field (optional)
                    ↓
Step 2: Click "Start"
                    ↓
Step 3: System generates Brand Configuration
├── Uses brand config skill/bible from directives
├── Processes uploaded docs
├── Creates structured brand config
└── Stores config for this project
                    ↓
Project Created → Redirect to Project View
```

**Brand Configuration includes:**
- Brand voice and tone
- Key product facts
- Terminology/vocabulary
- Things to avoid
- Example content (if provided)

**Data model:**
```
Project
├── id
├── name
├── site_url
├── brand_config (JSON)
├── uploaded_docs (file references)
├── additional_info (text)
├── created_at
└── status
```

---

## Feature 4: Collection Page Copy Workflow (MVP Core)

**Priority:** MVP - This is the main workflow

### Step 4.1: Upload URLs to Crawl

**User can:**
- Paste a list of URLs (one per line)
- Or upload a CSV with URLs
- See the list of URLs to be processed
- Remove URLs before starting

**System does:**
- Validate URLs (proper format, accessible)
- Show count of URLs to process

---

### Step 4.2: Crawl Pages + Generate Labels

**System does:**
- Crawl each URL
- Extract:
  - Current page title
  - Current meta description
  - Current page content/copy
  - H1, H2, H3 structure
  - Product information (if applicable)
  - Any existing keywords/themes
- **Generate page labels/categories** (for internal linking):
  - AI analyzes content to assign 2-5 semantic labels per page
  - Labels describe what the page is about (e.g., "running", "women", "trail", "lightweight")
  - Labels are used later to determine which pages are related
- Store crawl results + labels per page

**User sees:**
- Progress indicator (X of Y pages crawled)
- Success/failure status per URL
- Generated labels per page (can edit if needed)
- Can proceed when crawling complete

**Why labels matter:** Labels power the internal linking algorithm. Pages with overlapping labels are considered related and will link to each other.

---

### Step 4.3: Primary Keyword Generation

**System does:**
- For each crawled page:
  - Analyze content to identify topic/theme
  - Generate primary keyword candidate (using crawl data + AI analysis)
- Store primary keyword per page

**User sees:**
- List of pages with suggested primary keywords
- Current page title for context

**Note:** Secondary keywords are NOT generated here. POP provides LSI terms (superior alternative) in the Content Brief during generation.

---

### Step 4.4: Primary Keyword Approval + Priority Marking (Human in the Loop)

**User can:**
- View each page's suggested primary keyword
- Edit primary keyword
- **Mark pages as "priority"** (these get linked to more often)
- **Edit page labels** (affects internal linking relationships)
- Approve keywords for each page
- Bulk approve all (if confident)

**User sees:**
- Page URL
- Current page title
- Suggested primary keyword
- Page labels (editable)
- Priority toggle (star/flag)
- Approve/Edit buttons

**Priority pages:** When marked as priority, other related pages will preferentially link to these pages. Use for:
- Main category pages (e.g., "Running Shoes" over "Women's Trail Running Shoes")
- High-value commercial pages
- Pages you want to rank first

**Note:** No secondary keyword approval needed. POP's LSI terms (provided during content generation) replace the old secondary keyword workflow.

**Must approve before proceeding to internal link mapping.**

---

### Step 4.5: Internal Link Mapping

**Purpose:** Determine which pages should link to which other pages, using a deterministic algorithm (not just "let AI decide").

**System does:**
```
1. Build Relationship Graph
├── Compare labels across all pages
├── Calculate "relatedness score" based on label overlap
├── Pages with 2+ shared labels = related
└── Store relationships in link graph

2. Apply Priority Weighting
├── Priority pages get higher "link magnetism"
├── When choosing which related page to link to, prefer priority pages
└── Ensures important pages accumulate more internal links

3. Generate Link Recommendations per Page
├── For each page, select 3-6 internal links
├── Mix of: highly related (2+ label overlap) + priority pages
├── Avoid linking to self
├── Avoid duplicate links within same content piece
└── Store as "recommended_links" per page

4. Create Link Anchor Text Suggestions
├── Use target page's primary keyword as anchor (or variation)
├── Vary anchor text across pages (don't over-optimize)
└── Store anchor suggestions with each link
```

**User sees:**
- Link map visualization (optional - shows connections between pages)
- Per-page: list of recommended internal links with anchor text
- Can add/remove links manually
- Can adjust which pages are priority

**Internal Linking Rules (to research/refine):**
- Follow Kyle Roof's silo structure principles
- Related pages link to each other (horizontal)
- Sub-category pages link UP to main category (vertical)
- Priority pages receive more inbound links
- Anchor text should be varied but relevant
- 3-6 internal links per page (configurable)

**Research needed:** Study Kyle Roof's internal linking strategies and silo structures to refine this algorithm before implementation.

---

### Step 4.6: Content Generation

**Trigger:** Keywords approved AND internal link map generated

**System does (for each page, in parallel where possible):**

```
Phase 1: Get POP Content Brief
├── Send approved primary keyword + target URL to POP API
├── POP returns comprehensive brief:
│   ├── lsi_terms (replaces secondary keywords - better quality)
│   ├── related_questions (replaces PAA - direct from Google)
│   ├── word_count_target, word_count_min, word_count_max
│   ├── heading_targets (H1, H2, H3 counts)
│   ├── keyword_targets (placement recommendations)
│   └── competitors (top ranking pages analysis)
├── Load brand config
├── Load internal link recommendations for this page
└── Store Content Brief in database

Phase 2: Write
├── Generate content using Claude
│   ├── Meta description
│   ├── Page title
│   ├── Top description (short intro)
│   ├── Bottom description (longer copy, with FAQ from related_questions)
├── Follow brand voice
├── Hit POP brief targets
├── Include LSI terms naturally
├── Answer related questions (FAQ section)
├── **Insert internal links using link map:**
│   ├── Use recommended anchor text from link map
│   ├── Place links naturally within content
│   ├── Distribute across content (not clustered)
│   └── Include 3-6 internal links per page
└── Verify all recommended links are included

Phase 3: Check
├── AI trope detection
│   ├── Banned words/phrases
│   ├── Em dashes
│   ├── Triplet patterns
│   ├── Rhetorical questions
│   └── Score (must pass threshold)
├── **Internal link verification**
│   ├── All recommended links present?
│   ├── Anchor text matches recommendations?
│   └── Links properly formatted?
├── POP scoring API call
│   ├── Send content URL + keyword to POP
│   ├── Get page_score and recommendations
│   └── Iterate until score meets threshold (default 70)
└── Flag any issues
```

**User sees:**
- Progress (X of Y pages generated)
- Status per page (generating, checking, complete, needs review)
- POP score for each page
- Internal links included per page

---

### Step 4.7: Content Review & Editing

**User can:**
- Click into any page to view/edit content
- See all content fields:
  - Meta description
  - Page title
  - Top description
  - Bottom description (longer copy)

**For the bottom description (longer copy):**
- Toggle between **Rendered HTML** and **HTML source** view
- **Keyword highlighting:**
  - Primary keyword highlighted (one color)
  - LSI terms from POP brief highlighted (another color)
  - Related questions/FAQ terms highlighted (third color)
- Easy visual QA of keyword and term placement
- POP score displayed with breakdown

**User can:**
- Edit any field inline
- Re-run checks after editing
- Approve content for export

---

### Step 4.8: Export to Matrixify

**User can:**
- Select pages to export (or all approved)
- Click "Export for Matrixify"

**System does:**
- Generate Matrixify-compatible CSV/Excel format
- Include all required Shopify fields:
  - Handle (from URL)
  - Title
  - Body HTML
  - Meta description
  - (other Shopify fields as needed)
- Download file

**User gets:**
- File ready to upload to Shopify via Matrixify

---

---

## Feature 5: Keyword Cluster Creation (MVP)

**Priority:** MVP — Second core workflow

### Overview

Similar to onboarding, but instead of crawling existing pages, you start with a **seed keyword** and build a cluster of new pages around it.

### Client Project Dashboard Structure

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENT PROJECT VIEW                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ONBOARDING (Existing Pages)                          │   │
│  │ Optimize existing collection pages                   │   │
│  │ [View Progress] [Continue]                           │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ NEW CONTENT (Keyword Clusters)                       │   │
│  │ Build new collection page clusters                   │   │
│  │                                                       │   │
│  │ ┌───────────┐ ┌───────────┐ ┌───────────┐           │   │
│  │ │ Cluster 1 │ │ Cluster 2 │ │ + New     │           │   │
│  │ │ 5 pages   │ │ 3 pending │ │ Cluster   │           │   │
│  │ └───────────┘ └───────────┘ └───────────┘           │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Step 5.1: Create New Cluster

**User provides:**
- Seed primary keyword (e.g., "running shoes")
- Cluster name (optional, defaults to seed keyword)

**System does:**
- Calls POP API with seed keyword
- Gets suggestions for related keywords/pages to build
- Returns list of potential cluster pages

---

### Step 5.2: Keyword Approval (Same as Onboarding)

**User can:**
- View suggested keywords for the cluster
- Edit/add/remove keywords
- Approve keywords to proceed

**Same interface as onboarding keyword approval.**

**Note:** In clusters, the seed keyword page is automatically marked as the "parent" (priority) page.

---

### Step 5.3: Internal Link Structure (Cluster-Specific)

**Purpose:** Define hierarchical linking structure for the cluster. Different from onboarding because clusters have a clear parent-child structure.

**System does:**
```
1. Define Hierarchy
├── Seed keyword page = PARENT (hub page)
├── All other pages = CHILDREN (spoke pages)
└── Store hierarchy

2. Generate Link Rules
├── Every CHILD page links UP to PARENT (mandatory)
├── PARENT page links to all CHILDREN
├── CHILDREN link to 2-3 sibling CHILDREN (related by keyword similarity)
└── Store as link requirements per page

3. Create Anchor Text
├── Links TO parent: Use parent's primary keyword
├── Links TO siblings: Use sibling's primary keyword (varied)
├── Links FROM parent: Use child's primary keyword or descriptive text
└── Store anchor suggestions
```

**Linking Pattern:**
```
                    ┌─────────────────┐
                    │   PARENT PAGE   │
                    │ (seed keyword)  │
                    └────────┬────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
    ┌──────────┐      ┌──────────┐      ┌──────────┐
    │  CHILD 1 │◄────►│  CHILD 2 │◄────►│  CHILD 3 │
    │          │      │          │      │          │
    └──────────┘      └──────────┘      └──────────┘

    ▲ = links up to parent
    ◄► = sibling links (2-3 per page)
```

**User sees:**
- Visual cluster structure (parent + children)
- Link assignments per page
- Can adjust sibling links if needed

**Why this differs from onboarding:**
- Onboarding: Flat structure, links based on label similarity
- Clusters: Hierarchical structure, links based on parent-child relationship

---

### Step 5.4: Content Generation (REUSES Onboarding Pipeline)

**System does (for each approved keyword):**

```
Same pipeline as onboarding:

1. Get POP brief for keyword
2. Research (POP brief + brand config)
3. Write content (Claude)
4. Check quality (AI tropes + POP compliance)
```

**This is the SAME code as onboarding** — shared content generation pipeline.

---

### Step 5.5: Content Review & Editing (REUSES Onboarding)

**Same interface as onboarding:**
- View/edit page title, meta description, top description, bottom description
- HTML/rendered toggle for bottom description
- Keyword highlighting
- Approve for export

---

### Step 5.6: Export to Matrixify (REUSES Onboarding)

**Same export as onboarding** — generates Matrixify-compatible file.

---

### Shared Pipelines Summary

| Component | Onboarding | Clusters | Shared? |
|-----------|------------|----------|---------|
| URL Upload | ✅ | ❌ | No |
| Crawling + Label Generation | ✅ | ❌ | No |
| Seed Keyword Input | ❌ | ✅ | No |
| POP Cluster Suggestions | ❌ | ✅ | No |
| Primary Keyword Approval UI | ✅ | ✅ | **YES** |
| **Internal Link Mapping** | ✅ (label-based) | ✅ (hierarchical) | **NO** (different logic) |
| POP Content Brief Fetching | ✅ | ✅ | **YES** |
| Content Generation (uses LSI + links) | ✅ | ✅ | **YES** |
| Quality Checks (AI tropes + POP score) | ✅ | ✅ | **YES** |
| Content Review/Edit | ✅ | ✅ | **YES** |
| Export to Matrixify | ✅ | ✅ | **YES** |

**6 shared components** — build once, use in both workflows.

**Note:** Secondary keywords and PAA are NOT separate steps. POP's Content Brief provides LSI terms and related questions in a single call, which are used during content generation.

**Note:** Internal linking uses DIFFERENT logic per workflow:
- **Onboarding:** Label-based relatedness + priority weighting (flat structure)
- **Clusters:** Parent-child hierarchy + sibling links (silo structure)

---

## Feature 6: Page Registry (MVP)

**Priority:** MVP — Enables cross-workflow internal linking

### Purpose

A project-wide registry of ALL collection pages (from both onboarding and clusters) that:
1. Tracks all pages with their labels and keywords
2. Provides the pool for internal linking across workflows
3. Generates URL slugs for new cluster pages

### Data Model

```python
PageRegistry:
  id: UUID
  project_id: UUID
  url: str                      # Full URL (onboarding) or suggested slug (clusters)
  primary_keyword: str
  labels: JSON                  # ["running", "women", "trail"]
  source: str                   # "onboarding" | "cluster"
  cluster_id: UUID | None       # If from a cluster, which one
  status: str                   # "draft" | "approved" | "published"
  is_priority: bool             # Priority pages get more inbound links
  created_at: datetime
  published_at: datetime | None
```

### How Pages Enter the Registry

**Onboarding flow:**
```
Crawl pages → Pages added to registry
            → source = "onboarding"
            → status = "draft"
            → URL from crawl
            → Labels from label generation step

After export → status = "published"
```

**Cluster flow:**
```
Create cluster → Generate slug suggestions for each page
               → Pages added to registry
               → source = "cluster"
               → status = "draft"
               → URL = suggested slug (editable)
               → Labels inherited from cluster + page-specific

After export → status = "published"
```

### Slug Generation for Cluster Pages

When creating cluster pages, system suggests URL slugs:

```
Primary keyword: "trail running shoes for women"
                        ↓
Suggested slug: /collections/trail-running-shoes-women
                        ↓
User can edit before finalizing
```

**Slug rules:**
- Lowercase
- Spaces → hyphens
- Remove special characters
- Max 50 characters
- Must be unique within project

### Internal Linking Uses the Registry

When generating content for ANY page:
1. Query registry for all pages in project where `status != "draft"`
2. Apply linking algorithm (label-based or hierarchical)
3. Can link to ANY page in registry (onboarding OR cluster)

This means:
- Cluster pages can link to onboarding pages
- Onboarding pages can link to older cluster pages
- New clusters can link to pages from previous clusters

### Registry View in UI

```
┌─────────────────────────────────────────────────────────────────────┐
│  Page Registry                              [ + Add Page Manually ] │
├─────────────────────────────────────────────────────────────────────┤
│  Filter: [All ▼] [Onboarding ▼] [Clusters ▼] [Published ▼]         │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ URL/Slug                    │ Keyword        │ Labels  │ Status│ │
│  ├────────────────────────────────────────────────────────────────┤ │
│  │ /collections/running-shoes  │ running shoes  │ 3 tags  │ ✓ Pub │ │
│  │ /collections/hiking-boots   │ hiking boots   │ 4 tags  │ ✓ Pub │ │
│  │ /collections/trail-women    │ trail running..│ 5 tags  │ Draft │ │
│  │ ...                                                             │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  Total: 24 pages (18 published, 6 draft)                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Features for Later (NOT MVP)

### Feature 7: SEMrush Integration (Future)
- When a new cluster is created, auto-import keywords to SEMrush project
- Tag keywords by cluster name
- Track rankings over time

### Feature 8: Schema Markup Generation
- Generate JSON-LD schema for collection pages
- Product schema, BreadcrumbList, CollectionPage, etc.
- Export for implementation

### Feature 9: Template Code Updates
- Analyze current Shopify template code
- Suggest/generate template improvements
- Export code snippets

---

## Data Flow Summary

```
Create Project
     ↓
Upload URLs → Crawl + Generate Labels → Generate Primary Keywords
                                                   ↓
                                        Human Approves Keywords
                                        + Marks Priority Pages
                                                   ↓
                                        Internal Link Mapping
                                        (label-based relatedness
                                        + priority weighting)
                                                   ↓
                    ┌──────────────────────────────┼──────────────────────────────┐
                    ↓                              ↓                              ↓
              POP Content Brief              Brand Config                  Link Map
              (LSI terms, related            (voice, tone,            (which pages link
              questions, targets)            terminology)              to which, anchors)
                    ↓                              ↓                              ↓
                    └──────────────────────────────┼──────────────────────────────┘
                                                   ↓
                                            Generate Content
                                            (LSI terms + FAQ +
                                            internal links from map)
                                                   ↓
                                             Check Quality
                                            (AI tropes + POP +
                                            link verification)
                                                   ↓
                                            Human Review/Edit
                                                   ↓
                                            Export (Matrixify)
```

### Why This Flow is Simpler

| Old Flow | New Flow |
|----------|----------|
| Generate primary keyword | Generate primary keyword |
| Generate secondary keywords | ❌ Removed |
| Fetch PAA questions (DataForSEO) | ❌ Removed |
| Categorize PAA (Claude LLM) | ❌ Removed |
| Analyze PAA for content angle | ❌ Removed |
| Human approves keywords + PAA | Human approves primary keyword only |
| Fetch POP brief | Fetch POP brief (includes LSI + related questions) |

**Benefits:**
- Fewer API costs (no DataForSEO, no extra Claude calls)
- Faster workflow (fewer async steps)
- Better data quality (POP's LSI terms based on actual SERP analysis)
- Less code to maintain

---

## Vertical Slices (Build Order)

Based on dependencies and the shared component architecture:

### Slice 1: Project Foundation
- Dashboard (list projects)
- Create project (basic - name, URL only)
- Project detail view (with Onboarding + New Content sections)
- **Test:** Can create and view projects

### Slice 2: Brand Configuration
- Upload docs in project creation
- Brand config generation (using existing skill/bible)
- View/edit brand config in project
- **Test:** Can generate and view brand config

### Slice 3: URL Upload + Crawling (Onboarding-specific)
- Upload URLs interface
- Crawling pipeline
- View crawl results
- **Test:** Can upload URLs and see crawled data

### Slice 4: Primary Keyword Generation + Approval (SHARED)
- Generate primary keyword candidates (from crawled pages OR seed keyword)
- Primary keyword approval interface (reusable component)
- Edit primary keyword
- Mark pages as priority
- Edit page labels
- **Test:** Can see primary keyword, edit, approve, set priority
- **Note:** No secondary keywords here — POP provides LSI terms during content generation

### Slice 5: Internal Link Mapping (WORKFLOW-SPECIFIC)
- **Onboarding:** Label-based link algorithm
  - Calculate relatedness from label overlap
  - Weight priority pages higher
  - Generate 3-6 links per page with anchor text
- **Clusters:** Hierarchical link structure
  - Parent-child relationships
  - Sibling links between children
  - Mandatory links up to parent
- Link map visualization (optional)
- Manual link adjustment UI
- **Test:** Can see link map, adjust links, verify correct structure
- **Research:** Study Kyle Roof's silo/internal linking methodology before implementing

### Slice 6: Content Generation Pipeline (SHARED)
- POP Content Brief fetching (returns LSI terms, related questions, targets)
- Content writing (Claude) using brief data
- Quality checks (AI tropes + POP scoring API)
- **Test:** Can generate content that passes checks and achieves POP score ≥70
- **Architecture:** This is a shared service, not tied to onboarding
- **Reference:** See `backend/PLAN-remove-secondary-keywords-and-paa.md` for detailed flow

### Slice 7: Content Review + Editing (SHARED)
- Content detail view
- HTML/rendered toggle
- Keyword highlighting
- Inline editing
- **Test:** Can review, edit, re-check content

### Slice 8: Export (SHARED)
- Matrixify export format
- Download functionality
- **Test:** Can export and file works in Matrixify

### Slice 9: Keyword Cluster Creation (Clusters-specific)
- Seed keyword input UI
- POP API for cluster suggestions
- Wire into shared components (approval, generation, review, export)
- **Test:** Can create cluster, generate content, export

### Slice 10: Polish
- Dashboard metrics (clusters built/pending, content pending)
- Progress indicators
- Error handling
- Edge cases

---

## Architecture Note: Shared Components

Build these as **standalone, reusable services/components**:

```
backend/app/services/
├── content_generation.py    # SHARED - used by both workflows
├── content_quality.py       # SHARED - AI trope checks
├── pop_integration.py       # SHARED - Content Brief + Scoring API
├── matrixify_export.py      # SHARED - export formatting
├── internal_linking.py      # SHARED - base linking utilities
├── onboarding_links.py      # Onboarding-only - label-based link algorithm
├── cluster_links.py         # Clusters-only - hierarchical link structure
├── crawling.py              # Onboarding-only
└── cluster_suggestions.py   # Clusters-only

backend/app/integrations/
└── pop.py                   # POP API client (Content Brief + Scoring)

frontend/src/components/
├── KeywordApproval/         # SHARED - primary keyword approval
├── ContentEditor/           # SHARED
├── ContentReview/           # SHARED - includes POP score display
├── LinkMapViewer/           # SHARED - visualize internal links
├── ExportButton/            # SHARED
├── UrlUploader/             # Onboarding-only
└── SeedKeywordInput/        # Clusters-only
```

This way, when we build Slice 6-8 for onboarding, they automatically work for clusters in Slice 9.

### Files to Remove (from old flow)

Per `backend/PLAN-remove-secondary-keywords-and-paa.md`:
- `secondary_keywords.py` — replaced by POP LSI terms
- `paa_enrichment.py` — replaced by POP related questions
- `paa_categorization.py` — no longer needed
- `paa_analysis.py` — no longer needed
- `paa_cache.py` — no longer needed

---

## Resolved Questions

| Question | Answer |
|----------|--------|
| Dashboard metrics | Clusters built/pending, content generations pending |
| Keyword sources | **POP only** — keep it simple |
| Content fields | Page title, meta description, top description, bottom description |
| Matrixify format | User will provide example file |
| Secondary keywords | **Removed** — POP's LSI terms replace them (better quality, SERP-based) |
| PAA questions | **Removed** — POP's related_questions replace them (direct from Google, no DataForSEO costs) |
| Keyword approval steps | **1 step only** — approve primary keyword, then POP provides everything else |

---

## Research Needed: Internal Linking Strategy

### Kyle Roof's Silo Structure

Before implementing the internal linking algorithm (Slice 5), research Kyle Roof's approach to:
- **Silo structure** — How to organize pages into topical silos
- **Internal link patterns** — Which pages should link to which
- **Anchor text strategy** — How to vary anchors without over-optimization
- **Link juice flow** — How PageRank flows through internal links
- **Priority pages** — How to identify and boost important pages

### Resources to Study
- Kyle Roof's YouTube channel / podcast appearances on internal linking
- PageOptimizer Pro documentation on silo structure
- Case studies on internal linking impact on rankings

### Questions to Answer
1. How many internal links per page is optimal?
2. Should every page link back to the homepage/main category?
3. How do you handle pages that don't fit neatly into a silo?
4. What's the right balance between related links vs. priority links?
5. How often should anchor text match the target's primary keyword exactly?

### Algorithm Requirements
Based on research, define:
```
INPUTS:
- Page labels (onboarding) or hierarchy (clusters)
- Priority flags
- Primary keywords (for anchor text)

OUTPUTS:
- Per-page list of internal links
- Anchor text for each link
- Link placement suggestions (where in content)

CONSTRAINTS:
- Min/max links per page (configurable, default 3-6)
- No duplicate links within a page
- No self-links
- Priority pages get more inbound links
- Anchor text variation rules
```

### Implementation Notes
- Build as a deterministic algorithm, not AI-decided
- User should be able to see and override link suggestions
- Store link map in database for content generation to use
- Verify links are present in generated content during quality check

---

*This spec will be updated as we clarify details and build features.*
