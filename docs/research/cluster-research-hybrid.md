# Hybrid Pipeline Approach: Keyword Cluster Creation

## Research Report for Feature 5 (Keyword Cluster Creation)

---

## 1. Executive Summary

The hybrid approach combines **LLM-driven candidate generation** with **DataForSEO volume enrichment** and **POP content optimization data** in a multi-stage pipeline. This mirrors how professional SEO tools (Ahrefs, SEMrush, Surfer) work -- they combine multiple data signals (SERP analysis, search volume, semantic relevance, search intent) rather than relying on a single source.

**Recommended pipeline:** LLM generates broad candidates -> DataForSEO enriches with real volume/CPC data -> LLM filters and scores for relevance -> POP validates with SERP-based content briefs.

This approach maximizes quality while keeping API costs reasonable by using cheap/free LLM expansion first, then selectively calling paid APIs only on viable candidates.

---

## 2. How Professional SEO Tools Do Keyword Clustering

### Ahrefs
- **Parent Topic Grouping:** Groups keywords by the page that ranks #1 for them. If "trail running shoes" and "best trail runners" share the same #1 result, they belong to the same cluster.
- **SERP Overlap:** Uses 70%+ SERP overlap as the clustering signal. Keywords whose top-10 results overlap significantly are clustered together.
- **Data Sources:** Clickstream data + Google Ads API + their own web crawler.

### SEMrush (Keyword Strategy Builder)
- **Intent Classification:** Groups keywords by search intent (informational, navigational, commercial, transactional).
- **Topical Mapping:** Maps keywords to topic pillars and sub-topics.
- **SERP Similarity:** Uses SERP overlap to determine which keywords can target the same page.

### Surfer SEO
- **SERP-Based Clustering:** Scans top-performing pages for a keyword, identifies what related terms they rank for, and clusters by semantic similarity.
- **NLP Analysis:** Uses NLP to understand semantic relationships between keywords.
- **Content Gap Analysis:** Identifies sub-topics and supporting keywords that competitors cover.

### Common Pattern
All three tools share a core approach:
1. **Start with seed keyword** and expand via API data
2. **Analyze SERPs** to understand how Google groups related queries
3. **Cluster by search intent** and SERP overlap (not just keyword similarity)
4. **Enrich with volume/competition data** to prioritize clusters
5. **Present actionable groups** with clear parent-child relationships

---

## 3. Proposed Hybrid Pipeline Architecture

### Stage Overview

```
User Input: Seed keyword (e.g., "trail running shoes")
     |
     v
[Stage 1: LLM Candidate Generation]      ~0.5s, ~$0.002 Claude cost
     |  Output: 30-50 candidate keywords
     v
[Stage 2: DataForSEO Volume Enrichment]  ~2s, ~$0.05 DataForSEO cost
     |  Output: Candidates + volume/CPC/competition
     v
[Stage 3: LLM Filtering + Clustering]    ~1s, ~$0.003 Claude cost
     |  Output: 8-15 viable collection page keywords
     v
[Stage 4: User Approval]                 Manual step
     |  Output: 5-10 approved keywords
     v
[Stage 5: POP Content Briefs]            ~30-60s per keyword, POP credit cost
     |  Output: Full content briefs for approved pages
     v
[Existing Content Pipeline]
```

### Stage 1: LLM Candidate Generation (Claude)

**Purpose:** Generate a broad set of semantically relevant keyword candidates from the seed keyword.

**Input:**
- Seed keyword (e.g., "trail running shoes")
- Context: "e-commerce collection page"
- Optional: Site URL, niche/vertical

**LLM Prompt Strategy:**
```
Given the seed keyword "{seed_keyword}" for an e-commerce store, generate
30-50 related collection page keywords that a customer might search for.

Include:
- Direct variations (gender, use-case, material modifiers)
- Feature-based variations (waterproof, lightweight, cushioned)
- Price/quality modifiers (best, affordable, premium)
- Occasion/purpose variations (for hiking, for marathons)
- Comparison/intent keywords (vs road shoes, reviews)

Return as JSON array. Each keyword should be a viable Shopify collection page.
Do NOT include informational/blog keywords -- collection pages only.
```

**Why LLM first (not DataForSEO first):**
- DataForSEO `keyword_suggestions` returns keywords that textually contain the seed phrase. This misses semantic variations (e.g., "hiking trainers" from "trail running shoes").
- LLM understands semantic relationships and e-commerce patterns.
- LLM is essentially free (~$0.002 for this call).
- We get 30-50 candidates in ~0.5 seconds.

**Reuse opportunity:** This is very similar to `PrimaryKeywordService.generate_candidates()` -- same LLM call pattern, different prompt.

### Stage 2: DataForSEO Volume Enrichment

**Purpose:** Add real search volume, CPC, and competition data to each candidate.

**API Endpoint:** `get_keyword_volume_batch()` (existing in `dataforseo.py`)

**Input:** 30-50 keyword strings from Stage 1
**Output per keyword:**
- `search_volume` (monthly)
- `cpc` (cost per click)
- `competition` (0-100)
- `competition_level` (HIGH/MEDIUM/LOW)
- `monthly_searches` (12-month trend)

**Cost:** Single batch request for up to 1000 keywords. DataForSEO Google Ads Search Volume: ~$0.05 per batch of 50 keywords.

**Why DataForSEO (not POP):**
- POP has no keyword suggestion/volume endpoint -- it's a content optimization tool, not a keyword research tool.
- DataForSEO provides volume data in a single batch call (efficient).
- We already have `get_keyword_volume_batch()` built and tested.

**Optional enhancement:** Also call `get_keyword_suggestions()` (existing in `dataforseo.py`) to discover additional candidates the LLM might have missed. This adds ~$0.01 cost but can catch long-tail variations.

### Stage 3: LLM Filtering + Clustering

**Purpose:** Filter out low-quality candidates, group remaining into a coherent cluster, and select the best 8-15 for collection pages.

**Input:** Enriched keyword list (keyword + volume + CPC + competition)
**LLM task:**

```
Given this seed keyword "{seed_keyword}" and the following keyword candidates
with search data, select 8-15 keywords that would make good Shopify collection
pages for a keyword cluster.

SELECTION CRITERIA:
1. Each keyword should target a DISTINCT collection page (no overlapping intent)
2. Prefer keywords with search_volume > 100 and < 50,000
3. The seed keyword should be the PARENT page
4. All other keywords should be CHILD pages related to the parent
5. Ensure a mix of specificity (some broad, some narrow)
6. Remove any that are too similar (would cannibalize each other)

For each selected keyword, provide:
- keyword
- suggested_page_type: "parent" or "child"
- reasoning (1 sentence)

CANDIDATES:
{formatted_keyword_list_with_volume_data}
```

**Why LLM for filtering (not just volume thresholds):**
- Volume alone can't determine keyword cannibalization risk.
- LLM understands that "women's trail running shoes" and "trail running shoes for women" target the same page.
- LLM can assess parent-child relationships semantically.
- Scoring heuristics alone miss nuance.

**Reuse opportunity:** This is similar to `PrimaryKeywordService.filter_to_specific()` -- same pattern of LLM-based relevance filtering with structured output.

### Stage 4: User Approval (Existing UI)

**Purpose:** Human-in-the-loop review of suggested cluster pages.

**Reuses:** The keyword approval UI from onboarding (Step 4.4 in FEATURE_SPEC). Same interface with minor additions:
- Show parent/child designation
- Show suggested URL slug
- Allow reordering/reassigning parent
- Allow adding custom keywords

### Stage 5: POP Content Briefs (Existing Pipeline)

**Purpose:** For each approved keyword, fetch full content optimization data.

**Reuses:** `fetch_content_brief()` from `pop_content_brief.py` -- identical 3-step flow:
1. `get-terms` -> LSI phrases, variations
2. `create-report` -> competitors, word count, page score
3. `get-custom-recommendations` -> keyword placement targets

**Important difference from onboarding:** For clusters, we set `pageNotBuiltYet=true` in the POP API call (no URL to crawl). This is already handled -- the existing `create_report()` method defaults to `page_not_built_yet=True`.

---

## 4. Existing Code Reuse Map

| Component | Existing Code | Reuse Level | Changes Needed |
|-----------|--------------|-------------|----------------|
| LLM candidate generation | `primary_keyword.py:generate_candidates()` | **Adapt** | Different prompt (cluster-focused vs page-focused), different output format |
| DataForSEO volume enrichment | `primary_keyword.py:enrich_with_volume()` | **Direct reuse** | None -- same batch volume lookup |
| DataForSEO keyword suggestions | `dataforseo.py:get_keyword_suggestions()` | **Direct reuse** | Optional supplementary call |
| LLM relevance filtering | `primary_keyword.py:filter_to_specific()` | **Adapt** | Different prompt (cluster selection vs page specificity) |
| Keyword scoring | `primary_keyword.py:calculate_score()` | **Direct reuse** | Same composite score formula |
| POP content brief | `pop_content_brief.py:fetch_content_brief()` | **Direct reuse** | Already handles pageNotBuiltYet |
| POP 3-step flow | `pop_content_brief.py:_run_real_3step_flow()` | **Direct reuse** | No changes |
| Content generation pipeline | `content_generation.py:run_content_pipeline()` | **Direct reuse** | Same brief->write->check flow |
| Keyword approval UI | Frontend components (Step 4.4) | **Adapt** | Add parent/child designation, URL slug |
| DataForSEO client | `dataforseo.py:DataForSEOClient` | **Direct reuse** | Fully built with batching, retries, circuit breaker |
| POP client | `pop.py:POPClient/POPMockClient` | **Direct reuse** | Fully built with mock support |
| Claude client | `integrations/claude.py` | **Direct reuse** | Standard LLM calls |

**Summary:** ~60% direct reuse, ~30% adaptation of existing patterns, ~10% new code.

---

## 5. Handling New Pages vs. Onboarding Flow

### Key Differences

| Aspect | Onboarding | Cluster (New Pages) |
|--------|-----------|-------------------|
| Starting point | Existing URLs to crawl | Seed keyword only |
| URL available? | Yes (real URLs) | No (generate slugs) |
| POP `targetUrl` | Actual page URL | Placeholder or blank |
| POP `pageNotBuiltYet` | `false` (page exists) | `true` (no page yet) |
| Page content for context | Crawled HTML content | None (keyword + brand config only) |
| Labels | Generated from crawl data | Generated from keyword + LLM |
| Internal linking | Label-based (flat) | Hierarchical (parent-child silo) |

### How POP Handles New Pages

POP's `get-terms` endpoint works with just a keyword -- it doesn't require a URL to crawl. When `pageNotBuiltYet=true`:
- POP still analyzes SERP competitors for the keyword
- Returns LSI terms, related questions, heading targets
- Returns competitor analysis (URLs, word counts, page scores)
- Does NOT score the target page (no page to score)

This is already handled in our codebase -- `create_report()` in `pop.py` defaults to `page_not_built_yet=True`.

### URL Slug Generation

For cluster pages, we need to generate URL slugs since there are no existing URLs. The FEATURE_SPEC (Section 6) already specifies slug rules:
- Lowercase
- Spaces to hyphens
- Remove special characters
- Max 50 characters
- Must be unique within project

This is a simple string transformation from the primary keyword.

---

## 6. API Cost Estimates

### Per-Cluster Cost Breakdown

Assuming a typical cluster of 10 pages (1 parent + 9 children):

| Stage | API | Calls | Cost per Call | Total |
|-------|-----|-------|---------------|-------|
| 1. LLM Candidates | Claude Sonnet | 1 | ~$0.002 | $0.002 |
| 2. Volume Enrichment | DataForSEO Search Volume | 1 batch (50 kw) | ~$0.05 | $0.05 |
| 2b. Extra Suggestions (optional) | DataForSEO Keyword Suggestions | 1 | ~$0.01 | $0.01 |
| 3. LLM Filtering | Claude Sonnet | 1 | ~$0.003 | $0.003 |
| 5. POP Briefs | POP get-terms | 10 | 1 credit each | 10 credits |
| 5. POP Reports | POP create-report | 10 | 1 credit each | 10 credits |
| 5. POP Recommendations | POP get-custom-recs | 10 | 0 credits | 0 credits |
| Content Writing | Claude Sonnet | 10 | ~$0.02 each | $0.20 |
| Quality Checks | Internal | 10 | $0 | $0 |

**Total API cost per cluster (excluding POP credits):** ~$0.27
**Total POP credits per cluster:** ~20 credits
**Total time (Stages 1-3):** ~5-10 seconds
**Total time (Stage 5, content gen):** ~5-10 minutes (parallelizable)

### Cost Optimization Strategies

1. **LLM-first expansion is essentially free.** Claude costs ~$0.002 for a 50-keyword generation call. This replaces what would be a $0.05+ DataForSEO call.

2. **Batch DataForSEO calls.** Our existing `get_keyword_volume_batch()` handles up to 1000 keywords per request. One call covers the entire candidate list.

3. **Filter before POP.** POP credits are the most expensive resource. By filtering 50 candidates down to 10 before calling POP, we save 40 POP credits (80% savings).

4. **Cache POP briefs.** The existing `fetch_content_brief()` already caches briefs per page. If the user regenerates content, we skip the POP call.

5. **Optional DataForSEO suggestions.** The supplementary `get_keyword_suggestions()` call is optional. Skip it to save $0.01/cluster, or include it for better coverage.

---

## 7. Data Flow Diagram

```
User enters: "trail running shoes"
          |
          v
    +--------------------------+
    | Stage 1: Claude Sonnet   |
    | generate_cluster_        |
    | candidates()             |
    +--------------------------+
          |
          | 30-50 keywords:
          | - trail running shoes for women
          | - waterproof trail running shoes
          | - best trail running shoes 2024
          | - trail running shoes for beginners
          | - lightweight trail running shoes
          | - trail running shoes with rock plate
          | - wide trail running shoes
          | - ...
          v
    +--------------------------+
    | Stage 2: DataForSEO      |
    | enrich_with_volume()     |  <-- EXISTING CODE
    +--------------------------+
          |
          | Same 30-50 keywords + volume data:
          | - trail running shoes for women: 12,100/mo
          | - waterproof trail running shoes: 8,100/mo
          | - trail running shoes reviews: 2,400/mo (INFORMATIONAL - will be filtered)
          | - lightweight trail running shoes: 3,600/mo
          | - trail running shoes near me: 1,200/mo (LOCAL - will be filtered)
          | - ...
          v
    +--------------------------+
    | Stage 3: Claude Sonnet   |
    | filter_and_cluster()     |
    +--------------------------+
          |
          | 8-12 keywords with roles:
          | - trail running shoes [PARENT]
          | - trail running shoes for women [CHILD]
          | - waterproof trail running shoes [CHILD]
          | - lightweight trail running shoes [CHILD]
          | - trail running shoes for beginners [CHILD]
          | - wide trail running shoes [CHILD]
          | - trail running shoes with rock plate [CHILD]
          | - cushioned trail running shoes [CHILD]
          v
    +--------------------------+
    | Stage 4: User Approval   |  <-- EXISTING UI (adapted)
    | Keyword approval screen  |
    +--------------------------+
          |
          | 5-10 approved keywords
          v
    +--------------------------+
    | Stage 5: POP Briefs      |  <-- EXISTING CODE
    | fetch_content_brief()    |
    | per approved keyword     |
    +--------------------------+
          |
          v
    +--------------------------+
    | Existing Content Pipeline|  <-- EXISTING CODE
    | brief -> write -> check  |
    +--------------------------+
```

---

## 8. New Service: `ClusterKeywordService`

### Proposed Architecture

Create a new service `backend/app/services/cluster_keyword.py` that orchestrates the cluster creation pipeline. This service composes existing services rather than duplicating logic.

```python
class ClusterKeywordService:
    """Orchestrates keyword cluster creation from a seed keyword.

    Composes:
    - Claude client for LLM expansion and filtering
    - DataForSEO client for volume enrichment
    - PrimaryKeywordService for scoring logic (reused)
    """

    def __init__(
        self,
        claude_client: ClaudeClient,
        dataforseo_client: DataForSEOClient,
    ):
        self._claude = claude_client
        self._dataforseo = dataforseo_client
        # Reuse the scoring logic from primary keyword service
        self._keyword_service = PrimaryKeywordService(claude_client, dataforseo_client)

    async def generate_cluster(
        self,
        seed_keyword: str,
        project_id: str,
        db: AsyncSession,
    ) -> ClusterResult:
        """Full pipeline: seed -> candidates -> enrich -> filter -> return."""

        # Stage 1: LLM candidate generation
        candidates = await self._generate_cluster_candidates(seed_keyword)

        # Stage 2: Volume enrichment (reuses existing code)
        volume_data = await self._keyword_service.enrich_with_volume(candidates)

        # Stage 2b (optional): DataForSEO keyword suggestions for extra coverage
        extra_suggestions = await self._dataforseo.get_keyword_suggestions(
            seed_keyword, limit=50
        )
        # Merge extra suggestions into volume_data...

        # Stage 3: LLM filtering + cluster assignment
        cluster_pages = await self._filter_and_assign_roles(
            seed_keyword, volume_data
        )

        # Create Cluster + ClusterPage records in DB
        # Return for user approval
        return cluster_result

    async def _generate_cluster_candidates(self, seed_keyword: str) -> list[str]:
        """Stage 1: LLM generates 30-50 collection page candidates."""
        # Similar to PrimaryKeywordService.generate_candidates()
        # but with cluster-specific prompt
        ...

    async def _filter_and_assign_roles(
        self,
        seed_keyword: str,
        keywords_with_volume: dict[str, KeywordVolumeData],
    ) -> list[ClusterPageCandidate]:
        """Stage 3: LLM filters and assigns parent/child roles."""
        # Similar to PrimaryKeywordService.filter_to_specific()
        # but returns parent/child designations
        ...
```

### Database Models Needed

```python
# Already planned in FEATURE_SPEC (Feature 5):
Cluster:
    id: UUID
    project_id: UUID
    name: str
    seed_keyword: str
    status: str  # "draft" | "approved" | "generating" | "complete"

ClusterPage:
    id: UUID
    cluster_id: UUID
    keyword: str
    role: str  # "parent" | "child"
    url_slug: str  # Generated from keyword
    search_volume: int
    composite_score: float
    is_approved: bool
```

---

## 9. Advantages of the Hybrid Approach

### vs. POP-Only Approach
- **POP has no keyword discovery endpoint.** POP's `get-terms` requires a keyword + URL -- it optimizes existing content, it doesn't discover new keywords. You'd need to already know which collection pages to create.
- **POP is expensive for exploration.** Each POP call costs credits. Using POP to explore 50 keyword ideas would burn 50 credits. The hybrid approach filters to 10 candidates before POP, saving 80% of credits.
- **POP's data is content optimization data** (LSI terms, heading structure, word count targets), not keyword research data (search volume, CPC, competition trends).

### vs. LLM-Only Approach
- **LLMs hallucinate search volume.** They can't reliably predict whether "trail running shoes with rock plate" gets 10 or 10,000 searches/month.
- **LLMs miss long-tail variations** that real search data reveals. DataForSEO's keyword suggestions can surface variations the LLM wouldn't think of.
- **No real competition data.** Without DataForSEO, we'd be guessing about keyword difficulty and CPC.

### Why Hybrid Wins
- **Best of both worlds:** LLM semantic understanding + real API data.
- **Cost-efficient funnel:** Cheap LLM expansion at the top, expensive POP optimization only at the bottom.
- **Matches industry practice:** This is how Ahrefs/SEMrush/Surfer work -- multiple data signals combined.
- **Maximal code reuse:** Leverages existing `PrimaryKeywordService`, `DataForSEOClient`, `POPClient`, and `fetch_content_brief()`.

---

## 10. Risk Analysis

| Risk | Mitigation |
|------|-----------|
| LLM generates irrelevant candidates | Stage 3 filtering catches these; DataForSEO volume confirms actual demand |
| DataForSEO returns no volume data | Graceful fallback already exists in `enrich_with_volume()` -- keywords get `None` volume and lower composite scores |
| POP API is slow/down | Already handled with circuit breaker, timeout, and graceful degradation in `pop_content_brief.py` |
| LLM filtering is too aggressive | Same risk as `filter_to_specific()` -- existing fallback returns all keywords with default relevance 0.5 |
| Keyword cannibalization between clusters | Track all used keywords across clusters via `_used_primary_keywords` set (already in `PrimaryKeywordService`) |
| Cost overruns | Stages 1-3 cost ~$0.07 total. POP is the expensive part, and it only runs on approved keywords |

---

## 11. Recommended Implementation Order

1. **Create `ClusterKeywordService`** with Stages 1-3 (LLM expand -> DataForSEO enrich -> LLM filter)
2. **Create `Cluster` and `ClusterPage` database models**
3. **Create API endpoints** for cluster creation and keyword approval
4. **Adapt keyword approval UI** to show parent/child roles and URL slugs
5. **Wire into existing content pipeline** (Stage 5 reuses `fetch_content_brief` and `run_content_pipeline`)
6. **Add cluster-specific internal linking logic** (hierarchical silo structure per FEATURE_SPEC)

---

## 12. Summary Recommendation

**Use the hybrid pipeline approach.** It combines:
- **LLM semantic intelligence** for candidate generation and filtering (cheap, fast, understands e-commerce patterns)
- **DataForSEO real-world data** for volume/competition validation (reliable, already integrated)
- **POP content optimization** for content brief generation (already built, used only on approved keywords)

The funnel shape (broad -> narrow) ensures we spend the most expensive API credits only on keywords the user has approved, while still providing rich, data-backed suggestions at every stage.

**Estimated new code:** ~300-400 lines for `ClusterKeywordService` + ~100 lines for database models + API endpoint wiring. Most of the pipeline is composed from existing services.
